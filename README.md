# Realtime Voice Agent

A production-ready real-time voice agent system built with OpenAI's Realtime API and Agents SDK. Engage in natural voice conversations with an AI assistant that supports web search, tool use, and multi-agent coordination.

## Features

- **Three Core API Modules**:
  - **Transcription** - Speech-to-text with Whisper models
  - **TTS** - Text-to-speech with multiple voice options
  - **Realtime** - WebSocket-based realtime voice interactions
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
```bash
uv sync        # recommended
# or: pip install -e .
```

### Running the Application

**Note:** The example applications (`voice_agent.py`, `cli_agent.py`, `realtime_websocket.py`) are currently being refactored to work with the new package structure. They will be updated in a future release.

## API Usage

### Transcription (Speech-to-Text)

```python
from openai_apis import TranscriptionAPI, TranscriptionConfig

# Basic usage with defaults
api = TranscriptionAPI()
transcript = await api.transcribe_file("audio.wav")
print(transcript)

# With custom configuration
config = TranscriptionConfig(
    model="gpt-4o-mini-transcribe",
    language="hu",
    temperature=0.0
)
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
from openai_apis import TTSAPI, TTSConfig

# Basic usage
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

# Save to file
await api.synthesize_to_file("Hello world!", "output.mp3")

# Streaming synthesis
async for chunk in api.synthesize_stream("Long text..."):
    # Process audio chunks as they arrive
    pass

# Sync usage
audio = api.synthesize_sync("Hello!")
```

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
uv sync  # or: pip install -e .
python --version  # Should be >= 3.12
```

### Transcription in wrong language
Update STT settings: `STTModelSettings(language="hu")` - change to correct language code.

## Documentation

- **README.md** - This file (user guide)
- **specs.md** - Technical specifications and architecture
- **CLAUDE.md** - AI assistant development guidance
- **docs/LOGGING_AUDIT_TRAIL.md** - Logging reference
- **docs/ai_docs/** - OpenAI API documentation

## External Resources

- [OpenAI Realtime API Guide](https://platform.openai.com/docs/guides/realtime)
- [OpenAI Agents SDK Documentation](https://openai.github.io/openai-agents-python/)
- [OpenAI Agents SDK GitHub](https://github.com/openai/openai-agents-python)

---

**Version:** 1.0 | **Package:** openai-apis | **Status:** Production-ready
