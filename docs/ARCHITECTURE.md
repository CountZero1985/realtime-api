# OpenAI APIs - Architecture Documentation

System architecture documentation for the `openai_apis` Python package, covering module structure, relationships, data flow, and design patterns.

---

## Table of Contents

- [Overview](#overview)
- [Package Structure](#package-structure)
- [Architecture Diagram](#architecture-diagram)
- [Module Relationships](#module-relationships)
- [Data Flow](#data-flow)
  - [Voice Pipeline Mode](#voice-pipeline-mode)
  - [CLI Text Mode](#cli-text-mode)
  - [Realtime WebSocket Mode](#realtime-websocket-mode)
- [Session Lifecycle](#session-lifecycle)
- [Provider Pattern](#provider-pattern)
- [Examples Directory](#examples-directory)

---

## Overview

The `openai_apis` package is a production-ready real-time voice agent system integrating OpenAI's Realtime API and OpenAI Agents SDK. It provides a modular, extensible architecture for building voice and text-based AI applications.

### Key Capabilities

- **Real-time voice conversations** with low latency (<1s)
- **Multi-modal agent interactions** (voice + text)
- **Modular API design** with clean separation of concerns
- **Session lifecycle management** with state machines
- **Comprehensive audit logging** for compliance and debugging
- **Provider-based extensibility** for future integrations

### Design Principles

1. **Modularity**: Each API module (Transcription, TTS, Realtime) is independent and can be used standalone
2. **Stateless APIs**: Transcription and TTS are stateless endpoints with no conversation history
3. **Async-first**: All APIs support async/await with optional sync wrappers
4. **Configuration inheritance**: Shared `BaseConfig` ensures consistent API key and timeout handling
5. **Lifecycle management**: `BaseSession` abstract class provides consistent session lifecycle with state machines
6. **Audit trail**: Per-session and global audit logging for compliance and debugging

---

## Package Structure

```
openai_apis/
├── __init__.py             # Public API exports
├── _config.py              # Shared configuration classes
│                           # - BaseConfig (API key, timeout, audio format)
│                           # - AudioFormat (immutable audio specs)
│                           # - VADConfig (voice activity detection)
├── _logging.py             # Centralized logging infrastructure
│                           # - SessionAuditLog (per-session audit)
│                           # - AuditEvent (audit event dataclass)
│                           # - Global logging functions
├── _session.py             # Base session abstract class
│                           # - BaseSession (lifecycle management)
│                           # - SessionState (state enum)
│                           # - InvalidStateTransition (exception)
│
├── transcription/          # Speech-to-text API (M2)
│   ├── __init__.py         # Public exports
│   ├── config.py           # TranscriptionConfig (extends BaseConfig)
│   └── session.py          # TranscriptionAPI (stateless STT)
│
├── tts/                    # Text-to-speech API (M1)
│   ├── __init__.py         # Public exports
│   ├── config.py           # TTSConfig (extends BaseConfig)
│   ├── base.py             # BaseTTSProvider (abstract base class)
│   ├── openai_provider.py  # OpenAITTSProvider (OpenAI TTS implementation)
│   ├── elevenlabs_provider.py # ElevenLabsTTSProvider (stub implementation)
│   └── _registry.py        # TTSRegistry class and provider registry
│
└── realtime/               # Realtime voice API (M3)
    ├── __init__.py         # Public exports
    ├── config.py           # RealtimeConfig (extends BaseConfig)
    ├── session.py          # RealtimeVoiceAPI (WebSocket realtime)
    └── tools.py            # Agent tools for realtime sessions

examples/                   # Standalone example applications
├── agents/                 # Agent configurations for examples
│   ├── prompts/            # System prompts (Hungarian)
│   │   ├── __init__.py
│   │   ├── assisstant.py
│   │   └── tts_instruct.py
│   ├── tools.py            # Agent tools (websearch, time, display)
│   └── team.py             # Agent team setup (assisstant_agent, tools_agent)
│
├── utils/                  # Utility modules
│   ├── audio_io.py         # Audio recording and playback (24kHz)
│   └── time_format.py      # Hungarian time formatting
│
├── cli_app.py              # CLI interface module
│                           # - CLI (text-based interface)
│                           # - CLIConfig (CLI configuration)
│                           # - ConversationHistory (history management)
│
├── voice_pipeline.py       # Voice pipeline framework
│                           # - AgentFrameworkAPI (high-level voice API)
│                           # - StreamingVoiceWorkflow (custom workflow)
│                           # - VoiceConfig (voice pipeline configuration)
│
├── cli_agent.py            # Example: text-based agent
├── voice_agent.py          # Example: voice-based agent
└── realtime_websocket.py   # Example: realtime WebSocket API
```

---

## Architecture Diagram

The system follows a layered architecture with clear separation between user interface, application logic, agent orchestration, audio I/O, and external APIs.

```
┌─────────────────────────────────────────────────────────────┐
│                     User Interface Layer                     │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │ Voice Mode   │  │  CLI Mode    │  │ Realtime WS  │      │
│  │(voice_agent) │  │ (cli_agent)  │  │(realtime_ws) │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
└─────────────────────────────────────────────────────────────┘
                            │
┌─────────────────────────────────────────────────────────────┐
│                  Application Layer                           │
│  ┌──────────────────────────────────────────────────────┐   │
│  │        VoicePipeline (Agents SDK)                    │   │
│  │  ┌────────────┐  ┌────────────┐  ┌────────────┐    │   │
│  │  │    STT     │→ │  Workflow  │→ │    TTS     │    │   │
│  │  │ (Whisper)  │  │  (Custom)  │  │ (gpt-4o)   │    │   │
│  │  └────────────┘  └────────────┘  └────────────┘    │   │
│  └──────────────────────────────────────────────────────┘   │
│                            │                                 │
│  ┌──────────────────────────────────────────────────────┐   │
│  │     StreamingVoiceWorkflow (Custom Adapter)          │   │
│  │  - Input history management                          │   │
│  │  - Agent orchestration                               │   │
│  │  - Response streaming                                │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
                            │
┌─────────────────────────────────────────────────────────────┐
│                   Agent Layer                                │
│  ┌────────────────────┐      ┌──────────────────────────┐   │
│  │ Assistant Agent    │─────→│    Tools Agent           │   │
│  │ - Main interface   │      │  - Web search            │   │
│  │ - Conversation     │      │  - Information gathering │   │
│  │ - Delegation       │      │  - Specialized tools     │   │
│  └────────────────────┘      └──────────────────────────┘   │
│            │                            │                    │
│  ┌─────────────────────────────────────────────────────┐    │
│  │              Agentic Tools                          │    │
│  │  - websearch_tool                                   │    │
│  │  - get_current_time                                 │    │
│  │  - display_text_terminal                            │    │
│  └─────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────┘
                            │
┌─────────────────────────────────────────────────────────────┐
│                   Audio I/O Layer                            │
│  ┌────────────────┐              ┌───────────────────┐      │
│  │ record_audio() │              │   AudioPlayer     │      │
│  │ - sounddevice  │              │ - Streaming       │      │
│  │ - 24kHz mono   │              │ - Queue-based     │      │
│  │ - Push-to-talk │              │ - Low latency     │      │
│  └────────────────┘              └───────────────────┘      │
└─────────────────────────────────────────────────────────────┘
                            │
┌─────────────────────────────────────────────────────────────┐
│                    OpenAI API Layer                          │
│  ┌─────────────────────────────────────────────────────┐    │
│  │  OpenAI Agents SDK + Realtime API                   │    │
│  │  - gpt-4o-mini (agent model)                        │    │
│  │  - gpt-4o-mini-transcribe (STT)                     │    │
│  │  - gpt-4o-mini-tts (TTS, voice: ash)                │    │
│  │  - gpt-4o-mini-realtime-preview (WebSocket)         │    │
│  └─────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────┘
```

### Layer Responsibilities

| Layer | Responsibility | Components |
|-------|---------------|------------|
| **User Interface** | User interaction modes | CLI, Voice, Realtime WebSocket scripts |
| **Application** | Business logic and workflow | VoicePipeline, StreamingVoiceWorkflow, CLI |
| **Agent** | AI reasoning and tool use | assisstant_agent, tools_agent, tools |
| **Audio I/O** | Audio recording and playback | record_audio(), AudioPlayer |
| **OpenAI API** | External API integration | TranscriptionAPI, TTSAPI, RealtimeVoiceAPI |

---

## Module Relationships

### Shared Infrastructure

All API modules depend on shared infrastructure:

```
┌──────────────────┐
│   BaseConfig     │ ← Configuration base class
│ - api_key        │
│ - timeout        │
│ - audio_format   │
└──────────────────┘
         ▲
         │ extends
         │
    ┌────┴────┬─────────────┬──────────────┐
    │         │             │              │
┌───▼──────┐ ┌▼──────────┐ ┌▼───────────┐ │
│Transcript│ │ TTSConfig │ │ Realtime   │ │
│Config    │ │           │ │ Config     │ │
└──────────┘ └───────────┘ └────────────┘ │
                                          │
┌─────────────────────────────────────────┘
│
▼
┌──────────────────┐
│  AudioFormat     │ ← Immutable audio specs
│ - sample_rate    │   (used by all configs)
│ - channels       │
│ - dtype          │
│ - encoding       │
└──────────────────┘

┌──────────────────┐
│   BaseSession    │ ← Abstract session base
│ - session_id     │   (lifecycle management)
│ - state          │
│ - audit_log      │
└──────────────────┘
         ▲
         │ extends
         │
    ┌────┴────────────────┐
    │                     │
┌───▼──────────┐   ┌──────▼────────┐
│ Transcription│   │ Realtime      │
│ API (future) │   │ VoiceAPI      │
│              │   │ (has session) │
└──────────────┘   └───────────────┘

Note: TranscriptionAPI and TTSAPI are currently stateless and
do not extend BaseSession, but could in future versions for
connection pooling or streaming sessions.
```

### API Module Independence

Each API module can be used independently:

```python
# Use Transcription API standalone
from openai_apis import TranscriptionAPI
api = TranscriptionAPI()
transcript = await api.transcribe(audio_data)

# Use TTS API standalone
from openai_apis import TTSAPI
api = TTSAPI()
audio = await api.synthesize("Hello world")

# Use Realtime API standalone
from openai_apis import RealtimeVoiceAPI
api = RealtimeVoiceAPI()
api.run_session_sync()
```

No cross-dependencies between API modules. All share only the infrastructure layer (`_config.py`, `_session.py`, `_logging.py`).

---

## Data Flow

### Voice Pipeline Mode

Voice Pipeline mode uses the OpenAI Agents SDK `VoicePipeline` with a custom `StreamingVoiceWorkflow` adapter:

```
User Speaks
    ↓
record_audio() [Enter to start/stop]
    ↓
AudioInput buffer (numpy array, 24kHz mono PCM16)
    ↓
VoicePipeline → STT (gpt-4o-mini-transcribe, language: hu)
    ↓
Transcription text (Hungarian)
    ↓
StreamingVoiceWorkflow.run(transcription)
    ↓
Runner.run_streamed(assisstant_agent, input_history)
    ↓
Agent processing (may delegate to tools_agent)
    ↓
VoiceWorkflowHelper.stream_text_from(result)
    ↓
Text chunks → VoicePipeline TTS (gpt-4o-mini-tts, voice: ash, speed: 4.0)
    ↓
Audio chunks
    ↓
AudioPlayer.add_audio() → sounddevice.OutputStream
    ↓
User hears response
```

**Key Components:**

- **`record_audio()`**: Blocking, Enter-based recording (24kHz, mono, PCM16)
- **`VoicePipeline`**: Orchestrates STT → Workflow → TTS
- **`StreamingVoiceWorkflow`**: Custom adapter maintaining conversation history and agent state
- **`AudioPlayer`**: Queue-based audio playback with low latency

**Data Format:**

```python
input_history = [
    {"role": "user", "content": "Transcription text"},
    {"role": "assistant", "content": "Agent response"}
]
```

---

### CLI Text Mode

CLI mode bypasses audio I/O and interacts directly with the agent:

```
User types message
    ↓
input_history.append({"role": "user", "content": user_input})
    ↓
Runner.run_streamed(assisstant_agent, input_history)
    ↓
Agent processes with tools (may call tools_agent)
    ↓
VoiceWorkflowHelper.stream_text_from(result)
    ↓
Print chunks to terminal
    ↓
input_history.append({"role": "assistant", "content": full_response})
```

**Key Components:**

- **`CLI`**: Text-based interface with conversation history
- **`ConversationHistory`**: Manages conversation state
- **No audio**: Direct text input/output

---

### Realtime WebSocket Mode

Realtime mode uses direct WebSocket connection to OpenAI's Realtime API:

```
WebSocket connect → wss://api.openai.com/v1/realtime
    ↓
session.created → session.update (Hungarian, voice: sage) → session.updated
    ↓
User presses Enter → PTT active
    ↓
Microphone input → 500ms chunks → base64 encode
    ↓
input_audio_buffer.append events
    ↓
User presses Enter → PTT inactive
    ↓
input_audio_buffer.commit + response.create
    ↓
Server streams response.audio.delta events
    ↓
Base64 decode → numpy array → Speaker queue
    ↓
Speaker thread → sounddevice.OutputStream
    ↓
User hears response
```

**Key Components:**

- **`RealtimeVoiceAPI`**: WebSocket connection manager
- **`RealtimeAgentState`**: Custom state management
- **Event callbacks**: `on_transcription`, `on_response_audio`, `on_response_text`, `on_error`
- **Push-to-talk**: Enter key to start/stop recording

**WebSocket URL:**

```
wss://api.openai.com/v1/realtime?model=gpt-4o-mini-realtime-preview-2024-12-17
```

**Implemented Events:**

- Session: `session.created`, `session.updated`
- Conversation: `conversation.created`, `conversation.item.created`
- Audio buffer: `input_audio_buffer.committed`, `input_audio_buffer.cleared`
- Transcription: `conversation.item.input_audio_transcription.completed`
- Response: `response.created`, `response.done`, `response.audio.delta`, `response.audio.done`
- Transcript: `response.audio_transcript.delta`, `response.audio_transcript.done`
- Error: `error`

---

## Session Lifecycle

All API sessions that require connection management inherit from `BaseSession` and follow a consistent lifecycle state machine.

### State Machine

```
┌─────────┐
│ CREATED │ Initial state after construction
└────┬────┘
     │
     │ __aenter__() called
     ↓
┌────────────┐
│ CONNECTING │ Connection establishment in progress
└────┬───┬───┘
     │   │
     │   └─────→ (error) ──→ CLOSED (terminal)
     │
     │ _connect() succeeds
     ↓
┌───────────┐
│ CONNECTED │ Session active and ready for use
└────┬──┬───┘
     │  │
     │  └─────→ (forced close) ──→ CLOSED (terminal)
     │
     │ __aexit__() called
     ↓
┌──────────────┐
│DISCONNECTING │ Cleanup/disconnection in progress
└──────┬───────┘
       │
       │ _disconnect() completes
       ↓
   ┌────────┐
   │ CLOSED │ Terminal state (no transitions out)
   └────────┘

Direct transition shortcut:
CREATED ─────→ CLOSED (close without connecting)
```

### Valid Transitions

| From | To | Trigger |
|------|----|----|
| `CREATED` | `CONNECTING` | `__aenter__()` called |
| `CREATED` | `CLOSED` | Direct close without connecting |
| `CONNECTING` | `CONNECTED` | `_connect()` succeeds |
| `CONNECTING` | `CLOSED` | `_connect()` fails |
| `CONNECTED` | `DISCONNECTING` | `__aexit__()` called |
| `CONNECTED` | `CLOSED` | Forced close |
| `DISCONNECTING` | `CLOSED` | `_disconnect()` completes |
| `CLOSED` | — | Terminal state (no transitions out) |

### Lifecycle Management

**Automatic lifecycle with async context manager:**

```python
from openai_apis import BaseSession

async with MySession() as session:
    # Session is CONNECTED here
    # State: CREATED → CONNECTING → CONNECTED

    # Use session...
    result = await session.do_something()

# Session is CLOSED here
# State: CONNECTED → DISCONNECTING → CLOSED
```

**Guaranteed cleanup:** State is guaranteed to be `CLOSED` after exiting the context manager, even if `_disconnect()` raises an exception.

**Subclass implementation:**

```python
from openai_apis import BaseSession, BaseConfig

class MySession(BaseSession):
    async def _connect(self) -> None:
        """Called during CONNECTING state."""
        # Establish connection logic
        self.connection = await create_connection()

    async def _disconnect(self) -> None:
        """Called during DISCONNECTING state."""
        # Cleanup logic
        if self.connection:
            await self.connection.close()
```

### State Monitoring

**Event callbacks:**

```python
def on_state_change(data):
    print(f"State: {data['from'].value} → {data['to'].value}")

session.on("state_changed", on_state_change)

async with session:
    # Callbacks invoked for each transition
    pass
```

**Direct state checking:**

```python
from openai_apis import SessionState

async with MySession() as session:
    if session.state == SessionState.CONNECTED:
        # Safe to use session
        pass
```

---

## Provider Pattern

The TTS module uses a provider-based architecture with a class-based registry to support multiple TTS backends.

### Architecture

```
┌──────────────────┐
│ BaseTTSProvider  │ ← Abstract base class
│ - synthesize()   │   (defines provider interface)
│ - synthesize_    │
│   stream()       │
│ - synthesize_    │
│   to_file()      │
│ - supported_     │
│   voices         │
│ - provider_name  │
└────────┬─────────┘
         │ extends
         │
    ┌────┴──────────────────────────────┐
    │                                   │
┌───▼──────────────────┐   ┌────────▼──────────────┐
│ OpenAITTSProvider    │   │ ElevenLabsTTSProvider │
│ (built-in, active)   │   │ (built-in, stub)      │
│ - 13 voices          │   │ - 3 voices            │
│ - gpt-4o-mini-tts    │   │ - NotImplementedError │
└──────────────────────┘   └───────────────────────┘
         │
         │ aliased as
         ▼
    ┌────────┐
    │ TTSAPI │ (convenient alias)
    └────────┘

┌──────────────────────────────────────────┐
│ TTSRegistry (class-based registry)       │
│ - register(name, provider_class)         │
│ - get(name) → provider_class             │
│ - create(config) → provider_instance     │
│ - list_providers() → ["openai", ...]     │
└──────────────────────────────────────────┘
         │
         │ backward-compatible wrappers
         ▼
┌──────────────────────────────────────────┐
│ register_provider(), get_provider()      │
│ (free functions, delegate to class)      │
└──────────────────────────────────────────┘
```

**Built-in Providers:**
- **OpenAI** (`openai`) - Fully functional with 13 voices, instruction-based voice steering
- **ElevenLabs** (`elevenlabs`) - Stub implementation with 3 voices, raises `NotImplementedError`

### Adding a Custom Provider

**Step 1: Implement `BaseTTSProvider`**

```python
from openai_apis.tts import BaseTTSProvider
from typing import AsyncIterator, Optional, Union
from pathlib import Path
import numpy as np

class MyCustomTTSProvider(BaseTTSProvider):
    def __init__(self, config=None):
        self.config = config

    @property
    def provider_name(self) -> str:
        return "my_custom_provider"

    @property
    def supported_voices(self) -> list[str]:
        return ["voice_a", "voice_b", "voice_c"]

    async def synthesize(self, text: str, voice: Optional[str] = None,
                        speed: Optional[float] = None) -> np.ndarray:
        # Implementation here
        audio_data = await my_tts_engine.synthesize(text, voice, speed)
        return np.array(audio_data, dtype=np.int16)

    async def synthesize_stream(self, text: str, voice: Optional[str] = None,
                               speed: Optional[float] = None) -> AsyncIterator[bytes]:
        # Streaming implementation
        async for chunk in my_tts_engine.stream(text, voice, speed):
            yield chunk

    async def synthesize_to_file(self, text: str, file_path: Union[str, Path],
                                voice: Optional[str] = None,
                                speed: Optional[float] = None) -> Path:
        # File synthesis implementation
        audio = await self.synthesize(text, voice, speed)
        # Save to file...
        return Path(file_path)
```

**Step 2: Register the provider**

```python
from openai_apis import TTSRegistry

# Class method (recommended)
TTSRegistry.register("my_custom_tts", MyCustomTTSProvider)

# Or use backward-compatible function
from openai_apis.tts import register_provider
register_provider("my_custom_tts", MyCustomTTSProvider)
```

**Step 3: Use the provider**

```python
from openai_apis import TTSRegistry, TTSConfig

# Option A: Factory pattern (recommended)
config = TTSConfig(provider="my_custom_tts", voice="voice_a")
provider = TTSRegistry.create(config)
audio = await provider.synthesize("Hello world")

# Option B: Get class and instantiate manually
provider_class = TTSRegistry.get("my_custom_tts")
provider = provider_class(config=config)
audio = await provider.synthesize("Hello world")

# Option C: Backward-compatible function
from openai_apis.tts import get_provider
ProviderClass = get_provider("my_custom_tts")
provider = ProviderClass(config=config)
audio = await provider.synthesize("Hello world")
```

### Built-in Providers

| Provider Name | Class | Description |
|---------------|-------|-------------|
| `openai` | `OpenAITTSProvider` | OpenAI TTS (default) |

Future providers can be added without modifying existing code, following the Open/Closed Principle.

---

## Examples Directory

The `examples/` directory contains standalone runnable applications that demonstrate how to use the `openai_apis` library.

### Structure

```
examples/
├── agents/                # Agent configurations
│   ├── prompts/           # System prompts (Hungarian)
│   ├── tools.py           # Agent tools
│   └── team.py            # Agent team setup
├── utils/                 # Utility modules
│   ├── audio_io.py        # Audio I/O utilities
│   └── time_format.py     # Time formatting
├── cli_app.py             # CLI interface module
├── voice_pipeline.py      # Voice pipeline framework
├── cli_agent.py           # Example: text agent
├── voice_agent.py         # Example: voice agent
└── realtime_websocket.py  # Example: realtime API
```

### Example Scripts

| Script | Purpose | Uses |
|--------|---------|------|
| `cli_agent.py` | Text-based agent | `CLI`, `assisstant_agent` |
| `voice_agent.py` | Voice-based agent | `AgentFrameworkAPI`, `VoicePipeline` |
| `realtime_websocket.py` | Realtime WebSocket | `RealtimeVoiceAPI` |

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

### Agent Configuration

**`examples/agents/team.py`** defines two agents:

- **`assisstant_agent`**: Main conversational interface
  - Model: `gpt-4o-mini`
  - Tools: `get_current_time()`, `display_text_terminal()`
  - Sub-agents: `tools_agent.as_tool()` for delegation

- **`tools_agent`**: Specialized for web search
  - Model: `gpt-4o-mini`
  - Tools: `websearch_tool`

**Agent handoff:** Main assistant delegates to `tools_agent` via `agents=[tools_agent.as_tool()]`. The `Runner` handles orchestration automatically.

### Utility Modules

**`examples/utils/audio_io.py`** provides:
- `record_audio() -> np.ndarray`: Blocking, Enter-based recording (24kHz, mono, PCM16)
- `AudioPlayer`: Context manager for streaming audio playback with low latency

**`examples/utils/time_format.py`** provides:
- `magyar_ido_szoveggel() -> str`: Hungarian time strings (e.g., "tizenegy óra harmincöt perc")

### Relationship to Library

The `examples/` directory is **independent** from the `openai_apis` package:

- Examples import from `openai_apis` as an external library
- Examples can be copied to other projects as starting templates
- Library code never imports from `examples/`

This separation ensures the library remains clean and reusable, while examples demonstrate practical usage patterns.

---

## See Also

- **[API Reference](./API.md)** - Complete API documentation for all modules
- **[Logging & Audit Trail](./LOGGING_AUDIT_TRAIL.md)** - Logging and audit documentation
- **[Technical Specifications](../specs.md)** - Full technical specifications and design decisions
- **[CLAUDE.md](../CLAUDE.md)** - Development guidelines and patterns for contributors

---

**Version:** 1.0
**Last Updated:** 2025-12-26
