# CLAUDE.md

## Project Overview

Real-time voice agent system integrating OpenAI's Realtime API. The `openai_apis` Python package provides three core API modules (transcription, tts, realtime) plus shared infrastructure (session lifecycle, audit logging, MCP plugins, web server). Supports Hungarian language. Python 3.12+.

## Quick Commands

```bash
uv sync                              # Install dependencies
pytest tests/ -v                     # Run all tests (coverage automatic)
pytest tests/unit/ -v                # Unit tests only
pytest tests/integration/ -v         # Integration tests (E2E flows)

python examples/cli_app.py transcription  # Transcription mode
python examples/cli_app.py voice          # Voice mode
python examples/cli_app.py tts            # TTS mode
python examples/cli_agent.py              # Text-based agent
python examples/voice_agent.py            # Push-to-talk voice agent
python examples/realtime_websocket.py     # WebSocket realtime API
python examples/web_server/run.py         # FastAPI web server
```

## Architecture

```
openai_apis/
├── _config.py          # BaseConfig, AudioFormat, VADConfig
├── _logging.py         # SessionAuditLog, AuditEvent, get_logger, log_audit_event
├── _session.py         # BaseSession (state machine, async with, audit_log)
├── transcription/      # Speech-to-text (WebSocket + stateless)
├── tts/                # Text-to-speech (provider registry pattern)
├── realtime/           # Realtime voice (WebSocket, tool calling, barge-in)
├── mcp/                # Model Context Protocol plugin system
└── web/                # FastAPI web server module
```

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for detailed design, data flow diagrams, and module relationships.

## Core APIs

### Public exports (`from openai_apis import ...`)

**Transcription**: `TranscriptionSession`, `TranscriptionConfig`
- WebSocket realtime STT, VAD support, keywords, 100+ languages

**TTS**: `TTSProvider`, `TTSConfig`, `TTSRegistry`
- Provider pattern (OpenAI built-in, ElevenLabs stub), 13 voices, streaming

**Realtime**: `RealtimeSession`, `RealtimeConfig`
- WebSocket voice interaction, push-to-talk, tool calling, response interruption, conversation history

**Infrastructure**: `BaseSession`, `SessionState`, `SessionAuditLog`, `AudioFormat`, `VADConfig`, `ToolRegistry`, `MCPPlugin`, `MCPPluginManager`

**Web**: `create_app`, `run_server` (from `openai_apis.web`)

See [docs/API.md](docs/API.md) for complete method signatures, parameters, import patterns, and usage examples.

## Examples

| Script | Description |
|--------|-------------|
| `examples/cli_app.py` | Multi-mode CLI (transcription/voice/tts) — recommended entry point |
| `examples/cli_agent.py` | Text-based agent with conversation history |
| `examples/voice_agent.py` | Push-to-talk voice agent with ToolRegistry |
| `examples/realtime_websocket.py` | Low-level Realtime WebSocket API |
| `examples/web_server/run.py` | FastAPI web server (REST + WebSocket) |
| `examples/voice_pipeline.py` | Voice pipeline framework (AgentFrameworkAPI) |

Agent configs: `examples/agents/team.py` (shodan_agent, assistant_agent, search_agent), `examples/agents/tools.py`, `examples/agents/prompts/`

## Development Quick Tips

- **Audio defaults**: 24kHz, mono, int16, pcm16 — all modules use this
- **Env**: `OPENAI_API_KEY` loaded automatically from env or `.env`
- **Session pattern**: Always use `async with Session() as session:` for lifecycle management
- **Provider pattern**: Inherit `BaseTTSProvider`, register via `TTSRegistry.register(name, class)`
- **Config validation**: All `*Config` dataclasses validate in `__post_init__`
- **Async tests**: `asyncio_mode = "auto"` — no `@pytest.mark.asyncio` needed
- **Cross-example imports**: Examples use `sys.path.insert` for inter-example imports

## Documentation

| Document | Content |
|----------|---------|
| [docs/API.md](docs/API.md) | Complete API reference (all modules, configs, imports) |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | System design, data flow, state machines |
| [docs/LOGGING_AUDIT_TRAIL.md](docs/LOGGING_AUDIT_TRAIL.md) | Logging system, audit events, export |
| [docs/TESTING.md](docs/TESTING.md) | Test structure, fixtures, running tests |
| [docs/LINTING.md](docs/LINTING.md) | Code quality tools (ruff) |
| [docs/adr/](docs/adr/) | Architecture Decision Records |

## Known Issues

- `OPENAI_API_KEY` not validated for None in some edge cases
- Session memory management not implemented (no auto-truncation for realtime conversation history)
  - Manual: `clear_conversation()` method available
