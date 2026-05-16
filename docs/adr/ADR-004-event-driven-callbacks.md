# ADR-004: Event-Driven Callback System

## Status
Accepted

## Context
WebSocket-based sessions (transcription, realtime) receive streaming events from the server. Callers need to react to these events (audio chunks, transcript deltas, errors, session state changes) without polling. We considered:

1. **Async iterators** — `async for event in session:` pattern
2. **Callback registration** — `session.on("event", handler)` pattern
3. **Observable/RxPy** — reactive streams

Async iterators work well for single-consumer scenarios but don't support multiple listeners or typed events easily. Observables add a heavy dependency. Callbacks are simple, support multiple listeners, and are familiar from JavaScript WebSocket APIs.

## Decision
Implement an event callback system in `BaseSession`:

```python
# Registration
session.on("transcript.delta", on_transcript_delta)
session.on("audio.delta", on_audio_chunk)
session.on("error", on_error)

# Emission (internal, called by session implementations)
await self._emit("transcript.delta", TranscriptDelta(...))
```

Key design choices:
- **String-based event names** matching OpenAI's event naming convention (dot-separated)
- **Typed event dataclasses** in `realtime/events.py` (AudioDelta, AudioDone, TranscriptDelta, TranscriptCompleted, ErrorEvent, ConversationItem)
- **Multiple callbacks per event** (list of handlers)
- **Async callback support** (handlers can be async functions)
- **Built-in session events** emitted by BaseSession: `session.created`, `session.state_transition`, `session.closed`

## Consequences

**Easier:**
- Reacting to specific event types without processing all events
- Multiple consumers for the same event (e.g., UI update + audit log)
- Typed event objects provide IDE autocompletion and type safety
- Familiar pattern for developers coming from Node.js/browser WebSocket APIs

**More difficult:**
- Error handling in callbacks (exceptions in handlers need careful propagation)
- Ordering guarantees (callbacks for same event execute in registration order, but no cross-event ordering)
- Memory management (registered callbacks hold references, must disconnect to cleanup)
- Debugging event flow (no built-in tracing of which callbacks fired)
