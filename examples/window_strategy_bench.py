"""How should continuous speech be cut into turns, and what does each cut cost?

Silence-based boundaries are out: measured on the reference recording, between
0.7 s and 30.7 s of broadcast news there is not one 200 ms gap below -40 dBFS,
and server VAD, semantic VAD and our own 400 ms threshold all detect nothing
(see turn_strategy_bench.py). Whatever replaces them cannot depend on a pause.

Strategies compared on the same audio, with the app's own prompt:

  fixed:N        commit every N ms — what the app does today at 4000
  overlap:N:M    N ms windows that re-send the previous M ms, so a cut through
                 the middle of a clause still reaches the model with its run-up
  text:N         a parallel transcription session finds sentence ends in the
                 incoming text, and the cut lands there instead of on a timer

Two things are measured, because they trade against each other:

  * information — facts from an independent reference, checked one by one;
    sentence similarity is no use here, it scored "15 dead" against
    "August 15th" as a match.
  * lag — not just onset. What the listener feels is how far behind the
    speaker they are, and with consecutive interpreting that accumulates when
    a translation takes longer to say than its source segment lasted. Playback
    is simulated with a virtual playhead so the accumulation shows up.

Usage:
    uv run python examples/window_strategy_bench.py data/eval/<stamp>-input.wav \\
        --reference-json data/eval/eval-1.json \\
        --strategies fixed:4000 fixed:6000 fixed:8000
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import json
import os
import re
import statistics
import sys
import time
import wave
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import websockets
from openai import AsyncOpenAI

from closed_loop_eval import _check_fact, _extract_facts, _transcribe, _translate

MODEL = "gpt-realtime-mini"
SAMPLE_RATE = 24000
BYTES_PER_SAMPLE = 2
CHUNK_MS = 20

# The app's own prompt (app/lib/realtime/session_config.dart). The earlier
# comparison used the bench's v3 prompt, which made the model start asking
# clarifying questions — that measured the prompt, not the cutting strategy.
APP_PROMPT = """Egy tolmácsgép hangja vagy. Amit hallasz, azt add vissza magyarul. Semmi mást.
A kimeneted MINDIG magyar. Soha ne válaszolj a hallottakra, ne kommentáld.
Pontosan egyszer mondd el a fordítást, aztán hallgass el.
"""

SENTENCE_END = re.compile(r"[.!?…]")
CYRILLIC = re.compile(r"[\u0400-\u04FF]")


def _foreign_ratio(text: str) -> float:
    """Mekkora hányada cirill — vagyis mennyire NEM fordított a kimenet.

    Nem elméleti eset: a `fixed:6000` futás teljes kimenete **bolgárul** jött,
    a modell a forrást ismételte fordítás helyett. A tényellenőrző ezt nem
    fogja meg, mert a tények nyelvtől függetlenül ott vannak — 11/16-ot adott
    egy használhatatlan kimenetre. Egy magyar fordítónál a nyelv nem
    részletkérdés, hanem a feladat.
    """
    letters = [c for c in text if c.isalpha()]
    if not letters:
        return 0.0
    return len(CYRILLIC.findall(text)) / len(letters)


def _load_pcm(path: Path) -> bytes:
    with wave.open(str(path)) as w:
        if w.getframerate() != SAMPLE_RATE or w.getnchannels() != 1:
            sys.exit(f"{path}: 24 kHz mono PCM16 kell")
        return w.readframes(w.getnframes())


def _session(speed: float) -> dict:
    fmt = {"type": "audio/pcm", "rate": SAMPLE_RATE}
    return {
        "type": "session.update",
        "session": {
            "type": "realtime",
            "output_modalities": ["audio"],
            "instructions": APP_PROMPT,
            "audio": {
                "input": {
                    "format": fmt,
                    "transcription": {"model": "gpt-4o-mini-transcribe"},
                    "turn_detection": None,  # explicit null: a kliens vág
                },
                "output": {"format": fmt, "voice": "alloy", "speed": speed},
            },
        },
    }


class _Turn:
    """Egy vágás könyvelése — ebből jön a késleltetés."""

    __slots__ = ("index", "src_end", "first_delta", "audio_bytes", "text")

    def __init__(self, index: int, src_end: float) -> None:
        self.index = index
        self.src_end = src_end  # a forrásszegmens vége, stream-időben
        self.first_delta: float | None = None
        self.audio_bytes = 0
        self.text: list[str] = []

    @property
    def output_s(self) -> float:
        return self.audio_bytes / (SAMPLE_RATE * BYTES_PER_SAMPLE)


async def _run(pcm: bytes, key: str, plan: list[tuple[int, int]], speed: float) -> dict:
    """`plan` = [(kuldendo_bajt, atfedes_bajt)] vagasonkent, sorrendben."""
    url = f"wss://api.openai.com/v1/realtime?model={MODEL}"
    chunk = SAMPLE_RATE * BYTES_PER_SAMPLE * CHUNK_MS // 1000
    turns: list[_Turn] = []
    done = asyncio.Event()

    async with websockets.connect(
        url, additional_headers={"Authorization": f"Bearer {key}"}, max_size=None
    ) as ws:
        first = json.loads(await ws.recv())
        if first.get("type") == "error":
            return {"error": first["error"].get("message")}
        await ws.send(json.dumps(_session(speed)))

        t0 = time.perf_counter()
        cursor = 0  # melyik turnhoz tartozik a beerkezo delta

        async def reader() -> None:
            nonlocal cursor
            while not done.is_set():
                try:
                    ev = json.loads(await asyncio.wait_for(ws.recv(), timeout=25))
                except (asyncio.TimeoutError, websockets.ConnectionClosed):
                    return
                kind = ev.get("type", "")
                if kind.endswith("output_audio.delta"):
                    if cursor < len(turns):
                        t = turns[cursor]
                        if t.first_delta is None:
                            t.first_delta = time.perf_counter() - t0
                        t.audio_bytes += len(base64.b64decode(ev.get("delta", "")))
                elif kind.endswith("output_audio_transcript.delta"):
                    if cursor < len(turns):
                        turns[cursor].text.append(ev.get("delta", ""))
                elif kind == "response.done":
                    cursor += 1
                elif kind == "error":
                    print(f"    ! {ev['error'].get('message')}")

        task = asyncio.create_task(reader())

        async def send_span(span: bytes, *, realtime: bool) -> None:
            for off in range(0, len(span), chunk):
                await ws.send(
                    json.dumps(
                        {
                            "type": "input_audio_buffer.append",
                            "audio": base64.b64encode(span[off : off + chunk]).decode(),
                        }
                    )
                )
                # Az átfedés stream-ideje már eltelt egyszer; újraküldése nem
                # vehet el újabb valós időt, különben a mérés lelassulna.
                await asyncio.sleep(CHUNK_MS / 1000 if realtime else 0.002)

        pos = 0
        for send_bytes, overlap_bytes in plan:
            if overlap_bytes:
                await send_span(pcm[max(0, pos - overlap_bytes) : pos], realtime=False)
            end = min(len(pcm), pos + send_bytes)
            await send_span(pcm[pos:end], realtime=True)
            pos = end
            turns.append(_Turn(len(turns), pos / (SAMPLE_RATE * BYTES_PER_SAMPLE)))
            await ws.send(json.dumps({"type": "input_audio_buffer.commit"}))
            await ws.send(json.dumps({"type": "response.create"}))
            if pos >= len(pcm):
                break

        await asyncio.sleep(15)  # a hatralevo valaszok befutasa
        done.set()
        task.cancel()

    return {
        "turns": turns,
        "produced": " ".join("".join(t.text).strip() for t in turns).strip(),
        "error": None,
    }


def _lag(turns: list[_Turn]) -> dict:
    """Lejátszás-szimuláció: mennyivel van a hallgató a beszélő mögött.

    A playhead nem ugorhat vissza: ha az előző fordítás még szól, az új csak
    utána kezdődhet. Ettől halmozódik a csúszás — pontosan ez a HIBA-002.
    """
    playhead = 0.0
    onsets, ends = [], []
    for t in turns:
        if t.first_delta is None:
            continue
        onsets.append((t.first_delta - t.src_end) * 1000)
        playhead = max(playhead, t.first_delta) + t.output_s
        ends.append((playhead - t.src_end) * 1000)
    if not ends:
        return {}
    return {
        "onset_p50": round(statistics.median(onsets)),
        "onset_max": round(max(onsets)),
        "lag_first": round(ends[0]),
        "lag_p50": round(statistics.median(ends)),
        "lag_last": round(ends[-1]),
        "drift": round(ends[-1] - ends[0]),
    }


def _plan(strategy: str, total_bytes: int) -> list[tuple[int, int]]:
    kind, *rest = strategy.split(":")
    b = lambda ms: SAMPLE_RATE * BYTES_PER_SAMPLE * ms // 1000  # noqa: E731
    if kind == "fixed":
        step = b(int(rest[0]))
        n = (total_bytes + step - 1) // step
        return [(step, 0)] * n
    if kind == "overlap":
        step, ov = b(int(rest[0])), b(int(rest[1]))
        n = (total_bytes + step - 1) // step
        return [(step, 0 if i == 0 else ov) for i in range(n)]
    sys.exit(f"ismeretlen strategia: {strategy}")


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("input_wav", type=Path)
    ap.add_argument("--strategies", nargs="+", default=["fixed:4000", "fixed:6000", "fixed:8000"])
    ap.add_argument("--speed", type=float, default=1.15)
    ap.add_argument("--reference-json", type=Path)
    ap.add_argument("--json", type=Path)
    args = ap.parse_args()

    key = os.environ["OPENAI_API_KEY"]
    client = AsyncOpenAI(api_key=key)
    pcm = _load_pcm(args.input_wav)
    print(f"forras: {args.input_wav.name}  ({len(pcm) / (SAMPLE_RATE * BYTES_PER_SAMPLE):.1f}s)")

    if args.reference_json and args.reference_json.is_file():
        cached = json.loads(args.reference_json.read_text(encoding="utf-8"))
        reference = cached["reference"]
        facts = [c["fact"] for c in cached.get("facts", [])]
        print(f"referencia gyorsitotarbol: {len(facts)} teny\n")
    else:
        source_text = await _transcribe(client, args.input_wav, None)
        reference = await _translate(client, source_text)
        facts = await _extract_facts(client, reference)
        print(f"referencia epitve: {len(facts)} teny\n")

    results = {}
    for strat in args.strategies:
        print(f"--- {strat} ---")
        run = await _run(pcm, key, _plan(strat, len(pcm)), args.speed)
        if run.get("error"):
            print(f"    hiba: {run['error']}")
            continue
        lag = _lag(run["turns"])
        checks = await asyncio.gather(*(_check_fact(client, f, run["produced"]) for f in facts))
        yes = sum(1 for c in checks if c["verdict"] == "yes")
        part = sum(1 for c in checks if c["verdict"] == "partial")
        results[strat] = {
            "turns": len(run["turns"]),
            "lag": lag,
            "yes": yes,
            "partial": part,
            "no": len(checks) - yes - part,
            "produced": run["produced"],
            "foreign": round(_foreign_ratio(run["produced"]), 3),
            "checks": checks,
        }
        print(f"    {len(run['turns'])} fordulo · tenyek {yes}/{len(facts)} · "
              f"lag p50 {lag.get('lag_p50', 0)} ms\n")

    print("=" * 84)
    print(f"{'strategia':<16}{'ford.':>6}{'teny':>10}{'onset p50':>11}"
          f"{'lag elso':>10}{'lag p50':>9}{'lag vege':>10}{'drift':>8}")
    print("=" * 84)
    for strat, r in results.items():
        lg = r["lag"]
        facts_col = f"{r['yes']}+{r['partial']}"
        if r.get("foreign", 0) > 0.1:
            facts_col += "!"  
        print(f"{strat:<16}{r['turns']:>6}{facts_col:>10}"
              f"{lg.get('onset_p50', 0):>11}"
              f"{lg.get('lag_first', 0):>10}{lg.get('lag_p50', 0):>9}"
              f"{lg.get('lag_last', 0):>10}{lg.get('drift', 0):>+8}")
    print()
    print("!  = a kimenet nem magyar (cirill betuk aranya > 10%) — a tenyszam ilyenkor ertelmetlen")
    print("teny = pontos+reszleges  ·  lag = mennyivel van a hallgato a beszelo mogott (ms)")
    print("drift = a lag novekedese az elso fordulotol az utolsoig; >0 == halmozodik")

    for strat, r in results.items():
        print("\n" + "=" * 84)
        print(strat)
        print("=" * 84)
        print(r["produced"])

    if args.json:
        args.json.write_text(
            json.dumps({"reference": reference, "facts": facts, "results": results},
                       ensure_ascii=False, indent=2, default=str),
            encoding="utf-8",
        )
        print(f"\nnyers eredmeny: {args.json}")


if __name__ == "__main__":
    asyncio.run(main())
