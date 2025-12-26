# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

A real-time voice agent system integrating OpenAI's Realtime API and OpenAI Agents SDK. The project is organized as an `openai_apis` Python package with modular APIs for voice, audio, CLI, and agent interactions. Supports Hungarian language.

## Quick Commands

```bash
uv sync                              # Install dependencies
python examples/voice_agent.py       # Voice mode
python examples/cli_agent.py         # CLI mode
pytest tests/ -v                     # Run tests
pytest tests/ --cov=openai_apis      # Tests with coverage
```

## Core Components

**`openai_apis/cli/interface.py`** - Text-based CLI interface
- `CLI`: Main class with conversation history, streaming
- `CLIConfig`: Configuration dataclass
- Supports both async and sync interfaces

**`openai_apis/voice/agent_framework.py`** - Voice pipeline API
- `AgentFrameworkAPI`: Wraps VoicePipeline with callbacks
- `VoiceConfig`: Configuration for STT/TTS/agent settings
- Interactive and single-shot modes

**`openai_apis/voice/realtime_session.py`** - WebSocket realtime API
- `RealtimeVoiceAPI`: Direct WebSocket to OpenAI Realtime API
- `RealtimeConfig`: Session configuration
- Push-to-talk with audio streaming

**`openai_apis/audio/transcription.py`** - Speech-to-text
- `TranscriptionAPI`: Stateless STT endpoint
- Supports file and numpy array input
- Uses gpt-4o-mini-transcribe or whisper-1

**`openai_apis/audio/synthesis.py`** - Text-to-speech
- `TTSAPI`: Stateless TTS endpoint
- Multiple voice options (ash, sage, alloy, echo, shimmer)
- Streaming and batch synthesis

**`openai_apis/agents/team.py`** - Agent configurations
- `assisstant_agent`: Main agent with tools
- `tools_agent`: Specialized for web search
- Uses gpt-4o-mini model

**`openai_apis/agents/tools.py`** - Tool definitions
- `websearch_tool`: Web search
- `get_current_time()`: Hungarian formatted time
- `display_text_terminal()`: Terminal display

**`openai_apis/logging_config.py`** - Centralized logging
- `get_logger()`: Get module logger
- `log_audit_event()`: Audit trail logging
- `log_performance()`: Performance metrics
- `set_correlation_id()`: Request tracing

## Development Notes

### When Modifying Agents
- Agent instructions are in `openai_apis/agents/prompts/`
- Tools must be registered in both `tools.py` and assigned to agents in `team.py`
- For TTS output, avoid direct URLs in speech - use descriptive source attribution

### When Working with Audio
- Always use numpy arrays with shape (N, 1) or (N,) for consistency
- AudioPlayer flattens (N, 1) to (N,) automatically
- Ensure cleanup in finally blocks when working with audio streams

### Import Patterns

```python
# From package root
from openai_apis import CLI, TTSAPI, TranscriptionAPI

# From submodules
from openai_apis.cli import CLI, CLIConfig
from openai_apis.voice import AgentFrameworkAPI, RealtimeVoiceAPI
from openai_apis.audio import TranscriptionAPI, TTSAPI
from openai_apis.agents import assisstant_agent, websearch_tool
from openai_apis.utils import record_audio, AudioPlayer
```

### Logging
- Structured JSON logs to `logs/app.log` and `logs/error.log`
- Audit trail to `logs/audit.log`
- Correlation ID tracking for request tracing
- See `docs/LOGGING_AUDIT_TRAIL.md` for details

### Known Issues
- `OPENAI_API_KEY` loaded but not validated for None
- MCP server integrations (gmail/file container) are commented out
- Session memory management not implemented (conversation history truncation needed)
- Response interruption not yet implemented in realtime mode
