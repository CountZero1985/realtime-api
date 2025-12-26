# Realtime Voice Agent

A production-ready real-time voice agent system built with OpenAI's Realtime API and Agents SDK. Engage in natural voice conversations with an AI assistant that supports web search, tool use, and multi-agent coordination.

## Features

- **Real-time Voice Conversations** - Low-latency (<1s) voice interactions
- **Hungarian Language Support** - Optimized for Hungarian with extensibility to 90+ languages
- **Multi-Agent System** - Coordinated agent team with automatic handoffs
- **Web Search Integration** - Built-in web search capabilities
- **Multiple Modes**:
  - Voice Pipeline Mode (default) - Full voice conversation
  - CLI Text Mode - Development and testing
  - WebSocket Realtime Mode - Low-level control
- **Tool Integration** - Extensible tool system for custom capabilities

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

**Voice Mode:**
```bash
python examples/voice_agent.py
```
Press Enter to start/stop recording. Say "kilépés" or "exit" to quit.

**CLI Text Mode:**
```bash
python examples/cli_agent.py
```
Type messages to interact. Type 'q' to quit, 'h' to see history.

**Realtime WebSocket Mode:**
```bash
python examples/realtime_websocket.py
```

## Usage Guide

### Voice Mode Commands
- `<Enter>` - Start/stop recording
- `h` - View conversation history
- `q` - Quit application
- Voice: "kilépés", "exit" - Exit application

### CLI Mode Commands
- `<message>` - Send text message
- `h` - View conversation history
- `q` - Quit application

## Development

### Adding New Tools

1. **Define the tool in `openai_apis/agents/tools.py`:**
```python
from agents import function_tool

@function_tool
def my_custom_tool(param: str) -> str:
    """Tool description for the agent."""
    return result
```

2. **Register with agent in `openai_apis/agents/team.py`:**
```python
agent = Agent(
    name="agent_name",
    tools=[existing_tool, my_custom_tool],
    ...
)
```

### Using the APIs

```python
# CLI Interface
from openai_apis.cli import CLI
from openai_apis.agents import assisstant_agent

cli = CLI(agent=assisstant_agent)
cli.run_sync()

# Voice Pipeline
from openai_apis.voice import AgentFrameworkAPI

api = AgentFrameworkAPI(agent=assisstant_agent)
await api.run_interactive()

# Transcription
from openai_apis.audio import TranscriptionAPI

api = TranscriptionAPI()
text = await api.transcribe_file("audio.wav")

# Text-to-Speech
from openai_apis.audio import TTSAPI

api = TTSAPI()
audio = await api.synthesize("Szia!")
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
