# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

A real-time voice agent system integrating OpenAI's Realtime API and OpenAI Agents SDK. The project is organized as an `openai_apis` Python package with three core API modules (transcription, tts, realtime) plus shared infrastructure. Supports Hungarian language.

## Quick Commands

```bash
uv sync                              # Install dependencies
pytest tests/ -v                     # Run tests
pytest tests/ --cov=openai_apis      # Tests with coverage
```

## Package Structure

The `openai_apis` package follows a clean, modular architecture:

```
openai_apis/
├── _config.py          # Shared base configuration
├── _logging.py         # Centralized logging infrastructure
├── _session.py         # Base session abstract class
├── transcription/      # Speech-to-text API (M2)
│   ├── config.py
│   └── session.py
├── tts/                # Text-to-speech API (M1)
│   ├── base.py
│   ├── config.py
│   ├── openai_provider.py
│   └── _registry.py
└── realtime/           # Realtime voice API (M3)
    ├── config.py
    ├── session.py
    └── tools.py
```

## Core Components

### Transcription API (`openai_apis/transcription/`)
- **`TranscriptionAPI`**: Stateless speech-to-text using OpenAI Whisper
- **`TranscriptionConfig`**: Configuration for transcription (model, language, sample rate)
- Supports file and numpy array input
- Uses gpt-4o-mini-transcribe or whisper-1
- Async and sync interfaces

### TTS API (`openai_apis/tts/`)
- **`OpenAITTSProvider`**: OpenAI text-to-speech provider (also aliased as `TTSAPI`)
- **`BaseTTSProvider`**: Abstract base class for TTS providers
- **`TTSConfig`**: Configuration for TTS (model, voice, speed, format)
- Multiple voice options (ash, sage, alloy, echo, shimmer)
- Streaming and batch synthesis
- Provider-based architecture for future extensibility

### Realtime Voice API (`openai_apis/realtime/`)
- **`RealtimeVoiceAPI`**: Direct WebSocket connection to OpenAI Realtime API
- **`RealtimeAgentState`**: State manager for realtime sessions
- **`RealtimeConfig`**: Session configuration (model, voice, modalities)
- Push-to-talk audio streaming
- Real-time audio playback
- Event-driven callbacks

### Shared Infrastructure

**`_config.py`**: `BaseConfig` dataclass
- Base configuration class for all API sessions
- Holds common config like `api_key`, `timeout`, etc.

**`_logging.py`**: Centralized logging infrastructure
- Structured JSON logs to `logs/app.log` and `logs/error.log`
- Audit trail to `logs/audit.log`
- Correlation ID tracking for request tracing
- Functions: `get_logger()`, `log_audit_event()`, `log_performance()`, `set_correlation_id()`

**`_session.py`**: `BaseSession` abstract base class
- Session lifecycle management with state machine
- **SessionState enum**: CREATED → CONNECTING → CONNECTED → DISCONNECTING → CLOSED
- Async context manager support (`async with`)
- Automatic UUID session ID generation (`session_id` property)
- Event callback system (`on(event, callback)` and `_emit(event, data)`)
- Per-session audit logging
- Abstract methods: `_connect()` and `_disconnect()` (subclasses must implement)
- **InvalidStateTransition** exception for invalid state transitions

## Development Notes

### Import Patterns

```python
# From package root - recommended
from openai_apis import TranscriptionAPI, TranscriptionConfig
from openai_apis import TTSAPI, TTSConfig, OpenAITTSProvider
from openai_apis import RealtimeVoiceAPI, RealtimeConfig, RealtimeAgentState

# From submodules - also valid
from openai_apis.transcription import TranscriptionAPI, TranscriptionConfig
from openai_apis.tts import TTSAPI, TTSConfig, OpenAITTSProvider, BaseTTSProvider
from openai_apis.realtime import RealtimeVoiceAPI, RealtimeConfig, RealtimeAgentState

# Session infrastructure
from openai_apis import BaseSession, SessionState, InvalidStateTransition, BaseConfig

# Logging infrastructure
from openai_apis import get_logger, log_audit_event, log_performance, set_correlation_id
```

### Configuration Pattern

All API modules follow a consistent configuration pattern:

```python
from openai_apis import TranscriptionAPI, TranscriptionConfig

# Use defaults
api = TranscriptionAPI()

# Or customize
config = TranscriptionConfig(
    model="gpt-4o-mini-transcribe",
    language="hu",
    api_key="sk-...",  # Optional, reads from OPENAI_API_KEY env var
    timeout=60.0
)
api = TranscriptionAPI(config=config)
```

### When Working with Audio
- All audio is represented as numpy arrays with shape `(N,)` or `(N, 1)`
- Sample rate: 24000 Hz (default for all modules)
- Channels: 1 (mono)
- Ensure cleanup in finally blocks when working with audio streams

### Logging
- Structured JSON logs to `logs/app.log` and `logs/error.log`
- Audit trail to `logs/audit.log`
- Correlation ID tracking for request tracing
- Use `get_logger(__name__)` in modules for consistent logging
- See `docs/LOGGING_AUDIT_TRAIL.md` for details

### Implementing Custom Sessions

All API sessions should inherit from `BaseSession`:

```python
from openai_apis import BaseSession, BaseConfig

class MyCustomSession(BaseSession):
    def __init__(self, config: Optional[BaseConfig] = None):
        super().__init__(config)
        # Your initialization here

    async def _connect(self) -> None:
        """Establish connection (called automatically in async with)."""
        # Connection logic here
        pass

    async def _disconnect(self) -> None:
        """Tear down connection (called automatically on exit)."""
        # Cleanup logic here
        pass

# Usage with automatic lifecycle management
async with MyCustomSession() as session:
    # Session is now in CONNECTED state
    # Do work with session
    pass
# Session is now CLOSED and cleaned up
```

**State machine rules:**
- CREATED → CONNECTING → CONNECTED → DISCONNECTING → CLOSED (normal flow)
- CREATED → CLOSED (direct close without connecting)
- CLOSED is terminal (no transitions out)
- Use `session.state` to check current state
- Use `session.on("state_changed", callback)` to monitor transitions

### Adding New TTS Providers

The TTS module uses a provider-based architecture:

1. Create a new provider class inheriting from `BaseTTSProvider`
2. Implement `synthesize()` and `synthesize_stream()` methods
3. Register the provider in `tts/_registry.py`

### Known Issues
- `OPENAI_API_KEY` loaded but not validated for None in some edge cases
- Session memory management not implemented (conversation history truncation needed for realtime)
- Response interruption not yet implemented in realtime mode
