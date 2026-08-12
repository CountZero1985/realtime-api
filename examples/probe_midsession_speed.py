"""Can audio.output.speed be changed mid-session via session.update?

The whole adaptive-speed idea depends on this. If the speed is fixed for the
lifetime of the session, per-turn adaptation would require reconnecting — far
too expensive to do per phrase.

Method: one session, the SAME sentence translated three times, with a
session.update changing only `speed` between turns. If the produced audio
duration tracks the requested speed, the parameter is live.
"""
import asyncio, base64, json, os, sys, time

sys.path.insert(0, os.path.expanduser("~/projects/realtime-api/examples"))
from translation_latency_bench import (  # noqa: E402
    BYTES_PER_SAMPLE, CHUNK_MS, SAMPLE_RATE, DEFAULT_PROMPT,
    session_update, synthesize,
)
import websockets  # noqa: E402

TEXT = "Der Zug nach München fährt heute leider eine halbe Stunde später ab."
SPEEDS = [1.0, 1.5, 1.0]


async def main() -> None:
    key = os.environ["OPENAI_API_KEY"]
    pcm = await synthesize(TEXT, key)
    url = "wss://api.openai.com/v1/realtime?model=gpt-realtime-mini"
    chunk = SAMPLE_RATE * BYTES_PER_SAMPLE * CHUNK_MS // 1000

    async with websockets.connect(
        url, additional_headers={"Authorization": f"Bearer {key}"}, max_size=None
    ) as ws:
        first = json.loads(await ws.recv())
        if first.get("type") == "error":
            print("ERROR:", first["error"]); return

        results = []
        for turn, speed in enumerate(SPEEDS, 1):
            # Only the speed differs between turns; same prompt, same audio.
            await ws.send(json.dumps(session_update(DEFAULT_PROMPT, speed)))
            for off in range(0, len(pcm), chunk):
                await ws.send(json.dumps({
                    "type": "input_audio_buffer.append",
                    "audio": base64.b64encode(pcm[off:off + chunk]).decode(),
                }))
                await asyncio.sleep(0.004)

            t0 = time.perf_counter()
            await ws.send(json.dumps({"type": "input_audio_buffer.commit"}))
            await ws.send(json.dumps({"type": "response.create"}))

            audio_bytes, onset, text, err = 0, None, [], None
            while True:
                ev = json.loads(await asyncio.wait_for(ws.recv(), timeout=30))
                k = ev.get("type", "")
                if k == "error":
                    err = ev["error"].get("message"); break
                if k.endswith("output_audio.delta"):
                    if onset is None:
                        onset = time.perf_counter() - t0
                    audio_bytes += len(base64.b64decode(ev.get("delta", "")))
                elif k.endswith("output_audio_transcript.delta"):
                    text.append(ev.get("delta", ""))
                elif k == "response.done":
                    break
            secs = audio_bytes / (SAMPLE_RATE * BYTES_PER_SAMPLE)
            results.append((turn, speed, secs, err))
            print(f"  turn {turn}  speed={speed}  audio={secs:.2f}s  "
                  f"onset={round((onset or 0)*1000)}ms  err={err}")
            print(f"          {''.join(text).strip()}")

        print("\n" + "=" * 64)
        base = results[0][2]
        for turn, speed, secs, err in results:
            print(f"  speed {speed}: {secs:.2f}s  ({secs/base:.2f}x az elso turnhoz kepest)")
        fast = results[1][2]
        print()
        if base > 0 and fast / base < 0.85:
            print("EL: a session.update menet kozben MEGVALTOZTATJA a sebesseget.")
        else:
            print("NEM EL: a sebesseg a session elejen rogzul (vagy a hatas tul kicsi).")


asyncio.run(main())
