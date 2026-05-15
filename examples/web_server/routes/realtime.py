"""Realtime voice WebSocket endpoint — WS /ws/realtime."""

import json
import base64
import asyncio
from typing import Optional
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query

from openai_apis import RealtimeSession, RealtimeConfig, VADConfig
from openai_apis.realtime.events import AudioDelta, AudioDone, TranscriptDelta, TranscriptCompleted, ErrorEvent

router = APIRouter(tags=["realtime"])


@router.websocket("/ws/realtime")
async def realtime_websocket(
    websocket: WebSocket,
    voice: str = Query("ash", description="Voice"),
    language: str = Query("hu", description="Language code"),
    instructions: Optional[str] = Query(None, description="System instructions"),
):
    """WebSocket realtime voice session.

    Client sends:
        {"type": "audio", "data": "<base64 PCM16>"}
        {"type": "commit"}    — commit audio + create response
        {"type": "cancel"}    — cancel in-progress response
        {"type": "close"}     — graceful close

    Server sends:
        {"type": "session_ready"}
        {"type": "transcription", "text": "..."}
        {"type": "response_audio", "data": "<base64>"}
        {"type": "response_audio_done"}
        {"type": "response_text_delta", "text": "..."}
        {"type": "response_text", "text": "..."}
        {"type": "response_done"}
        {"type": "error", "message": "..."}
    """
    await websocket.accept()

    config = RealtimeConfig(
        voice=voice,
        language=language,
        instructions=instructions or f"You are a helpful assistant. Respond in {language} language.",
        vad=VADConfig(mode="disabled"),  # Push-to-talk: client controls commit
    )

    try:
        async with RealtimeSession(config) as session:
            # --- Register callbacks that forward events to browser ---
            def on_input_transcript(event: TranscriptCompleted):
                asyncio.ensure_future(websocket.send_json({
                    "type": "transcription",
                    "text": event.transcript,
                }))

            def on_audio_delta(event: AudioDelta):
                audio_b64 = base64.b64encode(event.audio_bytes).decode("ascii")
                asyncio.ensure_future(websocket.send_json({
                    "type": "response_audio",
                    "data": audio_b64,
                }))

            def on_audio_done(event: AudioDone):
                asyncio.ensure_future(websocket.send_json({
                    "type": "response_audio_done",
                }))

            def on_output_transcript_delta(event: TranscriptDelta):
                asyncio.ensure_future(websocket.send_json({
                    "type": "response_text_delta",
                    "text": event.delta,
                }))

            def on_output_transcript(event: TranscriptCompleted):
                asyncio.ensure_future(websocket.send_json({
                    "type": "response_text",
                    "text": event.transcript,
                }))

            def on_response_done(data):
                asyncio.ensure_future(websocket.send_json({
                    "type": "response_done",
                }))

            def on_error(event):
                msg = event.message if isinstance(event, ErrorEvent) else str(event)
                asyncio.ensure_future(websocket.send_json({
                    "type": "error",
                    "message": msg,
                }))

            session.on("transcript.input", on_input_transcript)
            session.on("audio.delta", on_audio_delta)
            session.on("audio.done", on_audio_done)
            session.on("transcript.delta", on_output_transcript_delta)
            session.on("transcript.output", on_output_transcript)
            session.on("response.done", on_response_done)
            session.on("error", on_error)

            await websocket.send_json({"type": "session_ready"})

            # --- Main receive loop ---
            while True:
                data = await websocket.receive_json()
                msg_type = data.get("type", "")

                if msg_type == "audio":
                    audio_b64 = data.get("data", "")
                    if audio_b64:
                        audio_bytes = base64.b64decode(audio_b64)
                        await session.send_audio(audio_bytes)

                elif msg_type == "commit":
                    await session.commit_audio()
                    await session.create_response()

                elif msg_type == "cancel":
                    await session.cancel_response()

                elif msg_type == "close":
                    break

    except WebSocketDisconnect:
        pass
    except Exception as e:
        try:
            await websocket.send_json({"type": "error", "message": str(e)})
        except Exception:
            pass
