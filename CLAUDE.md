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
python examples/voice_agent.py       # Voice-based agent (VoicePipeline)
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

## Example Applications

The `examples/` directory contains standalone runnable examples demonstrating different interaction modes:

### Example Scripts

**`examples/cli_agent.py`** - Text-based CLI agent
- Interactive text-based conversation with agent
- Uses `examples.cli_app.CLI` for interface
- Conversation history tracking
- Hungarian language support

**`examples/voice_agent.py`** - Voice-based agent
- Voice input → transcription → agent → TTS → audio output
- Uses OpenAI Agents SDK `VoicePipeline`
- Custom `StreamingVoiceWorkflow` for agent integration
- Push-to-talk recording mode

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

# Configuration classes
from openai_apis import AudioFormat, VADConfig

# Logging infrastructure
from openai_apis import get_logger, log_audit_event, log_performance, set_correlation_id

# Per-session audit logging
from openai_apis import SessionAuditLog, AuditEvent
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
from openai_apis import TranscriptionAPI, TranscriptionConfig, AudioFormat

# Use defaults (24kHz, mono, int16, pcm16 audio)
api = TranscriptionAPI()

# Or customize
config = TranscriptionConfig(
    model="gpt-4o-mini-transcribe",
    language="hu",
    api_key="sk-...",  # Optional, reads from OPENAI_API_KEY env var
    timeout=60.0
)
api = TranscriptionAPI(config=config)

# Custom audio format (inherited by all configs)
custom_format = AudioFormat(sample_rate=48000, channels=2, dtype="float32")
config = TranscriptionConfig(audio_format=custom_format)
api = TranscriptionAPI(config=config)
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

The TTS module uses a provider-based architecture:

1. Create a new provider class inheriting from `BaseTTSProvider`
2. Implement `synthesize()` and `synthesize_stream()` methods
3. Register the provider in `tts/_registry.py`

### Known Issues
- `OPENAI_API_KEY` loaded but not validated for None in some edge cases
- Session memory management not implemented (conversation history truncation needed for realtime)
- Response interruption not yet implemented in realtime mode
