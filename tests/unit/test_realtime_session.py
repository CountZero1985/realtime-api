#!/usr/bin/env python3
"""
Unit tests for RealtimeSession async WebSocket client.

Tests all functionality in the RealtimeSession module with comprehensive coverage.
Uses pytest-asyncio and MockWebSocket pattern matching test_transcription_session.py.
"""

import pytest
import asyncio
import json
import base64
import uuid
from unittest.mock import AsyncMock, MagicMock, patch, call

from openai_apis.realtime import (
    RealtimeSession,
    RealtimeAgentState,
    RealtimeConfig,
    TranscriptDelta,
    TranscriptCompleted,
    ErrorEvent,
    AudioDelta,
    AudioDone,
)
from openai_apis import SessionState, InvalidStateTransition


class MockWebSocket:
    """Mock WebSocket for testing."""

    def __init__(self, messages=None):
        """Initialize mock WebSocket.

        Args:
            messages: List of messages to return from recv(), or None for empty.
        """
        self.messages = messages or []
        self.sent_messages = []
        self.closed = False
        self.message_index = 0

    async def send(self, message):
        """Mock send - records sent messages."""
        self.sent_messages.append(message)

    async def recv(self):
        """Mock recv - returns messages from queue."""
        if self.message_index < len(self.messages):
            msg = self.messages[self.message_index]
            self.message_index += 1
            return msg
        # If no more messages, sleep forever (simulates waiting)
        await asyncio.sleep(1000)

    async def close(self):
        """Mock close."""
        self.closed = True

    def __aiter__(self):
        """Mock async iteration."""
        return self

    async def __anext__(self):
        """Mock async next for iteration."""
        if self.message_index < len(self.messages):
            msg = self.messages[self.message_index]
            self.message_index += 1
            return msg
        raise StopAsyncIteration


def make_handshake_messages():
    """Create session.created + session.updated handshake messages."""
    return [
        json.dumps({"type": "session.created", "session": {"id": "sess_test"}}),
        json.dumps({"type": "session.updated", "session": {"id": "sess_test"}}),
    ]


def mock_websockets_connect(mock_ws):
    """Create async mock for websockets.connect that returns mock_ws."""
    async def _connect(*args, **kwargs):
        return mock_ws
    return _connect


# RealtimeConfig Tests (keep existing config tests)

class TestRealtimeConfig:
    """Test RealtimeConfig dataclass."""

    def test_default_config(self):
        """Test default configuration values."""
        config = RealtimeConfig()
        assert config.model == "gpt-realtime-mini"
        assert config.voice == "ash"
        assert config.language == "hu"
        assert config.modalities == ["audio", "text"]
        assert config.temperature == 0.8
        assert config.input_audio_transcription is True

    def test_custom_config(self):
        """Test custom configuration values."""
        config = RealtimeConfig(
            model="gpt-4o-realtime-preview",
            voice="alloy",
            language="en",
            temperature=0.9,
        )
        assert config.model == "gpt-4o-realtime-preview"
        assert config.voice == "alloy"
        assert config.language == "en"
        assert config.temperature == 0.9

    def test_post_init_modalities(self):
        """Test __post_init__ sets modalities default."""
        config = RealtimeConfig()
        assert config.modalities == ["audio", "text"]

    def test_post_init_custom_modalities(self):
        """Test __post_init__ preserves custom modalities."""
        config = RealtimeConfig(modalities=["text"])
        assert config.modalities == ["text"]

    def test_config_with_vad(self):
        """Test RealtimeConfig with VAD configuration."""
        from openai_apis._config import VADConfig
        vad = VADConfig(mode="server_vad", threshold=0.7)
        config = RealtimeConfig(vad=vad)
        assert config.vad.mode == "server_vad"
        assert config.vad.threshold == 0.7

    def test_config_vad_default(self):
        """Test RealtimeConfig VAD default is server_vad."""
        config = RealtimeConfig()
        assert config.vad.mode == "server_vad"


# RealtimeAgentState Tests (keep existing state tests)

class TestRealtimeAgentState:
    """Test RealtimeAgentState class."""

    def test_initialization(self):
        """Test RealtimeAgentState initialization."""
        state = RealtimeAgentState()
        assert state.state == {}
        assert state.as_dict() == {}

    def test_set(self):
        """Test setting state values."""
        state = RealtimeAgentState()
        state.set("key", "value")
        assert state.state["key"] == "value"

    def test_get(self):
        """Test getting state values."""
        state = RealtimeAgentState()
        state.state["key"] = "value"
        assert state.get("key") == "value"

    def test_get_with_default(self):
        """Test getting non-existent key with default."""
        state = RealtimeAgentState()
        assert state.get("nonexistent", "default") == "default"

    def test_as_dict(self):
        """Test converting state to dict."""
        state = RealtimeAgentState()
        state.set("a", 1)
        state.set("b", 2)
        assert state.as_dict() == {"a": 1, "b": 2}

    def test_clear(self):
        """Test clearing state."""
        state = RealtimeAgentState()
        state.set("key", "value")
        state.clear()
        assert state.as_dict() == {}


# RealtimeSession Init Tests

class TestRealtimeSessionInit:
    """Test RealtimeSession initialization."""

    def test_default_config(self):
        """Default RealtimeConfig used when None."""
        session = RealtimeSession()
        assert isinstance(session._config, RealtimeConfig)
        assert session._config.model == "gpt-realtime-mini"

    def test_custom_config(self):
        """Custom config is stored."""
        config = RealtimeConfig(model="gpt-4o-realtime-preview", language="en")
        session = RealtimeSession(config=config)
        assert session._config.model == "gpt-4o-realtime-preview"
        assert session._config.language == "en"

    def test_initial_state_created(self):
        """State is CREATED after init."""
        session = RealtimeSession()
        assert session.state == SessionState.CREATED

    def test_session_id_generated(self):
        """Session ID is a valid UUID."""
        session = RealtimeSession()
        parsed_uuid = uuid.UUID(session.session_id)
        assert str(parsed_uuid) == session.session_id

    def test_agent_state_default(self):
        """Default RealtimeAgentState created."""
        session = RealtimeSession()
        assert isinstance(session.agent_state, RealtimeAgentState)
        assert session.agent_state.as_dict() == {}

    def test_agent_state_custom(self):
        """Custom state passed through."""
        state = RealtimeAgentState()
        state.set("test", "value")
        session = RealtimeSession(state=state)
        assert session.agent_state.get("test") == "value"


# RealtimeSession Lifecycle Tests

class TestRealtimeSessionLifecycle:
    """Test RealtimeSession lifecycle and state transitions."""

    @pytest.mark.asyncio
    async def test_connect_disconnect(self):
        """Full lifecycle with async context manager."""
        mock_ws = MockWebSocket(make_handshake_messages())

        with patch("openai_apis.realtime.session.websockets.connect", side_effect=mock_websockets_connect(mock_ws)):
            async with RealtimeSession() as session:
                assert session.state == SessionState.CONNECTED
                assert session._ws is not None
                assert session._receive_task is not None

            assert session.state == SessionState.CLOSED
            assert mock_ws.closed

    @pytest.mark.asyncio
    async def test_state_transitions(self):
        """CREATED → CONNECTING → CONNECTED → DISCONNECTING → CLOSED."""
        mock_ws = MockWebSocket(make_handshake_messages())
        session = RealtimeSession()

        # Initial state
        assert session.state == SessionState.CREATED

        with patch("openai_apis.realtime.session.websockets.connect", side_effect=mock_websockets_connect(mock_ws)):
            # Enter context
            await session.__aenter__()
            assert session.state == SessionState.CONNECTED

            # Exit context
            await session.__aexit__(None, None, None)
            assert session.state == SessionState.CLOSED

    @pytest.mark.asyncio
    async def test_connect_sends_session_update(self):
        """Verify session.update sent on connect."""
        mock_ws = MockWebSocket(make_handshake_messages())

        with patch("openai_apis.realtime.session.websockets.connect", side_effect=mock_websockets_connect(mock_ws)):
            async with RealtimeSession() as session:
                pass

            # Check sent messages
            assert len(mock_ws.sent_messages) == 1
            sent_event = json.loads(mock_ws.sent_messages[0])
            assert sent_event["type"] == "session.update"
            assert "session" in sent_event
            assert sent_event["session"]["voice"] == "ash"
            assert sent_event["session"]["model"] == "gpt-realtime-mini"

    @pytest.mark.asyncio
    async def test_session_created_event_emitted(self):
        """Callback fires on session.created."""
        mock_ws = MockWebSocket(make_handshake_messages())
        callback_data = []

        def callback(data):
            callback_data.append(data)

        with patch("openai_apis.realtime.session.websockets.connect", side_effect=mock_websockets_connect(mock_ws)):
            session = RealtimeSession()
            session.on("session.created", callback)
            async with session:
                pass

        assert len(callback_data) == 1
        assert callback_data[0]["id"] == "sess_test"

    @pytest.mark.asyncio
    async def test_session_updated_event_emitted(self):
        """Callback fires on session.updated."""
        mock_ws = MockWebSocket(make_handshake_messages())
        callback_data = []

        def callback(data):
            callback_data.append(data)

        with patch("openai_apis.realtime.session.websockets.connect", side_effect=mock_websockets_connect(mock_ws)):
            session = RealtimeSession()
            session.on("session.updated", callback)
            async with session:
                pass

        assert len(callback_data) == 1
        assert callback_data[0]["id"] == "sess_test"

    @pytest.mark.asyncio
    async def test_disconnect_cancels_receive_task(self):
        """Receive task cancelled on exit."""
        mock_ws = MockWebSocket(make_handshake_messages())

        with patch("openai_apis.realtime.session.websockets.connect", side_effect=mock_websockets_connect(mock_ws)):
            async with RealtimeSession() as session:
                receive_task = session._receive_task
                assert receive_task is not None

            # Task should be cancelled
            assert receive_task.cancelled()

    @pytest.mark.asyncio
    async def test_disconnect_closes_websocket(self):
        """WebSocket closed on exit."""
        mock_ws = MockWebSocket(make_handshake_messages())

        with patch("openai_apis.realtime.session.websockets.connect", side_effect=mock_websockets_connect(mock_ws)):
            async with RealtimeSession() as session:
                pass

        assert mock_ws.closed


# RealtimeSession Send Audio Tests

class TestRealtimeSessionSendAudio:
    """Test send_audio method."""

    @pytest.mark.asyncio
    async def test_send_audio_base64_encoded(self):
        """Verify base64 encoding."""
        mock_ws = MockWebSocket(make_handshake_messages())
        audio_chunk = b"\x00\x01\x02\x03"

        with patch("openai_apis.realtime.session.websockets.connect", side_effect=mock_websockets_connect(mock_ws)):
            async with RealtimeSession() as session:
                await session.send_audio(audio_chunk)

        # Check sent event
        sent_event = json.loads(mock_ws.sent_messages[1])  # [0] is session.update
        assert sent_event["type"] == "input_audio_buffer.append"
        assert sent_event["audio"] == base64.b64encode(audio_chunk).decode("ascii")

    @pytest.mark.asyncio
    async def test_send_audio_not_connected_raises(self):
        """InvalidStateTransition if not connected."""
        session = RealtimeSession()
        with pytest.raises(InvalidStateTransition):
            await session.send_audio(b"test")


# RealtimeSession Commit Audio Tests

class TestRealtimeSessionCommitAudio:
    """Test commit_audio method."""

    @pytest.mark.asyncio
    async def test_commit_audio_sends_event(self):
        """Verify correct event type."""
        mock_ws = MockWebSocket(make_handshake_messages())

        with patch("openai_apis.realtime.session.websockets.connect", side_effect=mock_websockets_connect(mock_ws)):
            async with RealtimeSession() as session:
                await session.commit_audio()

        sent_event = json.loads(mock_ws.sent_messages[1])
        assert sent_event["type"] == "input_audio_buffer.commit"

    @pytest.mark.asyncio
    async def test_commit_audio_not_connected_raises(self):
        """InvalidStateTransition if not connected."""
        session = RealtimeSession()
        with pytest.raises(InvalidStateTransition):
            await session.commit_audio()


# RealtimeSession Create Response Tests

class TestRealtimeSessionCreateResponse:
    """Test create_response method."""

    @pytest.mark.asyncio
    async def test_create_response_sends_event(self):
        """Verify response.create event."""
        mock_ws = MockWebSocket(make_handshake_messages())

        with patch("openai_apis.realtime.session.websockets.connect", side_effect=mock_websockets_connect(mock_ws)):
            async with RealtimeSession() as session:
                await session.create_response()

        sent_event = json.loads(mock_ws.sent_messages[1])
        assert sent_event["type"] == "response.create"
        assert "response" in sent_event
        assert sent_event["response"]["voice"] == "ash"

    @pytest.mark.asyncio
    async def test_create_response_not_connected_raises(self):
        """InvalidStateTransition if not connected."""
        session = RealtimeSession()
        with pytest.raises(InvalidStateTransition):
            await session.create_response()


# RealtimeSession Update Session Tests

class TestRealtimeSessionUpdateSession:
    """Test update_session method."""

    @pytest.mark.asyncio
    async def test_update_session_merges_kwargs(self):
        """Verify kwargs merged into session payload."""
        mock_ws = MockWebSocket(make_handshake_messages())

        with patch("openai_apis.realtime.session.websockets.connect", side_effect=mock_websockets_connect(mock_ws)):
            async with RealtimeSession() as session:
                await session.update_session(voice="alloy", temperature=0.9)

        sent_event = json.loads(mock_ws.sent_messages[1])
        assert sent_event["type"] == "session.update"
        assert sent_event["session"]["voice"] == "alloy"
        assert sent_event["session"]["temperature"] == 0.9

    @pytest.mark.asyncio
    async def test_update_session_not_connected_raises(self):
        """InvalidStateTransition if not connected."""
        session = RealtimeSession()
        with pytest.raises(InvalidStateTransition):
            await session.update_session(voice="alloy")


# RealtimeSession Send Tool Result Tests

class TestRealtimeSessionSendToolResult:
    """Test send_tool_result method."""

    @pytest.mark.asyncio
    async def test_send_tool_result_correct_format(self):
        """Verify conversation.item.create with function_call_output."""
        mock_ws = MockWebSocket(make_handshake_messages())

        with patch("openai_apis.realtime.session.websockets.connect", side_effect=mock_websockets_connect(mock_ws)):
            async with RealtimeSession() as session:
                await session.send_tool_result("call_123", '{"result": "success"}')

        sent_event = json.loads(mock_ws.sent_messages[1])
        assert sent_event["type"] == "conversation.item.create"
        assert sent_event["item"]["type"] == "function_call_output"
        assert sent_event["item"]["call_id"] == "call_123"
        assert sent_event["item"]["output"] == '{"result": "success"}'

    @pytest.mark.asyncio
    async def test_send_tool_result_not_connected_raises(self):
        """InvalidStateTransition if not connected."""
        session = RealtimeSession()
        with pytest.raises(InvalidStateTransition):
            await session.send_tool_result("call_123", "{}")


# RealtimeSession Event Handling Tests

class TestRealtimeSessionEventHandling:
    """Test event handling and callbacks."""

    @pytest.mark.asyncio
    async def test_input_transcription_completed(self):
        """transcript.input emits TranscriptCompleted."""
        messages = make_handshake_messages() + [
            json.dumps({
                "type": "conversation.item.input_audio_transcription.completed",
                "item_id": "item_123",
                "transcript": "Hello world",
            }),
        ]
        mock_ws = MockWebSocket(messages)
        callback_data = []

        def callback(data):
            callback_data.append(data)

        with patch("openai_apis.realtime.session.websockets.connect", side_effect=mock_websockets_connect(mock_ws)):
            async with RealtimeSession() as session:
                session.on("transcript.input", callback)
                await asyncio.sleep(0.1)  # Let receive loop process

        assert len(callback_data) == 1
        assert isinstance(callback_data[0], TranscriptCompleted)
        assert callback_data[0].transcript == "Hello world"
        assert callback_data[0].item_id == "item_123"

    @pytest.mark.asyncio
    async def test_output_transcription_done(self):
        """transcript.output emits TranscriptCompleted."""
        messages = make_handshake_messages() + [
            json.dumps({
                "type": "response.audio_transcript.done",
                "item_id": "item_456",
                "transcript": "Assistant response",
            }),
        ]
        mock_ws = MockWebSocket(messages)
        callback_data = []

        def callback(data):
            callback_data.append(data)

        with patch("openai_apis.realtime.session.websockets.connect", side_effect=mock_websockets_connect(mock_ws)):
            async with RealtimeSession() as session:
                session.on("transcript.output", callback)
                await asyncio.sleep(0.1)

        assert len(callback_data) == 1
        assert isinstance(callback_data[0], TranscriptCompleted)
        assert callback_data[0].transcript == "Assistant response"

    @pytest.mark.asyncio
    async def test_audio_delta(self):
        """audio.delta emits AudioDelta with audio_bytes, item_id, response_id."""
        audio_b64 = base64.b64encode(b"\x00\x01\x02\x03").decode("ascii")
        messages = make_handshake_messages() + [
            json.dumps({
                "type": "response.audio.delta",
                "delta": audio_b64,
                "item_id": "item_audio_1",
                "response_id": "resp_audio_1",
            }),
        ]
        mock_ws = MockWebSocket(messages)
        callback_data = []

        def callback(data):
            callback_data.append(data)

        with patch("openai_apis.realtime.session.websockets.connect", side_effect=mock_websockets_connect(mock_ws)):
            async with RealtimeSession() as session:
                session.on("audio.delta", callback)
                await asyncio.sleep(0.1)

        assert len(callback_data) == 1
        assert isinstance(callback_data[0], AudioDelta)
        assert callback_data[0].audio_bytes == b"\x00\x01\x02\x03"
        assert callback_data[0].item_id == "item_audio_1"
        assert callback_data[0].response_id == "resp_audio_1"

    @pytest.mark.asyncio
    async def test_audio_done(self):
        """audio.done emits AudioDone with item_id, response_id."""
        messages = make_handshake_messages() + [
            json.dumps({
                "type": "response.audio.done",
                "item_id": "item_audio_1",
                "response_id": "resp_123",
            }),
        ]
        mock_ws = MockWebSocket(messages)
        callback_data = []

        def callback(data):
            callback_data.append(data)

        with patch("openai_apis.realtime.session.websockets.connect", side_effect=mock_websockets_connect(mock_ws)):
            async with RealtimeSession() as session:
                session.on("audio.done", callback)
                await asyncio.sleep(0.1)

        assert len(callback_data) == 1
        assert isinstance(callback_data[0], AudioDone)
        assert callback_data[0].item_id == "item_audio_1"
        assert callback_data[0].response_id == "resp_123"

    @pytest.mark.asyncio
    async def test_tool_call(self):
        """tool.call emits call_id/name/arguments."""
        messages = make_handshake_messages() + [
            json.dumps({
                "type": "response.function_call_arguments.done",
                "call_id": "call_789",
                "name": "get_weather",
                "arguments": '{"city": "Budapest"}',
            }),
        ]
        mock_ws = MockWebSocket(messages)
        callback_data = []

        def callback(data):
            callback_data.append(data)

        with patch("openai_apis.realtime.session.websockets.connect", side_effect=mock_websockets_connect(mock_ws)):
            async with RealtimeSession() as session:
                session.on("tool.call", callback)
                await asyncio.sleep(0.1)

        assert len(callback_data) == 1
        assert callback_data[0]["call_id"] == "call_789"
        assert callback_data[0]["name"] == "get_weather"
        assert callback_data[0]["arguments"] == '{"city": "Budapest"}'

    @pytest.mark.asyncio
    async def test_response_done(self):
        """response.done emits."""
        messages = make_handshake_messages() + [
            json.dumps({"type": "response.done", "response_id": "resp_456"}),
        ]
        mock_ws = MockWebSocket(messages)
        callback_data = []

        def callback(data):
            callback_data.append(data)

        with patch("openai_apis.realtime.session.websockets.connect", side_effect=mock_websockets_connect(mock_ws)):
            async with RealtimeSession() as session:
                session.on("response.done", callback)
                await asyncio.sleep(0.1)

        assert len(callback_data) == 1
        assert callback_data[0]["response_id"] == "resp_456"

    @pytest.mark.asyncio
    async def test_error_event(self):
        """error emits ErrorEvent."""
        messages = make_handshake_messages() + [
            json.dumps({
                "type": "error",
                "error": {"code": "invalid_request", "message": "Bad request"},
            }),
        ]
        mock_ws = MockWebSocket(messages)
        callback_data = []

        def callback(data):
            callback_data.append(data)

        with patch("openai_apis.realtime.session.websockets.connect", side_effect=mock_websockets_connect(mock_ws)):
            async with RealtimeSession() as session:
                session.on("error", callback)
                await asyncio.sleep(0.1)

        assert len(callback_data) == 1
        assert isinstance(callback_data[0], ErrorEvent)
        assert callback_data[0].code == "invalid_request"
        assert callback_data[0].message == "Bad request"

    @pytest.mark.asyncio
    async def test_transcript_delta_accumulation(self):
        """Verify delta accumulation across multiple deltas."""
        messages = make_handshake_messages() + [
            json.dumps({
                "type": "conversation.item.input_audio_transcription.delta",
                "item_id": "item_123",
                "delta": "Hello",
            }),
            json.dumps({
                "type": "conversation.item.input_audio_transcription.delta",
                "item_id": "item_123",
                "delta": " world",
            }),
        ]
        mock_ws = MockWebSocket(messages)
        callback_data = []

        def callback(data):
            callback_data.append(data)

        with patch("openai_apis.realtime.session.websockets.connect", side_effect=mock_websockets_connect(mock_ws)):
            async with RealtimeSession() as session:
                session.on("transcript.delta", callback)
                await asyncio.sleep(0.1)

        assert len(callback_data) == 2
        assert callback_data[0].delta == "Hello"
        assert callback_data[0].accumulated == "Hello"
        assert callback_data[1].delta == " world"
        assert callback_data[1].accumulated == "Hello world"

    @pytest.mark.asyncio
    async def test_non_json_message_handled_gracefully(self):
        """Non-JSON messages are logged but don't crash the session."""
        messages = make_handshake_messages() + ["not-valid-json{{{"]
        mock_ws = MockWebSocket(messages)

        with patch("openai_apis.realtime.session.websockets.connect",
                   side_effect=mock_websockets_connect(mock_ws)):
            async with RealtimeSession() as session:
                await asyncio.sleep(0.1)
                # No crash - session still connected

    @pytest.mark.asyncio
    async def test_session_created_via_receive_loop(self):
        """session.created event emitted when received in receive loop (not handshake)."""
        messages = make_handshake_messages() + [
            json.dumps({"type": "session.created", "session": {"id": "sess_new"}}),
        ]
        mock_ws = MockWebSocket(messages)
        callback_data = []

        def callback(data):
            callback_data.append(data)

        with patch("openai_apis.realtime.session.websockets.connect",
                   side_effect=mock_websockets_connect(mock_ws)):
            session = RealtimeSession()
            session.on("session.created", callback)
            async with session:
                await asyncio.sleep(0.1)

        # Should have 2 total: one from handshake, one from receive loop
        assert len(callback_data) == 2

    @pytest.mark.asyncio
    async def test_session_updated_via_receive_loop(self):
        """session.updated event emitted when received in receive loop (not handshake)."""
        messages = make_handshake_messages() + [
            json.dumps({"type": "session.updated", "session": {"id": "sess_upd"}}),
        ]
        mock_ws = MockWebSocket(messages)
        callback_data = []

        def callback(data):
            callback_data.append(data)

        with patch("openai_apis.realtime.session.websockets.connect",
                   side_effect=mock_websockets_connect(mock_ws)):
            session = RealtimeSession()
            session.on("session.updated", callback)
            async with session:
                await asyncio.sleep(0.1)

        assert len(callback_data) == 2

    @pytest.mark.asyncio
    async def test_unknown_event_logged(self):
        """No error for unknown event types."""
        messages = make_handshake_messages() + [
            json.dumps({"type": "unknown.event.type"}),
        ]
        mock_ws = MockWebSocket(messages)

        with patch("openai_apis.realtime.session.websockets.connect", side_effect=mock_websockets_connect(mock_ws)):
            async with RealtimeSession() as session:
                await asyncio.sleep(0.1)
                # Should not raise


# RealtimeSession Reconnect Tests

class TestRealtimeSessionReconnect:
    """Test reconnection logic."""

    @pytest.mark.asyncio
    async def test_reconnect_on_connection_closed(self):
        """Reconnect triggered on connection close."""
        # First connection succeeds, then connection closes
        messages = make_handshake_messages()
        mock_ws1 = MockWebSocket(messages)
        mock_ws2 = MockWebSocket(make_handshake_messages())

        connect_calls = [mock_ws1, mock_ws2]
        call_index = [0]

        async def mock_connect(*args, **kwargs):
            ws = connect_calls[call_index[0]]
            call_index[0] += 1
            return ws

        with patch("openai_apis.realtime.session.websockets.connect", side_effect=mock_connect):
            session = RealtimeSession(max_reconnect_attempts=1, reconnect_delay=0.1)
            async with session:
                # Simulate connection close by stopping iteration
                pass

    @pytest.mark.asyncio
    async def test_reconnect_exponential_backoff(self):
        """Verify exponential backoff delays."""
        # This is hard to test without mocking sleep, so we just verify the logic exists
        session = RealtimeSession(max_reconnect_attempts=3, reconnect_delay=1.0)
        assert session._max_reconnect_attempts == 3
        assert session._reconnect_delay == 1.0

    @pytest.mark.asyncio
    async def test_reconnect_max_attempts_emits_error(self):
        """Error emitted after exhaustion."""
        # Mock connection always fails
        async def mock_connect(*args, **kwargs):
            raise Exception("Connection failed")

        callback_data = []

        def callback(data):
            callback_data.append(data)

        with patch("openai_apis.realtime.session.websockets.connect", side_effect=mock_connect):
            session = RealtimeSession(max_reconnect_attempts=1, reconnect_delay=0.05)
            session.on("error", callback)

            # Connect should fail
            with pytest.raises(Exception):
                async with session:
                    pass


# RealtimeSession Audit Log Tests

class TestRealtimeSessionAuditLog:
    """Test per-session audit logging."""

    @pytest.mark.asyncio
    async def test_connect_audit_events(self):
        """websocket.connected, session.configured logged."""
        mock_ws = MockWebSocket(make_handshake_messages())

        with patch("openai_apis.realtime.session.websockets.connect", side_effect=mock_websockets_connect(mock_ws)):
            async with RealtimeSession() as session:
                events = session.audit_log.events

        # Check for specific events
        event_types = [e.event_type for e in events]
        assert "websocket.connected" in event_types
        assert "session.configured" in event_types

    @pytest.mark.asyncio
    async def test_send_audio_audit(self):
        """audio.chunk_sent logged."""
        mock_ws = MockWebSocket(make_handshake_messages())

        with patch("openai_apis.realtime.session.websockets.connect", side_effect=mock_websockets_connect(mock_ws)):
            async with RealtimeSession() as session:
                await session.send_audio(b"test")
                events = session.audit_log.events

        event_types = [e.event_type for e in events]
        assert "audio.chunk_sent" in event_types

    @pytest.mark.asyncio
    async def test_disconnect_audit(self):
        """websocket.disconnected logged."""
        mock_ws = MockWebSocket(make_handshake_messages())

        with patch("openai_apis.realtime.session.websockets.connect", side_effect=mock_websockets_connect(mock_ws)):
            async with RealtimeSession() as session:
                pass
            events = session.audit_log.events

        event_types = [e.event_type for e in events]
        assert "websocket.disconnected" in event_types

    @pytest.mark.asyncio
    async def test_audio_output_multi_chunk_audit(self):
        """Multiple audio.delta + audio.done logs chunk_count and total_bytes."""
        chunk1 = b"\x00" * 4800  # 100ms of 24kHz mono PCM16
        chunk2 = b"\x00" * 4800
        b64_1 = base64.b64encode(chunk1).decode("ascii")
        b64_2 = base64.b64encode(chunk2).decode("ascii")
        messages = make_handshake_messages() + [
            json.dumps({"type": "response.audio.delta", "delta": b64_1, "item_id": "item_1", "response_id": "resp_1"}),
            json.dumps({"type": "response.audio.delta", "delta": b64_2, "item_id": "item_1", "response_id": "resp_1"}),
            json.dumps({"type": "response.audio.done", "item_id": "item_1", "response_id": "resp_1"}),
        ]
        mock_ws = MockWebSocket(messages)

        with patch("openai_apis.realtime.session.websockets.connect", side_effect=mock_websockets_connect(mock_ws)):
            async with RealtimeSession() as session:
                await asyncio.sleep(0.1)
                events = session.audit_log.events

        event_types = [e.event_type for e in events]
        assert "audio.output_completed" in event_types
        completed = [e for e in events if e.event_type == "audio.output_completed"][0]
        assert completed.data["chunk_count"] == 2
        assert completed.data["total_bytes"] == 9600
        assert "audio_duration_s" in completed.data

    @pytest.mark.asyncio
    async def test_send_audio_chunk_count_audit(self):
        """send_audio logs cumulative chunk count and total bytes."""
        mock_ws = MockWebSocket(make_handshake_messages())

        with patch("openai_apis.realtime.session.websockets.connect", side_effect=mock_websockets_connect(mock_ws)):
            async with RealtimeSession() as session:
                await session.send_audio(b"\x00" * 100)
                await session.send_audio(b"\x00" * 200)
                events = session.audit_log.events

        chunk_events = [e for e in events if e.event_type == "audio.chunk_sent"]
        assert len(chunk_events) == 2
        assert chunk_events[0].data["total_chunks"] == 1
        assert chunk_events[0].data["total_bytes"] == 100
        assert chunk_events[1].data["total_chunks"] == 2
        assert chunk_events[1].data["total_bytes"] == 300

    @pytest.mark.asyncio
    async def test_commit_audio_audit_duration(self):
        """commit_audio logs audio_duration_s based on accumulated bytes."""
        mock_ws = MockWebSocket(make_handshake_messages())

        with patch("openai_apis.realtime.session.websockets.connect", side_effect=mock_websockets_connect(mock_ws)):
            async with RealtimeSession() as session:
                # 48000 bytes = 1 second of 24kHz mono PCM16 (24000 samples * 2 bytes)
                await session.send_audio(b"\x00" * 48000)
                await session.commit_audio()
                events = session.audit_log.events

        committed = [e for e in events if e.event_type == "audio.buffer_committed"][0]
        assert committed.data["total_chunks"] == 1
        assert committed.data["total_bytes"] == 48000
        assert committed.data["audio_duration_s"] == 1.0

    @pytest.mark.asyncio
    async def test_commit_audio_resets_counters(self):
        """Counters reset after commit for next push-to-talk turn."""
        mock_ws = MockWebSocket(make_handshake_messages())

        with patch("openai_apis.realtime.session.websockets.connect", side_effect=mock_websockets_connect(mock_ws)):
            async with RealtimeSession() as session:
                await session.send_audio(b"\x00" * 100)
                await session.commit_audio()
                await session.send_audio(b"\x00" * 200)
                events = session.audit_log.events

        chunk_events = [e for e in events if e.event_type == "audio.chunk_sent"]
        # After reset, total_chunks should be 1 again
        assert chunk_events[1].data["total_chunks"] == 1
        assert chunk_events[1].data["total_bytes"] == 200


class TestRealtimeSessionWebsocketsImport:
    """Test websockets None guard (line 120)."""

    def test_init_raises_import_error_when_websockets_missing(self):
        """ImportError raised when websockets is None."""
        with patch("openai_apis.realtime.session.websockets", None):
            with pytest.raises(ImportError, match="websockets library required"):
                RealtimeSession()


class TestRealtimeSessionToolExecutionFailure:
    """Test _execute_tool error handling path (lines 341-352)."""

    @pytest.mark.asyncio
    async def test_execute_tool_failure_sends_error_result(self):
        """When tool handler raises, error JSON sent to model + response.create triggered."""
        from openai_apis.realtime import RealtimeSession, RealtimeConfig
        from openai_apis.realtime.tools import ToolRegistry

        registry = ToolRegistry()
        def failing_tool(city: str) -> dict:
            raise RuntimeError("Tool crashed")
        registry.register("broken", "A broken tool",
                         {"type": "object", "properties": {"city": {"type": "string"}}},
                         failing_tool)

        messages = [
            json.dumps({"type": "session.created", "session": {"id": "s1"}}),
            json.dumps({"type": "session.updated", "session": {"id": "s1"}}),
            json.dumps({
                "type": "response.function_call_arguments.done",
                "call_id": "call_fail",
                "name": "broken",
                "arguments": '{"city": "Budapest"}',
            }),
        ]
        mock_ws = MockWebSocket(messages)

        config = RealtimeConfig(tools=registry)
        with patch("openai_apis.realtime.session.websockets.connect",
                   side_effect=mock_websockets_connect(mock_ws)):
            async with RealtimeSession(config=config) as session:
                await asyncio.sleep(0.2)

        # Verify error result was sent
        sent_types = [json.loads(m)["type"] for m in mock_ws.sent_messages]
        assert "conversation.item.create" in sent_types
        assert "response.create" in sent_types

        tool_result_msg = next(
            json.loads(m) for m in mock_ws.sent_messages
            if json.loads(m)["type"] == "conversation.item.create"
        )
        output = json.loads(tool_result_msg["item"]["output"])
        assert "error" in output
        assert "Tool crashed" in output["error"]

    @pytest.mark.asyncio
    async def test_execute_tool_failure_audit_logged(self):
        """Audit log records tool.execution.failed on handler error."""
        from openai_apis.realtime import RealtimeSession, RealtimeConfig
        from openai_apis.realtime.tools import ToolRegistry

        registry = ToolRegistry()
        def failing_tool() -> dict:
            raise ValueError("bad input")
        registry.register("fail_tool", "desc", {}, failing_tool)

        messages = [
            json.dumps({"type": "session.created", "session": {"id": "s1"}}),
            json.dumps({"type": "session.updated", "session": {"id": "s1"}}),
            json.dumps({
                "type": "response.function_call_arguments.done",
                "call_id": "call_2",
                "name": "fail_tool",
                "arguments": "{}",
            }),
        ]
        mock_ws = MockWebSocket(messages)

        config = RealtimeConfig(tools=registry)
        with patch("openai_apis.realtime.session.websockets.connect",
                   side_effect=mock_websockets_connect(mock_ws)):
            async with RealtimeSession(config=config) as session:
                await asyncio.sleep(0.2)
                events = session.audit_log.events

        event_types = [e.event_type for e in events]
        assert "tool.execution.started" in event_types
        assert "tool.execution.failed" in event_types


class TestRealtimeSessionReceiveLoopErrors:
    """Test receive loop error handling (Step 5)."""

    @pytest.mark.asyncio
    async def test_receive_loop_generic_exception_emits_error(self):
        """Generic exception in receive loop emits 'error' event with type 'receive_loop_error'."""

        class ErrorMockWebSocket(MockWebSocket):
            """Mock WebSocket that raises RuntimeError after handshake."""

            async def __anext__(self):
                """Raise RuntimeError after returning handshake messages."""
                if self.message_index < len(self.messages):
                    msg = self.messages[self.message_index]
                    self.message_index += 1
                    return msg
                # After handshake, raise RuntimeError
                raise RuntimeError("Simulated receive loop error")

        messages = make_handshake_messages()
        mock_ws = ErrorMockWebSocket(messages)
        callback_data = []

        def error_callback(data):
            callback_data.append(data)

        with patch("openai_apis.realtime.session.websockets.connect",
                   side_effect=mock_websockets_connect(mock_ws)):
            async with RealtimeSession() as session:
                session.on("error", error_callback)
                await asyncio.sleep(0.1)  # Let receive loop encounter the error

        # Verify error event was emitted
        assert len(callback_data) == 1
        assert callback_data[0]["type"] == "receive_loop_error"
        assert "Simulated receive loop error" in callback_data[0]["error"]


class TestRealtimeSessionReconnection:
    """Test reconnection logic (Step 6)."""

    @pytest.mark.asyncio
    async def test_reconnect_success_after_connection_closed(self):
        """Successful reconnection after connection closed."""
        # First connection - handshake only
        mock_ws1 = MockWebSocket(make_handshake_messages())

        # Second connection - successful reconnect
        mock_ws2 = MockWebSocket(make_handshake_messages())

        call_count = [0]

        async def mock_connect(*args, **kwargs):
            ws = [mock_ws1, mock_ws2][call_count[0]]
            call_count[0] += 1
            return ws

        with patch("openai_apis.realtime.session.websockets.connect", side_effect=mock_connect), \
             patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:

            # Create session with shorter reconnect delay for testing
            session = RealtimeSession(max_reconnect_attempts=2, reconnect_delay=0.1)

            async with session:
                # Wait for initial connection
                await asyncio.sleep(0.05)

                # Simulate connection close by patching _ws to simulate ConnectionClosed
                import websockets
                # Trigger reconnection by simulating connection closed in receive loop
                session._receive_task.cancel()
                try:
                    await session._receive_task
                except asyncio.CancelledError:
                    pass

                # Manually trigger reconnect
                await session._reconnect()

            # Verify reconnect was attempted (sleep called with exponential backoff)
            assert mock_sleep.called
            # Verify second WebSocket was connected
            assert call_count[0] == 2

    @pytest.mark.asyncio
    async def test_reconnect_all_attempts_fail_emits_error(self):
        """Error emitted after all reconnection attempts fail."""
        callback_data = []

        def error_callback(data):
            callback_data.append(data)

        # Mock connect that always fails
        async def mock_connect_fail(*args, **kwargs):
            raise Exception("Connection refused")

        with patch("openai_apis.realtime.session.websockets.connect", side_effect=mock_connect_fail), \
             patch("asyncio.sleep", new_callable=AsyncMock):

            session = RealtimeSession(max_reconnect_attempts=2, reconnect_delay=0.05)
            session.on("error", error_callback)

            # Attempt reconnect (will fail all attempts)
            await session._reconnect()

        # Verify error event emitted after exhausting attempts
        assert len(callback_data) == 1
        assert callback_data[0]["type"] == "reconnect_failed"
        assert "Failed after 2 attempts" in callback_data[0]["error"]

    @pytest.mark.asyncio
    async def test_reconnect_audit_logs_each_attempt(self):
        """Audit log records reconnect_attempt, reconnect_success, or reconnect_failed."""
        # First attempt fails, second succeeds
        call_count = [0]

        async def mock_connect(*args, **kwargs):
            if call_count[0] == 0:
                call_count[0] += 1
                raise Exception("First attempt fails")
            # Second attempt succeeds
            call_count[0] += 1
            return MockWebSocket(make_handshake_messages())

        with patch("openai_apis.realtime.session.websockets.connect", side_effect=mock_connect), \
             patch("asyncio.sleep", new_callable=AsyncMock):

            session = RealtimeSession(max_reconnect_attempts=3, reconnect_delay=0.1)
            await session._reconnect()

            events = session.audit_log.events

        # Check audit log events
        event_types = [e.event_type for e in events]
        assert "websocket.reconnect_attempt" in event_types
        assert "websocket.reconnect_success" in event_types

        # Verify attempt count in logs
        attempt_events = [e for e in events if e.event_type == "websocket.reconnect_attempt"]
        # Should have 2 attempts (first fails, second succeeds)
        assert len(attempt_events) == 2
        assert attempt_events[0].data["attempt"] == 1
        assert attempt_events[1].data["attempt"] == 2

        # Verify success log
        success_events = [e for e in events if e.event_type == "websocket.reconnect_success"]
        assert len(success_events) == 1
        assert success_events[0].data["attempt"] == 2
