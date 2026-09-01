"""Does the client's 4 s cut cost us information, and does server VAD fix it?

ADR-0004 turned server VAD off with a real objection: for a translator,
barge-in is a bug, because continuous foreign speech would cut off every
in-flight Hungarian translation. But that objection conflates two separate
things — the server *detecting* a boundary, and the server *responding* and
*interrupting* on its own. The GA schema exposes them as separate flags.

Two strategies over the same recorded audio, scored the same way:

  A) turn_detection: null, client commits every `--window-ms` (the app today).
     Measured in the field: p50 and p95 of the phrase wait were both exactly
     4000 ms, so the hard timeout was not a safety net but every single turn,
     and every cut landed mid-sentence.

  B) semantic_vad with create_response=false and interrupt_response=false.
     The server decides where a thought ends but neither answers by itself
     nor interrupts anything, so ADR-0004's actual intent holds.

     MEASURED RESULT: B produces zero turns on broadcast news. The server
     accepts the config and echoes it back, emits speech_started once, and
     never emits speech_stopped — because the audio genuinely has no pause.
     On the reference recording there is not one gap of 200 ms below -40 dBFS
     anywhere between 0.7 s and 30.7 s. Server VAD with silence_duration_ms
     200 fails identically. This is not a tuning problem: silence-based
     boundary detection has nothing to detect on this material.

Scored on facts, not phrasing: sentence similarity rated "15 dead" against
"August 15th" as a match, which is exactly the error that matters most.

Usage:
    uv run python examples/turn_strategy_bench.py data/eval/<stamp>-input.wav \\
        --reference-json data/eval/eval-1.json
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import json
import os
import sys
import wave
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import websockets
from openai import AsyncOpenAI

from closed_loop_eval import (
    _check_fact,
    _extract_facts,
    _transcribe,
    _translate,
)
from translation_latency_bench import DEFAULT_PROMPT, SAMPLE_RATE

MODEL = "gpt-realtime-mini"
BYTES_PER_SAMPLE = 2
CHUNK_MS = 20


def _load_pcm(path: Path) -> bytes:
    with wave.open(str(path)) as w:
        if w.getframerate() != SAMPLE_RATE or w.getnchannels() != 1:
            sys.exit(f"{path}: 24 kHz mono PCM16 kell, ez {w.getframerate()} Hz / {w.getnchannels()} ch")
        return w.readframes(w.getnframes())


def _session(turn_detection: dict | None, speed: float) -> dict:
    """GA session payload. `turn_detection` None == explicit JSON null."""
    audio_format = {"type": "audio/pcm", "rate": SAMPLE_RATE}
    return {
        "type": "session.update",
        "session": {
            "type": "realtime",
            "output_modalities": ["audio"],
            "instructions": DEFAULT_PROMPT,
            "audio": {
                "input": {
                    "format": audio_format,
                    "transcription": {"model": "gpt-4o-mini-transcribe"},
                    "turn_detection": turn_detection,
                },
                "output": {"format": audio_format, "voice": "alloy", "speed": speed},
            },
        },
    }


async def _run(pcm: bytes, key: str, *, turn_detection, window_ms: int | None, speed: float) -> dict:
    """Stream the audio in real time and collect what came back."""
    url = f"wss://api.openai.com/v1/realtime?model={MODEL}"
    chunk = SAMPLE_RATE * BYTES_PER_SAMPLE * CHUNK_MS // 1000
    window_bytes = (
        SAMPLE_RATE * BYTES_PER_SAMPLE * window_ms // 1000 if window_ms else None
    )

    transcript: list[str] = []
    heard: list[str] = []
    turns = 0
    audio_bytes = 0
    done = asyncio.Event()

    async with websockets.connect(
        url, additional_headers={"Authorization": f"Bearer {key}"}, max_size=None
    ) as ws:
        first = json.loads(await ws.recv())
        if first.get("type") == "error":
            return {"error": first["error"].get("message")}
        await ws.send(json.dumps(_session(turn_detection, speed)))

        async def reader() -> None:
            nonlocal turns, audio_bytes
            while not done.is_set():
                try:
                    ev = json.loads(await asyncio.wait_for(ws.recv(), timeout=20))
                except (asyncio.TimeoutError, websockets.ConnectionClosed):
                    return
                kind = ev.get("type", "")
                if kind.endswith("output_audio_transcript.delta"):
                    transcript.append(ev.get("delta", ""))
                elif kind.endswith("output_audio.delta"):
                    audio_bytes += len(base64.b64decode(ev.get("delta", "")))
                elif "input_audio_transcription.completed" in kind:
                    heard.append(ev.get("transcript", ""))
                elif kind == "input_audio_buffer.committed":
                    # A szerver zárta le a frázist (B stratégia). A választ
                    # TOVÁBBRA IS a kliens kéri — ez az ADR-0004 magja.
                    if turn_detection is not None:
                        turns += 1
                        await ws.send(json.dumps({"type": "response.create"}))
                elif kind == "error":
                    print(f"    ! {ev['error'].get('message')}")

        task = asyncio.create_task(reader())

        sent_since_commit = 0
        for off in range(0, len(pcm), chunk):
            await ws.send(
                json.dumps(
                    {
                        "type": "input_audio_buffer.append",
                        "audio": base64.b64encode(pcm[off : off + chunk]).decode(),
                    }
                )
            )
            sent_since_commit += chunk
            # Valós idejű ütemezés: a VAD-nak azt kell látnia, amit élesben lát.
            await asyncio.sleep(CHUNK_MS / 1000)

            if window_bytes and sent_since_commit >= window_bytes:
                turns += 1
                await ws.send(json.dumps({"type": "input_audio_buffer.commit"}))
                await ws.send(json.dumps({"type": "response.create"}))
                sent_since_commit = 0

        if window_bytes and sent_since_commit > 0:
            turns += 1
            await ws.send(json.dumps({"type": "input_audio_buffer.commit"}))
            await ws.send(json.dumps({"type": "response.create"}))

        # A hátralévő válaszok befutására hagyunk időt.
        await asyncio.sleep(12)
        done.set()
        task.cancel()

    return {
        "produced": "".join(transcript).strip(),
        "heard": " ".join(heard).strip(),
        "turns": turns,
        "output_s": round(audio_bytes / (SAMPLE_RATE * BYTES_PER_SAMPLE), 1),
        "error": None,
    }


async def _score(client: AsyncOpenAI, facts: list[str], produced: str) -> dict:
    checks = await asyncio.gather(*(_check_fact(client, f, produced) for f in facts))
    yes = sum(1 for c in checks if c["verdict"] == "yes")
    part = sum(1 for c in checks if c["verdict"] == "partial")
    return {
        "checks": checks,
        "yes": yes,
        "partial": part,
        "no": len(checks) - yes - part,
        "pct": 100 * yes // max(len(checks), 1),
    }


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("input_wav", type=Path)
    ap.add_argument("--window-ms", type=int, default=4000, help="az A stratégia vágása")
    ap.add_argument("--speed", type=float, default=1.15)
    ap.add_argument("--eagerness", default="auto", choices=["low", "medium", "high", "auto"])
    ap.add_argument(
        "--reference-json",
        type=Path,
        help="korábbi closed_loop_eval kimenete; a referenciát innen veszi, "
        "hogy a két futás pontosan ugyanahhoz a mércéhez mérődjön",
    )
    ap.add_argument("--json", type=Path)
    args = ap.parse_args()

    key = os.environ["OPENAI_API_KEY"]
    client = AsyncOpenAI(api_key=key)
    pcm = _load_pcm(args.input_wav)
    seconds = len(pcm) / (SAMPLE_RATE * BYTES_PER_SAMPLE)
    print(f"forras: {args.input_wav.name}  ({seconds:.1f}s)\n")

    if args.reference_json and args.reference_json.is_file():
        cached = json.loads(args.reference_json.read_text(encoding="utf-8"))
        reference = cached["reference"]
        facts = [c["fact"] for c in cached.get("facts", [])]
        print(f"referencia a gyorsitotarbol: {len(facts)} teny")
    else:
        print("referencia epitese...")
        source_text = await _transcribe(client, args.input_wav, None)
        reference = await _translate(client, source_text)
        facts = await _extract_facts(client, reference)
        print(f"  {len(facts)} teny")
    if not facts:
        facts = await _extract_facts(client, reference)
    print()

    print(f"A) turn_detection: null, {args.window_ms} ms-enkent vagva...")
    a = await _run(pcm, key, turn_detection=None, window_ms=args.window_ms, speed=args.speed)
    print(f"   {a['turns']} fordulo, {a['output_s']}s hang")

    print(f"B) semantic_vad (create_response=false, interrupt_response=false, "
          f"eagerness={args.eagerness})...")
    b = await _run(
        pcm,
        key,
        turn_detection={
            "type": "semantic_vad",
            "create_response": False,
            "interrupt_response": False,
            "eagerness": args.eagerness,
        },
        window_ms=None,
        speed=args.speed,
    )
    print(f"   {b['turns']} fordulo, {b['output_s']}s hang\n")

    print("pontozas tenyenkent...\n")
    sa = await _score(client, facts, a["produced"])
    sb = await _score(client, facts, b["produced"])

    for label, run, sc in (("A — 4 s vagas", a, sa), ("B — semantic VAD", b, sb)):
        print("=" * 76)
        print(f"{label}   ·   {run['turns']} fordulo")
        print("=" * 76)
        print(run["produced"] + "\n")

    print("=" * 76)
    print("TENY-FEDETTSEG")
    print("=" * 76)
    print(f"A (4 s vagas)      {sa['yes']}/{len(facts)} pontos · {sa['partial']} reszleges "
          f"· {sa['no']} hianyzik  ->  {sa['pct']}%")
    print(f"B (semantic VAD)   {sb['yes']}/{len(facts)} pontos · {sb['partial']} reszleges "
          f"· {sb['no']} hianyzik  ->  {sb['pct']}%")
    print()
    for f, ca, cb in zip(facts, sa["checks"], sb["checks"]):
        if ca["verdict"] != cb["verdict"]:
            print(f"  elteres: A={ca['verdict']:<7} B={cb['verdict']:<7} {f}")

    if args.json:
        args.json.write_text(
            json.dumps(
                {"reference": reference, "facts": facts, "a": {**a, "score": sa}, "b": {**b, "score": sb}},
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        print(f"\nnyers eredmeny: {args.json}")


if __name__ == "__main__":
    asyncio.run(main())
