"""Base session class for all API sessions with lifecycle management."""
import enum
import uuid
import logging
from abc import ABC, abstractmethod
from typing import Optional, Callable, Any
from openai_apis._config import BaseConfig
from openai_apis._logging import get_logger, log_audit_event


class SessionState(enum.Enum):
    """Session state enumeration."""
    CREATED = "created"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    DISCONNECTING = "disconnecting"
    CLOSED = "closed"


class InvalidStateTransition(Exception):
    """Raised when an invalid session state transition is attempted."""
    pass


# Valid state transitions mapping
_VALID_TRANSITIONS: dict[SessionState, set[SessionState]] = {
    SessionState.CREATED: {SessionState.CONNECTING, SessionState.CLOSED},
    SessionState.CONNECTING: {SessionState.CONNECTED, SessionState.CLOSED},
    SessionState.CONNECTED: {SessionState.DISCONNECTING, SessionState.CLOSED},
    SessionState.DISCONNECTING: {SessionState.CLOSED},
    SessionState.CLOSED: set(),  # terminal state, no transitions out
}


class BaseSession(ABC):
    """Base class for all API sessions with lifecycle management."""

    def __init__(self, config: Optional[BaseConfig] = None) -> None:
        self._config: BaseConfig = config or BaseConfig()
        self._session_id: str = str(uuid.uuid4())
        self._state: SessionState = SessionState.CREATED
        self._callbacks: dict[str, list[Callable]] = {}
        self._logger: logging.Logger = get_logger(f"{self.__class__.__module__}.{self.__class__.__name__}")

        log_audit_event(
            event_type="session",
            action="session_created",
            session_id=self._session_id,
            details={"config_type": type(self._config).__name__},
        )

    @property
    def session_id(self) -> str:
        """Get the session ID."""
        return self._session_id

    @property
    def state(self) -> SessionState:
        """Get the current session state."""
        return self._state

    def _transition_to(self, new_state: SessionState) -> None:
        """Transition to a new state with validation.

        Args:
            new_state: The target state.

        Raises:
            InvalidStateTransition: If the transition is not allowed.
        """
        valid = _VALID_TRANSITIONS.get(self._state, set())
        if new_state not in valid:
            raise InvalidStateTransition(
                f"Cannot transition from {self._state.value} to {new_state.value}"
            )
        old_state = self._state
        self._state = new_state
        self._logger.debug(
            f"Session {self._session_id}: {old_state.value} -> {new_state.value}"
        )
        log_audit_event(
            event_type="session",
            action="state_transition",
            session_id=self._session_id,
            details={"from": old_state.value, "to": new_state.value},
        )
        self._emit("state_changed", {"from": old_state, "to": new_state})

    async def __aenter__(self) -> "BaseSession":
        """Enter async context manager."""
        self._transition_to(SessionState.CONNECTING)
        try:
            await self._connect()
            self._transition_to(SessionState.CONNECTED)
        except Exception:
            self._state = SessionState.CLOSED
            raise
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Exit async context manager."""
        try:
            if self._state == SessionState.CONNECTED:
                self._transition_to(SessionState.DISCONNECTING)
                await self._disconnect()
        finally:
            if self._state != SessionState.CLOSED:
                self._state = SessionState.CLOSED
            log_audit_event(
                event_type="session",
                action="session_closed",
                session_id=self._session_id,
                details={"had_error": exc_type is not None},
            )
            self._emit("closed", {"session_id": self._session_id})
        return None  # Don't suppress exceptions

    @abstractmethod
    async def _connect(self) -> None:
        """Establish connection. Called during __aenter__."""
        ...

    @abstractmethod
    async def _disconnect(self) -> None:
        """Tear down connection. Called during __aexit__."""
        ...

    def on(self, event: str, callback: Callable) -> None:
        """Register a callback for an event.

        Args:
            event: Event name.
            callback: Callable to invoke when event is emitted.
        """
        if event not in self._callbacks:
            self._callbacks[event] = []
        self._callbacks[event].append(callback)

    def _emit(self, event: str, data: Any = None) -> None:
        """Emit an event, calling all registered callbacks.

        Args:
            event: Event name.
            data: Data to pass to callbacks.
        """
        for cb in self._callbacks.get(event, []):
            try:
                cb(data)
            except Exception as e:
                self._logger.warning(
                    f"Callback error for event '{event}': {e}",
                    exc_info=True,
                )
