"""End-to-end integration tests for all API flows.

Tests the complete flow of each API module with mock WebSocket/API backends.
Each test class covers one scenario from GitHub Issue #38.
"""
import pytest
import asyncio
import json
import base64
import numpy as np
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from openai_apis import (
    TranscriptionSession, TranscriptionConfig,
    RealtimeSession, RealtimeConfig,
    TTSConfig, TTSRegistry,
    AudioFormat, VADConfig, SessionState, SessionAuditLog,
    ToolRegistry,
)
from openai_apis._session import InvalidStateTransition
from openai_apis.realtime.events import (
    AudioDelta, AudioDone, TranscriptDelta, TranscriptCompleted, ErrorEvent,
)
from openai_apis.tts import OpenAITTSProvider, TTSAPI

from tests.integration.conftest import (
    MockWebSocket, ErrorMockWebSocket, make_handshake_messages, mock_websockets_connect,
)


class TestTranscriptionFlow:
    """Scenario 1: Full transcription flow with mock WebSocket."""

    @pytest.mark.asyncio
    async def test_full_transcription_flow(self, sample_audio, mock_transcription_rest):
        """Session create → audio send → delta events → completed → close."""
        # Build WebSocket messages: handshake + transcription deltas + completed
        messages = make_handshake_messages() + [
            json.dumps({
                "type": "conversation.item.input_audio_transcription.delta",
                "item_id": "item_1",
                "delta": "Hel",
                "content_index": 0,
            }),
            json.dumps({
                "type": "conversation.item.input_audio_transcription.delta",
                "item_id": "item_1",
                "delta": "lo",
                "content_index": 0,
            }),
            json.dumps({
                "type": "conversation.item.input_audio_transcription.completed",
                "item_id": "item_1",
                "transcript": "Hello",
                "content_index": 0,
            }),
        ]

        mock_ws = MockWebSocket(messages)
        deltas = []
        completed = []

        with patch(
            "openai_apis.transcription.ws_session.websockets.connect",
            new_callable=AsyncMock,
            return_value=mock_ws,
        ):
            async with TranscriptionSession() as session:
                # Validate CONNECTED state
                assert session.state == SessionState.CONNECTED

                # Register callbacks
                session.on("transcript.delta", lambda d: deltas.append(d))
                session.on("transcript.completed", lambda d: completed.append(d))

                # Send audio
                audio_bytes = sample_audio.tobytes()
                await session.send_audio(audio_bytes)
                await session.commit_audio()

                # Let receive loop process messages
                await asyncio.sleep(0.1)

        # Validate state after close
        assert session.state == SessionState.CLOSED

        # Validate callbacks
        assert len(deltas) == 2
        assert deltas[0]["delta"] == "Hel"
        assert deltas[1]["delta"] == "lo"
        assert len(completed) == 1
        assert completed[0]["transcript"] == "Hello"

        # Validate sent messages: session.update + audio_buffer.append + audio_buffer.commit
        sent = [json.loads(m) for m in mock_ws.sent_messages]
        types = [m["type"] for m in sent]
        assert "session.update" in types
        assert "input_audio_buffer.append" in types
        assert "input_audio_buffer.commit" in types

        # Validate audit log
        events = session.audit_log.events
        event_types = [e.event_type for e in events]
        assert "session.created" in event_types
        assert "websocket.connected" in event_types
        assert "audio.chunk_sent" in event_types
        assert "audio.buffer_committed" in event_types
        assert "session.closed" in event_types

    @pytest.mark.asyncio
    async def test_transcription_state_transitions(self, mock_transcription_rest):
        """Verify all state transitions: CREATED → CONNECTING → CONNECTED → DISCONNECTING → CLOSED."""
        mock_ws = MockWebSocket(make_handshake_messages())
        states = []

        with patch(
            "openai_apis.transcription.ws_session.websockets.connect",
            new_callable=AsyncMock,
            return_value=mock_ws,
        ):
            session = TranscriptionSession()
            session.on("state_changed", lambda d: states.append((d["from"].value, d["to"].value)))
            assert session.state == SessionState.CREATED

            async with session:
                assert session.state == SessionState.CONNECTED

        assert session.state == SessionState.CLOSED
        assert ("created", "connecting") in states
        assert ("connecting", "connected") in states
        assert ("connected", "disconnecting") in states


class TestRealtimeVoiceFlow:
    """Scenario 2: Full realtime voice flow with mock WebSocket."""

    @pytest.mark.asyncio
    async def test_full_realtime_voice_flow(self, sample_audio):
        """Session create → audio send → audio deltas → transcript → close."""
        audio_chunk = base64.b64encode(b"\x00\x00" * 100).decode("ascii")
        messages = make_handshake_messages() + [
            json.dumps({
                "type": "response.created",
                "response": {"id": "resp_1"},
            }),
            json.dumps({
                "type": "response.audio.delta",
                "delta": audio_chunk,
                "item_id": "item_out_1",
                "response_id": "resp_1",
            }),
            json.dumps({
                "type": "response.audio.done",
                "item_id": "item_out_1",
                "response_id": "resp_1",
            }),
            json.dumps({
                "type": "response.audio_transcript.done",
                "item_id": "item_out_1",
                "transcript": "Szia!",
            }),
            json.dumps({
                "type": "conversation.item.input_audio_transcription.completed",
                "item_id": "item_in_1",
                "transcript": "Hello",
            }),
            json.dumps({
                "type": "response.done",
                "response": {"id": "resp_1", "status": "completed"},
            }),
        ]

        mock_ws = MockWebSocket(messages)
        audio_deltas = []
        audio_dones = []
        transcripts_in = []
        transcripts_out = []

        with patch(
            "openai_apis.realtime.session.websockets.connect",
            side_effect=mock_websockets_connect(mock_ws),
        ):
            async with RealtimeSession() as session:
                assert session.state == SessionState.CONNECTED

                session.on("audio.delta", lambda d: audio_deltas.append(d))
                session.on("audio.done", lambda d: audio_dones.append(d))
                session.on("transcript.input", lambda d: transcripts_in.append(d))
                session.on("transcript.output", lambda d: transcripts_out.append(d))

                # Send audio and request response
                await session.send_audio(sample_audio.tobytes()[:1000])
                await session.commit_audio()
                await session.create_response()

                await asyncio.sleep(0.1)

        # Validate callbacks
        assert len(audio_deltas) == 1
        assert isinstance(audio_deltas[0], AudioDelta)
        assert audio_deltas[0].item_id == "item_out_1"

        assert len(audio_dones) == 1
        assert isinstance(audio_dones[0], AudioDone)

        assert len(transcripts_in) == 1
        assert isinstance(transcripts_in[0], TranscriptCompleted)
        assert transcripts_in[0].transcript == "Hello"

        assert len(transcripts_out) == 1
        assert transcripts_out[0].transcript == "Szia!"

        # Validate conversation history (order matches event emission order in mock)
        history = session.get_conversation_history()
        assert len(history) == 2
        # In the mock, assistant transcript comes before user transcript
        assert history[0]["role"] == "assistant"
        assert history[0]["content"] == "Szia!"
        assert history[1]["role"] == "user"
        assert history[1]["content"] == "Hello"

        # Validate audit log
        event_types = [e.event_type for e in session.audit_log.events]
        assert "session.created" in event_types
        assert "audio.chunk_sent" in event_types
        assert "audio.buffer_committed" in event_types
        assert "response.create_sent" in event_types
        assert "session.closed" in event_types


class TestTTSFlow:
    """Scenario 3: Full TTS flow with mocked OpenAI client."""

    @pytest.mark.asyncio
    async def test_tts_synthesize_flow(self):
        """Provider create → synthesize → numpy audio output."""
        mock_audio_bytes = np.array([100, 200, 300, 400], dtype=np.int16).tobytes()

        tts = OpenAITTSProvider(config=TTSConfig(output_format="pcm"))

        with patch.object(tts, "_synthesize_bytes", return_value=mock_audio_bytes):
            audio = await tts.synthesize("Szia! Hogy vagy?")

        assert isinstance(audio, np.ndarray)
        assert audio.dtype == np.int16
        assert len(audio) == 4
        np.testing.assert_array_equal(audio, [100, 200, 300, 400])

    @pytest.mark.asyncio
    async def test_tts_synthesize_to_file_flow(self, tmp_path):
        """Provider create → synthesize_to_file → file exists."""
        mock_audio_bytes = np.array([1, 2, 3], dtype=np.int16).tobytes()
        output_path = tmp_path / "output.wav"

        tts = OpenAITTSProvider(config=TTSConfig(output_format="pcm"))

        with patch.object(tts, "_synthesize_bytes", return_value=mock_audio_bytes):
            result_path = await tts.synthesize_to_file("Hello", output_path)

        assert result_path.exists()
        assert result_path == output_path

    @pytest.mark.asyncio
    async def test_tts_registry_factory_flow(self):
        """TTSRegistry.create() → provider → synthesize."""
        config = TTSConfig(provider="openai", voice="sage", output_format="pcm")
        provider = TTSRegistry.create(config)
        assert provider.provider_name == "openai"
        assert "sage" in provider.supported_voices

    @pytest.mark.asyncio
    async def test_tts_empty_text_raises(self):
        """Synthesize with empty text raises ValueError."""
        tts = OpenAITTSProvider(config=TTSConfig())
        with pytest.raises(ValueError, match="cannot be empty"):
            await tts.synthesize("")


class TestToolCallingFlow:
    """Scenario 4: Tool calling flow with RealtimeSession."""

    @pytest.mark.asyncio
    async def test_tool_call_and_result_flow(self):
        """Session → tool call event → auto-execute → tool result sent → response created."""
        # Register a tool
        tools = ToolRegistry()
        tools.register(
            name="get_time",
            description="Get current time",
            parameters={"type": "object", "properties": {}, "required": []},
            handler=lambda: {"time": "12:00"},
        )

        config = RealtimeConfig(tools=tools)

        messages = make_handshake_messages() + [
            json.dumps({
                "type": "response.function_call_arguments.done",
                "call_id": "call_1",
                "name": "get_time",
                "arguments": "{}",
            }),
        ]

        mock_ws = MockWebSocket(messages)
        tool_calls = []

        with patch(
            "openai_apis.realtime.session.websockets.connect",
            side_effect=mock_websockets_connect(mock_ws),
        ):
            async with RealtimeSession(config=config) as session:
                session.on("tool.call", lambda d: tool_calls.append(d))
                await asyncio.sleep(0.2)  # Let receive loop + tool execution run

        # Validate tool.call callback
        assert len(tool_calls) == 1
        assert tool_calls[0]["name"] == "get_time"
        assert tool_calls[0]["call_id"] == "call_1"

        # Validate sent messages include tool result and response.create
        sent = [json.loads(m) for m in mock_ws.sent_messages]
        sent_types = [m["type"] for m in sent]
        assert "conversation.item.create" in sent_types  # tool result
        assert "response.create" in sent_types  # auto-create response after tool

        # Find the tool result message
        tool_result_msg = next(m for m in sent if m["type"] == "conversation.item.create")
        assert tool_result_msg["item"]["call_id"] == "call_1"
        result_data = json.loads(tool_result_msg["item"]["output"])
        assert result_data["time"] == "12:00"

        # Validate audit log
        event_types = [e.event_type for e in session.audit_log.events]
        assert "tool.execution.started" in event_types
        assert "tool.execution.completed" in event_types
        assert "tool.result_sent" in event_types

    @pytest.mark.asyncio
    async def test_async_tool_handler(self):
        """Async tool handler executes correctly."""
        tools = ToolRegistry()

        async def async_handler(city: str):
            return {"weather": "sunny", "city": city}

        tools.register(
            name="get_weather",
            description="Get weather",
            parameters={
                "type": "object",
                "properties": {"city": {"type": "string"}},
                "required": ["city"],
            },
            handler=async_handler,
        )

        config = RealtimeConfig(tools=tools)
        messages = make_handshake_messages() + [
            json.dumps({
                "type": "response.function_call_arguments.done",
                "call_id": "call_w1",
                "name": "get_weather",
                "arguments": '{"city": "Budapest"}',
            }),
        ]

        mock_ws = MockWebSocket(messages)
        with patch(
            "openai_apis.realtime.session.websockets.connect",
            side_effect=mock_websockets_connect(mock_ws),
        ):
            async with RealtimeSession(config=config) as session:
                await asyncio.sleep(0.2)

        # Validate tool result was sent with correct data
        sent = [json.loads(m) for m in mock_ws.sent_messages]
        tool_result_msg = next(m for m in sent if m["type"] == "conversation.item.create")
        result = json.loads(tool_result_msg["item"]["output"])
        assert result["city"] == "Budapest"
        assert result["weather"] == "sunny"


class TestAuditLogFlow:
    """Scenario 5: Audit log completeness and export flow."""

    @pytest.mark.asyncio
    async def test_audit_log_completeness(self, sample_audio):
        """Session operations produce complete audit trail."""
        messages = make_handshake_messages()
        mock_ws = MockWebSocket(messages)

        with patch(
            "openai_apis.realtime.session.websockets.connect",
            side_effect=mock_websockets_connect(mock_ws),
        ):
            async with RealtimeSession() as session:
                await session.send_audio(sample_audio.tobytes()[:1000])
                await session.commit_audio()
                await session.create_response()

        events = session.audit_log.events
        event_types = [e.event_type for e in events]

        # Validate required audit events
        assert "session.created" in event_types
        assert "session.state_transition" in event_types
        assert "websocket.connected" in event_types
        assert "session.configured" in event_types
        assert "audio.chunk_sent" in event_types
        assert "audio.buffer_committed" in event_types
        assert "response.create_sent" in event_types
        assert "websocket.disconnected" in event_types
        assert "session.closed" in event_types

        # Validate timestamps are monotonic
        timestamps = [e.timestamp for e in events]
        for i in range(1, len(timestamps)):
            assert timestamps[i] >= timestamps[i - 1]

        # Validate all events have session_id
        for event in events:
            assert event.session_id == session.session_id

    @pytest.mark.asyncio
    async def test_audit_log_export_json(self, sample_audio):
        """export_json() returns valid JSON with correct structure."""
        messages = make_handshake_messages()
        mock_ws = MockWebSocket(messages)

        with patch(
            "openai_apis.realtime.session.websockets.connect",
            side_effect=mock_websockets_connect(mock_ws),
        ):
            async with RealtimeSession() as session:
                await session.send_audio(sample_audio.tobytes()[:500])

        json_str = session.audit_log.export_json()
        data = json.loads(json_str)

        assert "session_id" in data
        assert data["session_id"] == session.session_id
        assert "events" in data
        assert isinstance(data["events"], list)
        assert len(data["events"]) > 0

        for event in data["events"]:
            assert "timestamp" in event
            assert "session_id" in event
            assert "event_type" in event
            assert "data" in event

    @pytest.mark.asyncio
    async def test_audit_log_export_to_file(self, sample_audio, temp_audit_dir):
        """export_to_file() writes valid JSON file."""
        messages = make_handshake_messages()
        mock_ws = MockWebSocket(messages)

        with patch(
            "openai_apis.realtime.session.websockets.connect",
            side_effect=mock_websockets_connect(mock_ws),
        ):
            async with RealtimeSession() as session:
                await session.send_audio(sample_audio.tobytes()[:500])

        export_path = temp_audit_dir / "audit.json"
        session.audit_log.export_to_file(export_path)

        assert export_path.exists()
        data = json.loads(export_path.read_text())
        assert data["session_id"] == session.session_id
        assert len(data["events"]) > 0

    @pytest.mark.asyncio
    async def test_audit_log_measure_context_manager(self):
        """SessionAuditLog.measure() records duration_ms."""
        messages = make_handshake_messages()
        mock_ws = MockWebSocket(messages)

        with patch(
            "openai_apis.realtime.session.websockets.connect",
            side_effect=mock_websockets_connect(mock_ws),
        ):
            async with RealtimeSession() as session:
                with session.audit_log.measure("test.operation", {"key": "value"}):
                    await asyncio.sleep(0.05)

        measured = [e for e in session.audit_log.events if e.event_type == "test.operation"]
        assert len(measured) == 1
        assert measured[0].duration_ms is not None
        assert measured[0].duration_ms >= 40  # ~50ms sleep, allow margin
        assert measured[0].data["key"] == "value"

    @pytest.mark.asyncio
    async def test_audit_log_audio_duration_tracking(self, sample_audio):
        """audio.buffer_committed event includes audio_duration_s."""
        messages = make_handshake_messages()
        mock_ws = MockWebSocket(messages)

        with patch(
            "openai_apis.realtime.session.websockets.connect",
            side_effect=mock_websockets_connect(mock_ws),
        ):
            async with RealtimeSession() as session:
                # Send 24000 samples * 2 bytes = 48000 bytes = 1 second
                audio_bytes = sample_audio.tobytes()
                await session.send_audio(audio_bytes)
                await session.commit_audio()

        committed = [e for e in session.audit_log.events if e.event_type == "audio.buffer_committed"]
        assert len(committed) == 1
        assert "audio_duration_s" in committed[0].data
        assert committed[0].data["audio_duration_s"] == pytest.approx(1.0, abs=0.01)


class TestConfigFlow:
    """Scenario 6: Configuration propagation to session.update event."""

    @pytest.mark.asyncio
    async def test_realtime_config_propagates_to_session_update(self):
        """RealtimeConfig values appear in the session.update WebSocket message."""
        config = RealtimeConfig(
            voice="sage",
            language="en",
            modalities=["audio"],
            reasoning_effort="minimal",
            vad=VADConfig(mode="semantic_vad", eagerness="high"),
        )

        mock_ws = MockWebSocket(make_handshake_messages())

        with patch(
            "openai_apis.realtime.session.websockets.connect",
            side_effect=mock_websockets_connect(mock_ws),
        ):
            async with RealtimeSession(config=config) as session:
                pass

        # Find the session.update message sent during connect
        sent = [json.loads(m) for m in mock_ws.sent_messages]
        update_msgs = [m for m in sent if m.get("type") == "session.update"]
        assert len(update_msgs) >= 1

        session_data = update_msgs[0]["session"]
        assert session_data["type"] == "realtime"
        assert session_data["audio"]["output"]["voice"] == "sage"
        assert session_data["output_modalities"] == ["audio"]
        assert session_data["reasoning"] == {"effort": "minimal"}
        turn_detection = session_data["audio"]["input"]["turn_detection"]
        assert turn_detection["type"] == "semantic_vad"
        assert turn_detection["eagerness"] == "high"
        assert session_data["audio"]["input"]["transcription"]["language"] == "en"

    @pytest.mark.asyncio
    async def test_transcription_config_propagates_to_session_update(self, mock_transcription_rest):
        """TranscriptionConfig values appear in the session.update WebSocket message."""
        config = TranscriptionConfig(
            language="en",
            vad=VADConfig(mode="server_vad", threshold=0.7, silence_duration_ms=800),
        )

        mock_ws = MockWebSocket(make_handshake_messages())

        with patch(
            "openai_apis.transcription.ws_session.websockets.connect",
            new_callable=AsyncMock,
            return_value=mock_ws,
        ):
            async with TranscriptionSession(config=config) as session:
                pass

        sent = [json.loads(m) for m in mock_ws.sent_messages]
        update_msgs = [m for m in sent if m.get("type") == "session.update"]
        assert len(update_msgs) >= 1

        session_data = update_msgs[0]["session"]
        assert session_data["type"] == "transcription"
        audio_input = session_data["audio"]["input"]
        assert audio_input["transcription"]["language"] == "en"
        assert audio_input["turn_detection"]["type"] == "server_vad"
        assert audio_input["turn_detection"]["threshold"] == 0.7
        assert audio_input["turn_detection"]["silence_duration_ms"] == 800

    @pytest.mark.asyncio
    async def test_vad_disabled_sets_null_turn_detection(self):
        """VADConfig(mode='disabled') sends turn_detection=None."""
        config = RealtimeConfig(vad=VADConfig(mode="disabled"))
        mock_ws = MockWebSocket(make_handshake_messages())

        with patch(
            "openai_apis.realtime.session.websockets.connect",
            side_effect=mock_websockets_connect(mock_ws),
        ):
            async with RealtimeSession(config=config) as session:
                pass

        sent = [json.loads(m) for m in mock_ws.sent_messages]
        update_msg = next(m for m in sent if m.get("type") == "session.update")
        assert update_msg["session"]["audio"]["input"]["turn_detection"] is None

    @pytest.mark.asyncio
    async def test_tool_registry_propagates_to_session_update(self):
        """ToolRegistry tools appear in session.update message."""
        tools = ToolRegistry()
        tools.register(
            name="test_tool",
            description="A test tool",
            parameters={"type": "object", "properties": {}},
            handler=lambda: "ok",
        )
        config = RealtimeConfig(tools=tools)
        mock_ws = MockWebSocket(make_handshake_messages())

        with patch(
            "openai_apis.realtime.session.websockets.connect",
            side_effect=mock_websockets_connect(mock_ws),
        ):
            async with RealtimeSession(config=config) as session:
                pass

        sent = [json.loads(m) for m in mock_ws.sent_messages]
        update_msg = next(m for m in sent if m.get("type") == "session.update")
        tools_data = update_msg["session"]["tools"]
        assert len(tools_data) == 1
        assert tools_data[0]["name"] == "test_tool"
        assert tools_data[0]["type"] == "function"

    def test_audio_format_consistency_across_configs(self):
        """AudioFormat defaults are consistent across config types."""
        tc = TranscriptionConfig()
        rc = RealtimeConfig()
        tts_c = TTSConfig()

        assert tc.audio_format.sample_rate == 24000
        assert rc.audio_format.sample_rate == 24000
        assert tts_c.sample_rate == 24000

        assert tc.audio_format.channels == 1
        assert rc.audio_format.channels == 1


class TestErrorRecovery:
    """Scenario 7: Error recovery and reconnection."""

    @pytest.mark.asyncio
    async def test_reconnect_on_connection_drop(self, mock_transcription_rest):
        """WebSocket drop triggers reconnection with exponential backoff."""
        # First connection succeeds, then drops (ConnectionClosed)
        # Second connection (reconnect) succeeds
        first_ws = ErrorMockWebSocket(make_handshake_messages())
        reconnect_ws = MockWebSocket(make_handshake_messages())

        call_count = 0

        async def connect_side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return first_ws
            return reconnect_ws

        with patch(
            "openai_apis.transcription.ws_session.websockets.connect",
            new_callable=AsyncMock,
            side_effect=connect_side_effect,
        ):
            session = TranscriptionSession(
                max_reconnect_attempts=3,
                reconnect_delay=0.01,  # Fast for testing
            )
            async with session:
                # Wait for initial connection
                await asyncio.sleep(0.1)
                # Trigger connection drop
                first_ws.should_raise = True
                # Wait for reconnection
                await asyncio.sleep(0.3)

        # Validate reconnection audit events
        event_types = [e.event_type for e in session.audit_log.events]
        assert "websocket.reconnect_attempt" in event_types
        assert "websocket.reconnect_success" in event_types

    @pytest.mark.asyncio
    async def test_reconnect_failure_emits_error(self, mock_transcription_rest):
        """All reconnect attempts failing emits error event."""
        first_ws = ErrorMockWebSocket(make_handshake_messages())

        async def failing_connect(*args, **kwargs):
            if failing_connect.count == 0:
                failing_connect.count += 1
                return first_ws
            raise ConnectionError("Connection refused")
        failing_connect.count = 0

        errors = []
        with patch(
            "openai_apis.transcription.ws_session.websockets.connect",
            new_callable=AsyncMock,
            side_effect=failing_connect,
        ):
            session = TranscriptionSession(
                max_reconnect_attempts=2,
                reconnect_delay=0.01,
            )
            session.on("error", lambda d: errors.append(d))
            async with session:
                await asyncio.sleep(0.1)
                # Trigger connection drop
                first_ws.should_raise = True
                # Wait for all reconnect attempts to fail
                await asyncio.sleep(0.5)

        # Validate error event emitted
        assert len(errors) >= 1
        reconnect_errors = [e for e in errors if e.get("type") == "reconnect_failed"]
        assert len(reconnect_errors) == 1

        # Validate audit log
        event_types = [e.event_type for e in session.audit_log.events]
        assert "websocket.reconnect_failed" in event_types

    @pytest.mark.asyncio
    async def test_send_audio_when_not_connected_raises(self):
        """send_audio() in wrong state raises InvalidStateTransition."""
        session = TranscriptionSession()
        assert session.state == SessionState.CREATED
        with pytest.raises(InvalidStateTransition):
            await session.send_audio(b"\x00\x00")

    @pytest.mark.asyncio
    async def test_realtime_error_event_from_server(self):
        """Server error event is emitted to error callback."""
        messages = make_handshake_messages() + [
            json.dumps({
                "type": "error",
                "error": {"code": "rate_limit", "message": "Too many requests"},
            }),
        ]
        mock_ws = MockWebSocket(messages)
        errors = []

        with patch(
            "openai_apis.realtime.session.websockets.connect",
            side_effect=mock_websockets_connect(mock_ws),
        ):
            async with RealtimeSession() as session:
                session.on("error", lambda d: errors.append(d))
                await asyncio.sleep(0.1)

        assert len(errors) == 1
        assert isinstance(errors[0], ErrorEvent)
        assert errors[0].code == "rate_limit"
        assert errors[0].message == "Too many requests"
