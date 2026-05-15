#!/usr/bin/env python3
"""Voice Agent Example - Push-to-talk with RealtimeSession and tool calling."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import asyncio
import numpy as np
from openai_apis import RealtimeSession, RealtimeConfig, VADConfig, ToolRegistry
from examples.utils.audio_io import record_audio, AudioPlayer
from examples.utils.time_format import magyar_ido_szoveggel
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

# --- Tool handlers ---
def get_current_time() -> dict:
    """Returns current time in Hungarian."""
    now = datetime.now()
    return {"time": magyar_ido_szoveggel(now.hour, now.minute)}

def get_weather(city: str) -> dict:
    """Returns mock weather for a city."""
    return {"city": city, "temperature": "22°C", "condition": "napos"}

# --- Tool registry ---
tools = ToolRegistry()
tools.register(
    name="get_current_time",
    description="Visszaadja az aktuális időt magyar nyelven.",
    parameters={"type": "object", "properties": {}, "required": []},
    handler=get_current_time,
)
tools.register(
    name="get_weather",
    description="Visszaadja egy város aktuális időjárását.",
    parameters={
        "type": "object",
        "properties": {"city": {"type": "string", "description": "A város neve"}},
        "required": ["city"],
    },
    handler=get_weather,
)

# --- Config ---
config = RealtimeConfig(
    language="hu",
    voice="ash",
    vad=VADConfig(mode="disabled"),
    instructions="Te egy magyar nyelvű asszisztens vagy. Röviden válaszolj. Ha időt vagy időjárást kérdeznek, használd az eszközeidet.",
    tools=tools,
)

async def main():
    """
    Main function for push-to-talk voice agent demonstration.

    This example demonstrates:
    - RealtimeSession with VAD disabled (push-to-talk mode)
    - ToolRegistry-based tool registration and execution
    - Event-driven audio streaming with delta accumulation
    - Manual audio recording via record_audio() utility
    - Chunked audio streaming to WebSocket (4800 samples/0.2s)
    - Conversation history tracking and viewing
    - Per-session audit log export on exit

    Interactive commands:
    - <Enter>: Start audio recording, speak request, press Enter to stop
    - h: Display conversation history
    - q: Quit and export audit log
    - Ctrl+C: Graceful exit with audit log export
    """
    print("Voice Agent - Push-to-Talk (RealtimeSession)")
    print("Eszközök: get_current_time, get_weather\n")

    audio_buffer = bytearray()
    audio_done_event = asyncio.Event()
    session = None

    try:
        async with RealtimeSession(config=config) as session:
            # Callbacks
            def on_audio_delta(event):
                audio_buffer.extend(event.audio_bytes)

            def on_audio_done(event):
                audio_done_event.set()

            def on_transcript_input(event):
                print(f"\n[TE] {event.transcript}")

            def on_transcript_output(event):
                print(f"[AI] {event.transcript}")

            def on_error(event):
                print(f"[HIBA] {event.code}: {event.message}")

            session.on("audio.delta", on_audio_delta)
            session.on("audio.done", on_audio_done)
            session.on("transcript.input", on_transcript_input)
            session.on("transcript.output", on_transcript_output)
            session.on("error", on_error)

            loop = asyncio.get_event_loop()

            while True:
                print("\n---")
                print("  <Enter> - felvétel indítása")
                print("  h - beszélgetés történet")
                print("  q - kilépés")
                print("---")

                user_input = await loop.run_in_executor(
                    None, input, "Válassz (<Enter>/h/q): "
                )
                user_input = user_input.strip().lower()

                if user_input == "q":
                    print("Kilépés...")
                    break

                elif user_input == "h":
                    history = session.get_conversation_history()
                    print("\n--- Beszélgetés történet ---")
                    for i, msg in enumerate(history):
                        role = "TE" if msg["role"] == "user" else "AI"
                        print(f"  {i+1}. [{role}] {msg['content']}")
                    if not history:
                        print("  (üres)")
                    print("---")
                    continue

                else:
                    # Record audio (blocking, in executor)
                    audio_np = await loop.run_in_executor(None, record_audio)

                    # Reset buffer and event
                    audio_buffer.clear()
                    audio_done_event.clear()

                    # Send audio chunks
                    audio_flat = audio_np.flatten()
                    CHUNK_SIZE = 4800  # 0.2s at 24kHz
                    for i in range(0, len(audio_flat), CHUNK_SIZE):
                        chunk = audio_flat[i:i + CHUNK_SIZE]
                        await session.send_audio(chunk.tobytes())

                    await session.commit_audio()
                    await session.create_response()

                    # Wait for response audio to complete
                    await audio_done_event.wait()

                    # Play response
                    if audio_buffer:
                        audio_array = np.frombuffer(bytes(audio_buffer), dtype=np.int16)
                        with AudioPlayer() as player:
                            player.add_audio(audio_array)

    except KeyboardInterrupt:
        print("\nKilépés (Ctrl+C)...")

    finally:
        # Export audit log
        if session is not None:
            audit_path = Path("logs/voice_agent_audit.json")
            session.audit_log.export_to_file(audit_path)
            print(f"\nAudit log: {audit_path}")

    print("A program véget ért.")

if __name__ == "__main__":
    asyncio.run(main())
