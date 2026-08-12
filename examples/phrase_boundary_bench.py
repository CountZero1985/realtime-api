"""What does the 4 s hard timeout cost, when it cuts mid-sentence?

The translator app commits a phrase boundary on 400 ms of silence OR after a
4 s hard timeout. Two field runs showed the same thing: p50 and p95 of the
phrase wait were both exactly 4000 ms over 13 and 16 turns, so the timeout was
not the safety net — it was every single turn. Continuous speech never leaves
400 ms of silence.

That means the source is chopped every 4 seconds regardless of where the
sentence is, and the model is asked to translate a fragment. The user hears it
as "half the sentence goes missing and a new part starts".

This measures the cost directly: the same passage translated twice in one
process, once cut at sentence boundaries and once cut every 4 s, so the two
transcripts can be read side by side.

Usage:
    uv run python examples/phrase_boundary_bench.py
    uv run python examples/phrase_boundary_bench.py --window-ms 6000
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import json
import os
import re
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import websockets

from translation_latency_bench import (
    BYTES_PER_SAMPLE,
    DEFAULT_PROMPT,
    SAMPLE_RATE,
    session_update,
    synthesize,
)

MODEL = "gpt-realtime-mini"

# A connected passage, not isolated sentences: the point is what happens when a
# cut lands mid-thought, which only shows up in continuous speech.
PASSAGE = [
    "Guten Tag, ich rufe an, weil ich gestern eine Buchung für nächsten "
    "Dienstag vorgenommen habe.",
    "Leider hat sich mein Terminplan geändert, und ich müsste die Reise auf "
    "Donnerstag verschieben.",
    "Können Sie mir sagen, ob dafür eine Umbuchungsgebühr anfällt und wie hoch "
    "sie wäre?",
    "Falls es zu teuer ist, würde ich die Buchung lieber ganz stornieren.",
]

SENTENCE_END = re.compile(r"[.!?…]\s*$")


async def _run_turn(ws, pcm: bytes, *, chunk_ms: int = 20) -> dict:
    """Append one slice of audio, commit it, and collect the response."""
    chunk = SAMPLE_RATE * BYTES_PER_SAMPLE * chunk_ms // 1000
    for off in range(0, len(pcm), chunk):
        await ws.send(
            json.dumps(
                {
                    "type": "input_audio_buffer.append",
                    "audio": base64.b64encode(pcm[off : off + chunk]).decode(),
                }
            )
        )
        await asyncio.sleep(0.004)

    t0 = time.perf_counter()
    await ws.send(json.dumps({"type": "input_audio_buffer.commit"}))
    await ws.send(json.dumps({"type": "response.create"}))

    heard: list[str] = []
    out: list[str] = []
    audio_bytes = 0
    onset = None
    while True:
        ev = json.loads(await asyncio.wait_for(ws.recv(), timeout=30))
        kind = ev.get("type", "")
        if kind == "error":
            return {"error": ev["error"].get("message"), "heard": "", "translation": ""}
        if kind.endswith("output_audio.delta"):
            if onset is None:
                onset = time.perf_counter() - t0
            audio_bytes += len(base64.b64decode(ev.get("delta", "")))
        elif kind.endswith("output_audio_transcript.delta"):
            out.append(ev.get("delta", ""))
        elif "input_audio_transcription.completed" in kind:
            heard.append(ev.get("transcript", ""))
        elif kind == "response.done":
            break

    return {
        "heard": " ".join(heard).strip(),
        "translation": "".join(out).strip(),
        "source_s": round(len(pcm) / (SAMPLE_RATE * BYTES_PER_SAMPLE), 2),
        "output_s": round(audio_bytes / (SAMPLE_RATE * BYTES_PER_SAMPLE), 2),
        "onset_ms": round((onset or 0) * 1000),
        "error": None,
    }


async def _session(key: str, slices: list[bytes], label: str) -> list[dict]:
    url = f"wss://api.openai.com/v1/realtime?model={MODEL}"
    async with websockets.connect(
        url, additional_headers={"Authorization": f"Bearer {key}"}, max_size=None
    ) as ws:
        first = json.loads(await ws.recv())
        if first.get("type") == "error":
            print(f"  {label}: ERROR {first['error']}")
            return []
        await ws.send(json.dumps(session_update(DEFAULT_PROMPT, 1.15)))

        results = []
        for i, pcm in enumerate(slices, 1):
            r = await _run_turn(ws, pcm)
            results.append(r)
            print(f"  [{label} {i}/{len(slices)}] {r['source_s']}s -> {r['output_s']}s")
            print(f"      hallott: {r['heard']}")
            print(f"      magyar : {r['translation']}")
        return results


def _cut_fixed(pcm: bytes, window_ms: int) -> list[bytes]:
    """Chop a continuous stream every `window_ms`, ignoring sentence structure."""
    step = SAMPLE_RATE * BYTES_PER_SAMPLE * window_ms // 1000
    return [pcm[i : i + step] for i in range(0, len(pcm), step)]


def _fragment_rate(results: list[dict]) -> tuple[int, int]:
    """How many fragments' *input* transcripts do not end a sentence.

    The input transcript is what the model actually heard, so a fragment that
    stops without terminal punctuation is direct evidence of a mid-sentence
    cut — no judgement call needed.
    """
    usable = [r for r in results if r.get("heard")]
    cut = sum(1 for r in usable if not SENTENCE_END.search(r["heard"]))
    return cut, len(usable)


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--window-ms",
        type=int,
        default=4000,
        help="the app's hard timeout (TurnThresholds.hardTimeout)",
    )
    args = ap.parse_args()
    key = os.environ["OPENAI_API_KEY"]

    print("TTS szintezis...")
    per_sentence = [await synthesize(s, key) for s in PASSAGE]
    continuous = b"".join(per_sentence)
    total_s = len(continuous) / (SAMPLE_RATE * BYTES_PER_SAMPLE)
    print(f"  {len(PASSAGE)} mondat, osszesen {total_s:.1f} s\n")

    print("A) MONDATHATARON vagva (ideal — a jelenlegi VAD sosem eri el)")
    natural = await _session(key, per_sentence, "mondat")

    print(f"\nB) {args.window_ms} MS-ENKENT vagva (a hard timeout, ami elesben MINDIG lefut)")
    chopped = await _session(key, _cut_fixed(continuous, args.window_ms), "idozito")

    print("\n" + "=" * 72)
    n_cut, n_tot = _fragment_rate(natural)
    c_cut, c_tot = _fragment_rate(chopped)
    print(f"Fordulok szama       mondathataron {len(natural)}  |  idozitovel {len(chopped)}")
    print(f"Mondat kozben vagva  mondathataron {n_cut}/{n_tot}   |  idozitovel {c_cut}/{c_tot}")
    if c_tot:
        print(f"                     -> a fragmentek {100 * c_cut // c_tot}%-a fel mondat")
    print()
    print("A ket 'magyar' blokkot egymas mellett kell elolvasni: a tartalmi")
    print("veszteseget szam nem meri, csak olvasas.")


asyncio.run(main())
