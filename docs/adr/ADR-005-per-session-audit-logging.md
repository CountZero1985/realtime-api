# ADR-005: Per-Session Audit Logging

## Status
Accepted

## Context
The system needs audit logging for compliance and debugging. Initially we had only global file-based logging (`logs/audit.log`). However, this approach has limitations:

- Events from concurrent sessions are interleaved in a single file
- No way to export a single session's audit trail
- File I/O on every event impacts performance for high-frequency events (audio chunks)
- Difficult to correlate events belonging to the same session

We needed session-scoped audit logging that is fast, exportable, and doesn't interfere with the global logging infrastructure.

## Decision
Add per-session in-memory audit logging via `SessionAuditLog` class, attached to every `BaseSession`:

```python
class SessionAuditLog:
    events: list[AuditEvent]  # Thread-safe in-memory storage

    def log(self, event_type: str, data: dict, duration_ms: float = None) -> None
    def measure(self, event_type: str, data: dict) -> ContextManager  # Auto-timing
    def export_json(self) -> str
    def export_to_file(self, path: Path) -> None
```

Key design choices:
- **In-memory storage** — no file I/O during session, export at end
- **Automatic timestamps** on every `AuditEvent`
- **Context manager for timing** — `with session.audit_log.measure("api.call"):` measures duration
- **Coexists with global logging** — `SessionAuditLog` for per-session, `log_audit_event()` for global
- **Thread-safe** — supports concurrent event logging from async tasks
- **Built-in events** emitted by `BaseSession`: `session.created`, `session.state_transition`, `session.closed`
- **Export on session close** — examples export to `logs/audit_<mode>_<timestamp>.json`

## Consequences

**Easier:**
- Exporting a complete audit trail for a single session
- Performance (no disk I/O during session, only memory writes)
- Testing (inspect `session.audit_log.events` in assertions)
- Correlating events (all events in one SessionAuditLog belong to same session)

**More difficult:**
- Memory usage grows with session duration (no automatic truncation)
- Must remember to export before session GC (data lost if not exported)
- Two logging systems to maintain (SessionAuditLog + global audit.log)
- No real-time monitoring of per-session events (only available after export)
