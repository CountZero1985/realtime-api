# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

A real-time voice agent system integrating OpenAI's Realtime API and OpenAI Agents SDK. The project is organized as an `openai_apis` Python package with three core API modules (transcription, tts, realtime) plus shared infrastructure. Supports Hungarian language.

## Quick Commands

```bash
uv sync                              # Install dependencies
pytest tests/ -v                     # Run tests
pytest tests/ --cov=openai_apis      # Tests with coverage

# Run example scripts
python examples/cli_agent.py         # Text-based agent (CLI)
python examples/voice_agent.py       # Push-to-talk voice agent (RealtimeSession)
python examples/realtime_websocket.py # WebSocket realtime API
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

examples/               # Standalone example applications
├── agents/             # Agent configurations for examples
│   ├── prompts/        # System prompts (Hungarian)
│   ├── tools.py        # Agent tools (websearch, time, display)
│   └── team.py         # Agent team setup
├── utils/              # Utility modules
│   ├── audio_io.py     # Audio recording and playback
│   └── time_format.py  # Hungarian time formatting
├── cli_app.py          # CLI interface module
├── voice_pipeline.py   # Voice pipeline framework
├── cli_agent.py        # Example: text-based agent
├── voice_agent.py      # Example: voice-based agent
└── realtime_websocket.py # Example: realtime WebSocket API
```

## Core Components

### Transcription API (`openai_apis/transcription/`)
- **`TranscriptionSession`**: WebSocket-based realtime transcription (recommended, in public API)
- **`TranscriptionAPI`**: Stateless speech-to-text using OpenAI Whisper (legacy, submodule only)
- **`TranscriptionConfig`**: Configuration for transcription with validation
  - Model: gpt-realtime-whisper (default), gpt-4o-mini-transcribe, gpt-4o-transcribe, whisper-1
  - Language: ISO 639-1 language codes (100+ supported) or None for auto-detect
  - VAD: Voice Activity Detection via `VADConfig` field
  - Keywords: List of terms to steer transcription accuracy
  - Prompt: Context to guide transcription
  - Log probabilities: Optional boolean flag
- Supports file and numpy array input
- Async and sync interfaces

### TTS API (`openai_apis/tts/`)
- **`TTSRegistry`**: Class-based provider registry with factory pattern
  - `register(name, provider_class)`: Register a TTS provider
  - `get(name)`: Get a registered provider class
  - `create(config)`: Factory method to instantiate provider from config
  - `list_providers()`: List all registered provider names
  - Built-in providers: "openai" (OpenAITTSProvider), "elevenlabs" (ElevenLabsTTSProvider stub)
- **`TTSProvider`**: Public alias for `BaseTTSProvider` abstract base class (in public API)
- **`OpenAITTSProvider`**: OpenAI text-to-speech provider (also aliased as `TTSAPI`, submodule only)
  - 13 voices: alloy, ash, ballad, coral, echo, fable, nova, onyx, sage, shimmer, verse, marin, cedar
  - Full implementation with streaming and batch synthesis
- **`ElevenLabsTTSProvider`**: ElevenLabs TTS provider (stub implementation, submodule only)
  - 3 voices: rachel, adam, bella
  - All methods raise `NotImplementedError` (placeholder for future integration)
- **`BaseTTSProvider`**: Abstract base class for TTS providers (submodule only, use `TTSProvider` from public API)
- **`TTSConfig`**: Configuration for TTS with `__post_init__` validation
  - Fields: `provider`, `model`, `voice`, `speed`, `instructions`, `output_format`, `language`, `sample_rate`
  - Validates `speed` (0.25-4.0), `voice` (against provider's supported voices), `output_format` (pcm/mp3/opus/aac/flac/wav), `provider` (must be registered)
  - Raises `ValueError` for invalid configurations
- Provider-based architecture with class-based registry for extensibility

### Realtime Voice API (`openai_apis/realtime/`)
- **`RealtimeSession`**: Direct WebSocket connection to OpenAI Realtime API (in public API)
- **`RealtimeVoiceAPI`**: Backward-compatible alias for `RealtimeSession` (submodule only)
- **`RealtimeAgentState`**: State manager for realtime sessions (internal, submodule only)
- **`RealtimeConfig`**: Session configuration (model, voice, modalities, language, keywords)
  - `language` field for setting transcription language (default: "hu")
  - `keywords` field for domain-specific transcription steering (comma-separated prompt)
- Push-to-talk audio streaming
- Real-time audio playback
- Event-driven callbacks
- **Response interruption (barge-in)**: Cancel in-progress responses via `cancel_response()` method
- **Conversation history tracking**: Automatic tracking of user/assistant transcripts via `get_conversation_history()` and `clear_conversation()` methods
- **VAD-based auto-interruption detection**: Automatic detection and logging when user speech interrupts assistant response

## Example Applications

The `examples/` directory contains standalone runnable examples demonstrating different interaction modes:

### Example Scripts

**`examples/cli_agent.py`** - Text-based CLI agent
- Interactive text-based conversation with agent
- Uses `examples.cli_app.CLI` for interface
- Conversation history tracking
- Hungarian language support

**`examples/voice_agent.py`** - Push-to-talk voice agent with RealtimeSession
- Interactive push-to-talk mode with Enter key recording
- Direct RealtimeSession WebSocket connection (no VoicePipeline)
- ToolRegistry-based tool calling (`get_current_time`, `get_weather`)
- Event-driven audio streaming: accumulate deltas, play on `audio.done`
- Conversation history viewing (`h` command)
- Audit log export to `logs/voice_agent_audit.json` on exit
- Demonstrates complete RealtimeSession workflow with Hungarian UI

**`examples/realtime_websocket.py`** - Realtime WebSocket API
- Direct WebSocket connection to OpenAI Realtime API
- Low-level API access via `openai_apis.realtime`
- Real-time audio streaming
- Event-driven callbacks

### Example Modules

**`examples/cli_app.py`** - CLI interface module
- `CLI`: Main text-based interface class
- `CLIConfig`: Configuration for CLI behavior
- `ConversationHistory`: History management
- Streaming response support

**`examples/voice_pipeline.py`** - Voice pipeline framework
- `AgentFrameworkAPI`: High-level voice interaction API
- `StreamingVoiceWorkflow`: Custom workflow for agent integration
- `VoiceConfig`: Voice pipeline configuration
- Callback support for transcription, response events

**`examples/agents/`** - Agent configurations
- `team.py`: `assisstant_agent` and `tools_agent` definitions
- `tools.py`: Agent tools (websearch, time, display)
- `prompts/`: System prompts in Hungarian

**`examples/utils/`** - Utility modules
- `audio_io.py`: `record_audio()` and `AudioPlayer` for 24kHz audio
- `time_format.py`: `magyar_ido_szoveggel()` for Hungarian time strings

### Running Examples

All examples use `sys.path.insert` to enable cross-example imports:

```python
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from examples.cli_app import CLI
from examples.agents.team import assisstant_agent
```

Run from project root:
```bash
python examples/cli_agent.py
python examples/voice_agent.py
python examples/realtime_websocket.py
```

### Shared Infrastructure

**`_config.py`**: Configuration classes
- **`BaseConfig`**: Base configuration class for all API sessions
  - `api_key`: OpenAI API key (reads from OPENAI_API_KEY env var if None)
  - `timeout`: Request timeout in seconds (default: 30.0)
  - `audio_format`: Audio format specification (default: AudioFormat())
  - `__post_init__` validation ensures timeout is positive and loads API key from environment
- **`AudioFormat`**: Frozen dataclass for immutable audio format specifications
  - `sample_rate`: Audio sample rate in Hz (default: 24000)
  - `channels`: Number of audio channels (default: 1, mono)
  - `dtype`: NumPy dtype, valid: "int16", "float32" (default: "int16")
  - `encoding`: Audio encoding, valid: "pcm16", "g711_ulaw", "g711_alaw" (default: "pcm16")
  - `__post_init__` validation ensures all parameters are valid
- **`VADConfig`**: Voice Activity Detection configuration
  - `mode`: VAD mode - "server_vad", "semantic_vad", or "disabled" (default: "server_vad")
  - `threshold`: Activation threshold for server_vad (0.0-1.0, default: 0.5)
  - `prefix_padding_ms`: Audio padding before speech (default: 300)
  - `silence_duration_ms`: Silence duration to end turn (default: 500)
  - `eagerness`: Eagerness for semantic_vad - "low", "medium", "high", "auto" (default: "auto")
  - `__post_init__` validation ensures mode-specific parameters are valid

**`_logging.py`**: Centralized logging infrastructure
- **Per-session audit logging**: `SessionAuditLog` and `AuditEvent` classes for in-memory per-session event tracking
- **Global audit trail**: Separate `audit.log` file for compliance tracking
- Structured JSON logs to `logs/app.log` and `logs/error.log`
- Correlation ID tracking for request tracing
- Classes: `SessionAuditLog`, `AuditEvent`, `_PerformanceContext`
- Functions: `get_logger()`, `log_audit_event()`, `log_performance()`, `set_correlation_id()`

**`_session.py`**: `BaseSession` abstract base class
- Session lifecycle management with state machine
- **SessionState enum**: CREATED → CONNECTING → CONNECTED → DISCONNECTING → CLOSED
- Async context manager support (`async with`)
- Automatic UUID session ID generation (`session_id` property)
- Event callback system (`on(event, callback)` and `_emit(event, data)`)
- **Per-session audit logging** via `session.audit_log` property (returns `SessionAuditLog`)
- Built-in session events: `session.created`, `session.state_transition`, `session.closed`
- Abstract methods: `_connect()` and `_disconnect()` (subclasses must implement)
- **InvalidStateTransition** exception for invalid state transitions

## Development Notes

### Import Patterns

**Library imports (openai_apis package):**
```python
# From package root - recommended (public API)
from openai_apis import TranscriptionSession, TranscriptionConfig
from openai_apis import RealtimeSession, RealtimeConfig
from openai_apis import TTSProvider, TTSConfig, TTSRegistry
from openai_apis import AudioFormat, VADConfig
from openai_apis import ToolRegistry
from openai_apis import MCPPlugin, MCPPluginManager
from openai_apis import BaseSession, SessionState, SessionAuditLog

# From submodules - for advanced usage
from openai_apis.transcription import TranscriptionAPI  # Stateless API
from openai_apis.tts import (
    OpenAITTSProvider,  # Direct provider access
    TTSAPI,  # Alias for OpenAITTSProvider
    ElevenLabsTTSProvider,
    BaseTTSProvider,
    register_provider,
    get_provider
)
from openai_apis.realtime import RealtimeVoiceAPI  # Alias for RealtimeSession
from openai_apis.realtime.events import (
    AudioDelta,
    AudioDone,
    TranscriptDelta,
    TranscriptCompleted,
    ErrorEvent
)

# Internal utilities (not in public API)
from openai_apis._session import InvalidStateTransition
from openai_apis._config import BaseConfig
from openai_apis._logging import AuditEvent, get_logger, log_audit_event, log_performance, set_correlation_id
```

**Example imports (examples/ directory):**
```python
# Agent configuration and tools
from examples.agents.team import assisstant_agent, tools_agent
from examples.agents.tools import websearch_tool, get_current_time, display_text_terminal
from examples.agents.prompts import assisstant_prompt, tts_instruct_prompt

# CLI interface
from examples.cli_app import CLI, CLIConfig, ConversationHistory

# Voice pipeline
from examples.voice_pipeline import (
    AgentFrameworkAPI,
    StreamingVoiceWorkflow,
    VoiceConfig,
    start_voice_agent
)

# Utilities
from examples.utils.audio_io import record_audio, AudioPlayer
from examples.utils.time_format import magyar_ido_szoveggel
```

### Configuration Pattern

All API modules follow a consistent configuration pattern:

```python
from openai_apis import TranscriptionSession, TranscriptionConfig, AudioFormat

# Use defaults (24kHz, mono, int16, pcm16 audio)
async with TranscriptionSession() as session:
    # Use session...
    pass

# Or customize
config = TranscriptionConfig(
    model="gpt-4o-mini-transcribe",
    language="hu",
    api_key="sk-...",  # Optional, reads from OPENAI_API_KEY env var
    timeout=60.0
)
async with TranscriptionSession(config=config) as session:
    # Use session...
    pass

# Custom audio format (inherited by all configs)
custom_format = AudioFormat(sample_rate=48000, channels=2, dtype="float32")
config = TranscriptionConfig(audio_format=custom_format)
async with TranscriptionSession(config=config) as session:
    # Use session...
    pass

# For TTS via registry
from openai_apis import TTSRegistry, TTSConfig

config = TTSConfig(voice="sage", speed=1.0)
tts = TTSRegistry.create(config)
audio = await tts.synthesize("Hello!")
```

**AudioFormat usage:**
```python
from openai_apis import AudioFormat

# Use defaults (24kHz, mono, int16, pcm16)
fmt = AudioFormat()

# Custom format for higher quality
fmt = AudioFormat(sample_rate=48000, channels=2, dtype="float32", encoding="pcm16")

# AudioFormat is immutable (frozen dataclass)
# fmt.sample_rate = 16000  # Raises FrozenInstanceError
```

**VADConfig usage:**
```python
from openai_apis import VADConfig

# Server-side VAD (default)
vad = VADConfig(mode="server_vad", threshold=0.7, silence_duration_ms=800)

# Semantic turn detection
vad = VADConfig(mode="semantic_vad", eagerness="high")

# Disable VAD for continuous processing
vad = VADConfig(mode="disabled")
```

### When Working with Audio
- All audio is represented as numpy arrays with shape `(N,)` or `(N, 1)`
- Sample rate: 24000 Hz (default for all modules)
- Channels: 1 (mono)
- Ensure cleanup in finally blocks when working with audio streams

### Logging and Audit Trail

**Per-session audit logging:**
- Each `BaseSession` has a `session.audit_log` property (type: `SessionAuditLog`)
- Thread-safe in-memory event storage with automatic timestamps
- Use `session.audit_log.log(event_type, data, duration_ms)` to log events
- Use `with session.audit_log.measure(event_type, data):` for automatic duration tracking
- Export via `export_json()` or `export_to_file(path)`
- Built-in events: `session.created`, `session.state_transition`, `session.closed`

**Global logging:**
- Structured JSON logs to `logs/app.log` and `logs/error.log`
- Global audit trail to `logs/audit.log` (for non-session events)
- Correlation ID tracking for request tracing
- Use `get_logger(__name__)` in modules for consistent logging
- Use global `log_audit_event()` for backward compatibility or non-session events
- See `docs/LOGGING_AUDIT_TRAIL.md` for complete documentation

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

    # Log custom audit events
    session.audit_log.log("custom.event", {"key": "value"})

    # Measure operation duration automatically
    with session.audit_log.measure("api.call", {"endpoint": "/test"}):
        result = await some_operation()

    # Access audit events
    events = session.audit_log.events  # list[AuditEvent]

    # Export audit trail
    session.audit_log.export_to_file(Path("session_audit.json"))
# Session is now CLOSED and cleaned up
```

**State machine rules:**
- CREATED → CONNECTING → CONNECTED → DISCONNECTING → CLOSED (normal flow)
- CREATED → CLOSED (direct close without connecting)
- CLOSED is terminal (no transitions out)
- Use `session.state` to check current state
- Use `session.on("state_changed", callback)` to monitor transitions

### Adding New TTS Providers

The TTS module uses a provider-based architecture with class-based registry:

1. **Create a new provider class** inheriting from `BaseTTSProvider`
   - Implement abstract methods: `synthesize()`, `synthesize_stream()`, `synthesize_to_file()`
   - Implement abstract properties: `provider_name`, `supported_voices`
2. **Register the provider** using `TTSRegistry.register(name, provider_class)`
   - For built-in providers: Add to `_register_builtins()` in `tts/_registry.py`
   - For external providers: Use `TTSRegistry.register()` or `register_provider()` function
3. **Use the provider** via factory pattern: `TTSRegistry.create(config)`

**Example:**
```python
from openai_apis.tts import BaseTTSProvider, TTSRegistry

class MyTTSProvider(BaseTTSProvider):
    @property
    def provider_name(self) -> str:
        return "my_provider"

    @property
    def supported_voices(self) -> list[str]:
        return ["voice1", "voice2"]

    async def synthesize(self, text, voice=None, speed=None):
        # Implementation
        pass

# Register
TTSRegistry.register("my_provider", MyTTSProvider)

# Use
config = TTSConfig(provider="my_provider", voice="voice1")
provider = TTSRegistry.create(config)
```

## Documentation

For detailed API reference and architecture information, see:

- **`docs/API.md`** - Complete API reference for all modules (Transcription, TTS, Realtime), configuration classes (AudioFormat, VADConfig, BaseConfig), session infrastructure (BaseSession, SessionState), and logging/audit system. Includes method signatures, parameters, return types, and usage examples.
- **`docs/ARCHITECTURE.md`** - System architecture documentation covering package structure, module relationships, data flow diagrams, session lifecycle state machine, and provider pattern.
- **`docs/LOGGING_AUDIT_TRAIL.md`** - Comprehensive logging and audit trail reference.

### Known Issues
- `OPENAI_API_KEY` loaded but not validated for None in some edge cases
- Session memory management not implemented (automatic conversation history truncation needed for realtime)
  - Manual management available via `clear_conversation()` method
