#!/usr/bin/env python3
"""
Realtime Voice API Module - WebSocket Realtime Session

This module provides a clean API for real-time voice interactions using
OpenAI's Realtime API via WebSockets. Supports push-to-talk audio streaming,
custom state management, and event-driven callbacks.

Features:
- Direct WebSocket connection to OpenAI Realtime API
- Push-to-talk audio recording and streaming
- Real-time audio playback with speaker queue
- Custom state management with RealtimeAgentState
- Event callbacks for all realtime events
- Session configuration and lifecycle management

Requirements:
- Requires websocket-client, numpy, and sounddevice for audio I/O
- Install with: pip install openai-apis[audio]

Example usage:
    from openai_apis.realtime import RealtimeVoiceAPI, RealtimeConfig

    def on_transcription(text):
        print(f"User said: {text}")

    api = RealtimeVoiceAPI(on_transcription=on_transcription)
    api.run_session_sync()
"""

import os
import json
try:
    import websocket
except ImportError:
    websocket = None

try:
    import numpy as np
except ImportError:
    np = None

try:
    import sounddevice as sd
except ImportError:
    sd = None
import threading
import time
import base64
import queue
from typing import Optional, Callable, Dict, Any, List
from dataclasses import asdict
from dotenv import load_dotenv
from openai_apis._logging import get_logger, set_correlation_id, log_audit_event, log_performance
from openai_apis.realtime.config import RealtimeConfig
from openai_apis.realtime.events import TranscriptDelta, TranscriptCompleted, ErrorEvent


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


class RealtimeVoiceAPI:
    """
    WebSocket-based realtime voice interaction API.

    This class manages direct WebSocket connections to OpenAI's Realtime API,
    handling audio streaming, event callbacks, and session lifecycle.

    Attributes:
        config: Realtime session configuration.
        state: RealtimeAgentState instance for state management.
        ws: WebSocketApp instance (None until connected).
    """

    def __init__(
        self,
        config: Optional[RealtimeConfig] = None,
        state: Optional[RealtimeAgentState] = None,
        api_key: Optional[str] = None,
        # Event callbacks
        on_transcription: Optional[Callable[[str], None]] = None,
        on_response_audio: Optional[Callable[["np.ndarray"], None]] = None,
        on_response_text: Optional[Callable[[str], None]] = None,
        on_error: Optional[Callable[[str], None]] = None,
        on_session_created: Optional[Callable[[str], None]] = None,
        on_session_updated: Optional[Callable[[], None]] = None,
    ):
        """
        Initialize the Realtime Voice API.

        Args:
            config: Realtime configuration settings.
            state: RealtimeAgentState instance for custom state.
            api_key: OpenAI API key (defaults to OPENAI_API_KEY env var).
            on_transcription: Callback when user speech is transcribed.
            on_response_audio: Callback when response audio chunk arrives.
            on_response_text: Callback when response text transcript arrives.
            on_error: Callback for error handling.
            on_session_created: Callback when session is created (receives session_id).
            on_session_updated: Callback when session is updated/configured.
        """
        self._check_realtime_deps()
        load_dotenv()

        self.config = config or RealtimeConfig()
        self.state = state or RealtimeAgentState()
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY")

        # Callbacks
        self._on_transcription = on_transcription
        self._on_response_audio = on_response_audio
        self._on_response_text = on_response_text
        self._on_error = on_error
        self._on_session_created = on_session_created
        self._on_session_updated = on_session_updated

        # WebSocket connection
        self.ws: Optional[websocket.WebSocketApp] = None

        # Session state
        self._session_id: Optional[str] = None
        self._session_ready = threading.Event()
        self._session_configured = threading.Event()

        # Push-to-talk state
        self._ptt_active = threading.Event()
        self._ptt_exit = threading.Event()

        # Speaker/audio output
        self._speaker_queue: queue.Queue = queue.Queue()
        self._speaker_thread: Optional[threading.Thread] = None
        self._speaker_stream: Optional[sd.OutputStream] = None
        self._audio_chunk_counter = 0

        # Delta accumulator: maps item_id -> {"accumulated": str, "start_time": float}
        self._delta_accumulator: Dict[str, Dict[str, Any]] = {}

        # Typed event callbacks: maps event_name -> list of callbacks
        self._event_callbacks: Dict[str, list[Callable]] = {}

        # Output device (None = default)
        self._output_device: Optional[int] = None

        # Logging
        self.logger = get_logger(__name__)
        self.logger.info(
            "RealtimeVoiceAPI initialized",
            extra={"extra_data": {"config": asdict(self.config)}}
        )

        log_audit_event(
            event_type="realtime_init",
            action="realtime_api_initialized",
            details={"model": self.config.model, "language": self.config.language}
        )

    def set_output_device(self, device_index: int) -> None:
        """Set the audio output device by index."""
        self._output_device = device_index

    def _accumulate_delta(self, item_id: str, delta: str) -> str:
        """Accumulate delta text for an item_id. Returns the accumulated text."""
        if item_id not in self._delta_accumulator:
            self._delta_accumulator[item_id] = {
                "accumulated": "",
                "start_time": time.time(),
            }
        self._delta_accumulator[item_id]["accumulated"] += delta
        return self._delta_accumulator[item_id]["accumulated"]

    def _complete_accumulation(self, item_id: str) -> float:
        """Complete accumulation for an item_id. Returns duration_ms since first delta."""
        entry = self._delta_accumulator.pop(item_id, None)
        if entry is None:
            return 0.0
        return (time.time() - entry["start_time"]) * 1000

    def _emit_event(self, event_name: str, event_data: Any) -> None:
        """Emit a typed event, calling all registered callbacks.

        Callbacks are invoked synchronously in the WebSocket message handler thread.
        Each callback is wrapped in try/except to prevent one failing callback
        from blocking others.
        """
        for cb in self._event_callbacks.get(event_name, []):
            try:
                cb(event_data)
            except Exception as e:
                self.logger.warning(
                    f"Callback error for event '{event_name}': {e}",
                    exc_info=True,
                )

    def on(self, event: str, callback: Callable) -> None:
        """Register a callback for a typed event.

        Supported events:
            - "transcript.delta": Receives TranscriptDelta
            - "transcript.completed": Receives TranscriptCompleted
            - "error": Receives ErrorEvent

        Args:
            event: Event name string.
            callback: Callable that receives the typed event object.
        """
        if event not in self._event_callbacks:
            self._event_callbacks[event] = []
        self._event_callbacks[event].append(callback)

    def _check_realtime_deps(self) -> None:
        """Check if required realtime dependencies are installed."""
        missing = []
        if websocket is None:
            missing.append("websocket-client")
        if np is None:
            missing.append("numpy")
        if sd is None:
            missing.append("sounddevice")
        if missing:
            raise ImportError(
                f"Missing dependencies for realtime module: {', '.join(missing)}. "
                "Install with: pip install openai-apis[audio]"
            )

    def _create_session_update_event(self) -> Dict[str, Any]:
        """Create session.update event from config."""
        return {
            "type": "session.update",
            "session": {
                "modalities": self.config.modalities,
                "instructions": self.config.instructions,
                "voice": self.config.voice,
                "input_audio_format": "pcm16",
                "output_audio_format": "pcm16",
                "input_audio_transcription": {
                    "model": self.config.transcription_model,
                    "language": self.config.language
                },
                "turn_detection": None,  # Manual turn detection (push-to-talk)
                "temperature": self.config.temperature,
                "max_response_output_tokens": self.config.max_response_output_tokens,
                "speed": self.config.speed,
                "tracing": "auto"
            }
        }

    def _on_open(self, ws: websocket.WebSocketApp) -> None:
        """WebSocket connection opened."""
        print("[INFO] Connected to Realtime API.")
        # Start PTT listener thread
        threading.Thread(target=self._ptt_listener, daemon=True).start()

    def _on_message(self, ws: websocket.WebSocketApp, message: str) -> None:
        """Handle incoming WebSocket messages."""
        try:
            event = json.loads(message)
        except Exception:
            print("[WARN] Binary or non-JSON event received")
            return

        event_type = event.get("type")
        print(f"[EVENT] {event_type}")

        # Session lifecycle events
        if event_type == "session.created" and not self._session_configured.is_set():
            session = event.get("session")
            if session:
                self._session_id = session.get("id")
                print(f"[INFO] Session created: {self._session_id}")

                self.logger.info(
                    f"Realtime session created: {self._session_id}",
                    extra={"extra_data": {"session_id": self._session_id}}
                )

                log_audit_event(
                    event_type="realtime_session",
                    action="session_created",
                    session_id=self._session_id,
                    details={"model": self.config.model}
                )

                if self._on_session_created:
                    self._on_session_created(self._session_id)

                # Send session.update to configure language/voice
                ws.send(json.dumps(self._create_session_update_event()))
                self._session_configured.set()
                print("[INFO] Session configuration sent (Hungarian transcription enabled)")

                log_audit_event(
                    event_type="realtime_session",
                    action="session_configured",
                    session_id=self._session_id,
                    details={"language": self.config.language, "voice": self.config.voice}
                )

        elif event_type == "session.updated" and self._session_configured.is_set() and not self._session_ready.is_set():
            print("[INFO] Session configured, push-to-talk enabled.")
            self._session_ready.set()

            if self._on_session_updated:
                self._on_session_updated()

            # Start microphone loop
            threading.Thread(target=self._mic_loop, args=(ws,), daemon=True).start()

        # Transcription events
        elif event_type == "conversation.item.input_audio_transcription.delta":
            item_id = event.get("item_id", "")
            delta_text = event.get("delta", "")
            accumulated = self._accumulate_delta(item_id, delta_text)

            delta_event = TranscriptDelta(
                item_id=item_id,
                delta=delta_text,
                accumulated=accumulated,
            )

            log_audit_event(
                event_type="transcript.delta",
                action="transcript_delta_received",
                session_id=self._session_id,
                details={
                    "item_id": item_id,
                    "delta_length": len(delta_text),
                    "accumulated_length": len(accumulated),
                },
            )

            self._emit_event("transcript.delta", delta_event)

        elif event_type == "conversation.item.input_audio_transcription.completed":
            transcript = event.get("transcript", "")
            print(f"[TRANSCRIPTION] {transcript}")

            self.logger.info(
                f"Transcription received: {transcript[:100]}...",
                extra={"extra_data": {"transcript_length": len(transcript)}}
            )

            log_audit_event(
                event_type="realtime_transcription",
                action="transcription_completed",
                session_id=self._session_id,
                details={"transcript_length": len(transcript), "language": self.config.language}
            )

            if self._on_transcription:
                self._on_transcription(transcript)

            item_id = event.get("item_id", "")
            duration_ms = self._complete_accumulation(item_id)
            completed_event = TranscriptCompleted(
                item_id=item_id,
                transcript=transcript,
                duration_ms=duration_ms,
            )

            log_audit_event(
                event_type="transcript.completed",
                action="transcription_completed",
                session_id=self._session_id,
                details={
                    "item_id": item_id,
                    "transcript_length": len(transcript),
                    "duration_ms": duration_ms,
                },
            )

            self._emit_event("transcript.completed", completed_event)

        # Audio response events
        elif event_type == "response.audio.delta":
            self._audio_chunk_counter += 1
            audio_b64 = event.get("delta", "")
            audio_bytes = base64.b64decode(audio_b64)
            audio_np = np.frombuffer(audio_bytes, dtype=np.int16)

            if audio_np.size > 0:
                self._speaker_queue.put(audio_np)

                if self._on_response_audio:
                    self._on_response_audio(audio_np)

                # Start speaker thread if not running
                if self._speaker_thread is None or not self._speaker_thread.is_alive():
                    self._start_speaker_thread()

        elif event_type == "response.audio.done":
            print(f"[INFO] Response audio complete ({self._audio_chunk_counter} chunks)")
            self._speaker_queue.put(None)  # Signal end
            self._audio_chunk_counter = 0

        # Text transcript events
        elif event_type == "response.audio_transcript.delta":
            item_id = event.get("item_id", "")
            delta_text = event.get("delta", "")
            accumulated = self._accumulate_delta(item_id, delta_text)

            delta_event = TranscriptDelta(
                item_id=item_id,
                delta=delta_text,
                accumulated=accumulated,
            )

            log_audit_event(
                event_type="transcript.delta",
                action="response_transcript_delta_received",
                session_id=self._session_id,
                details={
                    "item_id": item_id,
                    "delta_length": len(delta_text),
                    "accumulated_length": len(accumulated),
                },
            )

            self._emit_event("transcript.delta", delta_event)

        elif event_type == "response.audio_transcript.done":
            transcript = event.get("transcript", "")
            print(f"[TRANSCRIPT] {transcript}")
            if self._on_response_text:
                self._on_response_text(transcript)

            item_id = event.get("item_id", "")
            duration_ms = self._complete_accumulation(item_id)
            completed_event = TranscriptCompleted(
                item_id=item_id,
                transcript=transcript,
                duration_ms=duration_ms,
            )

            log_audit_event(
                event_type="transcript.completed",
                action="response_transcript_completed",
                session_id=self._session_id,
                details={
                    "item_id": item_id,
                    "transcript_length": len(transcript),
                    "duration_ms": duration_ms,
                },
            )

            self._emit_event("transcript.completed", completed_event)

        # Error events
        elif event_type == "error":
            error_msg = event.get("message", "Unknown error")
            print(f"[ERROR] {error_msg}")

            self.logger.error(
                f"Realtime API error: {error_msg}",
                extra={"extra_data": {"error_event": event}}
            )

            log_audit_event(
                event_type="realtime_error",
                action="error_received",
                session_id=self._session_id,
                details={"error_message": error_msg, "error_code": event.get("code")},
                status="error"
            )

            if self._on_error:
                self._on_error(error_msg)

            error_event = ErrorEvent(
                code=event.get("code", "unknown"),
                message=error_msg,
            )
            self._emit_event("error", error_event)

        # Other events (logging only)
        elif event_type == "conversation.created":
            print("[INFO] Conversation created")
        elif event_type == "input_audio_buffer.committed":
            print("[INFO] Audio buffer committed, user message item created")
        elif event_type == "response.created":
            print("[INFO] Response generation started")
        elif event_type == "response.done":
            print("[INFO] Response generation complete")

    def _on_error_ws(self, ws: websocket.WebSocketApp, error: Exception) -> None:
        """WebSocket error handler."""
        print(f"[ERROR] WebSocket error: {error}")
        if self._on_error:
            self._on_error(str(error))

    def _on_close(self, ws: websocket.WebSocketApp, close_status_code: int, close_msg: str) -> None:
        """WebSocket connection closed."""
        print(f"[INFO] Connection closed: {close_status_code} - {close_msg}")

    def _mic_loop(self, ws: websocket.WebSocketApp) -> None:
        """
        Microphone recording loop.

        Continuously reads from microphone, buffers audio, and sends
        chunks when they reach the configured duration (default 500ms).
        """
        print("[PTT] Press Enter to start/stop recording, 'q' to quit")
        self._session_ready.wait()

        buffer_size = int(self.config.sample_rate * self.config.chunk_duration_s)
        read_size = 1024  # Small block size for compatibility

        with sd.InputStream(
            samplerate=self.config.sample_rate,
            channels=self.config.channels,
            dtype='int16'
        ) as mic:
            while not self._ptt_exit.is_set():
                self._ptt_active.wait()
                if self._ptt_exit.is_set():
                    break

                print("[PTT] Recording started...")
                audio_buffer = np.empty((0,), dtype=np.int16)
                chunk_count = 0

                while self._ptt_active.is_set() and not self._ptt_exit.is_set():
                    available = mic.read_available
                    if available >= read_size:
                        data, _ = mic.read(read_size)
                        if data.size > 0:
                            audio_buffer = np.concatenate([audio_buffer, data.flatten()])

                            # Send chunks when buffer reaches target size
                            while len(audio_buffer) >= buffer_size:
                                chunk = audio_buffer[:buffer_size]
                                audio_buffer = audio_buffer[buffer_size:]
                                self._send_audio_chunk(ws, chunk)
                                chunk_count += 1
                    else:
                        time.sleep(0.01)

                # Send remaining buffer when recording stops
                if len(audio_buffer) > 0:
                    self._send_audio_chunk(ws, audio_buffer)
                    chunk_count += 1

                print(f"[PTT] Recording stopped, {chunk_count} chunks sent")

                if chunk_count > 0:
                    # Commit audio buffer
                    ws.send(json.dumps({"type": "input_audio_buffer.commit"}))

                    # Request response
                    response_create_event = {
                        "type": "response.create",
                        "response": {
                            "modalities": self.config.modalities,
                            "voice": self.config.voice,
                            "output_audio_format": "pcm16",
                            "tool_choice": "auto",
                            "temperature": self.config.temperature,
                            "max_output_tokens": 1024
                        }
                    }
                    ws.send(json.dumps(response_create_event))
                else:
                    print("[WARN] No audio chunks sent, skipping commit")

    def _send_audio_chunk(self, ws: "websocket.WebSocketApp", chunk: "np.ndarray") -> None:
        """Send audio chunk via input_audio_buffer.append event."""
        audio_b64 = base64.b64encode(chunk.tobytes()).decode("ascii")
        event = {
            "type": "input_audio_buffer.append",
            "audio": audio_b64
        }
        ws.send(json.dumps(event))

    def _ptt_listener(self) -> None:
        """Listen for Enter keypresses to toggle push-to-talk."""
        while not self._ptt_exit.is_set():
            key = input()
            if key.strip().lower() == 'q':
                print("[PTT] Exit requested (q)")
                self._ptt_exit.set()
                break

            if not self._ptt_active.is_set():
                print("[PTT] PUSH-TO-TALK: ON (Recording...)")
                self._ptt_active.set()
            else:
                print("[PTT] PUSH-TO-TALK: OFF (Stopped)")
                self._ptt_active.clear()

    def _start_speaker_thread(self) -> None:
        """Start the speaker output thread."""
        if self._speaker_thread is not None and self._speaker_thread.is_alive():
            return  # Already running

        def speaker_worker():
            played_chunks = 0
            try:
                self._speaker_stream = sd.OutputStream(
                    samplerate=self.config.sample_rate,
                    channels=self.config.channels,
                    dtype=np.int16,
                    device=self._output_device
                )
                self._speaker_stream.start()
                print(f"[AUDIO] Speaker started (device: {self._output_device})")

                empty_count = 0
                while True:
                    try:
                        chunk = self._speaker_queue.get(timeout=0.5)
                        if chunk is None:
                            print(f"[AUDIO] Speaker stopped ({played_chunks} chunks played)")
                            break

                        if not isinstance(chunk, np.ndarray) or chunk.dtype != np.int16:
                            print(f"[ERROR] Invalid chunk format: {type(chunk)}")
                            continue

                        if chunk.size == 0:
                            print("[WARN] Empty chunk, skipping")
                            continue

                        self._speaker_stream.write(chunk)
                        played_chunks += 1
                        empty_count = 0

                    except queue.Empty:
                        empty_count += 1
                        # Auto-stop after 3 empty timeouts (1.5s)
                        if empty_count >= 3:
                            print(f"[AUDIO] Speaker auto-stopped ({played_chunks} chunks played)")
                            break

            except Exception as e:
                print(f"[ERROR] Speaker thread exception: {e}")

            finally:
                if self._speaker_stream is not None:
                    try:
                        self._speaker_stream.stop()
                        self._speaker_stream.close()
                    except Exception as e:
                        print(f"[WARN] Speaker stream close error: {e}")
                    self._speaker_stream = None

                print("[AUDIO] Speaker thread stopped")
                self._speaker_thread = None

        self._speaker_thread = threading.Thread(target=speaker_worker, daemon=True)
        self._speaker_thread.start()

    def _stop_speaker_thread(self) -> None:
        """Stop the speaker output thread."""
        self._speaker_queue.put(None)
        if self._speaker_thread is not None:
            self._speaker_thread.join(timeout=2)
            self._speaker_thread = None

    def run_session(self) -> None:
        """
        Run a realtime voice session (blocking).

        Connects to OpenAI Realtime API via WebSocket and starts
        push-to-talk interaction loop. Blocks until session ends.
        """
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY not set")

        session_start = time.time()
        session_corr_id = set_correlation_id()

        url = f"wss://api.openai.com/v1/realtime?model={self.config.model}"
        headers = [
            f"Authorization: Bearer {self.api_key}",
            "OpenAI-Beta: realtime=v1"
        ]

        self.logger.info(
            "Starting Realtime API session",
            extra={"extra_data": {"model": self.config.model, "session_corr_id": session_corr_id}}
        )

        self.ws = websocket.WebSocketApp(
            url,
            header=headers,
            on_open=self._on_open,
            on_message=self._on_message,
            on_error=self._on_error_ws,
            on_close=self._on_close
        )

        try:
            print("[INFO] Starting Realtime API session...")
            self.ws.run_forever()
        except KeyboardInterrupt:
            print("[INFO] Session interrupted by user")
            self.logger.info("Session interrupted by user")
        finally:
            session_duration_ms = (time.time() - session_start) * 1000
            self.disconnect()

            log_performance(
                operation="realtime_session",
                duration_ms=session_duration_ms,
                details={"session_id": self._session_id}
            )

    def disconnect(self) -> None:
        """Disconnect from the session and cleanup resources."""
        print("[INFO] Disconnecting...")

        self.logger.info(
            "Disconnecting from Realtime API",
            extra={"extra_data": {"session_id": self._session_id}}
        )

        log_audit_event(
            event_type="realtime_session",
            action="session_disconnected",
            session_id=self._session_id,
            details={}
        )

        self._ptt_exit.set()
        self._stop_speaker_thread()

        if self.ws:
            self.ws.close()
            self.ws = None

        print("[INFO] Disconnected")
        self.logger.info("Realtime session disconnected")

    def get_session_id(self) -> Optional[str]:
        """Get the current session ID."""
        return self._session_id

    def clear_speaker_queue(self) -> None:
        """Clear the speaker queue (e.g., for interruption)."""
        while not self._speaker_queue.empty():
            try:
                self._speaker_queue.get_nowait()
            except Exception:
                break
        print("[DEBUG] Speaker queue cleared")


# Convenience function
def start_realtime_session(
    config: Optional[RealtimeConfig] = None,
    state: Optional[RealtimeAgentState] = None,
    on_transcription: Optional[Callable[[str], None]] = None
) -> None:
    """
    Start an interactive realtime voice session.

    Args:
        config: Optional realtime configuration.
        state: Optional state manager.
        on_transcription: Callback when user speech is transcribed.

    Example:
        >>> from realtime_voice_api import start_realtime_session
        >>> start_realtime_session()
    """
    api = RealtimeVoiceAPI(
        config=config,
        state=state,
        on_transcription=on_transcription
    )
    api.run_session()


if __name__ == "__main__":
    print("Realtime Voice API module")
    print("\nExample:")
    print("  from realtime_voice_api import RealtimeVoiceAPI")
    print("  api = RealtimeVoiceAPI()")
    print("  api.run_session()")
