"""Mit kuld a szerver egy adott turn_detection beallitas mellett?

A `semantic_vad` elvben pont az, amit egy forditotol varnank: a MODELL donti
el, hol er veget egy gondolat, nem egy csendkuszob. Ezen az anyagon (30 s
hirbeszed, szunet nelkul) viszont nulla fordulot adott — es felmerult, hogy a
szerver csak akkor szegmental, ha reagalhat is ra (`create_response`).

Ez a proba minden esemenytipust megszamol, es kiirja a visszaigazolt
konfiguraciot, hogy a "nem fogadta el" es a "elfogadta, de nem tuzel" esetek
szetvalasszanak.

    uv run python examples/probe_turn_detection.py '<turn_detection JSON>' [masodperc]
"""
import asyncio, base64, json, os, sys, wave

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import websockets
from translation_latency_bench import DEFAULT_PROMPT, SAMPLE_RATE

WAV = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                   "..", "data", "eval", "2026-08-12T19-13-48-input.wav")
TD = json.loads(sys.argv[1])
SECONDS = int(sys.argv[2]) if len(sys.argv) > 2 else 15


async def main() -> None:
    key = os.environ["OPENAI_API_KEY"]
    with wave.open(WAV) as w:
        pcm = w.readframes(w.getnframes())[: SAMPLE_RATE * 2 * SECONDS]
    fmt = {"type": "audio/pcm", "rate": SAMPLE_RATE}
    cfg = {"type": "session.update", "session": {
        "type": "realtime", "output_modalities": ["audio"],
        "instructions": DEFAULT_PROMPT,
        "audio": {"input": {"format": fmt,
                            "transcription": {"model": "gpt-4o-mini-transcribe"},
                            "turn_detection": TD},
                  "output": {"format": fmt, "voice": "alloy"}}}}

    url = "wss://api.openai.com/v1/realtime?model=gpt-realtime-mini"
    seen: dict[str, int] = {}
    async with websockets.connect(
        url, additional_headers={"Authorization": f"Bearer {key}"}, max_size=None
    ) as ws:
        await ws.recv()
        await ws.send(json.dumps(cfg))

        async def reader() -> None:
            while True:
                ev = json.loads(await ws.recv())
                k = ev.get("type", "?")
                seen[k] = seen.get(k, 0) + 1
                if k == "error":
                    print("  ERROR:", json.dumps(ev["error"], ensure_ascii=False))
                elif k == "session.updated":
                    td = ev["session"]["audio"]["input"].get("turn_detection")
                    print("  visszaigazolva:", json.dumps(td, ensure_ascii=False))

        task = asyncio.create_task(reader())
        chunk = SAMPLE_RATE * 2 * 20 // 1000
        for off in range(0, len(pcm), chunk):
            await ws.send(json.dumps({"type": "input_audio_buffer.append",
                                      "audio": base64.b64encode(pcm[off:off + chunk]).decode()}))
            await asyncio.sleep(0.02)  # valos ido: a VAD ezt latja elesben is
        await asyncio.sleep(6)
        task.cancel()

    print(f"\nesemenyek ({SECONDS} s hang utan):")
    for k, v in sorted(seen.items()):
        print(f"  {v:>3}  {k}")
    commits = seen.get("input_audio_buffer.committed", 0)
    print(f"\n-> {commits} frazishatar" + ("" if commits else "  (a szerver NEM szegmentalt)"))


asyncio.run(main())
