"""Streaming transcription WebSocket endpoint — WS /ws/transcription."""

import json
import asyncio
from typing import Optional
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query

from openai_apis import TranscriptionSession, TranscriptionConfig

router = APIRouter(tags=["transcription"])


@router.websocket("/ws/transcription")
async def transcription_websocket(
    websocket: WebSocket,
    language: str = Query("hu", description="ISO-639-1 language code"),
    model: str = Query("gpt-realtime-whisper", description="Transcription model"),
):
    """WebSocket streaming transcription.

    Client sends:
        {"type": "audio", "data": "<base64 PCM16>"}  — audio chunk
        {"type": "commit"}                            — commit buffer, trigger transcription
        {"type": "close"}                             — graceful close

    Server sends:
        {"type": "transcript.delta", "delta": "...", "item_id": "..."}
        {"type": "transcript.completed", "transcript": "...", "item_id": "..."}
        {"type": "session_ready"}
        {"type": "error", "message": "..."}
    """
    await websocket.accept()

    config = TranscriptionConfig(language=language, model=model)

    try:
        async with TranscriptionSession(config) as session:
            # Wire up callbacks to forward events to the browser WebSocket
            def on_delta(data):
                asyncio.ensure_future(websocket.send_json({
                    "type": "transcript.delta",
                    "delta": data["delta"],
                    "item_id": data.get("item_id"),
                }))

            def on_completed(data):
                asyncio.ensure_future(websocket.send_json({
                    "type": "transcript.completed",
                    "transcript": data["transcript"],
                    "item_id": data.get("item_id"),
                }))

            def on_error(data):
                asyncio.ensure_future(websocket.send_json({
                    "type": "error",
                    "message": str(data.get("error", "Unknown error")),
                }))

            session.on("transcript.delta", on_delta)
            session.on("transcript.completed", on_completed)
            session.on("error", on_error)

            await websocket.send_json({"type": "session_ready"})

            # Main receive loop — read client messages and forward audio
            while True:
                data = await websocket.receive_json()
                msg_type = data.get("type", "")

                if msg_type == "audio":
                    import base64
                    audio_b64 = data.get("data", "")
                    if audio_b64:
                        audio_bytes = base64.b64decode(audio_b64)
                        await session.send_audio(audio_bytes)

                elif msg_type == "commit":
                    await session.commit_audio()

                elif msg_type == "close":
                    break

    except WebSocketDisconnect:
        pass
    except Exception as e:
        try:
            await websocket.send_json({"type": "error", "message": str(e)})
        except Exception:
            pass
