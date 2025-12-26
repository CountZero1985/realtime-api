# Realtime Voice Agent - Technical Specifications

**Project:** OpenAI Realtime API Voice Agent System
**Version:** 1.0
**Last Updated:** 2025-12-26

---

## Executive Summary

A production-ready real-time voice agent system integrating OpenAI's Realtime API and OpenAI Agents SDK. Supports both voice-based and CLI text-based interactions, primarily configured for Hungarian language but extensible to any language.

**Key Capabilities:**
- Real-time voice conversations with low latency (<1s)
- Multi-modal agent interactions (voice + text)
- Agent team coordination with sub-agent handoffs
- Web search and tool integration
- Three modes: Voice Pipeline, WebSocket Realtime, CLI Text

---

## Architecture Overview

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

---

## Data Flow

### Voice Pipeline Mode

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

### CLI Text Mode

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

### Realtime WebSocket Mode

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

---

## Component Specifications

### StreamingVoiceWorkflow (`openai_apis/voice/workflow.py`)

Custom adapter bridging VoicePipeline to Agents SDK Runner.

**Class:** `StreamingVoiceWorkflow(VoiceWorkflowBase)`

**Responsibilities:**
1. Maintain conversation input history in OpenAI format
2. Process transcriptions through `Runner.run_streamed()`
3. Stream agent responses to TTS pipeline
4. Track agent state for handoffs

**Data Format:**
```python
[
    {"role": "user", "content": "Transcription text"},
    {"role": "assistant", "content": "Agent response"}
]
```

### Agent Team (`openai_apis/agents/team.py`)

**assisstant_agent:**
- Model: `gpt-4o-mini`
- Role: Main conversational interface
- Tools: `get_current_time()`, `display_text_terminal()`
- Sub-agents: `tools_agent.as_tool()` for delegation

**tools_agent:**
- Model: `gpt-4o-mini`
- Role: Web search and information retrieval
- Tools: `websearch_tool`

**Handoff:** Main assistant delegates to tools_agent via `agents=[tools_agent.as_tool()]`. Runner handles orchestration.

### Agentic Tools (`openai_apis/agents/tools.py`)

| Tool | Function | Returns |
|------|----------|---------|
| `websearch_tool` | Web search with query | Hungarian text summary |
| `get_current_time()` | Current time | Hungarian text (e.g., "tizenegy óra harmincöt perc") |
| `display_text_terminal(text)` | Print to terminal | Confirmation message |

**Design Principles:**
- Hungarian language outputs for voice compatibility
- Descriptive text instead of raw data for TTS
- Low latency where possible

### Audio Utilities (`openai_apis/utils/audio_io.py`)

**`record_audio() -> np.ndarray`**
- Blocking, Enter-based recording
- Sample Rate: 24000 Hz, Channels: 1, Format: `np.int16`

**`AudioPlayer` (Context Manager)**
- Stream audio playback with low latency
- Queue-based buffering, thread-safe
- Usage: `with AudioPlayer() as player: player.add_audio(chunk)`

### Realtime WebSocket (`openai_apis/voice/realtime_session.py`)

**WebSocket URL:** `wss://api.openai.com/v1/realtime?model=gpt-4o-mini-realtime-preview-2024-12-17`

**Implemented Events:**
- Session: `session.created`, `session.updated`
- Conversation: `conversation.created`, `conversation.item.created`
- Audio buffer: `input_audio_buffer.committed`, `input_audio_buffer.cleared`
- Transcription: `conversation.item.input_audio_transcription.completed`
- Response: `response.created`, `response.done`, `response.audio.delta`, `response.audio.done`
- Transcript: `response.audio_transcript.delta`, `response.audio_transcript.done`
- Error: `error`

---

## Configuration

### Audio Configuration

| Parameter | Value |
|-----------|-------|
| Sample Rate | 24000 Hz (Realtime API requirement) |
| Channels | 1 (mono) |
| Format | PCM16 (16-bit signed integers) |
| VoicePipeline chunk size | 2400 samples |
| Realtime API chunk duration | 500ms (12000 samples) |

### Language Configuration

**Voice Pipeline Mode:**
```python
STTModelSettings(language="hu")
```

**Realtime WebSocket Mode:**
```python
{"input_audio_transcription": {"model": "whisper-1", "language": "hu"}}
```

**Extensibility:** Change `language` parameter + update agent instructions. Supports 90+ languages via Whisper.

### API Models

| Purpose | Model |
|---------|-------|
| Agent reasoning | gpt-4o-mini |
| Speech-to-text | gpt-4o-mini-transcribe |
| Text-to-speech | gpt-4o-mini-tts (voice: ash, speed: 4.0) |
| WebSocket realtime | gpt-4o-mini-realtime-preview-2024-12-17 |

---

## Performance Characteristics

### Latency Benchmarks

**Voice Pipeline Mode:**
- STT: ~500ms-1s
- Agent Processing: ~300ms-2s
- TTS: ~200ms-500ms
- **End-to-End:** ~1s-3.5s

**Realtime WebSocket Mode:**
- Audio Streaming: <100ms
- Response Initiation: ~200ms-500ms
- **End-to-End:** ~500ms-1s

### Resource Usage

| Resource | Usage |
|----------|-------|
| Memory | ~100-200 MB base |
| CPU | ~5-10% idle, ~20-40% active |
| Network | ~50-100 KB/s during conversation |

---

## Security Considerations

### API Key Management

- Load from `.env` file via `python-dotenv`
- Never commit `.env` to repository
- Use environment variables in production
- Rotate keys regularly

### Recommended Improvements

1. **API Key Validation:**
```python
if not OPENAI_API_KEY:
    raise ValueError("OPENAI_API_KEY not set")
```

2. **Connection Retry:**
```python
for attempt in range(3):
    try:
        ws.run_forever()
        break
    except Exception:
        if attempt < 2:
            time.sleep(2 ** attempt)
        else:
            raise
```

---

## Known Limitations

1. **No API Key Validation** - Loaded but not checked for None
2. **No Conversation Persistence** - History lost on restart
3. **No History Truncation** - Session memory management not implemented
4. **No Response Interruption** - Not implemented in realtime mode
5. **Fixed Language Per Session** - No auto-detection
6. **Single User** - No multi-user support
7. **Limited Error Recovery** - Connection drops require restart
8. **MCP Disabled** - Gmail/file container integrations commented out

---

## Roadmap

### Completed
- [x] Comprehensive logging with audit trails
- [x] OOP module structure (`openai_apis` package)
- [x] Stateless transcription endpoint
- [x] Stateless TTS endpoint
- [x] Unit and integration test suites

### Planned
- [ ] Response interruption capability
- [ ] Conversation persistence (database)
- [ ] Session memory management
- [ ] Multi-language support (dynamic)
- [ ] Web UI interface

---

## Glossary

| Term | Definition |
|------|------------|
| STT | Speech-to-Text (transcription) |
| TTS | Text-to-Speech (synthesis) |
| VAD | Voice Activity Detection |
| PTT | Push-to-Talk |
| PCM16 | 16-bit linear PCM audio format |
| MCP | Model Context Protocol |
| Handoff | Agent delegation to sub-agent |

---

**Document Version:** 2.1
