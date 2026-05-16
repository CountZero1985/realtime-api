# ADR-002: BaseSession Abstract Base Class

## Status
Accepted

## Context
Multiple modules (transcription, realtime) require WebSocket session management with similar patterns: connecting, disconnecting, state tracking, event callbacks, and audit logging. Without a shared base class, each module would independently implement:

- Session lifecycle (connect/disconnect)
- State machine (CREATED → CONNECTING → CONNECTED → DISCONNECTING → CLOSED)
- Async context manager support (`async with`)
- Event callback registration and emission
- Per-session audit logging
- UUID session ID generation

This leads to code duplication and inconsistent behavior across modules.

## Decision
Implement a `BaseSession` abstract base class in `_session.py` that provides:

1. **State machine** with `SessionState` enum and validated transitions
2. **Async context manager** (`__aenter__`/`__aexit__`) that calls `_connect()`/`_disconnect()`
3. **Event system** with `on(event, callback)` and `_emit(event, data)` methods
4. **Per-session audit log** via `session.audit_log` property
5. **Abstract methods** `_connect()` and `_disconnect()` that subclasses must implement
6. **`InvalidStateTransition`** exception for invalid state changes

Subclasses (TranscriptionSession, RealtimeSession) implement only the connection-specific logic.

```python
class BaseSession(ABC):
    # Provides: state, session_id, audit_log, on(), _emit()
    # Requires: _connect(), _disconnect()

async with TranscriptionSession(config) as session:
    # Automatically: CREATED → CONNECTING → CONNECTED
    pass
    # Automatically: CONNECTED → DISCONNECTING → CLOSED
```

## Consequences

**Easier:**
- Adding new session-based APIs (only implement `_connect`/`_disconnect`)
- Consistent lifecycle behavior across all sessions
- Centralized audit logging without per-module implementation
- Testing session behavior (mock the base class)

**More difficult:**
- All sessions share the same state machine (no custom states per module)
- Subclasses must be careful not to break the state machine contract
- The base class is a single point of failure for all session types
