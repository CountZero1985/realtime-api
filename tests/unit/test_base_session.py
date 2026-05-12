"""Unit tests for BaseSession class."""
import pytest
import uuid
from unittest.mock import patch, MagicMock, call
from openai_apis import BaseSession, SessionState, InvalidStateTransition, BaseConfig


class ConcreteSession(BaseSession):
    """Concrete implementation for testing."""

    def __init__(self, config=None, connect_error=None, disconnect_error=None):
        super().__init__(config)
        self.connect_called = False
        self.disconnect_called = False
        self._connect_error = connect_error
        self._disconnect_error = disconnect_error

    async def _connect(self) -> None:
        self.connect_called = True
        if self._connect_error:
            raise self._connect_error

    async def _disconnect(self) -> None:
        self.disconnect_called = True
        if self._disconnect_error:
            raise self._disconnect_error


class TestSessionState:
    """Test session state initialization and properties."""

    def test_initial_state_is_created(self):
        """After __init__, state is CREATED."""
        session = ConcreteSession()
        assert session.state == SessionState.CREATED

    def test_session_id_is_uuid(self):
        """session_id is a valid UUID4 string."""
        session = ConcreteSession()
        # Should not raise
        parsed_uuid = uuid.UUID(session.session_id)
        assert str(parsed_uuid) == session.session_id

    def test_session_id_unique(self):
        """Two sessions have different IDs."""
        session1 = ConcreteSession()
        session2 = ConcreteSession()
        assert session1.session_id != session2.session_id

    def test_config_defaults(self):
        """Default BaseConfig is used when None passed."""
        session = ConcreteSession(config=None)
        assert isinstance(session._config, BaseConfig)


class TestStateTransitions:
    """Test state transition validation."""

    def test_valid_transition_created_to_connecting(self):
        """Valid transition from CREATED to CONNECTING."""
        session = ConcreteSession()
        session._transition_to(SessionState.CONNECTING)
        assert session.state == SessionState.CONNECTING

    def test_valid_transition_connecting_to_connected(self):
        """Valid transition from CONNECTING to CONNECTED."""
        session = ConcreteSession()
        session._transition_to(SessionState.CONNECTING)
        session._transition_to(SessionState.CONNECTED)
        assert session.state == SessionState.CONNECTED

    def test_valid_transition_connected_to_disconnecting(self):
        """Valid transition from CONNECTED to DISCONNECTING."""
        session = ConcreteSession()
        session._transition_to(SessionState.CONNECTING)
        session._transition_to(SessionState.CONNECTED)
        session._transition_to(SessionState.DISCONNECTING)
        assert session.state == SessionState.DISCONNECTING

    def test_valid_transition_disconnecting_to_closed(self):
        """Valid transition from DISCONNECTING to CLOSED."""
        session = ConcreteSession()
        session._transition_to(SessionState.CONNECTING)
        session._transition_to(SessionState.CONNECTED)
        session._transition_to(SessionState.DISCONNECTING)
        session._transition_to(SessionState.CLOSED)
        assert session.state == SessionState.CLOSED

    def test_valid_transition_created_to_closed(self):
        """Direct close from CREATED is valid."""
        session = ConcreteSession()
        session._transition_to(SessionState.CLOSED)
        assert session.state == SessionState.CLOSED

    def test_invalid_transition_closed_to_connecting(self):
        """Invalid transition from CLOSED to CONNECTING raises exception."""
        session = ConcreteSession()
        session._transition_to(SessionState.CLOSED)
        with pytest.raises(InvalidStateTransition) as exc_info:
            session._transition_to(SessionState.CONNECTING)
        assert "closed" in str(exc_info.value).lower()
        assert "connecting" in str(exc_info.value).lower()

    def test_invalid_transition_connected_to_created(self):
        """Invalid transition from CONNECTED to CREATED raises exception."""
        session = ConcreteSession()
        session._transition_to(SessionState.CONNECTING)
        session._transition_to(SessionState.CONNECTED)
        with pytest.raises(InvalidStateTransition):
            session._transition_to(SessionState.CREATED)

    def test_invalid_transition_disconnecting_to_connected(self):
        """Invalid transition from DISCONNECTING to CONNECTED raises exception."""
        session = ConcreteSession()
        session._transition_to(SessionState.CONNECTING)
        session._transition_to(SessionState.CONNECTED)
        session._transition_to(SessionState.DISCONNECTING)
        with pytest.raises(InvalidStateTransition):
            session._transition_to(SessionState.CONNECTED)


class TestAsyncContextManager:
    """Test async context manager lifecycle."""

    async def test_aenter_connects_and_transitions(self):
        """State goes CREATED -> CONNECTING -> CONNECTED."""
        session = ConcreteSession()
        assert session.state == SessionState.CREATED

        returned = await session.__aenter__()

        assert session.connect_called
        assert session.state == SessionState.CONNECTED
        assert returned is session

    async def test_aexit_disconnects_and_closes(self):
        """State goes CONNECTED -> DISCONNECTING -> CLOSED."""
        session = ConcreteSession()
        await session.__aenter__()
        assert session.state == SessionState.CONNECTED

        await session.__aexit__(None, None, None)

        assert session.disconnect_called
        assert session.state == SessionState.CLOSED

    async def test_full_lifecycle_with_async_with(self):
        """Full lifecycle using async with."""
        session = ConcreteSession()

        async with session as s:
            assert s is session
            assert session.state == SessionState.CONNECTED
            assert session.connect_called

        assert session.disconnect_called
        assert session.state == SessionState.CLOSED

    async def test_connect_failure_sets_closed(self):
        """If _connect() raises, state is CLOSED."""
        error = RuntimeError("Connection failed")
        session = ConcreteSession(connect_error=error)

        with pytest.raises(RuntimeError, match="Connection failed"):
            await session.__aenter__()

        assert session.state == SessionState.CLOSED

    async def test_disconnect_failure_still_closes(self):
        """If _disconnect() raises, state is CLOSED (cleanup guaranteed)."""
        error = RuntimeError("Disconnect failed")
        session = ConcreteSession(disconnect_error=error)

        await session.__aenter__()

        with pytest.raises(RuntimeError, match="Disconnect failed"):
            await session.__aexit__(None, None, None)

        assert session.state == SessionState.CLOSED

    async def test_context_manager_returns_self(self):
        """__aenter__ returns the session instance."""
        session = ConcreteSession()
        returned = await session.__aenter__()
        assert returned is session
        await session.__aexit__(None, None, None)


class TestEventCallbacks:
    """Test event callback system."""

    def test_on_registers_callback(self):
        """Callback is stored."""
        session = ConcreteSession()
        callback = MagicMock()

        session.on("test_event", callback)

        assert "test_event" in session._callbacks
        assert callback in session._callbacks["test_event"]

    def test_emit_calls_registered_callbacks(self):
        """Callback is called with data."""
        session = ConcreteSession()
        callback = MagicMock()
        session.on("test_event", callback)

        data = {"key": "value"}
        session._emit("test_event", data)

        callback.assert_called_once_with(data)

    def test_emit_multiple_callbacks(self):
        """Multiple callbacks for same event are all called."""
        session = ConcreteSession()
        callback1 = MagicMock()
        callback2 = MagicMock()
        session.on("test_event", callback1)
        session.on("test_event", callback2)

        data = {"key": "value"}
        session._emit("test_event", data)

        callback1.assert_called_once_with(data)
        callback2.assert_called_once_with(data)

    def test_emit_no_callbacks(self):
        """No error when emitting unregistered event."""
        session = ConcreteSession()
        # Should not raise
        session._emit("unregistered_event", {"data": "test"})

    def test_callback_error_does_not_propagate(self):
        """Exception in callback is caught, logged."""
        session = ConcreteSession()

        def failing_callback(data):
            raise ValueError("Callback error")

        working_callback = MagicMock()

        session.on("test_event", failing_callback)
        session.on("test_event", working_callback)

        # Should not raise, but should still call working_callback
        session._emit("test_event", {"key": "value"})

        working_callback.assert_called_once()

    async def test_state_changed_event_emitted(self):
        """state_changed event fires on transition."""
        session = ConcreteSession()
        callback = MagicMock()
        session.on("state_changed", callback)

        session._transition_to(SessionState.CONNECTING)

        callback.assert_called_once()
        args = callback.call_args[0][0]
        assert args["from"] == SessionState.CREATED
        assert args["to"] == SessionState.CONNECTING


class TestAuditLogging:
    """Test audit logging integration."""

    @patch("openai_apis._session.log_audit_event")
    def test_session_created_audit_event(self, mock_log):
        """session_created audit event logged on init."""
        session = ConcreteSession()

        # Find the session_created call
        created_calls = [
            c for c in mock_log.call_args_list
            if c[1].get("action") == "session_created"
        ]
        assert len(created_calls) == 1

        call_kwargs = created_calls[0][1]
        assert call_kwargs["event_type"] == "session"
        assert call_kwargs["session_id"] == session.session_id
        assert "config_type" in call_kwargs["details"]

    @patch("openai_apis._session.log_audit_event")
    def test_state_transition_audit_event(self, mock_log):
        """state_transition audit event logged."""
        session = ConcreteSession()
        mock_log.reset_mock()  # Clear init call

        session._transition_to(SessionState.CONNECTING)

        # Find the state_transition call
        transition_calls = [
            c for c in mock_log.call_args_list
            if c[1].get("action") == "state_transition"
        ]
        assert len(transition_calls) == 1

        call_kwargs = transition_calls[0][1]
        assert call_kwargs["event_type"] == "session"
        assert call_kwargs["session_id"] == session.session_id
        assert call_kwargs["details"]["from"] == "created"
        assert call_kwargs["details"]["to"] == "connecting"

    @patch("openai_apis._session.log_audit_event")
    async def test_session_closed_audit_event(self, mock_log):
        """session_closed audit event logged on exit."""
        session = ConcreteSession()
        mock_log.reset_mock()  # Clear init calls

        async with session:
            pass

        # Find the session_closed call
        closed_calls = [
            c for c in mock_log.call_args_list
            if c[1].get("action") == "session_closed"
        ]
        assert len(closed_calls) == 1

        call_kwargs = closed_calls[0][1]
        assert call_kwargs["event_type"] == "session"
        assert call_kwargs["session_id"] == session.session_id
        assert call_kwargs["details"]["had_error"] is False
