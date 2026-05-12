#!/usr/bin/env python3
"""Realtime WebSocket Example - Low-level WebSocket API.

This example demonstrates how to use the RealtimeVoiceAPI for direct
WebSocket-based voice interactions with OpenAI's Realtime API.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import asyncio
from openai_apis.realtime import RealtimeVoiceAPI, RealtimeConfig
from dotenv import load_dotenv

load_dotenv()

async def main():
    """Run realtime WebSocket session."""
    print("OpenAI Realtime API WebSocket - Push-to-Talk Mode")

    config = RealtimeConfig(
        language="hu",
        voice="ash",
        instructions="Te egy magyar nyelvű asszisztens vagy. Segíts a felhasználónak!"
    )

    def on_transcription(text: str):
        print(f"[TRANSZKRIPCIÓ] {text}")

    def on_audio_response(audio_data):
        print(f"[AUDIO] Received {len(audio_data)} bytes")

    api = RealtimeVoiceAPI(
        config=config,
        on_transcription=on_transcription,
        on_audio_response=on_audio_response
    )

    await api.run_session()

if __name__ == "__main__":
    asyncio.run(main())
