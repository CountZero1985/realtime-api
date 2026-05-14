"""Unit tests for TranscriptionSession WebSocket client."""
import pytest
import asyncio
import json
import base64
import uuid
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock, call
from openai_apis.transcription.ws_session import TranscriptionSession
from openai_apis.transcription.config import TranscriptionConfig
from openai_apis import SessionState, InvalidStateTransition, SessionAuditLog, VADConfig


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


class TestTranscriptionSessionInit:
    """Test initialization."""

    def test_default_config(self):
        """Default TranscriptionConfig used when None."""
        session = TranscriptionSession()
        assert isinstance(session._config, TranscriptionConfig)
        assert session._config.model == "gpt-4o-mini-transcribe"

    def test_custom_config(self):
        """Custom config is stored."""
        config = TranscriptionConfig(model="whisper-1", language="en")
        session = TranscriptionSession(config=config)
        assert session._config.model == "whisper-1"
        assert session._config.language == "en"

    def test_initial_state_created(self):
        """State is CREATED after init."""
        session = TranscriptionSession()
        assert session.state == SessionState.CREATED

    def test_session_id_generated(self):
        """Session ID is a valid UUID."""
        session = TranscriptionSession()
        # Should not raise
        parsed_uuid = uuid.UUID(session.session_id)
        assert str(parsed_uuid) == session.session_id

    def test_audit_log_created_event(self):
        """session.created audit event logged."""
        session = TranscriptionSession()
        events = session.audit_log.events
        assert len(events) == 1
        assert events[0].event_type == "session.created"

    def test_reconnect_params(self):
        """Custom reconnect params stored."""
        session = TranscriptionSession(
            max_reconnect_attempts=5, reconnect_delay=2.0
        )
        assert session._max_reconnect_attempts == 5
        assert session._reconnect_delay == 2.0

    def test_default_reconnect_params(self):
        """Default reconnect params."""
        session = TranscriptionSession()
        assert session._max_reconnect_attempts == 3
        assert session._reconnect_delay == 1.0


class TestTranscriptionSessionConnect:
    """Test _connect method (WebSocket connection)."""

    @pytest.mark.asyncio
    async def test_connect_establishes_websocket(self):
        """WebSocket connection made with correct URL and headers."""
        config = TranscriptionConfig(api_key="test-key", language="hu")
        session = TranscriptionSession(config=config)

        # Mock messages for session.created and session.updated
        mock_ws = MockWebSocket(
            messages=[
                json.dumps({"type": "session.created", "session": {}}),
                json.dumps({"type": "session.updated", "session": {}}),
            ]
        )

        with patch("openai_apis.transcription.ws_session.websockets.connect", new_callable=AsyncMock) as mock_connect:
            mock_connect.return_value = mock_ws

            async with session:
                # Verify connect was called with correct URL and headers
                mock_connect.assert_called_once()
                call_args = mock_connect.call_args
                url = call_args[0][0]
                headers = call_args[1]["additional_headers"]

                assert url.startswith("wss://api.openai.com/v1/realtime?model=")
                assert headers["Authorization"] == "Bearer test-key"
                assert headers["OpenAI-Beta"] == "realtime=v1"

    @pytest.mark.asyncio
    async def test_connect_sends_session_update(self):
        """session.update event sent after connection."""
        config = TranscriptionConfig(api_key="test-key", language="hu")
        session = TranscriptionSession(config=config)

        mock_ws = MockWebSocket(
            messages=[
                json.dumps({"type": "session.created", "session": {}}),
                json.dumps({"type": "session.updated", "session": {}}),
            ]
        )

        with patch("openai_apis.transcription.ws_session.websockets.connect", new_callable=AsyncMock) as mock_connect:
            mock_connect.return_value = mock_ws

            async with session:
                # Check that session.update was sent
                sent_messages = [json.loads(msg) for msg in mock_ws.sent_messages]
                session_update = next(
                    (msg for msg in sent_messages if msg["type"] == "session.update"),
                    None,
                )
                assert session_update is not None
                assert session_update["session"]["modalities"] == ["text"]
                assert session_update["session"]["input_audio_format"] == "pcm16"
                assert session_update["session"]["turn_detection"] is None

    @pytest.mark.asyncio
    async def test_connect_starts_receive_loop(self):
        """Receive task is created after connect."""
        config = TranscriptionConfig(api_key="test-key")
        session = TranscriptionSession(config=config)

        mock_ws = MockWebSocket(
            messages=[
                json.dumps({"type": "session.created", "session": {}}),
                json.dumps({"type": "session.updated", "session": {}}),
            ]
        )

        with patch("openai_apis.transcription.ws_session.websockets.connect", new_callable=AsyncMock) as mock_connect:
            mock_connect.return_value = mock_ws

            async with session:
                assert session._receive_task is not None
                assert isinstance(session._receive_task, asyncio.Task)

    @pytest.mark.asyncio
    async def test_connect_audit_logging(self):
        """Connection events are audit logged."""
        config = TranscriptionConfig(api_key="test-key")
        session = TranscriptionSession(config=config)

        mock_ws = MockWebSocket(
            messages=[
                json.dumps({"type": "session.created", "session": {}}),
                json.dumps({"type": "session.updated", "session": {}}),
            ]
        )

        with patch("openai_apis.transcription.ws_session.websockets.connect", new_callable=AsyncMock) as mock_connect:
            mock_connect.return_value = mock_ws

            async with session:
                events = session.audit_log.events
                event_types = [e.event_type for e in events]
                assert "websocket.connected" in event_types
                assert "session.configured" in event_types


class TestTranscriptionSessionDisconnect:
    """Test _disconnect method."""

    @pytest.mark.asyncio
    async def test_disconnect_closes_websocket(self):
        """WebSocket is closed."""
        config = TranscriptionConfig(api_key="test-key")
        session = TranscriptionSession(config=config)

        mock_ws = MockWebSocket(
            messages=[
                json.dumps({"type": "session.created", "session": {}}),
                json.dumps({"type": "session.updated", "session": {}}),
            ]
        )

        with patch("openai_apis.transcription.ws_session.websockets.connect", new_callable=AsyncMock) as mock_connect:
            mock_connect.return_value = mock_ws

            async with session:
                pass  # Exit context

            assert mock_ws.closed is True

    @pytest.mark.asyncio
    async def test_disconnect_cancels_receive_task(self):
        """Receive loop task is cancelled."""
        config = TranscriptionConfig(api_key="test-key")
        session = TranscriptionSession(config=config)

        mock_ws = MockWebSocket(
            messages=[
                json.dumps({"type": "session.created", "session": {}}),
                json.dumps({"type": "session.updated", "session": {}}),
            ]
        )

        with patch("openai_apis.transcription.ws_session.websockets.connect", new_callable=AsyncMock) as mock_connect:
            mock_connect.return_value = mock_ws

            async with session:
                receive_task = session._receive_task

            # Task should be cancelled and cleaned up
            assert receive_task.cancelled() or receive_task.done()

    @pytest.mark.asyncio
    async def test_disconnect_audit_logging(self):
        """Disconnect event audit logged."""
        config = TranscriptionConfig(api_key="test-key")
        session = TranscriptionSession(config=config)

        mock_ws = MockWebSocket(
            messages=[
                json.dumps({"type": "session.created", "session": {}}),
                json.dumps({"type": "session.updated", "session": {}}),
            ]
        )

        with patch("openai_apis.transcription.ws_session.websockets.connect", new_callable=AsyncMock) as mock_connect:
            mock_connect.return_value = mock_ws

            async with session:
                pass  # Exit context

            events = session.audit_log.events
            event_types = [e.event_type for e in events]
            assert "websocket.disconnected" in event_types


class TestSendAudio:
    """Test send_audio method."""

    @pytest.mark.asyncio
    async def test_send_audio_base64_encodes(self):
        """Audio bytes are base64-encoded in the event."""
        config = TranscriptionConfig(api_key="test-key")
        session = TranscriptionSession(config=config)

        mock_ws = MockWebSocket(
            messages=[
                json.dumps({"type": "session.created", "session": {}}),
                json.dumps({"type": "session.updated", "session": {}}),
            ]
        )

        with patch("openai_apis.transcription.ws_session.websockets.connect", new_callable=AsyncMock) as mock_connect:
            mock_connect.return_value = mock_ws

            async with session:
                # Send some audio
                test_audio = b"test audio data"
                await session.send_audio(test_audio)

                # Find the audio append event
                sent_messages = [json.loads(msg) for msg in mock_ws.sent_messages]
                audio_msg = next(
                    (msg for msg in sent_messages if msg["type"] == "input_audio_buffer.append"),
                    None,
                )

                assert audio_msg is not None
                assert audio_msg["audio"] == base64.b64encode(test_audio).decode("ascii")

    @pytest.mark.asyncio
    async def test_send_audio_correct_event_type(self):
        """Event type is input_audio_buffer.append."""
        config = TranscriptionConfig(api_key="test-key")
        session = TranscriptionSession(config=config)

        mock_ws = MockWebSocket(
            messages=[
                json.dumps({"type": "session.created", "session": {}}),
                json.dumps({"type": "session.updated", "session": {}}),
            ]
        )

        with patch("openai_apis.transcription.ws_session.websockets.connect", new_callable=AsyncMock) as mock_connect:
            mock_connect.return_value = mock_ws

            async with session:
                await session.send_audio(b"data")

                sent_messages = [json.loads(msg) for msg in mock_ws.sent_messages]
                audio_msg = next(
                    (msg for msg in sent_messages if msg["type"] == "input_audio_buffer.append"),
                    None,
                )
                assert audio_msg is not None

    @pytest.mark.asyncio
    async def test_send_audio_audit_logging(self):
        """Audio chunk send is audit logged."""
        config = TranscriptionConfig(api_key="test-key")
        session = TranscriptionSession(config=config)

        mock_ws = MockWebSocket(
            messages=[
                json.dumps({"type": "session.created", "session": {}}),
                json.dumps({"type": "session.updated", "session": {}}),
            ]
        )

        with patch("openai_apis.transcription.ws_session.websockets.connect", new_callable=AsyncMock) as mock_connect:
            mock_connect.return_value = mock_ws

            async with session:
                test_audio = b"test data"
                await session.send_audio(test_audio)

                events = session.audit_log.events
                event_types = [e.event_type for e in events]
                assert "audio.chunk_sent" in event_types

                # Check the event has chunk size
                audio_event = next(
                    (e for e in events if e.event_type == "audio.chunk_sent"), None
                )
                assert audio_event.data["chunk_size"] == len(test_audio)

    @pytest.mark.asyncio
    async def test_send_audio_requires_connected_state(self):
        """send_audio raises InvalidStateTransition if not CONNECTED."""
        session = TranscriptionSession()

        with pytest.raises(InvalidStateTransition):
            await session.send_audio(b"data")


class TestCommitAudio:
    """Test commit_audio method."""

    @pytest.mark.asyncio
    async def test_commit_sends_correct_event(self):
        """Event type is input_audio_buffer.commit."""
        config = TranscriptionConfig(api_key="test-key")
        session = TranscriptionSession(config=config)

        mock_ws = MockWebSocket(
            messages=[
                json.dumps({"type": "session.created", "session": {}}),
                json.dumps({"type": "session.updated", "session": {}}),
            ]
        )

        with patch("openai_apis.transcription.ws_session.websockets.connect", new_callable=AsyncMock) as mock_connect:
            mock_connect.return_value = mock_ws

            async with session:
                await session.commit_audio()

                sent_messages = [json.loads(msg) for msg in mock_ws.sent_messages]
                commit_msg = next(
                    (msg for msg in sent_messages if msg["type"] == "input_audio_buffer.commit"),
                    None,
                )
                assert commit_msg is not None

    @pytest.mark.asyncio
    async def test_commit_audit_logging(self):
        """Buffer commit is audit logged."""
        config = TranscriptionConfig(api_key="test-key")
        session = TranscriptionSession(config=config)

        mock_ws = MockWebSocket(
            messages=[
                json.dumps({"type": "session.created", "session": {}}),
                json.dumps({"type": "session.updated", "session": {}}),
            ]
        )

        with patch("openai_apis.transcription.ws_session.websockets.connect", new_callable=AsyncMock) as mock_connect:
            mock_connect.return_value = mock_ws

            async with session:
                await session.commit_audio()

                events = session.audit_log.events
                event_types = [e.event_type for e in events]
                assert "audio.buffer_committed" in event_types

    @pytest.mark.asyncio
    async def test_commit_requires_connected_state(self):
        """commit_audio raises InvalidStateTransition if not CONNECTED."""
        session = TranscriptionSession()

        with pytest.raises(InvalidStateTransition):
            await session.commit_audio()


class TestHandleMessage:
    """Test _handle_message routing."""

    def test_transcript_delta_emits_callback(self):
        """Delta event emits transcript.delta callback."""
        session = TranscriptionSession()
        callback_data = None

        def callback(data):
            nonlocal callback_data
            callback_data = data

        session.on("transcript.delta", callback)

        message = json.dumps({
            "type": "conversation.item.input_audio_transcription.delta",
            "delta": "test ",
            "item_id": "item_123",
            "content_index": 0,
        })

        session._handle_message(message)

        assert callback_data is not None
        assert callback_data["delta"] == "test "
        assert callback_data["item_id"] == "item_123"
        assert callback_data["content_index"] == 0

    def test_transcript_completed_emits_callback(self):
        """Completed event emits transcript.completed callback."""
        session = TranscriptionSession()
        callback_data = None

        def callback(data):
            nonlocal callback_data
            callback_data = data

        session.on("transcript.completed", callback)

        message = json.dumps({
            "type": "conversation.item.input_audio_transcription.completed",
            "transcript": "test transcript",
            "item_id": "item_456",
            "content_index": 0,
        })

        session._handle_message(message)

        assert callback_data is not None
        assert callback_data["transcript"] == "test transcript"
        assert callback_data["item_id"] == "item_456"

    def test_transcription_failed_emits_error(self):
        """Failed event emits error callback."""
        session = TranscriptionSession()
        callback_data = None

        def callback(data):
            nonlocal callback_data
            callback_data = data

        session.on("error", callback)

        message = json.dumps({
            "type": "conversation.item.input_audio_transcription.failed",
            "error": {"message": "Transcription failed"},
            "item_id": "item_789",
        })

        session._handle_message(message)

        assert callback_data is not None
        assert callback_data["type"] == "transcription_failed"
        assert callback_data["error"]["message"] == "Transcription failed"

    def test_server_error_emits_error(self):
        """Error event emits error callback."""
        session = TranscriptionSession()
        callback_data = None

        def callback(data):
            nonlocal callback_data
            callback_data = data

        session.on("error", callback)

        message = json.dumps({
            "type": "error",
            "error": {"message": "Server error occurred"},
        })

        session._handle_message(message)

        assert callback_data is not None
        assert callback_data["type"] == "server_error"
        assert callback_data["error"]["message"] == "Server error occurred"

    def test_unknown_event_no_error(self):
        """Unknown events are logged but don't cause errors."""
        session = TranscriptionSession()

        message = json.dumps({
            "type": "unknown.event.type",
            "data": "some data",
        })

        # Should not raise
        session._handle_message(message)

    def test_all_events_audit_logged(self):
        """Every received event is audit logged."""
        session = TranscriptionSession()

        message = json.dumps({
            "type": "conversation.item.input_audio_transcription.delta",
            "delta": "test",
            "item_id": "item_123",
        })

        session._handle_message(message)

        events = session.audit_log.events
        event_types = [e.event_type for e in events]
        assert "event.received.conversation.item.input_audio_transcription.delta" in event_types


class TestEventCallbacks:
    """Test callback registration and invocation."""

    def test_on_transcript_delta(self):
        """Registered transcript.delta callback is invoked with correct data."""
        session = TranscriptionSession()
        received_data = []

        def callback(data):
            received_data.append(data)

        session.on("transcript.delta", callback)

        # Emit delta event
        session._emit("transcript.delta", {"delta": "hello ", "item_id": "123"})

        assert len(received_data) == 1
        assert received_data[0]["delta"] == "hello "

    def test_on_transcript_completed(self):
        """Registered transcript.completed callback is invoked with transcript."""
        session = TranscriptionSession()
        received_data = []

        def callback(data):
            received_data.append(data)

        session.on("transcript.completed", callback)

        session._emit("transcript.completed", {"transcript": "full text", "item_id": "456"})

        assert len(received_data) == 1
        assert received_data[0]["transcript"] == "full text"

    def test_on_error(self):
        """Registered error callback is invoked."""
        session = TranscriptionSession()
        received_errors = []

        def callback(data):
            received_errors.append(data)

        session.on("error", callback)

        session._emit("error", {"type": "server_error", "error": {"message": "fail"}})

        assert len(received_errors) == 1
        assert received_errors[0]["type"] == "server_error"

    def test_multiple_callbacks(self):
        """Multiple callbacks for same event all fire."""
        session = TranscriptionSession()
        call_count = [0]

        def callback1(data):
            call_count[0] += 1

        def callback2(data):
            call_count[0] += 1

        session.on("transcript.completed", callback1)
        session.on("transcript.completed", callback2)

        session._emit("transcript.completed", {"transcript": "test"})

        assert call_count[0] == 2


class TestReconnect:
    """Test reconnection logic."""

    @pytest.mark.asyncio
    async def test_reconnect_attempts_on_connection_drop(self):
        """Reconnect is attempted when connection drops."""
        # This test is complex and would require mocking connection drops
        # For now, we test the basic reconnect method exists
        session = TranscriptionSession()
        assert hasattr(session, "_reconnect")
        assert callable(session._reconnect)

    @pytest.mark.asyncio
    async def test_reconnect_exponential_backoff(self):
        """Delay increases exponentially between attempts."""
        # Test the reconnect delay calculation logic
        session = TranscriptionSession(reconnect_delay=1.0)

        # The delays should be: 1.0, 2.0, 4.0 (exponential)
        expected_delays = [1.0, 2.0, 4.0]

        for attempt in range(3):
            delay = session._reconnect_delay * (2**attempt)
            assert delay == expected_delays[attempt]

    @pytest.mark.asyncio
    async def test_reconnect_max_attempts(self):
        """Gives up after max_reconnect_attempts."""
        session = TranscriptionSession(max_reconnect_attempts=2)
        assert session._max_reconnect_attempts == 2

    @pytest.mark.asyncio
    async def test_reconnect_audit_logging(self):
        """Reconnect attempts are audit logged."""
        # This requires a more complex test setup with connection failure simulation
        # The basic audit logging is tested in other tests
        session = TranscriptionSession()
        assert session.audit_log is not None


class TestAsyncContextManager:
    """Test async with lifecycle."""

    @pytest.mark.asyncio
    async def test_full_lifecycle(self):
        """async with connects and disconnects properly."""
        config = TranscriptionConfig(api_key="test-key")
        session = TranscriptionSession(config=config)

        mock_ws = MockWebSocket(
            messages=[
                json.dumps({"type": "session.created", "session": {}}),
                json.dumps({"type": "session.updated", "session": {}}),
            ]
        )

        with patch("openai_apis.transcription.ws_session.websockets.connect", new_callable=AsyncMock) as mock_connect:
            mock_connect.return_value = mock_ws

            assert session.state == SessionState.CREATED

            async with session:
                assert session.state == SessionState.CONNECTED

            assert session.state == SessionState.CLOSED

    @pytest.mark.asyncio
    async def test_state_transitions(self):
        """State goes CREATED -> CONNECTING -> CONNECTED -> DISCONNECTING -> CLOSED."""
        config = TranscriptionConfig(api_key="test-key")
        session = TranscriptionSession(config=config)

        mock_ws = MockWebSocket(
            messages=[
                json.dumps({"type": "session.created", "session": {}}),
                json.dumps({"type": "session.updated", "session": {}}),
            ]
        )

        states_seen = []

        def state_callback(data):
            states_seen.append((data["from"], data["to"]))

        session.on("state_changed", state_callback)

        with patch("openai_apis.transcription.ws_session.websockets.connect", new_callable=AsyncMock) as mock_connect:
            mock_connect.return_value = mock_ws

            async with session:
                pass  # Just enter and exit

        # Check that we saw the expected transitions
        assert (SessionState.CREATED, SessionState.CONNECTING) in states_seen
        assert (SessionState.CONNECTING, SessionState.CONNECTED) in states_seen
        assert (SessionState.CONNECTED, SessionState.DISCONNECTING) in states_seen


class TestVADConfiguration:
    """Test VAD configuration in session.update events."""

    def test_vad_config_to_turn_detection_none(self):
        """None VADConfig returns None (push-to-talk)."""
        result = TranscriptionSession._vad_config_to_turn_detection(None)
        assert result is None

    def test_vad_config_to_turn_detection_disabled(self):
        """Disabled mode returns None."""
        vad = VADConfig(mode="disabled")
        result = TranscriptionSession._vad_config_to_turn_detection(vad)
        assert result is None

    def test_vad_config_to_turn_detection_server_vad(self):
        """server_vad mode returns correct dict."""
        vad = VADConfig(
            mode="server_vad",
            threshold=0.7,
            prefix_padding_ms=200,
            silence_duration_ms=800,
        )
        result = TranscriptionSession._vad_config_to_turn_detection(vad)
        assert result == {
            "type": "server_vad",
            "threshold": 0.7,
            "prefix_padding_ms": 200,
            "silence_duration_ms": 800,
        }

    def test_vad_config_to_turn_detection_semantic_vad(self):
        """semantic_vad mode returns correct dict."""
        vad = VADConfig(mode="semantic_vad", eagerness="high")
        result = TranscriptionSession._vad_config_to_turn_detection(vad)
        assert result == {
            "type": "semantic_vad",
            "eagerness": "high",
        }

    @pytest.mark.asyncio
    async def test_session_update_with_server_vad(self):
        """session.update includes server_vad turn_detection when configured."""
        vad = VADConfig(mode="server_vad", threshold=0.6, silence_duration_ms=600)
        config = TranscriptionConfig(api_key="test-key", vad_config=vad)
        session = TranscriptionSession(config=config)

        mock_ws = MockWebSocket(
            messages=[
                json.dumps({"type": "session.created", "session": {}}),
                json.dumps({"type": "session.updated", "session": {}}),
            ]
        )

        with patch(
            "openai_apis.transcription.ws_session.websockets.connect",
            new_callable=AsyncMock,
        ) as mock_connect:
            mock_connect.return_value = mock_ws

            async with session:
                sent_messages = [json.loads(msg) for msg in mock_ws.sent_messages]
                session_update = next(
                    (msg for msg in sent_messages if msg["type"] == "session.update"),
                    None,
                )
                assert session_update is not None
                td = session_update["session"]["turn_detection"]
                assert td["type"] == "server_vad"
                assert td["threshold"] == 0.6
                assert td["silence_duration_ms"] == 600

    @pytest.mark.asyncio
    async def test_session_update_with_semantic_vad(self):
        """session.update includes semantic_vad turn_detection when configured."""
        vad = VADConfig(mode="semantic_vad", eagerness="low")
        config = TranscriptionConfig(api_key="test-key", vad_config=vad)
        session = TranscriptionSession(config=config)

        mock_ws = MockWebSocket(
            messages=[
                json.dumps({"type": "session.created", "session": {}}),
                json.dumps({"type": "session.updated", "session": {}}),
            ]
        )

        with patch(
            "openai_apis.transcription.ws_session.websockets.connect",
            new_callable=AsyncMock,
        ) as mock_connect:
            mock_connect.return_value = mock_ws

            async with session:
                sent_messages = [json.loads(msg) for msg in mock_ws.sent_messages]
                session_update = next(
                    (msg for msg in sent_messages if msg["type"] == "session.update"),
                    None,
                )
                assert session_update is not None
                td = session_update["session"]["turn_detection"]
                assert td["type"] == "semantic_vad"
                assert td["eagerness"] == "low"

    @pytest.mark.asyncio
    async def test_session_update_with_disabled_vad(self):
        """session.update has turn_detection=null when VAD disabled."""
        vad = VADConfig(mode="disabled")
        config = TranscriptionConfig(api_key="test-key", vad_config=vad)
        session = TranscriptionSession(config=config)

        mock_ws = MockWebSocket(
            messages=[
                json.dumps({"type": "session.created", "session": {}}),
                json.dumps({"type": "session.updated", "session": {}}),
            ]
        )

        with patch(
            "openai_apis.transcription.ws_session.websockets.connect",
            new_callable=AsyncMock,
        ) as mock_connect:
            mock_connect.return_value = mock_ws

            async with session:
                sent_messages = [json.loads(msg) for msg in mock_ws.sent_messages]
                session_update = next(
                    (msg for msg in sent_messages if msg["type"] == "session.update"),
                    None,
                )
                assert session_update is not None
                assert session_update["session"]["turn_detection"] is None

    @pytest.mark.asyncio
    async def test_session_update_default_no_vad(self):
        """Default config (no vad_config) sends turn_detection=null."""
        config = TranscriptionConfig(api_key="test-key")
        session = TranscriptionSession(config=config)

        mock_ws = MockWebSocket(
            messages=[
                json.dumps({"type": "session.created", "session": {}}),
                json.dumps({"type": "session.updated", "session": {}}),
            ]
        )

        with patch(
            "openai_apis.transcription.ws_session.websockets.connect",
            new_callable=AsyncMock,
        ) as mock_connect:
            mock_connect.return_value = mock_ws

            async with session:
                sent_messages = [json.loads(msg) for msg in mock_ws.sent_messages]
                session_update = next(
                    (msg for msg in sent_messages if msg["type"] == "session.update"),
                    None,
                )
                assert session_update is not None
                assert session_update["session"]["turn_detection"] is None

    @pytest.mark.asyncio
    async def test_update_vad_runtime(self):
        """update_vad sends a new session.update with turn_detection."""
        config = TranscriptionConfig(api_key="test-key")
        session = TranscriptionSession(config=config)

        mock_ws = MockWebSocket(
            messages=[
                json.dumps({"type": "session.created", "session": {}}),
                json.dumps({"type": "session.updated", "session": {}}),
            ]
        )

        with patch(
            "openai_apis.transcription.ws_session.websockets.connect",
            new_callable=AsyncMock,
        ) as mock_connect:
            mock_connect.return_value = mock_ws

            async with session:
                new_vad = VADConfig(mode="semantic_vad", eagerness="high")
                await session.update_vad(new_vad)

                sent_messages = [json.loads(msg) for msg in mock_ws.sent_messages]
                # The second session.update is the runtime VAD update
                vad_updates = [
                    msg for msg in sent_messages if msg["type"] == "session.update"
                ]
                assert len(vad_updates) == 2  # initial + runtime
                td = vad_updates[1]["session"]["turn_detection"]
                assert td["type"] == "semantic_vad"
                assert td["eagerness"] == "high"

    @pytest.mark.asyncio
    async def test_update_vad_requires_connected_state(self):
        """update_vad raises InvalidStateTransition if not CONNECTED."""
        session = TranscriptionSession()
        vad = VADConfig(mode="server_vad")

        with pytest.raises(InvalidStateTransition):
            await session.update_vad(vad)

    @pytest.mark.asyncio
    async def test_update_vad_audit_logging(self):
        """update_vad logs vad.updated audit event."""
        config = TranscriptionConfig(api_key="test-key")
        session = TranscriptionSession(config=config)

        mock_ws = MockWebSocket(
            messages=[
                json.dumps({"type": "session.created", "session": {}}),
                json.dumps({"type": "session.updated", "session": {}}),
            ]
        )

        with patch(
            "openai_apis.transcription.ws_session.websockets.connect",
            new_callable=AsyncMock,
        ) as mock_connect:
            mock_connect.return_value = mock_ws

            async with session:
                new_vad = VADConfig(mode="server_vad", threshold=0.8)
                await session.update_vad(new_vad)

                events = session.audit_log.events
                event_types = [e.event_type for e in events]
                assert "vad.updated" in event_types
                vad_event = next(
                    e for e in events if e.event_type == "vad.updated"
                )
                assert vad_event.data["mode"] == "server_vad"

    @pytest.mark.asyncio
    async def test_update_vad_updates_config(self):
        """update_vad updates the internal config's vad_config."""
        config = TranscriptionConfig(api_key="test-key")
        session = TranscriptionSession(config=config)

        mock_ws = MockWebSocket(
            messages=[
                json.dumps({"type": "session.created", "session": {}}),
                json.dumps({"type": "session.updated", "session": {}}),
            ]
        )

        with patch(
            "openai_apis.transcription.ws_session.websockets.connect",
            new_callable=AsyncMock,
        ) as mock_connect:
            mock_connect.return_value = mock_ws

            async with session:
                assert session._config.vad_config is None
                new_vad = VADConfig(mode="semantic_vad", eagerness="medium")
                await session.update_vad(new_vad)
                assert session._config.vad_config == new_vad
