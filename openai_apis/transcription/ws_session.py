"""WebSocket-based realtime transcription session.

Async WebSocket client for the OpenAI Realtime API transcription endpoint.
Inherits from BaseSession for lifecycle management, state machine, and audit logging.

Connection flow (ephemeral token):
    1. REST: POST /v1/realtime/transcription_sessions → client_secret
    2. WebSocket: connect to /v1/realtime with client_secret as Bearer token
    3. Session is pre-configured as transcription (no session.update needed
       unless reconfiguring mid-session)

Note: The transcription session REST endpoint may not be available on all
accounts/API versions. If it returns 404, a ConnectionError is raised with
clear instructions.
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

    Creates a dedicated transcription session using the ephemeral token flow:
    REST creates the session → returns a short-lived client_secret →
    WebSocket connects with that token.

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
    REST_BASE_URL = "https://api.openai.com/v1/realtime"

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

    # ------------------------------------------------------------------
    # VAD helpers
    # ------------------------------------------------------------------

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

    # ------------------------------------------------------------------
    # Connection lifecycle
    # ------------------------------------------------------------------

    async def _connect(self) -> None:
        """Establish WebSocket connection via ephemeral token flow.

        Steps:
            1. Set correlation ID for request tracing
            2. Create transcription session via REST (get ephemeral token)
            3. Connect WebSocket with ephemeral token
            4. Wait for session.created event
            5. Send session.update if needed (reconfigure)
            6. Start background receive loop

        Raises:
            ConnectionError: If REST endpoint is unavailable (404).
            Exception: If connection or setup fails.
        """
        set_correlation_id()

        transcription_model = self._config.model or "gpt-realtime-whisper"

        # Step 1: Create transcription session via REST → get ephemeral token
        client_secret = await self._create_transcription_session(
            transcription_model)

        # Step 2: Connect WebSocket with ephemeral token
        url = f"{self.WEBSOCKET_URL}?model={transcription_model}"
        headers = {
            "Authorization": f"Bearer {client_secret}",
        }

        self._ws = await websockets.connect(url, additional_headers=headers)
        self._audit_log.log("websocket.connected", {
            "url": url, "model": transcription_model,
        })
        self._logger.info(f"WebSocket connected to {url}")

        # Step 3: Wait for first server message
        first_msg = await self._ws.recv()
        first_event = json.loads(first_msg)

        if first_event.get("type") == "session.created":
            self._emit("session.created", first_event.get("session", {}))
            self._logger.debug("Received session.created event")
        elif first_event.get("type") == "error":
            error = first_event.get("error", {})
            raise ConnectionError(
                f"Server error on connect: {error.get('message', error)}"
            )
        else:
            self._logger.warning(
                f"Unexpected first event: {first_event.get('type')}"
            )

        # Step 4: Send session.update to (re)configure transcription params
        await self._send_session_update()

        # Wait for session.updated confirmation
        updated_msg = await self._ws.recv()
        updated_event = json.loads(updated_msg)
        if updated_event.get("type") == "session.updated":
            self._emit("session.updated", updated_event.get("session", {}))
            self._logger.debug("Received session.updated event")
        elif updated_event.get("type") == "error":
            error = updated_event.get("error", {})
            self._logger.warning(f"Session update error: {error}")
            self._emit("error", {"type": "session_update_error", "error": error})

        # Step 5: Start receive loop
        self._receive_task = asyncio.create_task(self._receive_loop())
        self._audit_log.log("session.configured", {
            "model": transcription_model,
            "language": self._config.language,
        })
        self._logger.info("Transcription session configured and ready")

    async def _create_transcription_session(self, model: str) -> str:
        """Create transcription session via REST API → get ephemeral client_secret.

        Args:
            model: Transcription model (e.g. gpt-realtime-whisper).

        Returns:
            Ephemeral client_secret token for WebSocket auth.

        Raises:
            ConnectionError: If the endpoint is unavailable.
        """
        try:
            import httpx
        except ImportError:
            raise ImportError(
                "httpx is required for transcription sessions. "
                "Install with: pip install httpx"
            )

        url = f"{self.REST_BASE_URL}/transcription_sessions"

        body = {
            "input_audio_format": "pcm16",
            "input_audio_transcription": {
                "model": model,
            },
        }

        if self._config.language:
            body["input_audio_transcription"]["language"] = self._config.language

        turn_detection = self._vad_config_to_turn_detection(self._config.vad)
        if turn_detection is not None:
            body["turn_detection"] = turn_detection

        headers = {
            "Authorization": f"Bearer {self._config.api_key}",
            "Content-Type": "application/json",
        }

        self._logger.debug(
            f"Creating transcription session via REST: model={model}")

        async with httpx.AsyncClient() as client:
            resp = await client.post(url, headers=headers, json=body, timeout=10)

        if resp.status_code == 404:
            raise ConnectionError(
                "Transcription session endpoint not available "
                f"(POST {url} returned 404). "
                "This may require a newer API version or account enablement. "
                "For non-streaming transcription, use TranscriptionAPI instead."
            )

        if resp.status_code != 200:
            error_detail = resp.text[:500]
            raise ConnectionError(
                f"Failed to create transcription session: "
                f"HTTP {resp.status_code}: {error_detail}"
            )

        data = resp.json()
        client_secret = data.get("client_secret", {}).get("value")
        if not client_secret:
            raise ConnectionError(
                "Transcription session response missing client_secret. "
                f"Response: {resp.text[:300]}"
            )

        self._audit_log.log("transcription_session.created", {
            "model": model,
            "expires_at": data.get("client_secret", {}).get("expires_at"),
        })
        self._logger.info(
            f"Transcription session created, got ephemeral token "
            f"(expires_at={data.get('client_secret', {}).get('expires_at')})"
        )

        return client_secret

    async def _disconnect(self) -> None:
        """Gracefully close WebSocket connection and cancel receive task."""
        if self._receive_task is not None:
            self._receive_task.cancel()
            try:
                await self._receive_task
            except asyncio.CancelledError:
                pass
            self._receive_task = None

        if self._ws is not None:
            await self._ws.close()
            self._ws = None

        self._audit_log.log("websocket.disconnected", {})
        self._logger.info("WebSocket disconnected")

    # ------------------------------------------------------------------
    # Audio send/commit
    # ------------------------------------------------------------------

    async def send_audio(self, chunk: bytes) -> None:
        """Send base64-encoded PCM16 audio chunk via input_audio_buffer.append.

        Args:
            chunk: Raw PCM16 audio bytes to send.

        Raises:
            InvalidStateTransition: If session is not in CONNECTED state.
        """
        if self._state != SessionState.CONNECTED:
            raise InvalidStateTransition(
                f"Cannot send audio in state {self._state.value}, "
                f"must be CONNECTED"
            )

        audio_b64 = base64.b64encode(chunk).decode("ascii")
        event = {"type": "input_audio_buffer.append", "audio": audio_b64}
        await self._send_event(event)
        self._audit_log.log("audio.chunk_sent", {"chunk_size": len(chunk)})

    async def commit_audio(self) -> None:
        """Commit audio buffer via input_audio_buffer.commit.

        Signals to the server that audio input is complete and
        transcription should begin. Required when turn_detection is disabled
        or set to null (push-to-talk mode).

        Raises:
            InvalidStateTransition: If session is not in CONNECTED state.
        """
        if self._state != SessionState.CONNECTED:
            raise InvalidStateTransition(
                f"Cannot commit audio in state {self._state.value}, "
                f"must be CONNECTED"
            )

        event = {"type": "input_audio_buffer.commit"}
        await self._send_event(event)
        self._audit_log.log("audio.buffer_committed", {})
        self._logger.debug("Audio buffer committed")

    # ------------------------------------------------------------------
    # Runtime VAD update
    # ------------------------------------------------------------------

    async def update_vad(self, vad_config: VADConfig) -> None:
        """Update VAD configuration at runtime.

        Sends a session.update event with the new turn_detection config.
        Per GA docs, turn_detection sits inside audio.input.

        Args:
            vad_config: New VAD configuration to apply.

        Raises:
            InvalidStateTransition: If session is not in CONNECTED state.
        """
        if self._state != SessionState.CONNECTED:
            raise InvalidStateTransition(
                f"Cannot update VAD in state {self._state.value}, "
                f"must be CONNECTED"
            )

        turn_detection = self._vad_config_to_turn_detection(vad_config)

        event = {
            "type": "session.update",
            "session": {
                "audio": {
                    "input": {
                        "turn_detection": turn_detection,
                    },
                },
            },
        }

        await self._send_event(event)
        self._config.vad = vad_config
        self._audit_log.log("vad.updated", {"mode": vad_config.mode})
        self._logger.debug(f"VAD updated to mode={vad_config.mode}")

    # ------------------------------------------------------------------
    # Internal: send/receive
    # ------------------------------------------------------------------

    async def _send_event(self, event: dict) -> None:
        """Send a JSON event over the WebSocket."""
        payload = json.dumps(event)
        await self._ws.send(payload)
        self._logger.debug(f"Sent event: {event.get('type')}")

    async def _receive_loop(self) -> None:
        """Background task: receive and dispatch WebSocket messages."""
        try:
            async for message in self._ws:
                self._handle_message(message)
        except websockets.ConnectionClosed:
            self._logger.warning(
                "WebSocket connection closed, attempting reconnect")
            await self._reconnect()
        except asyncio.CancelledError:
            self._logger.debug("Receive loop cancelled")
            raise
        except Exception as e:
            self._logger.error(f"Error in receive loop: {e}", exc_info=True)
            self._emit("error", {
                "type": "receive_loop_error", "error": str(e),
            })

    def _handle_message(self, message: str) -> None:
        """Parse and route incoming server events to callbacks."""
        try:
            event = json.loads(message)
            event_type = event.get("type")

            self._logger.debug(f"Received event: {event_type}")
            self._audit_log.log(f"event.received.{event_type}", event)

            # Transcript delta (streaming partial text)
            if event_type == (
                "conversation.item.input_audio_transcription.delta"
            ):
                self._emit("transcript.delta", {
                    "delta": event.get("delta", ""),
                    "item_id": event.get("item_id"),
                    "content_index": event.get("content_index", 0),
                })

            # Transcript completed (final text for a committed item)
            elif event_type == (
                "conversation.item.input_audio_transcription.completed"
            ):
                self._emit("transcript.completed", {
                    "transcript": event.get("transcript", ""),
                    "item_id": event.get("item_id"),
                    "content_index": event.get("content_index", 0),
                })

            # Transcript failed
            elif event_type == (
                "conversation.item.input_audio_transcription.failed"
            ):
                self._emit("error", {
                    "type": "transcription_failed",
                    "error": event.get("error", {}),
                    "item_id": event.get("item_id"),
                })

            # Server error
            elif event_type == "error":
                error_message = event.get("error", {}).get(
                    "message", "Unknown error")
                self._logger.error(f"Server error: {error_message}")
                self._emit("error", {
                    "type": "server_error",
                    "error": event.get("error", {}),
                })

            # Session lifecycle
            elif event_type == "session.created":
                self._emit("session.created", event.get("session", {}))
            elif event_type == "session.updated":
                self._emit("session.updated", event.get("session", {}))

            # Audio buffer confirmation
            elif event_type == "input_audio_buffer.committed":
                self._logger.info(
                    "Audio buffer committed confirmation received")

            # Speech started/stopped (VAD events)
            elif event_type == "input_audio_buffer.speech_started":
                self._logger.debug("Speech started (VAD)")
            elif event_type == "input_audio_buffer.speech_stopped":
                self._logger.debug("Speech stopped (VAD)")

            else:
                self._logger.debug(f"Unhandled event type: {event_type}")

        except json.JSONDecodeError as e:
            self._logger.error(f"Failed to parse message: {e}")
        except Exception as e:
            self._logger.error(
                f"Error handling message: {e}", exc_info=True)

    # ------------------------------------------------------------------
    # Session configuration
    # ------------------------------------------------------------------

    async def _send_session_update(self) -> None:
        """Send session.update event with transcription configuration.

        Uses the GA Realtime API format for transcription sessions.
        Per the official docs:
            session.type = "transcription"
            session.audio.input.format = {type, rate}
            session.audio.input.transcription = {model, language, delay, ...}
            session.audio.input.turn_detection = {...} (optional)

        Note: gpt-realtime-whisper does NOT support turn_detection; omit it
        or set to null. For push-to-talk, call commit_audio() manually.
        """
        transcription_model = self._config.model or "gpt-realtime-whisper"

        transcription_config = {
            "model": transcription_model,
        }
        if self._config.language:
            transcription_config["language"] = self._config.language

        # Build audio.input block
        audio_input = {
            "format": {
                "type": "audio/pcm",
                "rate": 24000,
            },
            "transcription": transcription_config,
        }

        # turn_detection inside audio.input (per GA docs)
        # Note: gpt-realtime-whisper does NOT support turn_detection
        turn_detection = self._vad_config_to_turn_detection(self._config.vad)
        if turn_detection is not None:
            audio_input["turn_detection"] = turn_detection

        event = {
            "type": "session.update",
            "session": {
                "type": "transcription",
                "audio": {
                    "input": audio_input,
                },
            },
        }

        await self._send_event(event)
        self._logger.debug(
            f"Sent session.update (transcription) "
            f"model={transcription_model}, "
            f"language={self._config.language}, "
            f"vad={self._config.vad.mode if self._config.vad else 'disabled'}"
        )

    # ------------------------------------------------------------------
    # Reconnection
    # ------------------------------------------------------------------

    async def _reconnect(self) -> None:
        """Attempt to reconnect with exponential backoff."""
        for attempt in range(self._max_reconnect_attempts):
            delay = self._reconnect_delay * (2 ** attempt)
            self._logger.info(
                f"Reconnection attempt {attempt + 1}/"
                f"{self._max_reconnect_attempts} after {delay}s delay"
            )
            self._audit_log.log("websocket.reconnect_attempt", {
                "attempt": attempt + 1, "delay": delay,
            })

            await asyncio.sleep(delay)

            try:
                # Re-create transcription session (new ephemeral token)
                model = self._config.model or "gpt-realtime-whisper"
                client_secret = await self._create_transcription_session(model)

                url = f"{self.WEBSOCKET_URL}?model={model}"
                headers = {
                    "Authorization": f"Bearer {client_secret}",
                }
                self._ws = await websockets.connect(
                    url, additional_headers=headers)

                # Wait for session.created
                msg = await self._ws.recv()
                event = json.loads(msg)
                if event.get("type") == "session.created":
                    self._emit(
                        "session.created", event.get("session", {}))

                # Send session.update
                await self._send_session_update()

                # Wait for session.updated
                msg = await self._ws.recv()
                event = json.loads(msg)
                if event.get("type") == "session.updated":
                    self._emit(
                        "session.updated", event.get("session", {}))

                # Restart receive loop
                self._receive_task = asyncio.create_task(
                    self._receive_loop())

                self._audit_log.log("websocket.reconnect_success", {
                    "attempt": attempt + 1,
                })
                self._logger.info(
                    f"Reconnection successful on attempt {attempt + 1}")
                return

            except Exception as e:
                self._logger.warning(
                    f"Reconnection attempt {attempt + 1} failed: {e}"
                )
                if attempt == self._max_reconnect_attempts - 1:
                    self._audit_log.log("websocket.reconnect_failed", {
                        "total_attempts": self._max_reconnect_attempts,
                    })
                    self._logger.error(
                        f"All {self._max_reconnect_attempts} "
                        f"reconnection attempts failed"
                    )
                    self._emit("error", {
                        "type": "reconnect_failed",
                        "error": (
                            f"Failed after "
                            f"{self._max_reconnect_attempts} attempts"
                        ),
                    })
