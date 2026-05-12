"""Base session class for all API sessions with lifecycle management.

This module provides the BaseSession abstract class that all API sessions inherit from.
It implements a state machine for session lifecycle management, async context manager
support, event callbacks, and per-session audit logging.

Session State Machine:
    CREATED → CONNECTING → CONNECTED → DISCONNECTING → CLOSED

Valid transitions:
    - CREATED → CONNECTING (normal startup)
    - CREATED → CLOSED (direct close without connecting)
    - CONNECTING → CONNECTED (successful connection)
    - CONNECTING → CLOSED (connection failure)
    - CONNECTED → DISCONNECTING (normal shutdown)
    - CONNECTED → CLOSED (forced close)
    - DISCONNECTING → CLOSED (cleanup complete)
    - CLOSED → (terminal state, no transitions out)

Example:
    ```python
    class MySession(BaseSession):
        async def _connect(self):
            # Connection logic
            pass

        async def _disconnect(self):
            # Cleanup logic
            pass

    # Use with async context manager
    async with MySession() as session:
        # Session is CONNECTED
        print(session.session_id)
        # Use session...
    # Session is CLOSED
    ```
"""
import enum
import uuid
import logging
from abc import ABC, abstractmethod
from typing import Optional, Callable, Any
from openai_apis._config import BaseConfig
from openai_apis._logging import get_logger, log_audit_event


class SessionState(enum.Enum):
    """Session state enumeration for lifecycle management.

    States:
        CREATED: Initial state after construction
        CONNECTING: Connection establishment in progress
        CONNECTED: Session is active and ready for use
        DISCONNECTING: Cleanup/disconnection in progress
        CLOSED: Terminal state, session is closed
    """
    CREATED = "created"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    DISCONNECTING = "disconnecting"
    CLOSED = "closed"


class InvalidStateTransition(Exception):
    """Raised when an invalid session state transition is attempted.

    Example:
        Attempting to transition from CLOSED to any other state will raise this exception,
        as CLOSED is a terminal state with no valid outbound transitions.
    """
    pass


# Valid state transitions mapping - defines which state transitions are allowed.
# Each key is a current state, and the value is a set of allowed next states.
# CLOSED is terminal (empty set), meaning no transitions out of CLOSED are allowed.
_VALID_TRANSITIONS: dict[SessionState, set[SessionState]] = {
    SessionState.CREATED: {SessionState.CONNECTING, SessionState.CLOSED},
    SessionState.CONNECTING: {SessionState.CONNECTED, SessionState.CLOSED},
    SessionState.CONNECTED: {SessionState.DISCONNECTING, SessionState.CLOSED},
    SessionState.DISCONNECTING: {SessionState.CLOSED},
    SessionState.CLOSED: set(),  # terminal state, no transitions out
}


class BaseSession(ABC):
    """Base class for all API sessions with lifecycle management.

    Provides:
    - State machine with validation (SessionState enum)
    - Async context manager support (automatic connect/disconnect)
    - Automatic UUID session ID generation
    - Event callback system (on/emit pattern)
    - Per-session audit logging integration

    Subclasses must implement:
    - _connect(): Establish connection (called during __aenter__)
    - _disconnect(): Tear down connection (called during __aexit__)

    Attributes:
        session_id (str): Auto-generated UUID for this session.
        state (SessionState): Current session state.

    Events:
        - "state_changed": Emitted on state transitions with {"from": old, "to": new}
        - "closed": Emitted when session closes with {"session_id": str}
    """

    def __init__(self, config: Optional[BaseConfig] = None) -> None:
        """Initialize a new session.

        Args:
            config: Session configuration. If None, uses default BaseConfig.
        """
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
        """Enter async context manager, establishing connection.

        Transitions: CREATED → CONNECTING → CONNECTED
        If _connect() fails, state is set to CLOSED and exception propagates.

        Returns:
            Self for use in 'async with' statement.

        Raises:
            Exception: If _connect() raises, state is set to CLOSED.
        """
        self._transition_to(SessionState.CONNECTING)
        try:
            await self._connect()
            self._transition_to(SessionState.CONNECTED)
        except Exception:
            self._state = SessionState.CLOSED
            raise
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Exit async context manager, cleaning up connection.

        Transitions: CONNECTED → DISCONNECTING → CLOSED
        State is guaranteed to be CLOSED on exit, even if _disconnect() raises.
        Emits "closed" event and logs "session_closed" audit event.

        Args:
            exc_type: Exception type if an exception occurred in the context.
            exc_val: Exception value if an exception occurred.
            exc_tb: Exception traceback if an exception occurred.

        Returns:
            None (does not suppress exceptions).
        """
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
        """Establish connection. Called during __aenter__.

        Subclasses must implement this to perform connection setup.
        State will be CONNECTING when this is called.
        If this raises an exception, state will be set to CLOSED.
        """
        ...

    @abstractmethod
    async def _disconnect(self) -> None:
        """Tear down connection. Called during __aexit__.

        Subclasses must implement this to perform cleanup and disconnection.
        State will be DISCONNECTING when this is called.
        State is guaranteed to be CLOSED after this, even if it raises.
        """
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
