# OpenAI APIs

> Unified Python interface for OpenAI's voice and text services — transcription, text-to-speech, and realtime voice interaction.

## Overview

`openai-apis` is a production-ready Python package providing three core API modules for building voice-enabled applications:

- **Transcription** — Speech-to-text via Audio API (`gpt-4o-mini-transcribe`) and realtime streaming (`gpt-realtime-whisper`, when available)
- **TTS** — Text-to-speech synthesis with 13+ voices and provider extensibility
- **Realtime** — Low-latency WebSocket voice interaction with tool calling support (`gpt-realtime-mini`)

Key features: async context manager sessions, provider-based TTS architecture, Voice Activity Detection (VAD), per-session audit logging, and support for 100+ languages (optimized for Hungarian).

### API status (GA, as of 2026-07)

| Module | Model | API | Status |
|--------|-------|-----|--------|
| `RealtimeSession` | `gpt-realtime-mini` | WebSocket `/v1/realtime` | ✅ Working |
| `TranscriptionAPI` | `gpt-4o-mini-transcribe` | REST `/v1/audio/transcriptions` | ✅ Working |
| `TranscriptionSession` | `gpt-realtime-whisper` | WebSocket (ephemeral token) | ❌ Endpoint not yet available |
| `TTSProvider` | `tts-1` / `tts-1-hd` | REST `/v1/audio/speech` | ✅ Working |

> **Note:** The OpenAI Beta Realtime API header (`OpenAI-Beta: realtime=v1`) was deprecated in May 2026. This package uses the GA API without the beta header.

## Installation

### Prerequisites

- **Python** >= 3.12
- **System dependencies** (Ubuntu/Debian):
  ```bash
  sudo apt install libportaudio2 portaudio19-dev
  ```

### Install the package

```bash
pip install -e .               # Core only
pip install -e ".[audio]"      # With audio support (recommended)
pip install -e ".[all]"        # All features
```

Or with [uv](https://github.com/astral-sh/uv):

```bash
uv sync                        # Core
uv sync --extra audio          # With audio
uv sync --extra all            # All features
```

For running the examples, install with `[audio]` or `[all]`.

| Extra    | Adds                                      | Use case                          |
|----------|-------------------------------------------|-----------------------------------|
| `audio`  | sounddevice, numpy, websocket-client      | Transcription, TTS, Realtime      |
| `web`    | fastapi, uvicorn, python-multipart        | Web server endpoints              |
| `agents` | openai-agents                             | Agent orchestration               |
| `dev`    | pytest, pytest-asyncio, pytest-cov, httpx | Testing                           |
| `all`    | All of the above                          | Everything                        |

### Environment setup

```bash
export OPENAI_API_KEY="sk-..."
# Or create a .env file:
echo "OPENAI_API_KEY=sk-..." > .env
```

## Quick Start

### Transcription (Speech-to-Text)

**Audio API** (file/buffer transcription — recommended, works now):

```python
from openai_apis.transcription import TranscriptionAPI, TranscriptionConfig

config = TranscriptionConfig(model="gpt-4o-mini-transcribe", language="hu")
api = TranscriptionAPI(config)

text = await api.transcribe_file("recording.wav")
print(text)
```

**Realtime streaming** (when `gpt-realtime-whisper` endpoint becomes available):

```python
from openai_apis import TranscriptionSession, TranscriptionConfig

async with TranscriptionSession(TranscriptionConfig(language="hu")) as session:
    session.on("transcript.completed", lambda t: print(f"Final: {t['transcript']}"))

    await session.send_audio(audio_chunk)  # PCM16 24kHz mono bytes
    await session.commit_audio()
```

### Text-to-Speech (TTS)

```python
from openai_apis import TTSRegistry, TTSConfig

config = TTSConfig(voice="sage", speed=1.0)
tts = TTSRegistry.create(config)

audio = await tts.synthesize("Szia! Hogy vagy?")  # Returns numpy array
await tts.synthesize_to_file("Hello world!", "output.mp3")
```

### Realtime Voice

```python
from openai_apis import RealtimeSession, RealtimeConfig

config = RealtimeConfig(voice="sage", language="hu")

async with RealtimeSession(config) as session:
    session.on("transcript.input", lambda t: print(f"User: {t.transcript}"))
    session.on("audio.delta", lambda e: play_audio(e.audio_bytes))

    await session.send_audio(audio_chunk)
    await session.commit_audio()
    await session.create_response()
```

See [docs/API.md](docs/API.md) for complete usage examples, streaming support, and advanced features.

## Configuration

### Audio format

```python
from openai_apis import AudioFormat

fmt = AudioFormat(sample_rate=24000, channels=1, dtype="int16", encoding="pcm16")  # defaults
```

### Voice Activity Detection (VAD)

```python
from openai_apis import VADConfig

vad = VADConfig(mode="server_vad", threshold=0.7, silence_duration_ms=800)
vad = VADConfig(mode="semantic_vad", eagerness="high")
vad = VADConfig(mode="disabled")  # push-to-talk
```

### Language

All sessions accept ISO 639-1 language codes. Default: `"hu"` (Hungarian).

```python
TranscriptionConfig(language="en")
RealtimeConfig(language="hu")
```

### Voice selection

OpenAI voices: alloy, ash, ballad, coral, echo, fable, nova, onyx, sage, shimmer, verse, marin, cedar.

```python
TTSConfig(voice="sage")
RealtimeConfig(voice="ash")
```

### Tool calling (Realtime)

```python
from openai_apis import ToolRegistry

tools = ToolRegistry()
tools.register(
    name="get_weather",
    description="Get weather for a city",
    parameters={"type": "object", "properties": {"city": {"type": "string"}}, "required": ["city"]},
    handler=lambda city: {"temp": 22, "conditions": "sunny"},
)
config = RealtimeConfig(tools=tools)
```

See [docs/API.md](docs/API.md) for full configuration reference.

## Examples

The `examples/` directory contains standalone applications:

**Multi-mode Interactive CLI (Recommended):**
```bash
# Transcription mode: microphone → real-time text
python examples/cli_app.py transcription --language hu

# Voice mode: microphone → AI voice response
python examples/cli_app.py voice --language hu --voice ash

# TTS mode: text input → audio output
python examples/cli_app.py tts --language hu --voice sage
```
Unified CLI application demonstrating all three core APIs (TranscriptionSession, RealtimeSession, TTSProvider) with push-to-talk interaction and per-session audit logging.

**Other Examples:**
```bash
python examples/cli_agent.py          # Text-based CLI agent
python examples/voice_agent.py        # Push-to-talk voice agent
python examples/realtime_websocket.py # Realtime WebSocket API
python examples/web_server/run.py     # FastAPI web server (requires [web] extra)
```

See the [examples/](examples/) directory for full source code and agent configurations.

## Testing

Run tests with pytest:

```bash
pytest tests/ -v                                    # All tests
pytest tests/ --cov=openai_apis --cov-report=term-missing  # With coverage
pytest tests/unit/ -v                               # Unit tests only
pytest tests/integration/ -v                        # Integration tests only
pytest tests/integration/test_e2e_flows.py -v       # E2E integration tests
```

**Test Suites:**
- **Unit tests** (`tests/unit/`): Fast tests for individual components with full mocking
- **Integration tests** (`tests/integration/`): E2E tests exercising complete API workflows with mock WebSocket backends
  - `test_e2e_flows.py`: 7 test classes covering transcription, realtime voice, TTS, tool calling, audit logging, configuration, and error recovery (23 tests)
  - `test_integration.py`: Additional integration scenarios
  - `test_public_api.py`: Public API surface validation
- **Web server tests** (`tests/test_web_server.py`, `tests/api/`): FastAPI endpoint tests

## API Reference

### Core Sessions

| Class | Module | Description |
|-------|--------|-------------|
| `TranscriptionAPI` | `openai_apis.transcription` | Audio API speech-to-text (file/buffer, `gpt-4o-mini-transcribe`) |
| `TranscriptionSession` | `openai_apis` | Realtime streaming speech-to-text (`gpt-realtime-whisper`) |
| `RealtimeSession` | `openai_apis` | WebSocket-based realtime voice interaction (`gpt-realtime-mini`) |
| `TTSRegistry` | `openai_apis` | Factory for creating TTS providers |
| `TTSProvider` | `openai_apis` | Abstract base class for TTS providers |

### Configuration

| Class | Module | Description |
|-------|--------|-------------|
| `TranscriptionConfig` | `openai_apis` | Transcription session settings (model, language, VAD) |
| `RealtimeConfig` | `openai_apis` | Realtime session settings (voice, language, tools) |
| `TTSConfig` | `openai_apis` | TTS provider settings (voice, speed, format) |
| `AudioFormat` | `openai_apis` | Immutable audio format specification |
| `VADConfig` | `openai_apis` | Voice Activity Detection configuration |

### Tools & Plugins

| Class | Module | Description |
|-------|--------|-------------|
| `ToolRegistry` | `openai_apis` | Register and manage tool definitions for Realtime |
| `MCPPlugin` | `openai_apis` | Model Context Protocol plugin base |
| `MCPPluginManager` | `openai_apis` | MCP plugin lifecycle manager |

### Session Infrastructure

| Class | Module | Description |
|-------|--------|-------------|
| `BaseSession` | `openai_apis` | Abstract session base with lifecycle management |
| `SessionState` | `openai_apis` | Session state enum (CREATED → CONNECTED → CLOSED) |
| `SessionAuditLog` | `openai_apis` | Per-session audit event logging |

For complete method signatures, parameters, and advanced usage, see [docs/API.md](docs/API.md).

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

### TranscriptionSession raises ConnectionError (404)
The realtime streaming transcription endpoint (`POST /v1/realtime/transcription_sessions`) is not yet available on all accounts. Use `TranscriptionAPI` with the Audio API as a working alternative:
```python
from openai_apis.transcription import TranscriptionAPI, TranscriptionConfig
api = TranscriptionAPI(TranscriptionConfig(model="gpt-4o-mini-transcribe"))
text = await api.transcribe_file("audio.wav")
```

### "beta_api_shape_disabled" error
The OpenAI Beta Realtime API (`OpenAI-Beta: realtime=v1`) was deprecated in May 2026. Update to the latest version of this package which uses the GA API.

### Transcription in wrong language
Update language setting: `TranscriptionConfig(language="hu")` - change to correct language code.

## Documentation

- **README.md** - This file (user guide and quick start)
- **[docs/API.md](docs/API.md)** - Complete API reference for all modules
- **[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)** - System architecture and design patterns
- **[docs/LOGGING_AUDIT_TRAIL.md](docs/LOGGING_AUDIT_TRAIL.md)** - Logging and audit trail reference
- **[docs/TESTING.md](docs/TESTING.md)** - Test architecture, fixtures, and running tests
- **[docs/LINTING.md](docs/LINTING.md)** - Code quality tools (ruff)

## External Resources

- [OpenAI Realtime API Guide](https://platform.openai.com/docs/guides/realtime)
- [OpenAI Agents SDK Documentation](https://openai.github.io/openai-agents-python/)
- [OpenAI Agents SDK GitHub](https://github.com/openai/openai-agents-python)

---

**Version:** 1.1 | **Package:** openai-apis | **Status:** Production-ready | **API:** OpenAI GA (2026-07)
