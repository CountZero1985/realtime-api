"""WebSocket-based realtime transcription session.

Async WebSocket client for the OpenAI Realtime API transcription endpoint.
Inherits from BaseSession for lifecycle management, state machine, and audit logging.
"""

import asyncio
import base64
import json
from typing import Optional
import websockets
from openai_apis._session import BaseSession, InvalidStateTransition, SessionState
from openai_apis._config import BaseConfig, VADConfig
from openai_apis._logging import get_logger, set_correlation_id, log_audit_event
from openai_apis.transcription.config import TranscriptionConfig


class TranscriptionSession(BaseSession):
    """Async WebSocket client for realtime transcription via OpenAI Realtime API.

    Connects to wss://api.openai.com/v1/realtime and streams audio for
    real-time speech-to-text transcription. Inherits lifecycle management,
    state machine, and audit logging from BaseSession.

    Supported callback events (registered via session.on()):
        - "transcript.delta": Partial transcription text (streaming)
        - "transcript.completed": Final complete transcription
        - "error": Error events from the server
        - "session.created": Server session created
        - "session.updated": Server session configured

    Args:
        config: TranscriptionConfig instance. If None, uses defaults.
        max_reconnect_attempts: Maximum reconnection attempts on drop (default: 3).
        reconnect_delay: Base delay in seconds between reconnect attempts (default: 1.0).

    Example:
        async with TranscriptionSession(config) as session:
            session.on("transcript.completed", lambda data: print(data["transcript"]))
            await session.send_audio(audio_bytes)
            await session.commit_audio()
    """

    WEBSOCKET_URL = "wss://api.openai.com/v1/realtime"
    REALTIME_MODEL = "gpt-realtime"

    def __init__(
        self,
        config: Optional[TranscriptionConfig] = None,
        max_reconnect_attempts: int = 3,
        reconnect_delay: float = 1.0,
    ) -> None:
        """Initialize transcription session.

        Args:
            config: TranscriptionConfig instance. If None, uses defaults.
            max_reconnect_attempts: Maximum reconnection attempts (default: 3).
            reconnect_delay: Base delay in seconds between reconnect attempts (default: 1.0).
        """
        super().__init__(config or TranscriptionConfig())
        self._config: TranscriptionConfig = self._config  # Type narrowing
        self._ws: Optional[websockets.WebSocketClientProtocol] = None
        self._receive_task: Optional[asyncio.Task] = None
        self._max_reconnect_attempts = max_reconnect_attempts
        self._reconnect_delay = reconnect_delay

    @staticmethod
    def _vad_config_to_turn_detection(vad_config: Optional[VADConfig]) -> Optional[dict]:
        """Convert VADConfig to OpenAI Realtime API turn_detection format.

        Args:
            vad_config: VADConfig instance, or None.

        Returns:
            None if vad_config is None or mode is "disabled".
            Dict with turn_detection config for server_vad or semantic_vad.
        """
        if vad_config is None or vad_config.mode == "disabled":
            return None

        if vad_config.mode == "server_vad":
            return {
                "type": "server_vad",
                "threshold": vad_config.threshold,
                "prefix_padding_ms": vad_config.prefix_padding_ms,
                "silence_duration_ms": vad_config.silence_duration_ms,
            }

        if vad_config.mode == "semantic_vad":
            return {
                "type": "semantic_vad",
                "eagerness": vad_config.eagerness,
            }

        return None

    async def _connect(self) -> None:
        """Establish WebSocket connection and start receive loop.

        Steps:
            1. Set correlation ID for request tracing
            2. Build WebSocket URL with model parameter
            3. Connect with authorization headers
            4. Wait for session.created event
            5. Send session.update configuration
            6. Wait for session.updated confirmation
            7. Start background receive loop

        Raises:
            Exception: If connection or setup fails.
        """
        set_correlation_id()

        # Build URL and headers
        url = f"{self.WEBSOCKET_URL}?model={self.REALTIME_MODEL}"
        headers = {
            "Authorization": f"Bearer {self._config.api_key}",
        }

        # Connect WebSocket
        self._ws = await websockets.connect(url, additional_headers=headers)
        self._audit_log.log("websocket.connected", {"url": url})
        self._logger.info(f"WebSocket connected to {url}")

        # Wait for session.created event
        session_created_msg = await self._ws.recv()
        session_created = json.loads(session_created_msg)
        if session_created.get("type") == "session.created":
            self._emit("session.created", session_created.get("session", {}))
            self._logger.debug("Received session.created event")

        # Send session.update
        await self._send_session_update()

        # Wait for session.updated confirmation
        session_updated_msg = await self._ws.recv()
        session_updated = json.loads(session_updated_msg)
        if session_updated.get("type") == "session.updated":
            self._emit("session.updated", session_updated.get("session", {}))
            self._logger.debug("Received session.updated event")

        # Start receive loop
        self._receive_task = asyncio.create_task(self._receive_loop())
        self._audit_log.log(
            "session.configured",
            {
                "model": self._config.model,
                "language": self._config.language,
            },
        )
        self._logger.info("Transcription session configured and ready")

    async def _disconnect(self) -> None:
        """Gracefully close WebSocket connection and cancel receive task.

        Steps:
            1. Cancel receive task if running
            2. Close WebSocket connection
            3. Clean up resources
            4. Log disconnection
        """
        # Cancel receive task
        if self._receive_task is not None:
            self._receive_task.cancel()
            try:
                await self._receive_task
            except asyncio.CancelledError:
                pass  # Expected
            self._receive_task = None

        # Close WebSocket
        if self._ws is not None:
            await self._ws.close()
            self._ws = None

        self._audit_log.log("websocket.disconnected", {})
        self._logger.info("WebSocket disconnected")

    async def send_audio(self, chunk: bytes) -> None:
        """Send base64-encoded PCM16 audio chunk via input_audio_buffer.append.

        Args:
            chunk: Raw PCM16 audio bytes to send.

        Raises:
            InvalidStateTransition: If session is not in CONNECTED state.
        """
        if self._state != SessionState.CONNECTED:
            raise InvalidStateTransition(
                f"Cannot send audio in state {self._state.value}, must be CONNECTED"
            )

        # Base64 encode the audio
        audio_b64 = base64.b64encode(chunk).decode("ascii")

        # Build and send event
        event = {"type": "input_audio_buffer.append", "audio": audio_b64}
        await self._send_event(event)

        self._audit_log.log("audio.chunk_sent", {"chunk_size": len(chunk)})

    async def commit_audio(self) -> None:
        """Commit audio buffer (push-to-talk mode) via input_audio_buffer.commit.

        Signals to the server that audio input is complete and transcription should begin.

        Raises:
            InvalidStateTransition: If session is not in CONNECTED state.
        """
        if self._state != SessionState.CONNECTED:
            raise InvalidStateTransition(
                f"Cannot commit audio in state {self._state.value}, must be CONNECTED"
            )

        # Build and send event
        event = {"type": "input_audio_buffer.commit"}
        await self._send_event(event)

        self._audit_log.log("audio.buffer_committed", {})
        self._logger.debug("Audio buffer committed")

    async def update_vad(self, vad_config: VADConfig) -> None:
        """Update VAD configuration at runtime.

        Sends a session.update event with the new turn_detection configuration.
        Can be called while the session is connected to switch between VAD modes.

        Args:
            vad_config: New VAD configuration to apply.

        Raises:
            InvalidStateTransition: If session is not in CONNECTED state.
        """
        if self._state != SessionState.CONNECTED:
            raise InvalidStateTransition(
                f"Cannot update VAD in state {self._state.value}, must be CONNECTED"
            )

        turn_detection = self._vad_config_to_turn_detection(vad_config)

        event = {
            "type": "session.update",
            "session": {
                "turn_detection": turn_detection,
            },
        }

        await self._send_event(event)
        self._config.vad = vad_config

        self._audit_log.log("vad.updated", {
            "mode": vad_config.mode,
        })
        self._logger.debug(f"VAD updated to mode={vad_config.mode}")

    async def _send_event(self, event: dict) -> None:
        """Send a JSON event over the WebSocket.

        Args:
            event: Event dictionary to serialize and send.
        """
        payload = json.dumps(event)
        await self._ws.send(payload)
        self._logger.debug(f"Sent event: {event.get('type')}")

    async def _receive_loop(self) -> None:
        """Background task: receive and dispatch WebSocket messages.

        Continuously receives messages from the WebSocket and routes them
        to appropriate handlers. Handles connection drops with reconnection logic.
        """
        try:
            async for message in self._ws:
                self._handle_message(message)
        except websockets.ConnectionClosed:
            self._logger.warning("WebSocket connection closed, attempting reconnect")
            await self._reconnect()
        except asyncio.CancelledError:
            # Clean exit
            self._logger.debug("Receive loop cancelled")
            raise
        except Exception as e:
            self._logger.error(f"Error in receive loop: {e}", exc_info=True)
            self._emit("error", {"type": "receive_loop_error", "error": str(e)})

    def _handle_message(self, message: str) -> None:
        """Parse and route incoming server events to callbacks.

        Args:
            message: JSON string message from server.
        """
        try:
            event = json.loads(message)
            event_type = event.get("type")

            self._logger.debug(f"Received event: {event_type}")
            self._audit_log.log(f"event.received.{event_type}", event)

            # Route by event type (GA API event names)
            if event_type in (
                "input_audio_buffer.transcription.delta",
                "conversation.item.input_audio_transcription.delta",  # beta compat
            ):
                delta = event.get("delta", "")
                item_id = event.get("item_id")
                self._emit(
                    "transcript.delta",
                    {
                        "delta": delta,
                        "item_id": item_id,
                        "content_index": event.get("content_index", 0),
                    },
                )

            elif event_type in (
                "input_audio_buffer.transcription.completed",
                "conversation.item.input_audio_transcription.completed",  # beta compat
            ):
                transcript = event.get("transcript", "")
                item_id = event.get("item_id")
                self._emit(
                    "transcript.completed",
                    {
                        "transcript": transcript,
                        "item_id": item_id,
                        "content_index": event.get("content_index", 0),
                    },
                )

            elif event_type in (
                "input_audio_buffer.transcription.failed",
                "conversation.item.input_audio_transcription.failed",  # beta compat
            ):
                error = event.get("error", {})
                self._emit(
                    "error",
                    {
                        "type": "transcription_failed",
                        "error": error,
                        "item_id": event.get("item_id"),
                    },
                )

            elif event_type == "error":
                error_message = event.get("error", {}).get("message", "Unknown error")
                self._logger.error(f"Server error: {error_message}")
                self._emit("error", {"type": "server_error", "error": event.get("error", {})})

            elif event_type == "session.created":
                self._emit("session.created", event.get("session", {}))

            elif event_type == "session.updated":
                self._emit("session.updated", event.get("session", {}))

            elif event_type == "input_audio_buffer.committed":
                self._logger.info("Audio buffer committed confirmation received")

            else:
                # Unknown event type - log but don't error
                self._logger.debug(f"Unhandled event type: {event_type}")

        except json.JSONDecodeError as e:
            self._logger.error(f"Failed to parse message: {e}")
        except Exception as e:
            self._logger.error(f"Error handling message: {e}", exc_info=True)

    async def _send_session_update(self) -> None:
        """Send session.update event with transcription configuration.

        Uses the GA Realtime API format (session type: transcription).
        The transcription model (e.g. gpt-realtime-whisper) is specified
        inside audio.input.transcription, not in the URL model parameter.
        """
        transcription_model = self._config.model or "gpt-realtime-whisper"

        transcription_config = {
            "model": transcription_model,
        }
        if self._config.language:
            transcription_config["language"] = self._config.language

        event = {
            "type": "session.update",
            "session": {
                "type": "transcription",
                "audio": {
                    "input": {
                        "format": {
                            "type": "audio/pcm",
                            "rate": 24000,
                        },
                        "transcription": transcription_config,
                    },
                },
                "turn_detection": self._vad_config_to_turn_detection(
                    self._config.vad
                ),
            },
        }

        await self._send_event(event)
        self._logger.debug(
            f"Sent session.update (GA transcription) with model={transcription_model}, "
            f"language={self._config.language}, "
            f"vad_mode={self._config.vad.mode if self._config.vad else 'disabled'}"
        )

    async def _reconnect(self) -> None:
        """Attempt to reconnect with exponential backoff.

        Tries up to max_reconnect_attempts times with exponentially increasing
        delays. If all attempts fail, emits error callback.
        """
        for attempt in range(self._max_reconnect_attempts):
            delay = self._reconnect_delay * (2**attempt)
            self._logger.info(
                f"Reconnection attempt {attempt + 1}/{self._max_reconnect_attempts} "
                f"after {delay}s delay"
            )
            self._audit_log.log(
                "websocket.reconnect_attempt",
                {"attempt": attempt + 1, "delay": delay},
            )

            await asyncio.sleep(delay)

            try:
                # Re-establish connection (without state transitions)
                url = f"{self.WEBSOCKET_URL}?model={self.REALTIME_MODEL}"
                headers = {
                    "Authorization": f"Bearer {self._config.api_key}",
                }
                self._ws = await websockets.connect(url, additional_headers=headers)

                # Wait for session.created
                session_created_msg = await self._ws.recv()
                session_created = json.loads(session_created_msg)
                if session_created.get("type") == "session.created":
                    self._emit("session.created", session_created.get("session", {}))

                # Send session.update
                await self._send_session_update()

                # Wait for session.updated
                session_updated_msg = await self._ws.recv()
                session_updated = json.loads(session_updated_msg)
                if session_updated.get("type") == "session.updated":
                    self._emit("session.updated", session_updated.get("session", {}))

                # Restart receive loop
                self._receive_task = asyncio.create_task(self._receive_loop())

                self._audit_log.log("websocket.reconnect_success", {"attempt": attempt + 1})
                self._logger.info(f"Reconnection successful on attempt {attempt + 1}")
                return

            except Exception as e:
                self._logger.warning(
                    f"Reconnection attempt {attempt + 1} failed: {e}"
                )
                if attempt == self._max_reconnect_attempts - 1:
                    # All attempts failed
                    self._audit_log.log(
                        "websocket.reconnect_failed",
                        {"total_attempts": self._max_reconnect_attempts},
                    )
                    self._logger.error(
                        f"All {self._max_reconnect_attempts} reconnection attempts failed"
                    )
                    self._emit(
                        "error",
                        {
                            "type": "reconnect_failed",
                            "error": f"Failed after {self._max_reconnect_attempts} attempts",
                        },
                    )
