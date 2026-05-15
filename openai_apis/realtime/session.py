#!/usr/bin/env python3
"""
Realtime Voice API Module - Async WebSocket Session

This module provides a clean async API for real-time voice interactions using
OpenAI's Realtime API via WebSockets. Pure protocol client following BaseSession
architecture pattern - audio I/O (mic/speaker) belongs in examples.

Features:
- Async WebSocket connection to OpenAI Realtime API
- BaseSession lifecycle management and audit logging
- Event-driven callbacks for all realtime events
- Push-to-talk audio streaming support
- Session configuration and state management

Requirements:
- Requires websockets library
- Install with: pip install websockets

Example usage:
    from openai_apis.realtime import RealtimeSession, RealtimeConfig

    async def on_transcript(data):
        print(f"User said: {data['transcript']}")

    async with RealtimeSession() as session:
        session.on("transcript.input", on_transcript)
        await session.send_audio(audio_chunk)
        await session.commit_audio()
        await session.create_response()
"""

import json
import base64
import time
import asyncio
from typing import Optional, Dict, Any

try:
    import websockets
except ImportError:
    websockets = None

from openai_apis._session import BaseSession, SessionState, InvalidStateTransition
from openai_apis._logging import get_logger, set_correlation_id
from openai_apis.realtime.config import RealtimeConfig
from openai_apis.realtime.tools import ToolRegistry
from openai_apis.realtime.events import (
    TranscriptDelta, TranscriptCompleted, ErrorEvent,
    AudioDelta, AudioDone, ConversationItem,
)


class RealtimeAgentState:
    """
    State manager for realtime agent session.

    Stores tool outputs and other state information that can be
    passed to the session via session.update events.
    """

    def __init__(self):
        """Initialize empty state."""
        self.state: Dict[str, Any] = {}

    def set(self, key: str, value: Any) -> None:
        """Set a state value."""
        self.state[key] = value

    def get(self, key: str, default: Any = None) -> Any:
        """Get a state value."""
        return self.state.get(key, default)

    def as_dict(self) -> Dict[str, Any]:
        """Get state as dictionary."""
        return dict(self.state)

    def clear(self) -> None:
        """Clear all state."""
        self.state.clear()


class RealtimeSession(BaseSession):
    """Async WebSocket client for OpenAI Realtime API conversation sessions.

    Inherits lifecycle management, state machine, and per-session audit logging
    from BaseSession. Uses async context manager pattern.

    Callback events (registered via session.on()):
        - "audio.delta": Output audio chunk (AudioDelta with audio_bytes, item_id, response_id)
        - "audio.done": Output audio stream complete (AudioDone with item_id, response_id)
        - "transcript.input": Input transcription (TranscriptCompleted)
        - "transcript.output": Output transcription (TranscriptCompleted)
        - "transcript.delta": Partial transcription (TranscriptDelta)
        - "tool.call": Tool/function call request from model (dict)
        - "response.done": Response generation complete (dict)
        - "error": Error from server (ErrorEvent)
        - "session.created": Server session created (dict)
        - "session.updated": Server session configured (dict)
    """

    WEBSOCKET_URL = "wss://api.openai.com/v1/realtime"

    def __init__(
        self,
        config: Optional[RealtimeConfig] = None,
        state: Optional[RealtimeAgentState] = None,
        max_reconnect_attempts: int = 3,
        reconnect_delay: float = 1.0,
    ) -> None:
        """Initialize RealtimeSession.

        Args:
            config: Realtime configuration settings.
            state: RealtimeAgentState instance for custom state.
            max_reconnect_attempts: Maximum reconnection attempts.
            reconnect_delay: Base delay for exponential backoff (seconds).
        """
        if websockets is None:
            raise ImportError(
                "websockets library required for RealtimeSession. "
                "Install with: pip install websockets"
            )
        super().__init__(config or RealtimeConfig())
        self._config: RealtimeConfig = self._config  # type narrowing
        self._state_manager: RealtimeAgentState = state or RealtimeAgentState()
        self._ws: Optional[Any] = None  # websockets.WebSocketClientProtocol
        self._receive_task: Optional[asyncio.Task] = None
        self._max_reconnect_attempts = max_reconnect_attempts
        self._reconnect_delay = reconnect_delay
        # Extract ToolRegistry if provided via config
        self._tool_registry: Optional[ToolRegistry] = None
        if isinstance(self._config.tools, ToolRegistry):
            self._tool_registry = self._config.tools
        # Delta accumulator: maps item_id -> {"accumulated": str, "start_time": float}
        self._delta_accumulator: Dict[str, Dict[str, Any]] = {}
        # Audio output accumulator: maps item_id -> {"chunk_count": int, "total_bytes": int, "start_time": float}
        self._audio_output_accumulator: Dict[str, Dict[str, Any]] = {}
        # Input audio counters for audit
        self._input_audio_chunks: int = 0
        self._input_audio_bytes: int = 0
        # Conversation history tracking
        self._conversation_history: list[ConversationItem] = []
        # Track current in-progress response for interruption
        self._current_response_id: Optional[str] = None

    @property
    def agent_state(self) -> RealtimeAgentState:
        """Get the per-session agent state manager."""
        return self._state_manager

    async def _connect(self) -> None:
        """Establish WebSocket connection and configure session.

        Called by BaseSession during __aenter__.
        Transitions: CONNECTING → CONNECTED
        """
        set_correlation_id()
        url = f"{self.WEBSOCKET_URL}?model={self._config.model}"
        headers = {
            "Authorization": f"Bearer {self._config.api_key}",
            "OpenAI-Beta": "realtime=v1",
        }
        self._ws = await websockets.connect(url, additional_headers=headers)
        self._audit_log.log("websocket.connected", {"url": url})

        # Wait for session.created
        msg = await self._ws.recv()
        event = json.loads(msg)
        if event.get("type") == "session.created":
            self._emit("session.created", event.get("session", {}))

        # Send session.update configuration
        await self._send_session_update()

        # Wait for session.updated
        msg = await self._ws.recv()
        event = json.loads(msg)
        if event.get("type") == "session.updated":
            self._emit("session.updated", event.get("session", {}))

        # Start background receive loop
        self._receive_task = asyncio.create_task(self._receive_loop())
        self._audit_log.log("session.configured", {
            "model": self._config.model,
            "language": self._config.language,
        })

    async def _disconnect(self) -> None:
        """Tear down WebSocket connection.

        Called by BaseSession during __aexit__.
        Cancels receive task and closes WebSocket.
        """
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

    async def send_audio(self, chunk: bytes) -> None:
        """Send base64-encoded PCM16 audio chunk.

        Args:
            chunk: Raw PCM16 audio bytes.

        Raises:
            InvalidStateTransition: If not in CONNECTED state.

        Audit Logging:
            Logs 'audio.chunk_sent' event with chunk_size, total_chunks, and
            total_bytes (cumulative since last commit).
        """
        self._assert_connected("send_audio")
        audio_b64 = base64.b64encode(chunk).decode("ascii")
        await self._send_event({"type": "input_audio_buffer.append", "audio": audio_b64})
        self._input_audio_chunks += 1
        self._input_audio_bytes += len(chunk)
        self._audit_log.log("audio.chunk_sent", {
            "chunk_size": len(chunk),
            "total_chunks": self._input_audio_chunks,
            "total_bytes": self._input_audio_bytes,
        })

    async def commit_audio(self) -> None:
        """Commit audio buffer (push-to-talk).

        Signals end of user audio input, creating a conversation item.
        Resets input audio counters for next turn.

        Raises:
            InvalidStateTransition: If not in CONNECTED state.

        Audit Logging:
            Logs 'audio.buffer_committed' event with total_chunks, total_bytes,
            and audio_duration_s calculated from accumulated data.
        """
        self._assert_connected("commit_audio")
        await self._send_event({"type": "input_audio_buffer.commit"})
        sample_rate = self._config.audio_format.sample_rate
        channels = self._config.audio_format.channels
        bytes_per_sample = 2  # PCM16
        audio_duration_s = self._input_audio_bytes / (sample_rate * channels * bytes_per_sample)
        self._audit_log.log("audio.buffer_committed", {
            "total_chunks": self._input_audio_chunks,
            "total_bytes": self._input_audio_bytes,
            "audio_duration_s": round(audio_duration_s, 3),
        })
        # Reset input counters after commit
        self._input_audio_chunks = 0
        self._input_audio_bytes = 0

    async def create_response(self) -> None:
        """Trigger response generation from the model.

        Raises:
            InvalidStateTransition: If not in CONNECTED state.
        """
        self._assert_connected("create_response")
        event = {
            "type": "response.create",
            "response": {
                "modalities": self._config.modalities,
                "voice": self._config.voice,
                "output_audio_format": "pcm16",
                "tool_choice": "auto",
                "temperature": self._config.temperature,
                "max_output_tokens": 1024,
            },
        }
        await self._send_event(event)
        self._audit_log.log("response.create_sent", {})

    async def cancel_response(self) -> None:
        """Cancel the current in-progress response (barge-in).

        Sends a `response.cancel` event to the server. The server will
        stop generating audio/text and emit `response.done` with status "cancelled".

        Raises:
            InvalidStateTransition: If not in CONNECTED state.

        Audit Logging:
            Logs 'response.cancel_sent' event with response_id if available.
        """
        self._assert_connected("cancel_response")
        event: dict[str, Any] = {"type": "response.cancel"}
        await self._send_event(event)
        self._audit_log.log("response.cancel_sent", {
            "response_id": self._current_response_id,
        })

    async def update_session(self, **kwargs) -> None:
        """Update session configuration at runtime.

        Args:
            **kwargs: Session config fields to update (e.g., voice="alloy",
                      temperature=0.9, instructions="...").

        Raises:
            InvalidStateTransition: If not in CONNECTED state.
        """
        self._assert_connected("update_session")
        session_update = self._create_session_update_payload()
        # Merge kwargs into session payload
        session_update["session"].update(kwargs)
        await self._send_event(session_update)
        self._audit_log.log("session.update_sent", {"fields": list(kwargs.keys())})

    async def send_tool_result(self, call_id: str, result: str) -> None:
        """Send tool call result back to the model.

        Args:
            call_id: The tool call ID from the "tool.call" event.
            result: JSON string result of the tool invocation.

        Raises:
            InvalidStateTransition: If not in CONNECTED state.
        """
        self._assert_connected("send_tool_result")
        event = {
            "type": "conversation.item.create",
            "item": {
                "type": "function_call_output",
                "call_id": call_id,
                "output": result,
            },
        }
        await self._send_event(event)
        self._audit_log.log("tool.result_sent", {"call_id": call_id})

    def get_conversation_history(self) -> list[dict[str, str]]:
        """Get conversation history as a list of role/content dicts.

        Returns:
            List of dicts with "role" and "content" keys, e.g.:
            [{"role": "user", "content": "Hello"}, {"role": "assistant", "content": "Hi!"}]
        """
        return [
            {"role": item.role, "content": item.content}
            for item in self._conversation_history
        ]

    async def clear_conversation(self) -> None:
        """Clear the in-memory conversation history.

        Resets the tracked conversation items list to empty.

        Audit Logging:
            Logs 'conversation.cleared' event with item count before clearing.
        """
        count = len(self._conversation_history)
        self._conversation_history.clear()
        self._audit_log.log("conversation.cleared", {"items_cleared": count})

    async def _execute_tool(self, call_id: str, name: str, arguments: str) -> None:
        """Execute a tool from the registry, send result, and trigger response.

        Args:
            call_id: The tool call ID.
            name: The tool name.
            arguments: JSON string of arguments.
        """
        self._audit_log.log("tool.execution.started", {
            "call_id": call_id,
            "name": name,
            "arguments": arguments,
        })
        start_time = time.time()
        try:
            result = await self._tool_registry.execute(name, arguments)
            duration_ms = (time.time() - start_time) * 1000
            self._audit_log.log("tool.execution.completed", {
                "call_id": call_id,
                "name": name,
                "result": result,
            }, duration_ms=duration_ms)
            await self.send_tool_result(call_id, result)
            await self.create_response()
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            self._audit_log.log("tool.execution.failed", {
                "call_id": call_id,
                "name": name,
                "error": str(e),
            }, duration_ms=duration_ms)
            self._logger.error(f"Tool execution failed: {name}: {e}", exc_info=True)
            # Send error result so the model knows the tool failed
            error_result = json.dumps({"error": str(e)})
            await self.send_tool_result(call_id, error_result)
            await self.create_response()

    def _assert_connected(self, operation: str) -> None:
        """Verify session is in CONNECTED state.

        Args:
            operation: Name of operation being attempted.

        Raises:
            InvalidStateTransition: If not in CONNECTED state.
        """
        if self._state != SessionState.CONNECTED:
            raise InvalidStateTransition(
                f"Cannot {operation} in state {self._state.value}, must be CONNECTED"
            )

    async def _send_event(self, event: dict) -> None:
        """Send event to WebSocket.

        Args:
            event: Event dictionary to send.
        """
        payload = json.dumps(event)
        await self._ws.send(payload)
        self._logger.debug(f"Sent event: {event.get('type')}")

    def _create_session_update_payload(self) -> Dict[str, Any]:
        """Create session.update event from config.

        Returns:
            Dict containing session.update event structure.
        """
        return self._config.to_session_update()

    async def _send_session_update(self) -> None:
        """Send session.update event during connection setup."""
        await self._send_event(self._create_session_update_payload())

    async def _receive_loop(self) -> None:
        """Background receive loop for WebSocket messages.

        Handles reconnection on connection close.
        Runs until cancelled or max reconnect attempts exhausted.
        """
        try:
            async for message in self._ws:
                self._handle_message(message)
        except websockets.ConnectionClosed:
            self._logger.warning("WebSocket connection closed")
            await self._reconnect()
        except asyncio.CancelledError:
            raise
        except Exception as e:
            self._logger.error(f"Receive loop error: {e}", exc_info=True)
            self._emit("error", {"type": "receive_loop_error", "error": str(e)})

    def _handle_message(self, message: str) -> None:
        """Handle incoming WebSocket message.

        Routes events to appropriate handlers and emits callbacks.

        Args:
            message: Raw WebSocket message (JSON string).
        """
        try:
            event = json.loads(message)
        except json.JSONDecodeError:
            self._logger.warning("Non-JSON message received")
            return

        event_type = event.get("type")
        self._logger.debug(f"Received: {event_type}")
        self._audit_log.log(f"event.received.{event_type}", event)

        # Input transcription
        if event_type == "conversation.item.input_audio_transcription.delta":
            item_id = event.get("item_id", "")
            delta_text = event.get("delta", "")
            accumulated = self._accumulate_delta(item_id, delta_text)
            self._emit("transcript.delta", TranscriptDelta(
                item_id=item_id, delta=delta_text, accumulated=accumulated,
            ))

        elif event_type == "conversation.item.input_audio_transcription.completed":
            item_id = event.get("item_id", "")
            transcript = event.get("transcript", "")
            duration_ms = self._complete_accumulation(item_id)
            self._emit("transcript.input", TranscriptCompleted(
                item_id=item_id, transcript=transcript, duration_ms=duration_ms,
            ))

        # Output transcription (model speech as text)
        elif event_type == "response.audio_transcript.delta":
            item_id = event.get("item_id", "")
            delta_text = event.get("delta", "")
            accumulated = self._accumulate_delta(item_id, delta_text)
            self._emit("transcript.delta", TranscriptDelta(
                item_id=item_id, delta=delta_text, accumulated=accumulated,
            ))

        elif event_type == "response.audio_transcript.done":
            item_id = event.get("item_id", "")
            transcript = event.get("transcript", "")
            duration_ms = self._complete_accumulation(item_id)
            self._emit("transcript.output", TranscriptCompleted(
                item_id=item_id, transcript=transcript, duration_ms=duration_ms,
            ))

        # Audio response
        elif event_type == "response.audio.delta":
            audio_b64 = event.get("delta", "")
            audio_bytes = base64.b64decode(audio_b64)
            item_id = event.get("item_id", "")
            response_id = event.get("response_id", "")
            # Accumulate for audit
            if item_id not in self._audio_output_accumulator:
                self._audio_output_accumulator[item_id] = {
                    "chunk_count": 0,
                    "total_bytes": 0,
                    "start_time": time.time(),
                }
            self._audio_output_accumulator[item_id]["chunk_count"] += 1
            self._audio_output_accumulator[item_id]["total_bytes"] += len(audio_bytes)
            self._emit("audio.delta", AudioDelta(
                audio_bytes=audio_bytes,
                item_id=item_id,
                response_id=response_id,
            ))

        elif event_type == "response.audio.done":
            item_id = event.get("item_id", "")
            response_id = event.get("response_id", "")
            # Audit log with accumulated audio stats
            acc = self._audio_output_accumulator.pop(item_id, None)
            if acc is not None:
                duration_ms = (time.time() - acc["start_time"]) * 1000
                sample_rate = self._config.audio_format.sample_rate
                channels = self._config.audio_format.channels
                bytes_per_sample = 2  # PCM16 = 2 bytes per sample
                audio_duration_s = acc["total_bytes"] / (sample_rate * channels * bytes_per_sample)
                self._audit_log.log("audio.output_completed", {
                    "item_id": item_id,
                    "response_id": response_id,
                    "chunk_count": acc["chunk_count"],
                    "total_bytes": acc["total_bytes"],
                    "audio_duration_s": round(audio_duration_s, 3),
                    "streaming_duration_ms": round(duration_ms, 1),
                })
            self._emit("audio.done", AudioDone(
                item_id=item_id,
                response_id=response_id,
            ))

        # Tool calls
        elif event_type == "response.function_call_arguments.done":
            tool_data = {
                "call_id": event.get("call_id", ""),
                "name": event.get("name", ""),
                "arguments": event.get("arguments", ""),
            }
            self._emit("tool.call", tool_data)

            # Auto-execute if ToolRegistry is available
            if self._tool_registry is not None:
                asyncio.create_task(
                    self._execute_tool(
                        tool_data["call_id"],
                        tool_data["name"],
                        tool_data["arguments"],
                    )
                )

        # Response lifecycle
        elif event_type == "response.done":
            self._emit("response.done", {"response_id": event.get("response_id", "")})

        # Errors
        elif event_type == "error":
            error_data = event.get("error", {})
            error_event = ErrorEvent(
                code=error_data.get("code", "unknown"),
                message=error_data.get("message", "Unknown error"),
            )
            self._emit("error", error_event)

        # Session events (during receive loop, after initial handshake)
        elif event_type == "session.created":
            self._emit("session.created", event.get("session", {}))
        elif event_type == "session.updated":
            self._emit("session.updated", event.get("session", {}))
        # Other events logged but not dispatched
        else:
            self._logger.debug(f"Unhandled event: {event_type}")

    def _accumulate_delta(self, item_id: str, delta: str) -> str:
        """Accumulate delta text for an item_id.

        Args:
            item_id: Item identifier.
            delta: Text fragment to accumulate.

        Returns:
            Accumulated text so far for this item_id.
        """
        if item_id not in self._delta_accumulator:
            self._delta_accumulator[item_id] = {
                "accumulated": "",
                "start_time": time.time(),
            }
        self._delta_accumulator[item_id]["accumulated"] += delta
        return self._delta_accumulator[item_id]["accumulated"]

    def _complete_accumulation(self, item_id: str) -> float:
        """Complete accumulation for an item_id.

        Args:
            item_id: Item identifier.

        Returns:
            Duration in milliseconds since first delta for this item_id.
        """
        entry = self._delta_accumulator.pop(item_id, None)
        if entry is None:
            return 0.0
        return (time.time() - entry["start_time"]) * 1000

    async def _reconnect(self) -> None:
        """Attempt to reconnect with exponential backoff.

        Tries up to max_reconnect_attempts times with exponential delay.
        Emits error event if all attempts fail.
        """
        for attempt in range(self._max_reconnect_attempts):
            delay = self._reconnect_delay * (2 ** attempt)
            self._logger.info(
                f"Reconnect attempt {attempt + 1}/{self._max_reconnect_attempts} in {delay}s"
            )
            self._audit_log.log("websocket.reconnect_attempt", {
                "attempt": attempt + 1, "delay": delay,
            })
            await asyncio.sleep(delay)
            try:
                url = f"{self.WEBSOCKET_URL}?model={self._config.model}"
                headers = {
                    "Authorization": f"Bearer {self._config.api_key}",
                    "OpenAI-Beta": "realtime=v1",
                }
                self._ws = await websockets.connect(url, additional_headers=headers)

                msg = await self._ws.recv()
                event = json.loads(msg)
                if event.get("type") == "session.created":
                    self._emit("session.created", event.get("session", {}))

                await self._send_session_update()

                msg = await self._ws.recv()
                event = json.loads(msg)
                if event.get("type") == "session.updated":
                    self._emit("session.updated", event.get("session", {}))

                self._receive_task = asyncio.create_task(self._receive_loop())
                self._audit_log.log("websocket.reconnect_success", {"attempt": attempt + 1})
                return
            except Exception as e:
                self._logger.warning(f"Reconnect attempt {attempt + 1} failed: {e}")
                if attempt == self._max_reconnect_attempts - 1:
                    self._audit_log.log("websocket.reconnect_failed", {
                        "total_attempts": self._max_reconnect_attempts,
                    })
                    self._emit("error", {
                        "type": "reconnect_failed",
                        "error": f"Failed after {self._max_reconnect_attempts} attempts",
                    })
