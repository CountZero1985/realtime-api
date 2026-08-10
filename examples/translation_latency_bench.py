#!/usr/bin/env python3
"""Translation latency benchmark for the Realtime API.

Measures what a prompt-driven simultaneous translator actually costs: how
long after committing an utterance the first translated audio arrives, and
whether the model translates rather than answers.

Why raw WebSocket instead of `RealtimeSession`: this benchmark measures the
*API*, so it must not inherit the client library's assumptions about event
names or payload shape. It is also how we discover when those assumptions
drift — the observed event types are printed at the end.

Input audio is synthesised with TTS rather than recorded, so a run is
reproducible and comparable across models and days.

Usage:
    python examples/translation_latency_bench.py
    python examples/translation_latency_bench.py --model gpt-realtime-2.1 --runs 5
    python examples/translation_latency_bench.py --fast --json results.json

Pacing note: `--fast` streams the audio as quickly as the socket accepts it,
so the server holds the whole utterance before the commit. That is not how a
live microphone behaves and tends to *overstate* onset latency. Real-time
pacing is the default for exactly this reason.
"""

import argparse
import asyncio
import base64
import json
import os
import statistics
import sys
import time
from pathlib import Path

import httpx
import websockets
from dotenv import load_dotenv

load_dotenv()

SAMPLE_RATE = 24000
BYTES_PER_SAMPLE = 2
CHUNK_MS = 40

DEFAULT_PROMPT = """Te egy szinkrontolmács vagy. A feladatod KIZÁRÓLAG a hallott beszéd magyarra fordítása.

SZABÁLYOK:
- Soha ne válaszolj a hallottakra, ne kommentáld, ne egészítsd ki.
- Ne kérdezz vissza, ne kérj pontosítást.
- Csak a fordítást mondd ki, semmi mást.
- Egyes szám első személyben fordíts, ahogy a beszélő mondta — soha ne függő
  beszédben ("azt mondja, hogy...", "azt szeretné tudni, hogy...").
- Ha nem érted, fordítsd le azt, amit hallottál, a legjobb tudásod szerint.
- Tartsd meg a beszélő stílusát és regiszterét.
"""

SENTENCES = [
    ("en", "I think we should leave now, but Anna hasn't arrived yet."),
    ("en", "The contract needs to be signed before Friday, otherwise we lose the deposit."),
    ("de", "Der Zug nach München fährt heute leider eine halbe Stunde später ab."),
    ("de", "Können Sie mir bitte sagen, wo sich der nächste Geldautomat befindet?"),
]

# Crude hints, not verdicts. A human still has to read every output; these
# only make the two observed failure modes easier to spot in a long run.
#
# 1. Reported speech — the model narrates the utterance instead of speaking
#    as the speaker ("azt szeretné tudni, hogy...").
REPORTED_SPEECH_MARKERS = (
    "azt szeretné tudni",
    "azt kérdezi",
    "azt mondja",
    "megkérdezte",
    "azt szeretné",
    "arra kíváncsi",
)


def looks_like_an_answer(source: str, translation: str) -> bool:
    """True when a question seems to have been answered instead of translated.

    A translated question is still a question. Observed in the wild: the model
    heard "Können Sie mir sagen, wo der nächste Geldautomat ist?" correctly and
    replied with an invented street address — the worst failure mode for a
    translator, because the output is fluent and confident.
    """
    return source.rstrip().endswith("?") and "?" not in translation


def api_key() -> str:
    key = os.environ.get("OPENAI_API_KEY")
    if not key:
        sys.exit("OPENAI_API_KEY is not set (put it in .env or the environment).")
    return key


async def synthesize(text: str, key: str, voice: str = "alloy") -> bytes:
    """Render source-language speech as 24 kHz mono PCM16.

    `response_format="pcm"` already matches what the Realtime API expects, so
    no resampling step can distort the measurement.
    """
    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(
            "https://api.openai.com/v1/audio/speech",
            headers={"Authorization": f"Bearer {key}"},
            json={
                "model": "gpt-4o-mini-tts",
                "voice": voice,
                "input": text,
                "response_format": "pcm",
            },
        )
        resp.raise_for_status()
        return resp.content


def session_update(prompt: str) -> dict:
    """GA session config for client-driven turn taking."""
    audio_format = {"type": "audio/pcm", "rate": SAMPLE_RATE}
    return {
        "type": "session.update",
        "session": {
            "type": "realtime",
            "output_modalities": ["audio"],
            "instructions": prompt,
            "audio": {
                "input": {
                    "format": audio_format,
                    "transcription": {"model": "gpt-4o-mini-transcribe"},
                    # Explicit null: the client decides where turns end.
                    # With server VAD the incoming speech would cut off every
                    # translation mid-sentence.
                    "turn_detection": None,
                },
                "output": {"format": audio_format, "voice": "alloy"},
            },
        },
    }


async def measure_one(model: str, text: str, prompt: str, key: str, realtime: bool) -> dict:
    """Run a single utterance through the API and time the response onset."""
    pcm = await synthesize(text, key)
    url = f"wss://api.openai.com/v1/realtime?model={model}"

    seen_events: set[str] = set()
    transcript: list[str] = []
    heard: list[str] = []
    onset: float | None = None
    audio_bytes = 0
    error: str | None = None

    async with websockets.connect(
        url, additional_headers={"Authorization": f"Bearer {key}"}, max_size=None
    ) as ws:
        first = json.loads(await ws.recv())
        if first.get("type") == "error":
            return {"error": first["error"].get("message", "unknown"), "source": text}

        await ws.send(json.dumps(session_update(prompt)))

        chunk = SAMPLE_RATE * BYTES_PER_SAMPLE * CHUNK_MS // 1000
        for offset in range(0, len(pcm), chunk):
            await ws.send(json.dumps({
                "type": "input_audio_buffer.append",
                "audio": base64.b64encode(pcm[offset:offset + chunk]).decode(),
            }))
            await asyncio.sleep(CHUNK_MS / 1000 if realtime else 0.005)

        committed_at = time.perf_counter()
        await ws.send(json.dumps({"type": "input_audio_buffer.commit"}))
        await ws.send(json.dumps({"type": "response.create"}))

        while True:
            try:
                event = json.loads(await asyncio.wait_for(ws.recv(), timeout=30))
            except asyncio.TimeoutError:
                error = "no response.done within 30s"
                break

            kind = event.get("type", "?")
            seen_events.add(kind)

            if kind == "error":
                error = event["error"].get("message", "unknown")
                break
            if kind.endswith("output_audio.delta") or kind == "response.audio.delta":
                if onset is None:
                    onset = time.perf_counter() - committed_at
                audio_bytes += len(base64.b64decode(event.get("delta", "")))
            elif kind.endswith("output_audio_transcript.delta") or kind == "response.audio_transcript.delta":
                transcript.append(event.get("delta", ""))
            elif "input_audio_transcription.completed" in kind:
                heard.append(event.get("transcript", ""))
            elif kind == "response.done":
                break

    translation = "".join(transcript).strip()
    lowered = translation.lower()
    return {
        "source": text,
        "source_audio_s": round(len(pcm) / (SAMPLE_RATE * BYTES_PER_SAMPLE), 2),
        "heard": " ".join(heard).strip(),
        "translation": translation,
        "onset_ms": round(onset * 1000) if onset is not None else None,
        "output_audio_s": round(audio_bytes / (SAMPLE_RATE * BYTES_PER_SAMPLE), 2),
        "reported_speech_suspected": any(m in lowered for m in REPORTED_SPEECH_MARKERS),
        "answered_instead_of_translated": looks_like_an_answer(text, translation),
        "error": error,
        "event_types": sorted(seen_events),
    }


def summarize(results: list[dict]) -> None:
    onsets = [r["onset_ms"] for r in results if r.get("onset_ms") is not None]
    if not onsets:
        print("\nNo successful runs — nothing to summarise.")
        return

    ordered = sorted(onsets)
    p95 = ordered[min(len(ordered) - 1, int(len(ordered) * 0.95))]
    print("\n" + "=" * 72)
    print(
        f"ONSET  n={len(ordered)}  "
        f"min={ordered[0]}  median={round(statistics.median(ordered))}  "
        f"p95={p95}  max={ordered[-1]} ms"
    )

    answered = [r for r in results if r.get("answered_instead_of_translated")]
    if answered:
        print(f"\n⚠  {len(answered)}/{len(results)} run(s) answered the question instead of "
              f"translating it — the failure mode that makes this approach unusable:")
        for r in answered:
            print(f"     source: {r['source']}")
            print(f"     output: {r['translation']}")

    suspects = [r for r in results if r.get("reported_speech_suspected")]
    if suspects:
        print(f"\n⚠  {len(suspects)}/{len(results)} run(s) look like reported speech "
              f"rather than translation — read these:")
        for r in suspects:
            print(f"     {r['translation']}")

    observed = sorted({e for r in results for e in r.get("event_types", [])})
    audio_events = [e for e in observed if "audio" in e]
    if audio_events:
        print("\nAudio-bearing event types the API actually sent:")
        for e in audio_events:
            print(f"   {e}")


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--model", default="gpt-realtime-mini",
                        help="Realtime model id (default: %(default)s)")
    parser.add_argument("--runs", type=int, default=3,
                        help="Repeats per sentence, for variance (default: %(default)s)")
    parser.add_argument("--fast", action="store_true",
                        help="Stream audio as fast as possible instead of in real time. "
                             "Overstates onset latency; see module docstring.")
    parser.add_argument("--prompt-file", type=Path,
                        help="Read the translator prompt from a file instead of the built-in one")
    parser.add_argument("--json", type=Path, help="Write raw results to this path")
    args = parser.parse_args()

    key = api_key()
    prompt = args.prompt_file.read_text(encoding="utf-8") if args.prompt_file else DEFAULT_PROMPT
    pacing = "as-fast-as-possible" if args.fast else "real-time"

    print(f"Model: {args.model}   runs/sentence: {args.runs}   pacing: {pacing}")
    print("=" * 72)

    results: list[dict] = []
    for lang, text in SENTENCES:
        print(f"\n[{lang.upper()}] {text}")
        for run in range(1, args.runs + 1):
            result = await measure_one(args.model, text, prompt, key, realtime=not args.fast)
            result["lang"] = lang
            results.append(result)
            if result.get("error"):
                print(f"  #{run}  ✗ {result['error']}")
                continue
            flag = ""
            if result["answered_instead_of_translated"]:
                flag = "  ⚠ ANSWERED, did not translate"
            elif result["reported_speech_suspected"]:
                flag = "  ⚠ reported speech?"
            print(f"  #{run}  onset {result['onset_ms']:>4} ms  |  {result['translation']}{flag}")

    summarize(results)

    if args.json:
        args.json.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\nRaw results written to {args.json}")


if __name__ == "__main__":
    asyncio.run(main())
