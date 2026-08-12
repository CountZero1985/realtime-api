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

# Hardened against three failure modes measured on gpt-realtime-mini:
# answering a question instead of translating it (invented a street address),
# narrating in reported speech, and drifting from formal to informal register.
# An earlier draft framed the task as "repeat what you hear in Hungarian" and
# produced a run that echoed the German source verbatim — hence the explicit
# "output is always Hungarian" rule.
DEFAULT_PROMPT = """Egy tolmácsgép hangja vagy. Nem vagy résztvevő a beszélgetésben, nem szólítanak meg, és soha nem hozzád beszélnek. A hallott mondat mindig két másik ember között hangzik el; a te egyetlen dolgod, hogy magyarul tolmácsold.

ALAPSZABÁLY
Amit hallasz, azt add vissza magyarul. Semmi mást.
A kimeneted MINDIG magyar — akkor is, ha a forrásnyelvet jól ismered.
Soha ne ismételd meg a forrásnyelvi mondatot.

A KÉRDÉSEK A LEGFONTOSABBAK
Ha a hallott mondat kérdés, a te kimeneted is kérdés — ugyanaz a kérdés, magyarul.
Soha ne válaszolj rá. Nem tudod a választ, és nem is a te dolgod.
Soha ne találj ki adatot: címet, időpontot, árat, nevet, útbaigazítást.

  HALLOD:  "Could you tell me where the nearest pharmacy is?"
  HELYES:  "Meg tudná mondani, hol van a legközelebbi gyógyszertár?"
  HIBÁS:   "A legközelebbi gyógyszertár a sarkon van."      <- válaszoltál
  HIBÁS:   "Azt kérdezi, hol van a legközelebbi gyógyszertár." <- függő beszéd

  HALLOD:  "What time does the last train leave?"
  HELYES:  "Hánykor indul az utolsó vonat?"
  HIBÁS:   "Az utolsó vonat 23:40-kor indul."               <- kitalált adat

TOVÁBBI SZABÁLYOK
- Úgy beszélj, ahogy a beszélő beszélt: egyes szám első személyben, nem róla.
- Magázódás marad magázódás, tegeződés marad tegeződés.
- Pontosan egyszer mondd el a fordítást, aztán hallgass el. Ne ismételd meg,
  ne fogalmazd át, ne told meg magyarázattal.
- Ne kommentálj, ne kérj pontosítást, ne szólj közbe.
- Ha valamit nem értettél tisztán, fordítsd le a legjobb tudásod szerint —
  de ne találd ki, mi hangozhatott el.
- Természetes, gördülékeny magyar mondatot mondj, ne szó szerinti tükörfordítást.
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


def load_sentences(path: Path) -> list[tuple[str, str]]:
    """Read source utterances from a file: 'lang<TAB>text' per line.

    Lets a run target the cases a prompt is being hardened against —
    questions, for instance, where answering instead of translating shows up.
    """
    out: list[tuple[str, str]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        lang, _, text = line.partition("\t")
        out.append((lang, text) if text else ("xx", lang))
    if not out:
        sys.exit(f"No usable sentences in {path}")
    return out


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


def _audio_output(audio_format: dict, speed: float | None) -> dict:
    """Build audio.output, omitting `speed` when unset so the server default applies."""
    out = {"format": audio_format, "voice": "alloy"}
    if speed is not None:
        out["speed"] = speed
    return out


def session_update(prompt: str, speed: float | None = None) -> dict:
    """GA session config for client-driven turn taking.

    ``speed`` compresses the spoken output. It matters for more than comfort:
    if the translation takes longer to say than the source phrase lasted, a
    continuous stream falls further behind on every turn (see the project's
    HIBA-002). Speed is the cheapest lever against that drift.
    """
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
                "output": _audio_output(audio_format, speed),
            },
        },
    }


async def measure_one(model: str, text: str, prompt: str, key: str, realtime: bool,
                      speed: float | None = None) -> dict:
    """Run a single utterance through the API and time the response onset."""
    pcm = await synthesize(text, key)
    url = f"wss://api.openai.com/v1/realtime?model={model}"

    seen_events: set[str] = set()
    transcript: list[str] = []
    heard: list[str] = []
    onset: float | None = None
    audio_bytes = 0
    deltas: list[tuple[float, float]] = []
    error: str | None = None

    async with websockets.connect(
        url, additional_headers={"Authorization": f"Bearer {key}"}, max_size=None
    ) as ws:
        first = json.loads(await ws.recv())
        if first.get("type") == "error":
            return {"error": first["error"].get("message", "unknown"), "source": text}

        await ws.send(json.dumps(session_update(prompt, speed)))

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
                # (arrival time, audio seconds available so far) — feeds the
                # jitter-buffer simulation below.
                deltas.append(
                    (time.perf_counter(), audio_bytes / (SAMPLE_RATE * BYTES_PER_SAMPLE))
                )
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
        # >1.0 means the translation takes longer to say than the source did:
        # on a continuous stream the lag then grows on every turn.
        "duration_ratio": round(
            (audio_bytes / (SAMPLE_RATE * BYTES_PER_SAMPLE)) / max(len(pcm) / (SAMPLE_RATE * BYTES_PER_SAMPLE), 0.01), 2
        ),
        # Does the audio arrive fast enough to be played without gaps?
        **{f"jitter_{k}": v for k, v in simulate_jitter_buffer(deltas).items()},
        "reported_speech_suspected": any(m in lowered for m in REPORTED_SPEECH_MARKERS),
        "answered_instead_of_translated": looks_like_an_answer(text, translation),
        "error": error,
        "event_types": sorted(seen_events),
    }


def simulate_jitter_buffer(
    deltas: list[tuple[float, float]], prebuffer_s: float = 0.06
) -> dict:
    """Replay the arrival timestamps against the app's own jitter buffer.

    The Flutter client (`app/lib/realtime/jitter_buffer.dart`) prebuffers
    `prebuffer_s` of audio, then plays at real time. If the server delivers
    audio slower than it is consumed, the buffer empties mid-utterance and
    playback drops out — audible as a glitch, not as slowness.

    Returns the minimum buffer depth reached (negative == underrun) and the
    delivery rate in audio-seconds produced per wall-clock second. Below 1.0
    the server cannot sustain real-time playback at all.
    """
    if len(deltas) < 2:
        return {"min_depth_s": None, "underran": None, "delivery_rate": None}

    t_first, _ = deltas[0]
    t_last, total_audio_s = deltas[-1]
    wall = t_last - t_first
    delivery_rate = (total_audio_s / wall) if wall > 0 else float("inf")

    # Playback starts once prebuffer_s of audio has accumulated.
    start = next((t for t, cum in deltas if cum >= prebuffer_s), None)
    if start is None:  # whole utterance is shorter than the prebuffer
        return {"min_depth_s": None, "underran": False, "delivery_rate": round(delivery_rate, 2)}

    # Depth at each arrival: audio available minus audio already played.
    min_depth = min(cum - (t - start) for t, cum in deltas if t >= start)
    return {
        "min_depth_s": round(min_depth, 3),
        "underran": min_depth < 0,
        "delivery_rate": round(delivery_rate, 2),
    }


def summarize(results: list[dict]) -> None:
    onsets = [r["onset_ms"] for r in results if r.get("onset_ms") is not None]
    if not onsets:
        print("\nNo successful runs — nothing to summarise.")
        return

    ordered = sorted(onsets)
    p95 = ordered[min(len(ordered) - 1, int(len(ordered) * 0.95))]
    print("\n" + "=" * 72)

    # The drift metric: spoken-output duration relative to the source phrase.
    # Above 1.0 the translation cannot keep up with a continuous speaker, and
    # the lag compounds turn after turn no matter how fast the onset is.
    ratios = [r["duration_ratio"] for r in results if r.get("duration_ratio")]
    if ratios:
        ordered_r = sorted(ratios)
        med_r = ordered_r[len(ordered_r) // 2]
        over = sum(1 for x in ratios if x > 1.0)
        print(
            f"HOSSZARANY (kimenet/forras)  med={med_r:.2f}  "
            f"min={ordered_r[0]:.2f}  max={ordered_r[-1]:.2f}  "
            f"| {over}/{len(ratios)} futas hosszabb a forrasnal"
        )
        if med_r > 1.0:
            print("  ⚠ a median >1.0: folyamatos beszednel a lemaradas nő")
    print(
        f"ONSET  n={len(ordered)}  "
        f"min={ordered[0]}  median={round(statistics.median(ordered))}  "
        f"p95={p95}  max={ordered[-1]} ms"
    )

    # Glitch metric: can the 60 ms jitter buffer sustain gapless playback?
    # A negative depth means the client runs out of audio mid-sentence, which
    # is heard as a dropout — a different fault from "the voice is too fast".
    depths = [r["jitter_min_depth_s"] for r in results if r.get("jitter_min_depth_s") is not None]
    rates = [r["jitter_delivery_rate"] for r in results if r.get("jitter_delivery_rate")]
    if depths:
        under = sum(1 for d in depths if d < 0)
        print(
            f"JITTER (60 ms elopuffer)  min_melyseg med={statistics.median(depths):+.3f} s  "
            f"legrosszabb={min(depths):+.3f} s  | {under}/{len(depths)} futas alulcsordult"
        )
        if rates:
            print(
                f"  szallitasi rata  med={statistics.median(rates):.2f}x valos ido  "
                f"(min={min(rates):.2f}x)  — 1.0 alatt a lejatszas nem tarthato"
            )
        if under:
            print("  ⚠ alulcsordulas: a hang lyukas lesz, ez NEM a sebesseg hibaja")

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
    parser.add_argument("--sentences-file", type=Path,
                        help="Source utterances, one per line as 'lang<TAB>text' "
                             "(or just text, defaulting to 'xx'). Lines starting with # are ignored.")
    parser.add_argument("--speed", type=float,
                        help="Spoken output speed (e.g. 1.15). Omit for the server default. "
                             "Compressing the output is the cheapest lever against lag drift.")
    parser.add_argument("--json", type=Path, help="Write raw results to this path")
    args = parser.parse_args()

    key = api_key()
    prompt = args.prompt_file.read_text(encoding="utf-8") if args.prompt_file else DEFAULT_PROMPT
    sentences = load_sentences(args.sentences_file) if args.sentences_file else SENTENCES
    pacing = "as-fast-as-possible" if args.fast else "real-time"

    print(f"Model: {args.model}   runs/sentence: {args.runs}   pacing: {pacing}")
    print("=" * 72)

    results: list[dict] = []
    for lang, text in sentences:
        print(f"\n[{lang.upper()}] {text}")
        for run in range(1, args.runs + 1):
            result = await measure_one(args.model, text, prompt, key,
                                       realtime=not args.fast, speed=args.speed)
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
            print(f"  #{run}  onset {result['onset_ms']:>4} ms  "
                  f"hossz×{result['duration_ratio']:.2f}  |  {result['translation']}{flag}")

    summarize(results)

    if args.json:
        args.json.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\nRaw results written to {args.json}")


if __name__ == "__main__":
    asyncio.run(main())
