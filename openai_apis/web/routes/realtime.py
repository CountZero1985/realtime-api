"""Realtime voice WebSocket proxy endpoint."""

import os
import json
import asyncio
from typing import Optional
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
import websockets

from openai_apis._logging import get_logger, log_audit_event
from dotenv import load_dotenv

router = APIRouter(tags=["realtime"])
logger = get_logger(__name__)

load_dotenv()

# OpenAI Realtime API configuration
OPENAI_REALTIME_URL = "wss://api.openai.com/v1/realtime"
DEFAULT_MODEL = "gpt-realtime-mini"


def create_session_update_event(
    voice: str = "sage",
    language: str = "hu",
    instructions: str = "You are a helpful assistant. Respond in the user's language.",
    temperature: float = 0.8,
    speed: float = 1.1,
) -> dict:
    """Create a GA session.update event for the OpenAI Realtime API.

    Args:
        voice: Output voice.
        language: Input transcription language (ISO-639-1).
        instructions: System instructions.
        temperature: Accepted for backwards compatibility and ignored — the GA
            session object has no temperature field.
        speed: Output speech speed (GA: audio.output.speed).
    """
    del temperature  # not part of the GA session schema
    audio_format = {"type": "audio/pcm", "rate": 24000}
    return {
        "type": "session.update",
        "session": {
            "type": "realtime",
            "output_modalities": ["audio"],
            "instructions": instructions,
            "audio": {
                "input": {
                    "format": audio_format,
                    "transcription": {
                        "model": "gpt-4o-mini-transcribe",
                        "language": language,
                    },
                    # Explicit null: manual turn detection, no server VAD.
                    "turn_detection": None,
                },
                "output": {
                    "format": audio_format,
                    "voice": voice,
                    "speed": speed,
                },
            },
            "max_output_tokens": "inf",
        }
    }


@router.websocket("/ws/realtime")
async def realtime_websocket(
    websocket: WebSocket,
    voice: str = Query("sage", description="Voice: sage, ash, alloy, echo, shimmer"),
    language: str = Query("hu", description="Language code"),
    instructions: Optional[str] = Query(None, description="System instructions"),
    temperature: float = Query(0.8, description="Temperature (0.0 - 1.0)"),
    speed: float = Query(1.1, description="Speech speed (0.25 - 4.0)"),
):
    """
    WebSocket proxy to OpenAI Realtime API.

    This endpoint accepts WebSocket connections from the browser and proxies
    them to OpenAI's Realtime API, handling session configuration and
    message forwarding.

    Client sends:
    - {"type": "audio", "data": "<base64-encoded PCM16 audio>"}
    - {"type": "commit"} - Commit audio buffer and request response
    - {"type": "cancel"} - Cancel current response

    Server sends (forwarded from OpenAI):
    - {"type": "transcription", "text": "..."} - User speech transcription
    - {"type": "response_audio", "data": "..."} - Response audio chunk (base64)
    - {"type": "response_text", "text": "..."} - Response text transcript
    - {"type": "response_done"} - Response complete
    - {"type": "error", "message": "..."} - Error message
    - {"type": "session_ready"} - Session configured and ready
    """
    await websocket.accept()
    logger.info(f"Realtime WebSocket connected: voice={voice}, language={language}")

    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        await websocket.send_json({"type": "error", "message": "OPENAI_API_KEY not configured"})
        await websocket.close()
        return

    # Default instructions if not provided
    if not instructions:
        instructions = f"You are a helpful assistant. Respond in {language} language."

    openai_ws = None
    session_configured = False

    try:
        # Connect to OpenAI Realtime API
        url = f"{OPENAI_REALTIME_URL}?model={DEFAULT_MODEL}"
        # No OpenAI-Beta header: the beta Realtime API was disabled in May 2026.
        headers = {
            "Authorization": f"Bearer {api_key}",
        }

        async with websockets.connect(url, additional_headers=headers) as openai_ws:
            logger.info("Connected to OpenAI Realtime API")

            log_audit_event(
                event_type="realtime_proxy",
                action="openai_connected",
                details={"voice": voice, "language": language},
            )

            async def forward_from_openai():
                """Forward messages from OpenAI to browser."""
                nonlocal session_configured

                try:
                    async for message in openai_ws:
                        try:
                            event = json.loads(message)
                            event_type = event.get("type", "")

                            # Handle session lifecycle
                            if event_type == "session.created" and not session_configured:
                                # Send session configuration
                                session_update = create_session_update_event(
                                    voice=voice,
                                    language=language,
                                    instructions=instructions,
                                    temperature=temperature,
                                    speed=speed,
                                )
                                await openai_ws.send(json.dumps(session_update))
                                session_configured = True
                                logger.info("Session configuration sent")

                            elif event_type == "session.updated":
                                await websocket.send_json({"type": "session_ready"})
                                logger.info("Session ready")

                            # Forward transcription
                            elif event_type == "conversation.item.input_audio_transcription.completed":
                                transcript = event.get("transcript", "")
                                await websocket.send_json({
                                    "type": "transcription",
                                    "text": transcript,
                                })

                            # Forward response audio
                            elif event_type == "response.audio.delta":
                                audio_b64 = event.get("delta", "")
                                if audio_b64:
                                    await websocket.send_json({
                                        "type": "response_audio",
                                        "data": audio_b64,
                                    })

                            # Forward response text transcript
                            elif event_type == "response.audio_transcript.delta":
                                text = event.get("delta", "")
                                if text:
                                    await websocket.send_json({
                                        "type": "response_text_delta",
                                        "text": text,
                                    })

                            elif event_type == "response.audio_transcript.done":
                                transcript = event.get("transcript", "")
                                await websocket.send_json({
                                    "type": "response_text",
                                    "text": transcript,
                                })

                            # Response lifecycle
                            elif event_type == "response.audio.done":
                                await websocket.send_json({"type": "response_audio_done"})

                            elif event_type == "response.done":
                                await websocket.send_json({"type": "response_done"})

                            # Errors
                            elif event_type == "error":
                                error_msg = event.get("error", {}).get("message", "Unknown error")
                                await websocket.send_json({
                                    "type": "error",
                                    "message": error_msg,
                                })
                                logger.error(f"OpenAI error: {error_msg}")

                        except json.JSONDecodeError:
                            logger.warning("Non-JSON message from OpenAI")

                except websockets.exceptions.ConnectionClosed:
                    logger.info("OpenAI WebSocket closed")

            async def forward_to_openai():
                """Forward messages from browser to OpenAI."""
                try:
                    while True:
                        data = await websocket.receive_json()
                        msg_type = data.get("type", "")

                        if msg_type == "audio":
                            # Forward audio chunk
                            audio_b64 = data.get("data", "")
                            if audio_b64:
                                await openai_ws.send(json.dumps({
                                    "type": "input_audio_buffer.append",
                                    "audio": audio_b64,
                                }))

                        elif msg_type == "commit":
                            # Commit audio buffer and request response
                            await openai_ws.send(json.dumps({
                                "type": "input_audio_buffer.commit"
                            }))
                            await openai_ws.send(json.dumps({
                                "type": "response.create",
                                "response": {
                                    "output_modalities": ["audio"],
                                    "audio": {
                                        "output": {
                                            "format": {"type": "audio/pcm", "rate": 24000},
                                            "voice": voice,
                                        },
                                    },
                                }
                            }))
                            logger.info("Audio committed, response requested")

                        elif msg_type == "cancel":
                            # Cancel current response
                            await openai_ws.send(json.dumps({
                                "type": "response.cancel"
                            }))
                            logger.info("Response cancelled")

                        elif msg_type == "clear":
                            # Clear audio buffer
                            await openai_ws.send(json.dumps({
                                "type": "input_audio_buffer.clear"
                            }))

                except WebSocketDisconnect:
                    logger.info("Browser WebSocket disconnected")

            # Run both forwarding tasks concurrently
            await asyncio.gather(
                forward_from_openai(),
                forward_to_openai(),
                return_exceptions=True,
            )

    except websockets.exceptions.InvalidStatusCode as e:
        error_msg = f"Failed to connect to OpenAI: {e}"
        logger.error(error_msg)
        try:
            await websocket.send_json({"type": "error", "message": error_msg})
        except Exception:
            pass

    except Exception as e:
        error_msg = f"Realtime proxy error: {str(e)}"
        logger.error(error_msg)
        try:
            await websocket.send_json({"type": "error", "message": error_msg})
        except Exception:
            pass

    finally:
        log_audit_event(
            event_type="realtime_proxy",
            action="session_ended",
            details={"voice": voice, "language": language},
        )
        logger.info("Realtime WebSocket session ended")
