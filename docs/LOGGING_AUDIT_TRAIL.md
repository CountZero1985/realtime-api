# Logging and Audit Trail Documentation

## Overview

Centralized logging and per-session audit trail system implemented in `openai_apis/_logging.py`.

## Architecture

### Components

1. **`openai_apis/_logging.py`** — Centralized logging configuration and audit classes
2. **Structured Logging** — JSON format for production, human-readable for development
3. **Per-Session Audit Logging** — `SessionAuditLog` for in-memory per-session event tracking
4. **Global Audit Trail** — Separate `audit.log` file for compliance
5. **Performance Metrics** — Duration tracking via `log_performance()` and `SessionAuditLog.measure()`
6. **Correlation IDs** — Request tracking across components

### Log Files

All logs are stored in `./logs/`:

| File | Purpose | Rotation |
|------|---------|----------|
| `app.log` | All application logs | 10MB, 5 backups |
| `audit.log` | Global audit trail | 20MB, 10 backups |
| `error.log` | Errors only | 10MB, 5 backups |

### Log Formats

**Console (Development):**
```
2025-12-25 10:30:15 - cli - INFO - [abc-123-def] - Query completed successfully
```

**JSON (Production — `app.log`):**
```json
{
  "timestamp": "2025-12-25T10:30:15.123456",
  "level": "INFO",
  "logger": "cli",
  "message": "Query completed successfully",
  "module": "cli",
  "function": "query",
  "line": 175,
  "correlation_id": "abc-123-def",
  "extra": {"response_length": 150, "duration_ms": 234.5}
}
```

**Audit Trail (`audit.log`):**
```json
{
  "timestamp": "2025-12-25T10:30:15.123456",
  "event_type": "cli_query",
  "session_id": "session_456",
  "correlation_id": "abc-123-def",
  "action": "query_completed",
  "details": {"message_length": 50, "response_length": 150, "duration_ms": 234.5},
  "status": "success"
}
```

## Per-Session Audit Logging

All sessions inheriting from `BaseSession` have a built-in per-session audit log via `session.audit_log`.

### Usage

```python
from openai_apis import BaseSession, SessionAuditLog, AuditEvent

async with MySession() as session:
    # Log custom events
    session.audit_log.log(
        event_type="api.call",
        data={"endpoint": "/transcribe", "size": 1024}
    )

    # Automatic duration tracking
    with session.audit_log.measure("expensive_operation", {"param": "value"}):
        result = await do_expensive_work()

    # Access events
    events = session.audit_log.events  # list[AuditEvent]

    # Export
    session.audit_log.export_to_file(Path("logs/session_audit.json"))
```

### Built-in Session Events

All sessions automatically log:
- `session.created` — data: `{"config_type": "..."}`
- `session.state_transition` — data: `{"from": "...", "to": "..."}`
- `session.closed` — data: `{"had_error": bool}`

### SessionAuditLog API

```python
class SessionAuditLog:
    @property
    def session_id(self) -> str: ...

    @property
    def events(self) -> list[AuditEvent]: ...

    def log(self, event_type: str, data: dict = None, duration_ms: float = None) -> None: ...

    def measure(self, event_type: str, data: dict = None) -> ContextManager: ...

    def export_json(self) -> str: ...

    def export_to_file(self, path: Path) -> None: ...
```

Thread-safe and async-safe.

### Export Format

```json
{
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "events": [
    {
      "timestamp": "2025-12-25T10:30:15.123456",
      "session_id": "550e8400-e29b-41d4-a716-446655440000",
      "event_type": "session.created",
      "data": {"config_type": "BaseConfig"},
      "duration_ms": null
    }
  ]
}
```

## Global Logging Functions

All imported from `openai_apis._logging`:

```python
from openai_apis._logging import get_logger, log_audit_event, log_performance, set_correlation_id
```

### get_logger(name)

```python
logger = get_logger(__name__)
logger.info("Operation completed")
logger.error("Operation failed", exc_info=True)
```

### set_correlation_id(id)

```python
corr_id = set_correlation_id("user-request-123")
# All subsequent logs include this correlation ID
```

### log_audit_event(...)

```python
log_audit_event(
    event_type="transcription",
    action="audio_transcribed",
    session_id="session_456",
    details={"duration_seconds": 5.2, "language": "hu"},
    status="success"
)
```

### log_performance(...)

```python
log_performance(
    operation="process_audio",
    duration_ms=234.5,
    details={"audio_length": 24000}
)
```

## Module Event Types

### Realtime Session Events

| Event Type | Action | When |
|-----------|---------|------|
| `realtime_session` | `session_created` | WebSocket session established |
| `realtime_session` | `session_configured` | Session config sent |
| `realtime_session` | `session_disconnected` | Session ended |
| `realtime_audio` | `audio_chunk_sent` | Audio sent to server |
| `realtime_audio` | `audio_stream_completed` | Audio stream finished |
| `realtime_response` | `response_started` | Response generation started |
| `realtime_response` | `response_completed` | Response finished |
| `realtime_error` | `error_received` | Server error |

### Transcription Events

| Event Type | Action | When |
|-----------|---------|------|
| `transcription` | `transcription_started` | Transcription begins |
| `transcription` | `transcription_completed` | Transcription succeeds |
| `transcription` | `transcription_failed` | Transcription fails |

### TTS Events

| Event Type | Action | When |
|-----------|---------|------|
| `tts` | `synthesis_started` | Synthesis begins |
| `tts` | `synthesis_completed` | Synthesis succeeds |
| `tts` | `synthesis_failed` | Synthesis fails |
| `tts_stream` | `stream_synthesis_started` | Streaming starts |
| `tts_stream` | `stream_synthesis_completed` | Streaming completes |

## Audit Trail Queries

```bash
# Count by event type
cat logs/audit.log | jq -r '.event_type' | sort | uniq -c

# Failed operations
cat logs/audit.log | jq 'select(.status=="error")'

# Performance metrics
cat logs/app.log | jq 'select(.logger=="performance")'
```

## Privacy

- User input text is **not** logged by default
- Audio data is **never** logged
- Only metadata (length, duration, language) is logged
- Transcripts can be optionally included with `LOG_TRANSCRIPTS=true`
