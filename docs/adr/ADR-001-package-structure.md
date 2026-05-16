# ADR-001: Modular Package Structure

## Status
Accepted

## Context
The project started as a monolithic script integrating OpenAI's Realtime API. As functionality grew (transcription, TTS, realtime voice, web server, MCP plugins), a single-file or flat-package approach became unmaintainable. We needed a structure that:

- Allows independent development and testing of each API module
- Provides clear public API boundaries via `__init__.py` exports
- Supports shared infrastructure (config, logging, session management) without circular imports
- Makes it easy to add new modules (e.g., web, mcp) without modifying existing ones

## Decision
Organize `openai_apis` as a Python package with domain-specific subpackages:

```
openai_apis/
├── _config.py          # Shared configuration (prefixed _ = internal)
├── _logging.py         # Shared logging infrastructure
├── _session.py         # Base session abstract class
├── transcription/      # Speech-to-text API
├── tts/                # Text-to-speech API
├── realtime/           # Realtime voice API
├── mcp/                # Model Context Protocol plugins
└── web/                # FastAPI web server
```

Key design choices:
- **Underscore-prefixed shared modules** (`_config.py`, `_logging.py`, `_session.py`) signal internal infrastructure
- **Each subpackage is self-contained** with its own `config.py`, `session.py` (or equivalent), and `__init__.py`
- **Root `__init__.py`** re-exports the public API, so consumers use `from openai_apis import X`
- **Examples live outside the package** in `examples/` with `sys.path.insert` for cross-imports

## Consequences

**Easier:**
- Adding new modules (just create a new subpackage and export from root)
- Unit testing in isolation (each module has clear boundaries)
- Understanding the codebase (directory structure mirrors domain concepts)
- Maintaining backward compatibility (internal changes don't affect public API)

**More difficult:**
- Shared state between modules requires careful design (resolved via `_config.py` base classes)
- Import paths are slightly longer for advanced/internal usage
- Must maintain `__init__.py` exports when adding new public classes
