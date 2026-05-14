# Realtime Voice Agent

A production-ready real-time voice agent system built with OpenAI's Realtime API and Agents SDK. Engage in natural voice conversations with an AI assistant that supports web search, tool use, and multi-agent coordination.

## Features

- **Three Core API Modules**:
  - **Transcription** - Speech-to-text with Whisper models
  - **TTS** - Text-to-speech with multiple voice options
  - **Realtime** - WebSocket-based realtime voice interactions
- **Session Lifecycle Management** - BaseSession with state machine, async context manager support
- **Hungarian Language Support** - Optimized for Hungarian with extensibility to 90+ languages
- **Clean, Stateless APIs** - Simple, predictable interfaces with no hidden state
- **Provider-Based Architecture** - Extensible TTS system supporting multiple providers
- **Comprehensive Logging** - Audit trail, performance tracking, correlation IDs
- **Async & Sync Support** - All APIs support both async and sync usage patterns

## Quick Start

### Prerequisites

**Python:** >= 3.12

**System Dependencies (Ubuntu/Debian):**
```bash
sudo apt install libportaudio2 portaudio19-dev libportaudiocpp0 \
                 libasound2-dev libjack-jackd2-0
```

### Installation

1. **Clone the repository**
```bash
git clone <repository-url>
cd realtime-api
```

2. **Set up environment**
```bash
echo "OPENAI_API_KEY=your_openai_api_key_here" > .env
```

3. **Install dependencies**

The package supports modular installation via optional extras:

```bash
# Core library only (for basic imports and config)
pip install -e .

# With audio support (transcription, TTS, realtime) - RECOMMENDED
pip install -e ".[audio]"
# or with uv:
uv sync --extra audio

# With all features (audio + web + agents)
pip install -e ".[all]"
# or with uv:
uv sync --extra all

# Development dependencies
pip install -e ".[dev]"
# or with uv:
uv sync --extra dev
```

**Optional extras:**
- `audio`: Adds `sounddevice`, `numpy`, `websocket-client` (required for transcription, TTS, realtime)
- `web`: Adds `fastapi`, `uvicorn`, `python-multipart`, `aiofiles` (for web server features)
- `agents`: Adds `openai-agents` (for agent orchestration)
- `dev`: Adds `pytest`, `pytest-asyncio`, `pytest-cov`, `httpx` (for testing)
- `all`: Installs all optional dependencies

For running the examples, install with `[audio]` or `[all]`.

### Running the Examples

The project includes three example applications demonstrating different interaction modes:

**Text-based CLI Agent:**
```bash
python examples/cli_agent.py
```
Interactive text-based conversation with the AI assistant in Hungarian.

**Voice-based Agent:**
```bash
python examples/voice_agent.py
```
Voice input → transcription → agent → TTS → audio output pipeline.

**Realtime WebSocket API:**
```bash
python examples/realtime_websocket.py
```
Direct WebSocket connection to OpenAI Realtime API with real-time audio streaming.

## API Usage

### Transcription (Speech-to-Text)

```python
from openai_apis import TranscriptionAPI, TranscriptionConfig, AudioFormat

# Basic usage with defaults (24kHz, mono, int16, pcm16)
api = TranscriptionAPI()
transcript = await api.transcribe_file("audio.wav")
print(transcript)

# With custom configuration
config = TranscriptionConfig(
    model="gpt-4o-mini-transcribe",
    language="hu",
    keywords=["technical", "OpenAI"]
)
api = TranscriptionAPI(config=config)

# Custom audio format
audio_format = AudioFormat(sample_rate=48000, channels=2)
config = TranscriptionConfig(audio_format=audio_format)
api = TranscriptionAPI(config=config)

# From numpy array
import numpy as np
audio_data = np.array([...])  # Shape: (N,) or (N, 1)
transcript = await api.transcribe(audio_data)

# Sync usage
transcript = api.transcribe_file_sync("audio.wav")
```

### Text-to-Speech (TTS)

```python
from openai_apis import TTSAPI, TTSConfig, AudioFormat

# Basic usage (defaults to 24kHz, mono, int16, pcm16)
api = TTSAPI()
audio = await api.synthesize("Szia! Hogy vagy?")
# Returns numpy array ready for playback

# With custom voice and speed
config = TTSConfig(
    voice="sage",
    speed=1.5,
    model="gpt-4o-mini-tts"
)
api = TTSAPI(config=config)

# Instruction-based voice steering (gpt-4o-mini-tts only)
config = TTSConfig(
    model="gpt-4o-mini-tts",
    voice="ash",
    instructions="Speak in a warm, friendly tone with slight excitement"
)
api = TTSAPI(config=config)
audio = await api.synthesize("Hello! How can I help you today?")

# Custom audio format for higher quality
audio_format = AudioFormat(sample_rate=48000, dtype="float32")
config = TTSConfig(audio_format=audio_format)
api = TTSAPI(config=config)

# Save to file
await api.synthesize_to_file("Hello world!", "output.mp3")

# Streaming synthesis with configurable chunk size
config = TTSConfig(chunk_size=2048)  # 2KB chunks
api = TTSAPI(config=config)
async for chunk in api.synthesize_stream("Long text..."):
    # Process audio chunks as they arrive (uniform 2KB chunks)
    pass

# Or override chunk size per call
async for chunk in api.synthesize_stream("Text", chunk_size=512):
    # 512-byte chunks for this call only
    pass

# Backpressure control for flow management
import asyncio
backpressure = asyncio.Event()
backpressure.set()  # Must be set initially to allow streaming

async for chunk in api.synthesize_stream("Text", backpressure_event=backpressure):
    # Process chunk
    play_audio(chunk)
    # Pause streaming if needed
    if should_pause():
        backpressure.clear()  # Pauses next chunk
    # Resume later
    if should_resume():
        backpressure.set()  # Resumes streaming

# Sync usage
audio = api.synthesize_sync("Hello!")
```

**Available voices:**
- **OpenAI (13 voices):** alloy, ash, ballad, coral, echo, fable, nova, onyx, sage, shimmer, verse, marin, cedar
- **ElevenLabs (3 voices - stub):** rachel, adam, bella

**Provider Registry:** The TTS system uses a provider registry pattern:
```python
from openai_apis import TTSRegistry

# List registered providers
providers = TTSRegistry.list_providers()  # ["elevenlabs", "openai"]

# Create provider from config
config = TTSConfig(provider="elevenlabs", voice="rachel")
provider = TTSRegistry.create(config)
```

**Configuration validation:** `TTSConfig` validates all parameters on initialization:
- `speed` must be between 0.25 and 4.0
- `voice` must be in the provider's supported voices list
- `output_format` must be one of: pcm, mp3, opus, aac, flac, wav
- `provider` must be registered (currently "openai" and "elevenlabs")

Invalid values raise `ValueError` with clear error messages.

**Note:** ElevenLabs provider is a stub implementation. All methods raise `NotImplementedError`.

### Realtime Voice API

```python
from openai_apis import RealtimeVoiceAPI, RealtimeConfig

# Define callbacks
def on_transcription(text):
    print(f"User said: {text}")

def on_response_text(text):
    print(f"Agent: {text}")

# Configure and run
config = RealtimeConfig(
    voice="sage",
    language="hu",
    instructions="segíts a felhasználónak"
)

api = RealtimeVoiceAPI(
    config=config,
    on_transcription=on_transcription,
    on_response_text=on_response_text
)

# Run session (blocking)
api.run_session_sync()
```

**Streaming transcript events with delta callbacks:**

```python
from openai_apis import (
    RealtimeVoiceAPI,
    TranscriptDelta,
    TranscriptCompleted,
    ErrorEvent
)

api = RealtimeVoiceAPI()

# Register callback for streaming transcript deltas (~200-500ms intervals)
def on_delta(event: TranscriptDelta):
    print(f"\r[Streaming] {event.accumulated}", end="", flush=True)

api.on("transcript.delta", on_delta)

# Register callback for completed transcripts
def on_completed(event: TranscriptCompleted):
    print(f"\n[Final] {event.transcript} ({event.duration_ms:.0f}ms)")

api.on("transcript.completed", on_completed)

# Register error handler
def on_error(event: ErrorEvent):
    print(f"\n[Error {event.code}] {event.message}")

api.on("error", on_error)

# Run session with streaming callbacks
api.run_session_sync()
```

### Session Lifecycle Management

All API sessions inherit from `BaseSession`, which provides automatic lifecycle management:

```python
from openai_apis import BaseSession, SessionState, InvalidStateTransition

# Using async context manager (recommended)
async with MySession() as session:
    # Session automatically transitions: CREATED → CONNECTING → CONNECTED
    print(session.state)  # SessionState.CONNECTED
    print(session.session_id)  # Auto-generated UUID
    # Do work...
# Session automatically transitions: DISCONNECTING → CLOSED

# Event callbacks
def on_state_change(data):
    print(f"State changed: {data['from']} → {data['to']}")

session.on("state_changed", on_state_change)

# State transitions are validated
try:
    session._transition_to(SessionState.CONNECTED)  # If not valid
except InvalidStateTransition as e:
    print(f"Invalid transition: {e}")
```

**Session States:**
- `CREATED` - Initial state after construction
- `CONNECTING` - Connection in progress
- `CONNECTED` - Active session
- `DISCONNECTING` - Cleanup in progress
- `CLOSED` - Terminal state (no further transitions)

### Audio Format Configuration

All API modules support customizable audio formats via `AudioFormat`:

```python
from openai_apis import AudioFormat, TranscriptionConfig, TTSAPI

# Default format (24kHz, mono, int16, pcm16)
fmt = AudioFormat()

# Custom format for higher quality
fmt = AudioFormat(
    sample_rate=48000,  # 48kHz sample rate
    channels=2,         # Stereo
    dtype="float32",    # Floating-point audio
    encoding="pcm16"    # PCM encoding
)

# Use with any API configuration
config = TranscriptionConfig(audio_format=fmt)

# AudioFormat is immutable (frozen dataclass)
# This ensures format specs can't be accidentally modified
```

**Supported values:**
- `sample_rate`: Any positive integer (Hz). Default: 24000
- `channels`: Any positive integer. Default: 1 (mono)
- `dtype`: "int16" or "float32". Default: "int16"
- `encoding`: "pcm16", "g711_ulaw", or "g711_alaw". Default: "pcm16"

### Voice Activity Detection (VAD) Configuration

Configure voice activity detection for realtime sessions:

```python
from openai_apis import VADConfig

# Server-side VAD (silence detection)
vad = VADConfig(
    mode="server_vad",
    threshold=0.7,              # Sensitivity (0.0-1.0)
    prefix_padding_ms=300,      # Audio before speech
    silence_duration_ms=800     # Silence to end turn
)

# Semantic turn detection
vad = VADConfig(
    mode="semantic_vad",
    eagerness="high"  # "low", "medium", "high", or "auto"
)

# Disable VAD for continuous processing
vad = VADConfig(mode="disabled")
```

### Per-Session Audit Logging

Each session has its own structured audit log accessible via the `audit_log` property:

```python
from openai_apis import BaseSession, SessionAuditLog, AuditEvent

async with MySession() as session:
    # Log custom events
    session.audit_log.log("api.call", {"endpoint": "/transcribe"})

    # Measure operation duration automatically
    with session.audit_log.measure("processing", {"type": "audio"}):
        # Operation is timed automatically
        result = await process_data()

    # Access logged events
    events = session.audit_log.events  # Returns list[AuditEvent]
    for event in events:
        print(f"{event.event_type}: {event.duration_ms}ms")

    # Export session audit trail
    json_str = session.audit_log.export_json()

    # Or save to file
    from pathlib import Path
    session.audit_log.export_to_file(Path("audit_trail.json"))
```

**Built-in session events:**
- `session.created` - Session initialized
- `session.state_transition` - State change occurred
- `session.closed` - Session terminated

## Example Applications

The `examples/` directory contains standalone applications demonstrating the APIs:

### Directory Structure

```
examples/
├── agents/                  # Agent configurations
│   ├── prompts/            # System prompts (Hungarian)
│   │   ├── voice_assistant.py
│   │   └── tts.py
│   ├── tools.py            # Agent tools (websearch, time, display)
│   └── team.py             # Agent team setup
├── utils/                   # Utility modules
│   ├── audio_io.py         # Audio recording and playback
│   └── time_format.py      # Hungarian time formatting
├── cli_app.py              # CLI interface module
├── voice_pipeline.py       # Voice pipeline framework
├── cli_agent.py            # Example: text-based agent
├── voice_agent.py          # Example: voice-based agent
└── realtime_websocket.py   # Example: realtime WebSocket API
```

### Example Usage

**Import pattern in examples:**
```python
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from examples.cli_app import CLI
from examples.agents.team import assisstant_agent
from examples.utils.audio_io import record_audio, AudioPlayer
```

### Testing

```bash
pytest tests/ -v                                    # All tests
pytest tests/ --cov=openai_apis --cov-report=term-missing  # With coverage
pytest tests/unit/ -v                               # Unit tests only
```

## Troubleshooting

### No audio input/output
```bash
# Check audio devices
python -c "import sounddevice; print(sounddevice.query_devices())"

# Install missing dependencies
sudo apt install libportaudio2 portaudio19-dev
```

### API Key errors
```bash
cat .env  # Should show: OPENAI_API_KEY=sk-...
```

### Import errors
```bash
# If you see "numpy is required" or "sounddevice is required" errors:
pip install -e ".[audio]"  # or: uv sync --extra audio

# Generic solution:
uv sync --extra all  # or: pip install -e ".[all]"
python --version  # Should be >= 3.12
```

### Missing optional dependencies
The package uses lazy imports for optional dependencies. If you try to use a feature without its dependencies installed, you'll see a helpful error message like:

```
ImportError: numpy is required for this feature. Install it with: pip install openai-apis[audio]
```

Install the appropriate extra to resolve the error.

### Transcription in wrong language
Update STT settings: `STTModelSettings(language="hu")` - change to correct language code.

## Documentation

- **README.md** - This file (user guide and quick start)
- **docs/API.md** - Complete API reference for all modules
- **docs/ARCHITECTURE.md** - System architecture and design patterns
- **docs/LOGGING_AUDIT_TRAIL.md** - Logging and audit trail reference
- **specs.md** - Technical specifications and implementation details
- **CLAUDE.md** - AI assistant development guidance
- **docs/ai_docs/** - OpenAI API documentation

## External Resources

- [OpenAI Realtime API Guide](https://platform.openai.com/docs/guides/realtime)
- [OpenAI Agents SDK Documentation](https://openai.github.io/openai-agents-python/)
- [OpenAI Agents SDK GitHub](https://github.com/openai/openai-agents-python)

---

**Version:** 1.0 | **Package:** openai-apis | **Status:** Production-ready
