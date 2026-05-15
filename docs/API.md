# OpenAI APIs - API Reference

Complete API reference for the `openai_apis` Python package, covering transcription, text-to-speech, realtime voice, and shared infrastructure.

---

## Table of Contents

- [Overview](#overview)
- [Quick Start](#quick-start)
- [Configuration Classes](#configuration-classes)
  - [AudioFormat](#audioformat)
  - [VADConfig](#vadconfig)
  - [BaseConfig](#baseconfig)
- [Transcription API](#transcription-api)
  - [TranscriptionConfig](#transcriptionconfig)
  - [TranscriptionAPI](#transcriptionapi)
  - [TranscriptionSession](#transcriptionsession)
- [TTS API](#tts-api)
  - [TTSConfig](#ttsconfig)
  - [TTSRegistry](#ttsregistry)
  - [BaseTTSProvider](#basettsproider)
  - [OpenAITTSProvider (TTSAPI)](#openaitts provider-ttsapi)
  - [ElevenLabsTTSProvider](#elevenlabsttsprovider)
- [Realtime Voice API](#realtime-voice-api)
  - [RealtimeConfig](#realtimeconfig)
  - [ToolRegistry](#toolregistry)
  - [RealtimeAgentState](#realtimeagentstate)
  - [RealtimeSession](#realtimesession)
- [MCP Plugin System](#mcp-plugin-system)
  - [MCPPlugin](#mcpplugin)
  - [MCPPluginManager](#mcppluginmanager)
  - [FileSystemPlugin](#filesystemplugin)
  - [GmailPlugin](#gmailplugin)
- [Session Infrastructure](#session-infrastructure)
  - [SessionState](#sessionstate)
  - [InvalidStateTransition](#invalidstatetransition)
  - [BaseSession](#basesession)
- [Logging & Audit](#logging--audit)
  - [SessionAuditLog](#sessionauditlog)
  - [AuditEvent](#auditevent)
  - [Global Logging Functions](#global-logging-functions)
- [Web Server Example (FastAPI)](#web-server-example-fastapi)
  - [Endpoints](#endpoints)
  - [Architecture](#architecture)
  - [Testing](#testing)
  - [Production Deployment](#production-deployment)
- [Import Reference](#import-reference)

---

## Overview

The `openai_apis` package provides a unified Python interface for OpenAI's voice and text services, with three core API modules and an extensible plugin system:

- **Transcription API** - Speech-to-text using Whisper models
- **TTS API** - Text-to-speech synthesis with multiple voices
- **Realtime Voice API** - Low-latency WebSocket-based voice interaction
- **MCP Plugin System** - Model Context Protocol plugin architecture for extensible tool integration

All modules share common infrastructure for configuration, session management, audio format handling, and audit logging.

### Installation

```bash
# Install with UV (recommended)
uv sync

# Or with pip - core package only
pip install openai-apis

# With audio support (required for all features)
pip install openai-apis[audio]

# With all optional dependencies
pip install openai-apis[all]
```

### Environment Setup

All APIs require an OpenAI API key. Set the `OPENAI_API_KEY` environment variable:

```bash
export OPENAI_API_KEY="sk-..."
```

Or create a `.env` file in your project root:

```
OPENAI_API_KEY=sk-...
```

---

## Quick Start

**Note:** The `openai_apis` package exports a minimal, clean public API from the package root. For session-based APIs (recommended), use:
- `TranscriptionSession` for realtime transcription
- `RealtimeSession` for realtime voice
- `TTSRegistry.create()` for text-to-speech

Legacy stateless APIs (`TranscriptionAPI`, `TTSAPI`) are still available via submodule imports (e.g., `from openai_apis.transcription import TranscriptionAPI`).

### Transcription (Speech-to-Text)

**WebSocket Session (Recommended):**

```python
from openai_apis import TranscriptionSession, TranscriptionConfig

# Use async context manager
async with TranscriptionSession() as session:
    # Register callbacks
    session.on("transcript.completed", lambda t: print(f"Final: {t.transcript}"))

    # Send audio and commit
    await session.send_audio(audio_chunk)
    await session.commit_audio()
```

**Stateless API (Legacy):**

```python
from openai_apis.transcription import TranscriptionAPI
import numpy as np

# Initialize API (uses OPENAI_API_KEY from environment)
api = TranscriptionAPI()

# Transcribe numpy array (async)
audio_data = np.array([...], dtype=np.int16)  # 24kHz mono PCM16
transcript = await api.transcribe(audio_data)
print(transcript)

# Transcribe from file (sync)
transcript = api.transcribe_file_sync("recording.wav")
print(transcript)
```

### TTS (Text-to-Speech)

**Via Registry (Recommended):**

```python
from openai_apis import TTSRegistry, TTSConfig
import numpy as np

# Create provider via registry
config = TTSConfig(voice="sage", speed=1.0)
tts = TTSRegistry.create(config)

# Synthesize text to audio (async)
audio = await tts.synthesize("Hello, how are you?")
# audio is numpy array (int16, mono, 24kHz) ready for playback

# Save to file (sync)
tts.synthesize_to_file_sync("Hello world!", "output.mp3")
```

**Direct Provider Import (Alternative):**

```python
from openai_apis.tts import OpenAITTSProvider  # or TTSAPI (alias)

api = OpenAITTSProvider()
audio = await api.synthesize("Hello!")
```

### Realtime Voice (WebSocket)

```python
from openai_apis import RealtimeSession
import asyncio

async def main():
    async with RealtimeSession() as session:
        # Define callbacks
        def on_transcript(data):
            print(f"User said: {data.transcript}")

        def on_audio(chunk: bytes):
            # Process audio bytes
            play_audio(chunk)

        session.on("transcript.input", on_transcript)
        session.on("audio.delta", on_audio)

        # Send audio and trigger response
        await session.send_audio(audio_chunk)
        await session.commit_audio()
        await session.create_response()

asyncio.run(main())
```

---

## Configuration Classes

### AudioFormat

Immutable audio format specification used across all modules.

**Type:** `@dataclass(frozen=True)`

#### Fields

| Field | Type | Default | Valid Values | Description |
|-------|------|---------|--------------|-------------|
| `sample_rate` | `int` | `24000` | > 0 | Audio sample rate in Hz |
| `channels` | `int` | `1` | > 0 | Number of audio channels (1 = mono) |
| `dtype` | `str` | `"int16"` | `"int16"`, `"float32"` | NumPy dtype for audio data |
| `encoding` | `str` | `"pcm16"` | `"pcm16"`, `"g711_ulaw"`, `"g711_alaw"` | Audio encoding format |

#### Usage

```python
from openai_apis import AudioFormat

# Use defaults (24kHz, mono, int16, pcm16)
fmt = AudioFormat()

# Custom format for higher quality
fmt = AudioFormat(
    sample_rate=48000,
    channels=2,
    dtype="float32",
    encoding="pcm16"
)

# AudioFormat is immutable (frozen dataclass)
# fmt.sample_rate = 16000  # Raises FrozenInstanceError
```

#### Validation

- `sample_rate` must be positive
- `channels` must be positive
- `dtype` must be one of: `"int16"`, `"float32"`
- `encoding` must be one of: `"pcm16"`, `"g711_ulaw"`, `"g711_alaw"`

Raises `ValueError` if any validation fails.

---

### VADConfig

Voice Activity Detection configuration for realtime audio streams.

**Type:** `@dataclass`

#### Fields

| Field | Type | Default | Valid Values | Description |
|-------|------|---------|--------------|-------------|
| `mode` | `Literal[str]` | `"server_vad"` | `"server_vad"`, `"semantic_vad"`, `"disabled"` | VAD mode |
| `threshold` | `float` | `0.5` | 0.0-1.0 | Activation threshold (server_vad only) |
| `prefix_padding_ms` | `int` | `300` | >= 0 | Audio padding before speech (server_vad only) |
| `silence_duration_ms` | `int` | `500` | >= 0 | Silence duration to end turn (server_vad only) |
| `eagerness` | `Literal[str]` | `"auto"` | `"low"`, `"medium"`, `"high"`, `"auto"` | Turn detection eagerness (semantic_vad only) |

#### VAD Modes

- **`server_vad`**: Server-side silence detection using threshold and timing parameters
- **`semantic_vad`**: Semantic turn detection using eagerness parameter
- **`disabled`**: No VAD, continuous processing

#### Usage

```python
from openai_apis import VADConfig

# Server-side VAD with custom threshold
vad = VADConfig(
    mode="server_vad",
    threshold=0.7,
    silence_duration_ms=800
)

# Semantic turn detection
vad = VADConfig(
    mode="semantic_vad",
    eagerness="high"
)

# Disable VAD for continuous processing
vad = VADConfig(mode="disabled")
```

#### Validation

- `mode` must be one of the valid modes
- If `mode == "server_vad"`:
  - `threshold` must be between 0.0 and 1.0
  - `prefix_padding_ms` must be non-negative
  - `silence_duration_ms` must be non-negative
- If `mode == "semantic_vad"`:
  - `eagerness` must be one of the valid values

Raises `ValueError` if any validation fails.

---

### BaseConfig

Base configuration class for all API sessions. Inherited by `TranscriptionConfig`, `TTSConfig`, and `RealtimeConfig`.

**Type:** `@dataclass`

#### Fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `api_key` | `Optional[str]` | `None` | OpenAI API key. If `None`, reads from `OPENAI_API_KEY` env var |
| `timeout` | `float` | `30.0` | Request timeout in seconds (must be > 0) |
| `audio_format` | `AudioFormat` | `AudioFormat()` | Audio format specification |

#### Usage

```python
from openai_apis import BaseConfig, AudioFormat

# API key from environment (OPENAI_API_KEY)
config = BaseConfig()

# Explicit API key and custom timeout
config = BaseConfig(
    api_key="sk-...",
    timeout=60.0
)

# Custom audio format
fmt = AudioFormat(sample_rate=48000, channels=2)
config = BaseConfig(audio_format=fmt)
```

#### Validation

- If `api_key` is `None`, automatically reads from `OPENAI_API_KEY` environment variable
- `timeout` must be positive

Raises `ValueError` if validation fails.

---

## Transcription API

Speech-to-text transcription using OpenAI's Whisper models. Stateless API with no conversation history.

### TranscriptionConfig

Configuration for transcription settings. Extends `BaseConfig`.

**Type:** `@dataclass`

#### Fields

| Field | Type | Default | Valid Values | Description |
|-------|------|---------|--------------|-------------|
| `model` | `str` | `"gpt-realtime-whisper"` | See SUPPORTED_TRANSCRIPTION_MODELS | Model to use for transcription |
| `language` | `Optional[str]` | `"hu"` | ISO 639-1 code or `None` | Language code (None for auto-detect) |
| `vad` | `VADConfig` | `VADConfig()` | Valid VADConfig instance | Voice Activity Detection configuration |
| `keywords` | `list[str]` | `[]` | Any list of strings | Keywords to steer transcription accuracy |
| `prompt` | `Optional[str]` | `None` | Any string | Context prompt to guide transcription |
| `include_logprobs` | `bool` | `False` | `True`, `False` | Whether to request log probabilities from API |

Plus all fields from `BaseConfig` (`api_key`, `timeout`, `audio_format`).

**Supported Models (SUPPORTED_TRANSCRIPTION_MODELS):**
- `"gpt-realtime-whisper"` (default)
- `"gpt-4o-mini-transcribe"`
- `"gpt-4o-transcribe"`
- `"whisper-1"`

**Supported Languages (SUPPORTED_LANGUAGES):**
100+ ISO 639-1 language codes including: af, am, ar, as, az, ba, be, bg, bn, bo, br, bs, ca, cs, cy, da, de, el, en, es, et, eu, fa, fi, fo, fr, gl, gu, ha, haw, he, hi, hr, ht, hu, hy, id, is, it, ja, jw, ka, kk, km, kn, ko, la, lb, ln, lo, lt, lv, mg, mi, mk, ml, mn, mr, ms, mt, my, ne, nl, nn, no, oc, pa, pl, ps, pt, ro, ru, sa, sd, si, sk, sl, sn, so, sq, sr, su, sv, sw, ta, te, tg, th, tk, tl, tr, tt, uk, ur, uz, vi, yi, yo, yue, zh.

#### Validation

- `model` must be in `SUPPORTED_TRANSCRIPTION_MODELS`
- `language` must be a valid ISO 639-1 code or `None` (for auto-detect)
- `vad` must be a valid `VADConfig` instance
- All `BaseConfig` validations apply (timeout > 0, api_key loaded from env)

Raises `ValueError` if any validation fails.

#### Usage

```python
from openai_apis import TranscriptionConfig, VADConfig

# Use defaults (gpt-realtime-whisper, Hungarian, 24kHz mono)
config = TranscriptionConfig()

# Custom model and language
config = TranscriptionConfig(
    model="whisper-1",
    language="en"
)

# Auto-detect language
config = TranscriptionConfig(language=None)

# With VAD configuration
vad = VADConfig(mode="semantic_vad", eagerness="high")
config = TranscriptionConfig(vad=vad)

# With keywords for better accuracy on domain-specific terms
config = TranscriptionConfig(
    keywords=["OpenAI", "Budapest", "Python"],
    prompt="Technical discussion about AI"
)

# Request log probabilities
config = TranscriptionConfig(include_logprobs=True)

# All features combined
config = TranscriptionConfig(
    model="gpt-4o-mini-transcribe",
    language="en",
    vad=VADConfig(mode="server_vad", threshold=0.7),
    keywords=["machine learning", "neural networks"],
    prompt="AI research discussion",
    include_logprobs=True
)
```

---

### TranscriptionAPI

Main transcription API class. Provides async and sync interfaces for audio transcription.

**Constructor:**

```python
TranscriptionAPI(config: Optional[TranscriptionConfig] = None)
```

**Parameters:**
- `config` (`Optional[TranscriptionConfig]`): Configuration. If `None`, uses default `TranscriptionConfig()`.

**Attributes:**
- `config` (`TranscriptionConfig`): Current configuration
- `client` (`AsyncOpenAI`): Async OpenAI client
- `sync_client` (`OpenAI`): Sync OpenAI client

#### Async Methods

**`transcribe(audio, language=None, prompt=None) -> str`**

Transcribe audio from numpy array.

- **Parameters:**
  - `audio` (`np.ndarray`): Audio data (int16 or float32, mono or stereo)
  - `language` (`Optional[str]`): Language override
  - `prompt` (`Optional[str]`): Context prompt override
- **Returns:** `str` - Transcribed text
- **Raises:** `ValueError` if audio is empty or invalid

**`transcribe_file(file_path, language=None, prompt=None) -> str`**

Transcribe audio from file.

- **Parameters:**
  - `file_path` (`Union[str, Path]`): Path to audio file
  - `language` (`Optional[str]`): Language override
  - `prompt` (`Optional[str]`): Context prompt override
- **Returns:** `str` - Transcribed text
- **Raises:** `FileNotFoundError` if file doesn't exist

**`transcribe_batch(audio_files, language=None, prompt=None) -> list[str]`**

Transcribe multiple files in batch.

- **Parameters:**
  - `audio_files` (`list[Union[str, Path]]`): List of file paths
  - `language` (`Optional[str]`): Language override
  - `prompt` (`Optional[str]`): Context prompt override
- **Returns:** `list[str]` - List of transcripts in same order
- **Raises:** `FileNotFoundError` if any file doesn't exist

#### Sync Methods

Same signatures as async methods, with `_sync` suffix:
- `transcribe_sync(audio, language=None, prompt=None) -> str`
- `transcribe_file_sync(file_path, language=None, prompt=None) -> str`
- `transcribe_batch_sync(audio_files, language=None, prompt=None) -> list[str]`

#### Convenience Functions

The module also exports standalone functions for common use cases:

```python
from openai_apis.transcription import (
    transcribe_audio,      # async, numpy array
    transcribe_file,       # async, file path
    transcribe_audio_sync, # sync, numpy array
    transcribe_file_sync   # sync, file path
)
```

#### Usage Examples

**Basic transcription from numpy array:**

```python
from openai_apis import TranscriptionAPI
import numpy as np

api = TranscriptionAPI()

# Transcribe audio data (async)
audio = np.array([...], dtype=np.int16)  # 24kHz mono PCM16
transcript = await api.transcribe(audio)
print(transcript)
```

**Transcribe from file (sync):**

```python
api = TranscriptionAPI()

# Transcribe WAV file
transcript = api.transcribe_file_sync("recording.wav")
print(transcript)
```

**Batch transcription with custom settings:**

```python
config = TranscriptionConfig(
    model="whisper-1",
    language="en",
    keywords=["technical", "API"]
)
api = TranscriptionAPI(config)

files = ["file1.wav", "file2.mp3", "file3.m4a"]
transcripts = await api.transcribe_batch(files)

for file, text in zip(files, transcripts):
    print(f"{file}: {text}")
```

---

### TranscriptionSession

WebSocket-based async session for real-time transcription via OpenAI Realtime API. Inherits from `BaseSession` for lifecycle management.

**Constructor:**

```python
TranscriptionSession(
    config: Optional[TranscriptionConfig] = None,
    max_reconnect_attempts: int = 3,
    reconnect_delay: float = 1.0
)
```

**Parameters:**
- `config` (`Optional[TranscriptionConfig]`): Configuration. If `None`, uses default `TranscriptionConfig()`.
- `max_reconnect_attempts` (`int`): Maximum reconnection attempts on connection drop (default: 3)
- `reconnect_delay` (`float`): Base delay in seconds between reconnect attempts (default: 1.0, exponential backoff)

**Attributes:**
- `session_id` (`str`): Unique session UUID
- `state` (`SessionState`): Current session state (CREATED, CONNECTING, CONNECTED, DISCONNECTING, CLOSED)
- `audit_log` (`SessionAuditLog`): Per-session audit trail

**Constants:**
- `WEBSOCKET_URL` = `"wss://api.openai.com/v1/realtime"`
- `REALTIME_MODEL` = `"gpt-4o-mini-realtime-preview-2024-12-17"`

#### Methods

**`async send_audio(chunk: bytes) -> None`**

Send base64-encoded PCM16 audio chunk to the server.

- **Parameters:**
  - `chunk` (`bytes`): Raw PCM16 audio bytes (24kHz mono)
- **Raises:** `InvalidStateTransition` if session is not in CONNECTED state
- **Audit Event:** `audio.chunk_sent` with `{"chunk_size": <bytes>}`

**`async commit_audio() -> None`**

Commit audio buffer to trigger transcription (push-to-talk mode).

- **Raises:** `InvalidStateTransition` if session is not in CONNECTED state
- **Audit Event:** `audio.buffer_committed`

**`async update_vad(vad_config: VADConfig) -> None`**

Update Voice Activity Detection configuration at runtime.

Sends a `session.update` event with new turn_detection configuration. Can be called while the session is connected to switch between VAD modes (server_vad, semantic_vad, disabled).

- **Parameters:**
  - `vad_config` (`VADConfig`): New VAD configuration to apply
- **Raises:** `InvalidStateTransition` if session is not in CONNECTED state
- **Audit Event:** `vad.updated` with `{"mode": <vad_mode>}`
- **Side Effects:** Updates internal `_config.vad_config` to preserve setting across reconnections

**`on(event: str, callback: Callable) -> None`**

Register a callback for a specific event (inherited from `BaseSession`).

- **Parameters:**
  - `event` (`str`): Event name (see [Supported Events](#supported-events) below)
  - `callback` (`Callable[[dict], None]`): Callback function receiving event data

#### Supported Events

Events can be registered via `session.on(event_name, callback)`:

| Event | Data Fields | Description |
|-------|-------------|-------------|
| `transcript.delta` | `delta` (str), `item_id` (str), `content_index` (int) | Partial transcription text (streaming) |
| `transcript.completed` | `transcript` (str), `item_id` (str), `content_index` (int) | Final complete transcription |
| `error` | `type` (str), `error` (dict), `item_id` (str, optional) | Error events from server |
| `session.created` | Server session configuration (dict) | Server session created |
| `session.updated` | Server session configuration (dict) | Server session configured |

**Inherited events from BaseSession:**
- `session.created`: Local session created
- `session.state_transition`: State changed (data: `{"from": <state>, "to": <state>}`)
- `session.closed`: Local session closed

#### Lifecycle Management

`TranscriptionSession` implements the `BaseSession` async context manager pattern:

```python
async with TranscriptionSession(config) as session:
    # Session is automatically connected (state: CONNECTED)
    # Work with session here
    pass
# Session is automatically disconnected (state: CLOSED)
```

**State transitions:**
1. **CREATED** → Initial state after `__init__`
2. **CONNECTING** → During `async with` entry (establishing WebSocket)
3. **CONNECTED** → After successful connection and configuration
4. **DISCONNECTING** → During `async with` exit (closing WebSocket)
5. **CLOSED** → Final state after cleanup

#### Usage Examples

**Basic real-time transcription:**

```python
from openai_apis import TranscriptionSession, TranscriptionConfig

# Configure session
config = TranscriptionConfig(language="hu", model="whisper-1")

# Connect and transcribe
async with TranscriptionSession(config) as session:
    # Register callback for complete transcripts
    def on_transcript(data):
        print(f"Transcript: {data['transcript']}")

    session.on("transcript.completed", on_transcript)

    # Send audio chunks (PCM16, 24kHz mono)
    for chunk in audio_chunks:
        await session.send_audio(chunk)

    # Commit to trigger transcription
    await session.commit_audio()
```

**Streaming transcription with delta events:**

```python
async with TranscriptionSession() as session:
    # Register callbacks for streaming and final transcript
    session.on("transcript.delta", lambda d: print(d["delta"], end=""))
    session.on("transcript.completed", lambda d: print(f"\nFinal: {d['transcript']}"))

    # Stream audio
    await session.send_audio(audio_chunk_1)
    await session.send_audio(audio_chunk_2)
    await session.commit_audio()
```

**Error handling and reconnection:**

```python
config = TranscriptionConfig(language="en")

async with TranscriptionSession(
    config,
    max_reconnect_attempts=5,
    reconnect_delay=2.0
) as session:
    # Register error callback
    def on_error(data):
        print(f"Error: {data['type']} - {data.get('error')}")

    session.on("error", on_error)

    # Send audio and commit
    await session.send_audio(audio_data)
    await session.commit_audio()
```

**VAD configuration and runtime switching:**

```python
from openai_apis import TranscriptionSession, TranscriptionConfig, VADConfig

# Start with server-side VAD
vad = VADConfig(mode="server_vad", threshold=0.6, silence_duration_ms=600)
config = TranscriptionConfig(vad_config=vad)

async with TranscriptionSession(config) as session:
    # Stream audio with automatic turn detection
    await session.send_audio(audio_chunk)
    # No need to call commit_audio() - VAD handles turn detection

    # Switch to semantic VAD at runtime
    new_vad = VADConfig(mode="semantic_vad", eagerness="high")
    await session.update_vad(new_vad)

    # Switch to push-to-talk mode (disable VAD)
    await session.update_vad(VADConfig(mode="disabled"))
    await session.send_audio(audio_chunk)
    await session.commit_audio()  # Manual commit required when VAD disabled
```

**Access audit trail:**

```python
async with TranscriptionSession() as session:
    await session.send_audio(audio_data)
    await session.commit_audio()

    # Export session audit log
    session.audit_log.export_to_file("session_audit.json")

    # Or access events directly
    for event in session.audit_log.events:
        print(f"{event.timestamp}: {event.event_type} - {event.data}")
```

#### Reconnection Behavior

If the WebSocket connection drops during the receive loop, `TranscriptionSession` automatically attempts reconnection:

1. Detects `websockets.ConnectionClosed` exception
2. Attempts reconnection up to `max_reconnect_attempts` times
3. Uses exponential backoff: `delay = reconnect_delay * (2 ** attempt)`
4. Re-establishes connection and re-configures session
5. Emits `error` event if all attempts fail

**Note:** Audio buffer is **not** preserved during reconnection. Callers should handle the `error` callback to detect reconnection failures and re-send audio if needed.

---

## TTS API

Text-to-speech synthesis using OpenAI's TTS models. Provider-based architecture for extensibility.

### TTSConfig

Configuration for TTS settings. Extends `BaseConfig`.

**Type:** `@dataclass`

#### Fields

| Field | Type | Default | Valid Values | Description |
|-------|------|---------|--------------|-------------|
| `provider` | `str` | `"openai"` | Must be registered in provider registry | Provider identifier (validated on init) |
| `model` | `str` | `"gpt-4o-mini-tts"` | `"gpt-4o-mini-tts"`, `"tts-1"`, `"tts-1-hd"` | TTS model |
| `voice` | `str` | `"ash"` | See [supported voices](#openaitts-provider-ttsapi) | Voice to use (validated against provider, 13 voices for OpenAI) |
| `speed` | `float` | `1.0` | 0.25-4.0 | Speech speed multiplier (validated on init, 1.0 = normal speed) |
| `instructions` | `Optional[str]` | `None` | Any string | Voice steering instructions (gpt-4o-mini-tts only) |
| `output_format` | `str` | `"pcm"` | `"pcm"`, `"mp3"`, `"opus"`, `"aac"`, `"flac"`, `"wav"` | Output audio format (validated on init) |
| `language` | `str` | `"hu"` | ISO-639-1 code | Language hint for synthesis |
| `sample_rate` | `int` | `24000` | > 0 | Sample rate (PCM format only) |
| `chunk_size` | `int` | `1024` | > 0 | Streaming chunk size in bytes (validated on init) |

Plus all fields from `BaseConfig` (`api_key`, `timeout`, `audio_format`).

#### Validation

`TTSConfig` validates all parameters on initialization via `__post_init__`:

- **`speed`**: Must be between 0.25 and 4.0 (inclusive). Raises `ValueError` if out of range.
- **`output_format`**: Must be one of: `"pcm"`, `"mp3"`, `"opus"`, `"aac"`, `"flac"`, `"wav"`. Raises `ValueError` if invalid.
- **`chunk_size`**: Must be positive (> 0). Raises `ValueError` if not positive.
- **`provider`**: Must be registered in the provider registry. Raises `ValueError` if unknown. Currently supported: "openai", "elevenlabs".
- **`voice`**: Must be in the provider's `supported_voices`. For OpenAI provider, must be one of 13 supported voices. For ElevenLabs, must be one of 3 voices (rachel, adam, bella). Raises `ValueError` if invalid.

```python
# Valid configuration
config = TTSConfig(speed=2.0, voice="sage", output_format="mp3")

# Invalid speed - raises ValueError
config = TTSConfig(speed=5.0)  # ValueError: speed must be between 0.25 and 4.0

# Invalid voice - raises ValueError
config = TTSConfig(voice="unknown")  # ValueError: Invalid voice 'unknown'

# Invalid format - raises ValueError
config = TTSConfig(output_format="ogg")  # ValueError: output_format must be one of ...

# Invalid provider - raises ValueError
config = TTSConfig(provider="fake")  # ValueError: Unknown provider 'fake'
```

#### Usage

```python
from openai_apis import TTSConfig

# Use defaults (gpt-4o-mini-tts, ash voice, 1.0x speed, PCM)
config = TTSConfig()

# Custom voice and speed
config = TTSConfig(
    voice="sage",
    speed=1.5,
    output_format="mp3"
)

# Instruction-based voice steering (gpt-4o-mini-tts only)
config = TTSConfig(
    model="gpt-4o-mini-tts",
    voice="ash",
    instructions="Speak in a warm, friendly tone with slight excitement"
)

# High quality TTS
config = TTSConfig(
    model="tts-1-hd",
    voice="alloy",
    speed=1.0
)
```

---

### TTSRegistry

Class-based registry for managing TTS providers using the factory pattern. Provides methods to register, retrieve, and instantiate TTS providers.

**Type:** Class (singleton-like, all methods are class methods)

#### Class Methods

**`register(name: str, provider_class: Type[BaseTTSProvider]) -> None`**

Register a TTS provider class.

- **Parameters:**
  - `name` (`str`): Provider name (e.g., "openai", "elevenlabs")
  - `provider_class` (`Type[BaseTTSProvider]`): Provider class inheriting from `BaseTTSProvider`
- **Returns:** `None`

**`get(name: str) -> Type[BaseTTSProvider]`**

Get a registered TTS provider class by name.

- **Parameters:**
  - `name` (`str`): Provider name
- **Returns:** `Type[BaseTTSProvider]` - Provider class
- **Raises:** `KeyError` if provider is not registered

**`create(config: TTSConfig) -> BaseTTSProvider`**

Create a TTS provider instance from configuration using the factory pattern.

- **Parameters:**
  - `config` (`TTSConfig`): Configuration with `provider` field set
- **Returns:** `BaseTTSProvider` - Instantiated TTS provider
- **Raises:** `KeyError` if `config.provider` is not registered

**`list_providers() -> list[str]`**

List all registered provider names.

- **Returns:** `list[str]` - Sorted list of registered provider names

#### Backward-Compatible Functions

For backward compatibility, the module also exports free functions:

- `register_provider(name, provider_class)` - Thin wrapper around `TTSRegistry.register()`
- `get_provider(name)` - Thin wrapper around `TTSRegistry.get()`

#### Built-in Providers

The following providers are auto-registered on module import:
- **"openai"** - `OpenAITTSProvider`
- **"elevenlabs"** - `ElevenLabsTTSProvider` (stub)

#### Usage Examples

**Listing registered providers:**

```python
from openai_apis import TTSRegistry

# Get all registered providers
providers = TTSRegistry.list_providers()
print(providers)  # ["elevenlabs", "openai"]
```

**Creating a provider from config:**

```python
from openai_apis import TTSRegistry, TTSConfig

# Factory pattern - create provider from config
config = TTSConfig(provider="openai", voice="sage")
provider = TTSRegistry.create(config)

# Provider is an instance of OpenAITTSProvider
audio = await provider.synthesize("Hello world!")
```

**Registering a custom provider:**

```python
from openai_apis import TTSRegistry, BaseTTSProvider

class MyCustomTTSProvider(BaseTTSProvider):
    @property
    def provider_name(self) -> str:
        return "custom"

    @property
    def supported_voices(self) -> list[str]:
        return ["voice1", "voice2"]

    # Implement abstract methods...
    async def synthesize(self, text, voice=None, speed=None):
        # Implementation
        pass

# Register the custom provider
TTSRegistry.register("custom", MyCustomTTSProvider)

# Now it's available for use
config = TTSConfig(provider="custom", voice="voice1")
provider = TTSRegistry.create(config)
```

**Getting a provider class directly:**

```python
from openai_apis import TTSRegistry

# Get the provider class (not an instance)
provider_class = TTSRegistry.get("openai")
print(provider_class)  # <class 'OpenAITTSProvider'>

# Instantiate it manually
provider = provider_class(config=my_config)
```

**Using backward-compatible functions:**

```python
from openai_apis.tts import register_provider, get_provider

# Same as TTSRegistry.register()
register_provider("my_provider", MyProviderClass)

# Same as TTSRegistry.get()
provider_class = get_provider("openai")
```

---

### BaseTTSProvider

Abstract base class for TTS providers. Defines the provider interface that all TTS providers must implement. Provides concrete sync wrapper methods that delegate to the async abstract methods.

**Public API Name:** `TTSProvider` (exported from package root as an alias for `BaseTTSProvider`)

**Type:** Abstract class

#### Abstract Methods

Subclasses must implement these async methods:

**`async synthesize(text: str, voice: Optional[str] = None, speed: Optional[float] = None) -> np.ndarray`**

Synthesize text to audio as numpy array (async).

- **Parameters:**
  - `text` (`str`): Text to synthesize
  - `voice` (`Optional[str]`): Voice override (provider-specific)
  - `speed` (`Optional[float]`): Speed multiplier override
- **Returns:** `np.ndarray` - Audio data as numpy array

**`async synthesize_stream(text: str, voice: Optional[str] = None, speed: Optional[float] = None, chunk_size: Optional[int] = None) -> AsyncIterator[bytes]`**

Synthesize text to audio with streaming (async).

- **Parameters:**
  - `text` (`str`): Text to synthesize
  - `voice` (`Optional[str]`): Voice override (provider-specific)
  - `speed` (`Optional[float]`): Speed multiplier override
  - `chunk_size` (`Optional[int]`): Chunk size override (bytes). If None, uses config default. API response bytes are buffered and yielded in uniform chunks of this size.
- **Yields:** `bytes` - Audio chunks

**`async synthesize_to_file(text: str, file_path: Union[str, Path], voice: Optional[str] = None, speed: Optional[float] = None) -> Path`**

Synthesize text to audio and save to file (async).

- **Parameters:**
  - `text` (`str`): Text to synthesize
  - `file_path` (`Union[str, Path]`): Output file path
  - `voice` (`Optional[str]`): Voice override (provider-specific)
  - `speed` (`Optional[float]`): Speed multiplier override
- **Returns:** `Path` - Path to the saved audio file

#### Abstract Properties

Subclasses must implement these properties:

**`supported_voices` (property) -> list[str]**

List of voices supported by this provider.

**`provider_name` (property) -> str**

Provider identifier (e.g., "openai", "elevenlabs").

#### Concrete Methods

The base class provides these sync wrapper methods (inherited automatically):

**`synthesize_sync(text: str, voice: Optional[str] = None, speed: Optional[float] = None) -> np.ndarray`**

Synchronous wrapper for `synthesize()`. Delegates to the async method using `asyncio.run()`.

**`synthesize_to_file_sync(text: str, file_path: Union[str, Path], voice: Optional[str] = None, speed: Optional[float] = None) -> Path`**

Synchronous wrapper for `synthesize_to_file()`. Delegates to the async method using `asyncio.run()`.

#### Usage

```python
from openai_apis.tts import BaseTTSProvider
from typing import AsyncIterator, Optional, Union
from pathlib import Path
import numpy as np

class MyCustomTTSProvider(BaseTTSProvider):
    """Custom TTS provider implementation."""

    @property
    def supported_voices(self) -> list[str]:
        return ["voice_a", "voice_b", "voice_c"]

    @property
    def provider_name(self) -> str:
        return "my_custom_provider"

    async def synthesize(self, text: str, voice: Optional[str] = None,
                        speed: Optional[float] = None) -> np.ndarray:
        # Implementation here
        return np.array([...], dtype=np.int16)

    async def synthesize_stream(self, text: str, voice: Optional[str] = None,
                               speed: Optional[float] = None) -> AsyncIterator[bytes]:
        # Implementation here
        for chunk in chunks:
            yield chunk

    async def synthesize_to_file(self, text: str, file_path: Union[str, Path],
                                voice: Optional[str] = None,
                                speed: Optional[float] = None) -> Path:
        # Implementation here
        audio = await self.synthesize(text, voice, speed)
        # Save audio to file...
        return Path(file_path)

# Usage - sync wrappers are inherited automatically
provider = MyCustomTTSProvider()
audio = provider.synthesize_sync("Hello world!")  # No need to implement this
provider.synthesize_to_file_sync("Text", "output.wav")  # Inherited from base
```

---

### OpenAITTSProvider (TTSAPI)

OpenAI text-to-speech provider. Implements `BaseTTSProvider` interface. Also exported as `TTSAPI` alias for backward compatibility.

**Constructor:**

```python
OpenAITTSProvider(config: Optional[TTSConfig] = None)
```

**Parameters:**
- `config` (`Optional[TTSConfig]`): Configuration. If `None`, uses default `TTSConfig()`.

**Attributes:**
- `config` (`TTSConfig`): Current configuration
- `client` (`AsyncOpenAI`): Async OpenAI client
- `sync_client` (`OpenAI`): Sync OpenAI client

#### Properties

**`supported_voices` (property) -> list[str]**

List of voices supported by OpenAI TTS.

- **Returns:** `["alloy", "ash", "ballad", "coral", "echo", "fable", "nova", "onyx", "sage", "shimmer", "verse", "marin", "cedar"]` (13 voices)

**`provider_name` (property) -> str**

Provider identifier.

- **Returns:** `"openai"`

#### Async Methods

**`synthesize(text, voice=None, speed=None, instructions=None) -> np.ndarray`**

Synthesize text to speech as numpy array.

- **Parameters:**
  - `text` (`str`): Text to synthesize
  - `voice` (`Optional[str]`): Voice override
  - `speed` (`Optional[float]`): Speed override
  - `instructions` (`Optional[str]`): Voice steering instructions (gpt-4o-mini-tts only)
- **Returns:** `np.ndarray` - Audio data (int16, mono, 24kHz for PCM)
- **Raises:** `ValueError` if text is empty, `TTSSynthesisError` on API errors

**`synthesize_to_file(text, file_path, voice=None, speed=None, instructions=None) -> Path`**

Synthesize text and save to file.

- **Parameters:**
  - `text` (`str`): Text to synthesize
  - `file_path` (`Union[str, Path]`): Output file path
  - `voice` (`Optional[str]`): Voice override
  - `speed` (`Optional[float]`): Speed override
  - `instructions` (`Optional[str]`): Voice steering instructions (gpt-4o-mini-tts only)
- **Returns:** `Path` - Path to the saved audio file
- **Raises:** `ValueError` if text is empty, `TTSSynthesisError` on API errors

**`synthesize_stream(text, voice=None, speed=None, instructions=None, chunk_size=None, backpressure_event=None) -> AsyncIterator[bytes]`**

Synthesize text with streaming audio chunks. Includes comprehensive audit logging (start, complete, error events).

- **Parameters:**
  - `text` (`str`): Text to synthesize
  - `voice` (`Optional[str]`): Voice override
  - `speed` (`Optional[float]`): Speed override
  - `instructions` (`Optional[str]`): Voice steering instructions (gpt-4o-mini-tts only)
  - `chunk_size` (`Optional[int]`): Chunk size override (bytes). If None, uses config default. API response bytes are buffered and yielded in uniform chunks of exactly this size (except potentially the final chunk).
  - `backpressure_event` (`Optional[asyncio.Event]`): Optional asyncio.Event for backpressure control. When provided, the generator awaits this event before yielding each chunk. Consumer should set() the event to allow streaming, and clear() to pause. The event must be set initially, or the generator will block.
- **Yields:** `bytes` - Audio chunks (uniform size, except potentially final chunk)
- **Raises:** `ValueError` if text is empty, `TTSSynthesisError` on API errors

**`synthesize_batch(texts, voice=None, speed=None) -> list[np.ndarray]`**

Synthesize multiple texts in batch.

- **Parameters:**
  - `texts` (`list[str]`): List of texts to synthesize
  - `voice` (`Optional[str]`): Voice override
  - `speed` (`Optional[float]`): Speed override
- **Returns:** `list[np.ndarray]` - List of audio arrays
- **Raises:** `ValueError` if any text is empty

#### Sync Methods

**Inherited from `BaseTTSProvider`:**
- `synthesize_sync(text, voice=None, speed=None) -> np.ndarray` - Synchronous wrapper for `synthesize()`
- `synthesize_to_file_sync(text, file_path, voice=None, speed=None) -> Path` - Synchronous wrapper for `synthesize_to_file()`

**OpenAI-specific sync methods:**
- `synthesize_batch_sync(texts, voice=None, speed=None) -> list[np.ndarray]` - Batch synthesis (synchronous)

#### Convenience Functions

```python
from openai_apis.tts import (
    synthesize_text,      # async, returns numpy array
    synthesize_to_file,   # async, saves to file
    synthesize_text_sync, # sync, returns numpy array
    synthesize_to_file_sync # sync, saves to file
)
```

#### Provider Registry

The TTS module includes a provider registry for managing multiple TTS providers:

```python
from openai_apis.tts import register_provider, get_provider

# Register a custom provider
register_provider("my_provider", MyCustomTTSProvider)

# Get a provider by name
provider_class = get_provider("openai")  # Returns OpenAITTSProvider
```

#### Usage Examples

**Basic synthesis:**

```python
from openai_apis import TTSRegistry, TTSConfig

# Via registry (recommended)
config = TTSConfig(voice="sage")
tts = TTSRegistry.create(config)

# Synthesize to numpy array (async)
audio = await tts.synthesize("Hello, how are you?")
# audio is int16 numpy array, ready for playback

# Synthesize to file (sync)
tts.synthesize_to_file_sync("Hello world!", "output.mp3")

# Or direct provider import (alternative)
from openai_apis.tts import OpenAITTSProvider
api = OpenAITTSProvider()
audio = await api.synthesize("Hello!")
```

**Streaming synthesis:**

```python
from openai_apis import OpenAITTSProvider, TTSConfig

api = OpenAITTSProvider()

# Basic streaming with default chunk size (1024 bytes)
async for audio_chunk in api.synthesize_stream("Long text to synthesize..."):
    # Play or process each chunk as it arrives
    play_audio(audio_chunk)

# Custom chunk size from config
config = TTSConfig(chunk_size=2048)  # 2KB chunks
api = OpenAITTSProvider(config=config)
async for chunk in api.synthesize_stream("Text"):
    # Chunks are exactly 2048 bytes (except final chunk)
    process_chunk(chunk)

# Override chunk size per call
async for chunk in api.synthesize_stream("Text", chunk_size=512):
    # 512-byte chunks for this specific call
    process_chunk(chunk)

# Backpressure control for flow management
import asyncio
backpressure = asyncio.Event()
backpressure.set()  # Must be set initially to allow streaming

async for chunk in api.synthesize_stream(
    "Long text to synthesize...",
    backpressure_event=backpressure
):
    # Process chunk
    await play_audio_async(chunk)

    # Pause streaming if buffer is full
    if audio_buffer_full():
        backpressure.clear()  # Pauses next chunk
        await asyncio.sleep(0.1)
        backpressure.set()  # Resumes streaming
```

**Batch synthesis with custom voice:**

```python
config = TTSConfig(voice="sage", speed=1.2)
api = OpenAITTSProvider(config)

texts = ["First sentence.", "Second sentence.", "Third sentence."]
audio_arrays = await api.synthesize_batch(texts)

for i, audio in enumerate(audio_arrays):
    print(f"Text {i+1}: {len(audio)} samples")
```

**Instruction-based voice steering (gpt-4o-mini-tts only):**

```python
from openai_apis import TTSRegistry, TTSConfig

# Configure with instructions
config = TTSConfig(
    model="gpt-4o-mini-tts",
    voice="ash",
    instructions="Speak in a warm, friendly tone with slight excitement"
)
tts = TTSRegistry.create(config)

# Instructions from config are used automatically
audio = await tts.synthesize("Hello! How can I help you today?")

# Or override per-call
audio = await tts.synthesize(
    "This is urgent!",
    instructions="Speak quickly with urgency"
)
```

**Error handling:**

```python
from openai_apis import TTSRegistry, TTSConfig
from openai_apis.tts import TTSSynthesisError

tts = TTSRegistry.create(TTSConfig())

try:
    audio = await tts.synthesize("Hello world!")
except TTSSynthesisError as e:
    print(f"TTS synthesis failed: {e}")
```

The `TTSSynthesisError` exception is raised when the TTS API encounters errors during synthesis, including API failures, network issues, or processing errors. All OpenAI TTS methods (`synthesize`, `synthesize_stream`, `synthesize_to_file`) can raise this exception.

---

### ElevenLabsTTSProvider

ElevenLabs text-to-speech provider stub. Implements `BaseTTSProvider` interface but all synthesis methods raise `NotImplementedError`. Serves as a placeholder for future ElevenLabs integration.

**Status:** Stub implementation - not functional

**Constructor:**

```python
ElevenLabsTTSProvider(config: Optional[TTSConfig] = None)
```

**Parameters:**
- `config` (`Optional[TTSConfig]`): Configuration (stored but not used in stub)

**Attributes:**
- `config` (`Optional[TTSConfig]`): Stored configuration

#### Properties

**`supported_voices` (property) -> list[str]**

List of voices supported by ElevenLabs TTS (stub).

- **Returns:** `["rachel", "adam", "bella"]` (3 voices)

**`provider_name` (property) -> str**

Provider identifier.

- **Returns:** `"elevenlabs"`

#### Methods

All synthesis methods raise `NotImplementedError`:

**`async synthesize(text, voice=None, speed=None) -> np.ndarray`**

- **Raises:** `NotImplementedError("ElevenLabs provider not yet implemented")`

**`async synthesize_stream(text, voice=None, speed=None) -> AsyncIterator[bytes]`**

- **Raises:** `NotImplementedError("ElevenLabs provider not yet implemented")`

**`async synthesize_to_file(text, file_path, voice=None, speed=None) -> Path`**

- **Raises:** `NotImplementedError("ElevenLabs provider not yet implemented")`

**`synthesize_sync(text, voice=None, speed=None) -> np.ndarray`**

Inherited sync wrapper from `BaseTTSProvider`.

- **Raises:** `NotImplementedError("ElevenLabs provider not yet implemented")`

**`synthesize_to_file_sync(text, file_path, voice=None, speed=None) -> Path`**

Inherited sync wrapper from `BaseTTSProvider`.

- **Raises:** `NotImplementedError("ElevenLabs provider not yet implemented")`

#### Usage

The ElevenLabs provider is registered and can be used in configuration, but all synthesis operations will fail:

```python
from openai_apis import TTSConfig, TTSRegistry

# Valid configuration - provider and voices are validated
config = TTSConfig(provider="elevenlabs", voice="rachel")

# Create provider instance
provider = TTSRegistry.create(config)
print(provider.provider_name)  # "elevenlabs"
print(provider.supported_voices)  # ["rachel", "adam", "bella"]

# But synthesis will fail
try:
    audio = await provider.synthesize("Hello world!")
except NotImplementedError as e:
    print(f"Expected: {e}")  # "ElevenLabs provider not yet implemented"
```

**Why this exists:** The stub implementation allows the provider registry architecture to be tested and validated before integrating the actual ElevenLabs API. It also demonstrates the provider pattern for future TTS provider implementations.

---

## Realtime Voice API

Low-latency WebSocket-based voice interaction using OpenAI's Realtime API.

**Note:** Requires optional dependencies: `websocket-client`, `numpy`, `sounddevice`. Install with:

```bash
pip install openai-apis[audio]
```

### RealtimeConfig

Configuration for Realtime API sessions. Extends `BaseConfig`.

**Type:** `@dataclass`

#### Fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `model` | `str` | `"gpt-realtime-mini"` | Realtime model (gpt-realtime-mini, gpt-4o-mini-realtime-preview-2024-12-17, gpt-4o-realtime-preview, gpt-4o-realtime-preview-2024-12-17) |
| `instructions` | `Optional[str]` | `None` | System prompt / instructions for the agent |
| `voice` | `str` | `"ash"` | Output voice for TTS (alloy, ash, ballad, coral, echo, sage, shimmer, verse) |
| `language` | `str` | `"hu"` | Language code for transcription (ISO-639-1) |
| `vad` | `VADConfig` | `VADConfig()` | Voice Activity Detection configuration |
| `temperature` | `float` | `0.8` | Model sampling temperature (0.6-1.2) |
| `max_response_output_tokens` | `Union[int, str]` | `"inf"` | Max output tokens ("inf" or positive integer) |
| `input_audio_transcription` | `bool` | `True` | Whether to request input audio transcription |
| `modalities` | `list[str]` | `["audio", "text"]` | Enabled modalities (["audio", "text"]) |
| `tools` | `Union[list[dict], ToolRegistry]` | `[]` | Tool definitions (JSON Schema format) or ToolRegistry instance for automatic execution |

Plus all fields from `BaseConfig` (`api_key`, `timeout`, `audio_format`).

**Note:** Audio format (sample rate, channels, encoding) is now configured via `BaseConfig.audio_format` (AudioFormat dataclass).

#### Validation

`RealtimeConfig` performs comprehensive validation in `__post_init__`:
- **model**: Must be one of the supported realtime models
- **voice**: Must be one of the supported realtime voices
- **temperature**: Must be between 0.6 and 1.2
- **max_response_output_tokens**: Must be "inf" or a positive integer
- **modalities**: Must only contain "audio" and/or "text"

Invalid configurations raise `ValueError` with clear error messages.

#### Usage

```python
from openai_apis import RealtimeConfig, VADConfig

# Use defaults (Hungarian, ash voice, server VAD enabled)
config = RealtimeConfig()

# English conversation with custom voice and temperature
config = RealtimeConfig(
    language="en",
    voice="alloy",
    instructions="You are a helpful assistant.",
    temperature=0.7
)

# Custom VAD configuration
config = RealtimeConfig(
    vad=VADConfig(mode="semantic_vad", eagerness="high")
)

# Disable VAD for push-to-talk mode
config = RealtimeConfig(
    vad=VADConfig(mode="disabled")
)

# Text-only mode (no audio)
config = RealtimeConfig(modalities=["text"])

# With function calling tools (raw format)
tools = [
    {
        "type": "function",
        "name": "get_weather",
        "description": "Get current weather for a location",
        "parameters": {
            "type": "object",
            "properties": {
                "location": {"type": "string"}
            },
            "required": ["location"]
        }
    }
]
config = RealtimeConfig(tools=tools)

# With ToolRegistry for automatic execution (recommended)
from openai_apis import ToolRegistry

registry = ToolRegistry()
registry.register(
    name="get_weather",
    description="Get current weather for a location",
    parameters={
        "type": "object",
        "properties": {
            "location": {"type": "string"}
        },
        "required": ["location"]
    },
    handler=lambda location: {"temp": 22, "conditions": "sunny"}
)
config = RealtimeConfig(tools=registry)

# Disable input transcription (audio-only mode)
config = RealtimeConfig(input_audio_transcription=False)
```

#### Session Update Conversion

The `to_session_update()` method converts the config to the OpenAI Realtime API `session.update` event format:

```python
config = RealtimeConfig(
    voice="sage",
    temperature=0.9,
    vad=VADConfig(mode="server_vad", threshold=0.7)
)

# Convert to session.update event
event = config.to_session_update()
# Returns:
# {
#     "type": "session.update",
#     "session": {
#         "model": "gpt-realtime-mini",
#         "voice": "sage",
#         "modalities": ["audio", "text"],
#         "input_audio_format": "pcm16",
#         "output_audio_format": "pcm16",
#         "temperature": 0.9,
#         "max_response_output_tokens": "inf",
#         "turn_detection": {
#             "type": "server_vad",
#             "threshold": 0.7,
#             "prefix_padding_ms": 300,
#             "silence_duration_ms": 500
#         },
#         "input_audio_transcription": {
#             "model": "whisper-1",
#             "language": "hu"
#         }
#     }
# }
```

---

### ToolRegistry

Registry for tool/function definitions used with Realtime API sessions. Enables registering tools with JSON Schema parameters and handler functions, automatic conversion to API format, and automatic execution when tool calls arrive.

**Type:** Class

#### Constructor

```python
ToolRegistry()
```

Creates an empty tool registry.

#### Methods

**`register(name: str, description: str, parameters: dict, handler: Callable) -> None`**

Register a tool with JSON Schema parameters and handler function.

- **Parameters:**
  - `name` (`str`): Unique tool name. Must not be empty or already registered.
  - `description` (`str`): Human-readable description of what the tool does.
  - `parameters` (`dict`): JSON Schema object describing the tool's parameters (must include "type": "object").
  - `handler` (`Callable`): Function that executes the tool. Can be sync or async. Receives keyword arguments matching the parameters schema.
- **Raises:**
  - `ValueError`: If name is empty or already registered.

**`to_api_format() -> list[dict]`**

Convert all tool definitions to OpenAI Realtime API format.

- **Returns:** `list[dict]` - List of tool definitions. Each entry has `{"type": "function", "name": ..., "description": ..., "parameters": ...}`.

**`async execute(name: str, arguments: str) -> str`**

Execute a registered tool handler. Parses JSON arguments, calls the handler (sync or async), and returns the result as a JSON string.

- **Parameters:**
  - `name` (`str`): Name of the registered tool.
  - `arguments` (`str`): JSON string of arguments to pass to the handler.
- **Returns:** `str` - JSON string of the handler's return value.
- **Raises:**
  - `KeyError`: If the tool name is not registered.
  - `json.JSONDecodeError`: If arguments is not valid JSON.

#### Properties

**`tool_names` (property) -> list[str]**

List all registered tool names (sorted alphabetically).

#### Special Methods

**`__len__() -> int`**

Return the number of registered tools.

**`__bool__() -> bool`**

Return True if any tools are registered, False otherwise.

#### Usage

**Basic registration and use:**

```python
from openai_apis import ToolRegistry, RealtimeConfig, RealtimeSession

# Create registry
tools = ToolRegistry()

# Register a sync handler
def get_weather(city: str) -> dict:
    return {"city": city, "temp": 22, "conditions": "sunny"}

tools.register(
    name="get_weather",
    description="Get current weather for a city",
    parameters={
        "type": "object",
        "properties": {
            "city": {"type": "string", "description": "City name"}
        },
        "required": ["city"]
    },
    handler=get_weather
)

# Register an async handler
async def web_search(query: str) -> dict:
    # Perform actual search...
    return {"query": query, "results": [...]}

tools.register(
    name="web_search",
    description="Search the web for information",
    parameters={
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Search query"}
        },
        "required": ["query"]
    },
    handler=web_search
)

# Check registered tools
print(tools.tool_names)  # ["get_weather", "web_search"]
print(len(tools))        # 2
print(bool(tools))       # True
```

**Integration with RealtimeSession:**

```python
from openai_apis import ToolRegistry, RealtimeConfig, RealtimeSession

# Configure session with tools
config = RealtimeConfig(tools=tools)

async with RealtimeSession(config) as session:
    # Tool calls from the model are automatically executed
    # Results are sent back to the model
    # Model continues the conversation with tool results

    # Tool executions are logged in audit trail
    events = session.audit_log.events
    tool_events = [e for e in events if e.event_type.startswith("tool.")]

    for event in tool_events:
        print(f"{event.event_type}: {event.data}")
        # tool.execution.started: {"call_id": "...", "name": "get_weather", ...}
        # tool.execution.completed: {"call_id": "...", "result": "{...}", ...}
```

**Error handling:**

```python
# If a tool handler raises an exception, it's caught and logged
def failing_tool() -> dict:
    raise ValueError("Something went wrong")

tools.register("failing_tool", "A tool that fails", {}, failing_tool)

# When the model calls this tool:
# 1. Exception is caught
# 2. Logged to audit trail with "tool.execution.failed" event
# 3. Error result is sent to model: {"error": "Something went wrong"}
# 4. Model can handle the error gracefully and continue
```

**Manual execution (for testing):**

```python
import asyncio

# Execute a tool manually
result = await tools.execute("get_weather", '{"city": "Budapest"}')
print(result)  # '{"city": "Budapest", "temp": 22, "conditions": "sunny"}'

# Test with invalid tool name
try:
    await tools.execute("unknown_tool", "{}")
except KeyError as e:
    print(e)  # "Unknown tool: 'unknown_tool'. Available: get_weather, web_search"
```

**Audit logging:**

When a ToolRegistry is provided to RealtimeSession, tool executions are automatically logged with the following event types:

- `tool.execution.started`: Tool execution begins (includes `call_id`, `name`, `arguments`)
- `tool.execution.completed`: Tool execution succeeds (includes `call_id`, `name`, `result`, `duration_ms`)
- `tool.execution.failed`: Tool execution fails (includes `call_id`, `name`, `error`, `duration_ms`)

---

### RealtimeAgentState

State manager for realtime sessions. Stores custom state data that can be passed to session updates.

**Type:** Class

#### Methods

**`__init__()`**

Initialize empty state.

**`set(key: str, value: Any) -> None`**

Set a state value.

**`get(key: str, default: Any = None) -> Any`**

Get a state value.

**`as_dict() -> Dict[str, Any]`**

Get state as dictionary.

**`clear() -> None`**

Clear all state.

#### Usage

```python
from openai_apis import RealtimeAgentState

state = RealtimeAgentState()

# Set state values
state.set("user_name", "Alice")
state.set("context", {"preference": "formal"})

# Get state values
name = state.get("user_name")
context = state.get("context", {})

# Export state
state_dict = state.as_dict()

# Clear state
state.clear()
```

---

### Event Types

Typed event objects for realtime streaming events.

#### TranscriptDelta

**Type:** `@dataclass`

Partial transcription event emitted at ~200-500ms intervals during speech recognition.

**Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `item_id` | `str` | Unique identifier for the conversation item |
| `delta` | `str` | Incremental text fragment for this update |
| `accumulated` | `str` | Full text accumulated so far for this `item_id` |

**Emitted for:**
- User input transcription: `conversation.item.input_audio_transcription.delta`
- Assistant response transcript: `response.audio_transcript.delta`

**Usage:**

```python
from openai_apis import RealtimeSession, TranscriptDelta

async with RealtimeSession() as session:
    def on_delta(event: TranscriptDelta):
        print(f"Delta: {event.delta}")
        print(f"Full text so far: {event.accumulated}")

    session.on("transcript.delta", on_delta)
```

#### TranscriptCompleted

**Type:** `@dataclass`

Final transcription event emitted when a speech turn is completed.

**Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `item_id` | `str` | Unique identifier for the conversation item |
| `transcript` | `str` | Complete final transcript text |
| `duration_ms` | `float` | Time elapsed from first delta to completion (milliseconds) |

**Emitted for:**
- User input transcription complete: `conversation.item.input_audio_transcription.completed`
- Assistant response transcript complete: `response.audio_transcript.done`

**Usage:**

```python
from openai_apis import RealtimeSession, TranscriptCompleted

async with RealtimeSession() as session:
    def on_completed(event: TranscriptCompleted):
        print(f"Complete: {event.transcript}")
        print(f"Duration: {event.duration_ms}ms")

    session.on("transcript.input", on_completed)
    session.on("transcript.output", on_completed)
```

#### ErrorEvent

**Type:** `@dataclass`

Error event for realtime API errors.

**Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `code` | `str` | Error code from the API |
| `message` | `str` | Human-readable error message |

**Usage:**

```python
from openai_apis import RealtimeSession, ErrorEvent

async with RealtimeSession() as session:
    def on_error(event: ErrorEvent):
        print(f"Error {event.code}: {event.message}")

    session.on("error", on_error)
```

#### AudioDelta

**Type:** `@dataclass`

Output audio chunk event from model response, emitted for each audio packet during streaming.

**Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `audio_bytes` | `bytes` | Base64-decoded PCM16 audio data (24kHz, mono, 16-bit) |
| `item_id` | `str` | Unique identifier for the response item |
| `response_id` | `str` | Unique identifier for the response |

**Emitted for:** `response.audio.delta` WebSocket events

**Usage:**

```python
from openai_apis import RealtimeSession, AudioDelta

async with RealtimeSession() as session:
    def on_audio_chunk(event: AudioDelta):
        # Play audio chunk immediately for low-latency playback
        audio_player.write(event.audio_bytes)
        print(f"Audio chunk: {len(event.audio_bytes)} bytes")

    session.on("audio.delta", on_audio_chunk)
```

#### AudioDone

**Type:** `@dataclass`

Audio stream completion marker, emitted when all audio chunks for a response have been delivered.

**Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `item_id` | `str` | Unique identifier for the response item |
| `response_id` | `str` | Unique identifier for the response |

**Emitted for:** `response.audio.done` WebSocket events

**Usage:**

```python
from openai_apis import RealtimeSession, AudioDone

async with RealtimeSession() as session:
    def on_audio_complete(event: AudioDone):
        print(f"Audio stream complete for item {event.item_id}")
        audio_player.flush()

    session.on("audio.done", on_audio_complete)
```

**Audit Logging:**

When `audio.done` is emitted, an `audio.output_completed` audit event is automatically logged with:
- `chunk_count`: Number of audio chunks received
- `total_bytes`: Total bytes of audio data
- `audio_duration_s`: Duration of audio in seconds (calculated from byte count)
- `streaming_duration_ms`: Wall-clock time from first chunk to completion

#### ConversationItem

**Type:** `@dataclass`

A conversation history entry with role and content. Automatically tracked by `RealtimeSession` from completed transcription events.

**Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `role` | `str` | Speaker role: `"user"` or `"assistant"` |
| `content` | `str` | Transcript text |
| `item_id` | `str` | OpenAI conversation item ID |

**Usage:**

`ConversationItem` objects are created automatically by `RealtimeSession` when transcription events complete. Access them via `session.get_conversation_history()`:

```python
from openai_apis import RealtimeSession

async with RealtimeSession() as session:
    # ... conversation happens ...

    # Get conversation history
    history = session.get_conversation_history()
    # Returns: [{"role": "user", "content": "..."}, {"role": "assistant", "content": "..."}]

    # Or access raw ConversationItem objects from session internals (not recommended)
    # items: list[ConversationItem] = session._conversation_history
```

**Tracked from events:**
- `conversation.item.input_audio_transcription.completed` (user speech)
- `response.audio_transcript.done` (assistant speech)

---

### RealtimeSession

Async WebSocket client for OpenAI Realtime API conversation sessions. Inherits from `BaseSession` for full lifecycle management, state machine, and per-session audit logging. Uses async context manager pattern for automatic connection/disconnection.

**Note:** `RealtimeVoiceAPI` is maintained as a backward-compatible alias for `RealtimeSession`.

**Constructor:**

```python
RealtimeSession(
    config: Optional[RealtimeConfig] = None,
    state: Optional[RealtimeAgentState] = None,
    max_reconnect_attempts: int = 3,
    reconnect_delay: float = 1.0
)
```

**Parameters:**
- `config` (`Optional[RealtimeConfig]`): Realtime configuration (defaults to `RealtimeConfig()`)
- `state` (`Optional[RealtimeAgentState]`): Custom state manager (defaults to new `RealtimeAgentState()`)
- `max_reconnect_attempts` (`int`): Maximum reconnection attempts on connection loss (default: 3)
- `reconnect_delay` (`float`): Base delay in seconds for exponential backoff (default: 1.0)

**Attributes:**
- `session_id` (`str`): Auto-generated UUID for session (inherited from `BaseSession`)
- `state` (`SessionState`): Current session state (inherited from `BaseSession`)
- `audit_log` (`SessionAuditLog`): Per-session audit log (inherited from `BaseSession`)
- `agent_state` (`RealtimeAgentState`): State manager for tool outputs and custom state

#### Methods

**`on(event: str, callback: Callable) -> None`** *(inherited from BaseSession)*

Register a callback for session events.

- **Parameters:**
  - `event` (`str`): Event name to listen for
  - `callback` (`Callable`): Function to call when event occurs
- **Returns:** `None`

**Supported events:**

| Event | Data Type | Description |
|-------|-----------|-------------|
| `"audio.delta"` | `AudioDelta` | Output audio chunk (typed event with `audio_bytes`, `item_id`, `response_id`) |
| `"audio.done"` | `AudioDone` | Output audio stream complete (typed event with `item_id`, `response_id`) |
| `"transcript.input"` | `TranscriptCompleted` | Input transcription (user speech as text) |
| `"transcript.output"` | `TranscriptCompleted` | Output transcription (model speech as text) |
| `"transcript.delta"` | `TranscriptDelta` | Partial transcription updates (~200-500ms intervals) |
| `"tool.call"` | `dict` | Tool/function call request (contains `call_id`, `name`, `arguments`) |
| `"response.created"` | `dict` | Response generation started (contains `id` and `status`) |
| `"response.done"` | `dict` | Response generation complete (contains `response_id` and `status`) |
| `"response.interrupted"` | `dict` | Response interrupted by user speech (contains `response_id` and `trigger`) |
| `"input_audio_buffer.speech_started"` | `dict` | VAD detected user speech start (raw event data) |
| `"error"` | `ErrorEvent` | Error events from the API |
| `"session.created"` | `dict` | Server session created (contains session metadata) |
| `"session.updated"` | `dict` | Server session configured (contains session metadata) |

Plus inherited `BaseSession` events: `"session.created"`, `"state_changed"`, `"session.closed"`

**Features:**
- Multiple callbacks can be registered for the same event
- Callbacks are invoked in the receive loop (async context)
- Each callback is wrapped in try/except to prevent one failing callback from blocking others
- Typed event objects for all streaming events (`AudioDelta`, `AudioDone`, `TranscriptDelta`, `TranscriptCompleted`, `ErrorEvent`)

**Example:**

```python
from openai_apis import RealtimeSession, TranscriptDelta, TranscriptCompleted, AudioDelta

async with RealtimeSession() as session:
    # Register delta callback for streaming transcripts
    def on_delta(event: TranscriptDelta):
        print(f"[{event.item_id}] +{event.delta}")

    session.on("transcript.delta", on_delta)

    # Register completion callback
    def on_complete(event: TranscriptCompleted):
        print(f"Final: {event.transcript} ({event.duration_ms:.0f}ms)")

    session.on("transcript.input", on_complete)

    # Register audio chunk callback
    def on_audio(event: AudioDelta):
        # Process audio bytes from typed event
        play_audio(event.audio_bytes)

    session.on("audio.delta", on_audio)
```

**`async send_audio(chunk: bytes) -> None`**

Send base64-encoded PCM16 audio chunk to the server.

- **Parameters:**
  - `chunk` (`bytes`): Raw PCM16 audio bytes
- **Returns:** `None`
- **Raises:** `InvalidStateTransition` if not in CONNECTED state
- **Audit Logging:** Logs `audio.chunk_sent` event with `chunk_size`, `total_chunks`, and `total_bytes` (cumulative)

**`async commit_audio() -> None`**

Commit audio buffer (push-to-talk mode). Signals end of user audio input, creating a conversation item.

- **Returns:** `None`
- **Raises:** `InvalidStateTransition` if not in CONNECTED state
- **Audit Logging:** Logs `audio.buffer_committed` event with `total_chunks`, `total_bytes`, and `audio_duration_s`; resets input counters for next turn

**`async create_response() -> None`**

Trigger response generation from the model.

- **Returns:** `None`
- **Raises:** `InvalidStateTransition` if not in CONNECTED state

**`async update_session(**kwargs) -> None`**

Update session configuration at runtime.

- **Parameters:**
  - `**kwargs`: Session config fields to update (e.g., `voice="alloy"`, `temperature=0.9`, `instructions="..."`)
- **Returns:** `None`
- **Raises:** `InvalidStateTransition` if not in CONNECTED state

**`async send_tool_result(call_id: str, result: str) -> None`**

Send tool call result back to the model.

- **Parameters:**
  - `call_id` (`str`): The tool call ID from the `"tool.call"` event
  - `result` (`str`): JSON string result of the tool invocation
- **Returns:** `None`
- **Raises:** `InvalidStateTransition` if not in CONNECTED state

**`async cancel_response() -> None`**

Cancel the current in-progress response (barge-in).

Sends a `response.cancel` event to the server. The server will stop generating audio/text and emit `response.done` with status "cancelled".

- **Returns:** `None`
- **Raises:** `InvalidStateTransition` if not in CONNECTED state
- **Audit Logging:** Logs `response.cancel_sent` event with `response_id` if available

**`get_conversation_history() -> list[dict[str, str]]`**

Get conversation history as a list of role/content dicts.

Returns the automatically tracked conversation history including all completed user and assistant transcriptions.

- **Returns:** List of dicts with `"role"` and `"content"` keys
  ```python
  [
      {"role": "user", "content": "Hello"},
      {"role": "assistant", "content": "Hi there!"},
      {"role": "user", "content": "How are you?"}
  ]
  ```
- **Note:** This is a synchronous method (no `await` needed)

**`async clear_conversation() -> None`**

Clear the in-memory conversation history.

Resets the tracked conversation items list to empty. Useful for starting a fresh conversation or managing memory in long sessions.

- **Returns:** `None`
- **Audit Logging:** Logs `conversation.cleared` event with `items_cleared` count

#### Usage Examples

**Basic realtime session:**

```python
from openai_apis import RealtimeSession, RealtimeConfig
import asyncio

async def main():
    config = RealtimeConfig(
        voice="sage",
        language="hu",
        instructions="You are a helpful assistant."
    )

    async with RealtimeSession(config) as session:
        # Register callbacks
        def on_transcript(data):
            print(f"User: {data.transcript}")

        def on_audio(chunk: bytes):
            # Process audio bytes (e.g., play to speaker)
            play_audio(chunk)

        session.on("transcript.input", on_transcript)
        session.on("audio.delta", on_audio)

        # Send audio and trigger response
        await session.send_audio(audio_chunk)
        await session.commit_audio()
        await session.create_response()

asyncio.run(main())
```

**With custom state and error handling:**

```python
from openai_apis import RealtimeSession, RealtimeAgentState, RealtimeConfig, ErrorEvent

async def main():
    state = RealtimeAgentState()
    state.set("user_preferences", {"language": "en"})

    config = RealtimeConfig(
        language="en",
        voice="alloy",
        instructions="You are a friendly assistant.",
        keywords=["OpenAI", "API"]
    )

    async with RealtimeSession(config, state) as session:
        # Error handling
        def on_error(event: ErrorEvent):
            print(f"Error {event.code}: {event.message}")

        session.on("error", on_error)

        # Session lifecycle events
        def on_session_created(data):
            print(f"Session started: {session.session_id}")

        session.on("session.created", on_session_created)

        # Send audio and create response
        await session.send_audio(audio_data)
        await session.commit_audio()
        await session.create_response()

asyncio.run(main())
```

**Streaming transcript events with delta callbacks:**

```python
from openai_apis import (
    RealtimeSession,
    TranscriptDelta,
    TranscriptCompleted,
    ErrorEvent
)

async def main():
    async with RealtimeSession() as session:
        # Track streaming transcripts with deltas
        def on_transcript_delta(event: TranscriptDelta):
            """Called every ~200-500ms with partial transcript."""
            print(f"\r[Streaming] {event.accumulated}", end="", flush=True)

        session.on("transcript.delta", on_transcript_delta)

        # Handle completed transcripts
        def on_transcript_completed(event: TranscriptCompleted):
            """Called when speech turn completes."""
            print(f"\n[Complete] {event.transcript}")
            print(f"Duration: {event.duration_ms:.0f}ms")

        session.on("transcript.input", on_transcript_completed)
        session.on("transcript.output", on_transcript_completed)

        # Handle errors
        def on_api_error(event: ErrorEvent):
            """Called on API errors."""
            print(f"\n[Error {event.code}] {event.message}")

        session.on("error", on_api_error)

        # Send audio and trigger response
        await session.send_audio(audio_chunk)
        await session.commit_audio()
        await session.create_response()

asyncio.run(main())
```

**Tool calls and results:**

```python
from openai_apis import RealtimeSession
import json

async def main():
    async with RealtimeSession() as session:
        # Handle tool calls
        async def on_tool_call(data: dict):
            call_id = data["call_id"]
            name = data["name"]
            arguments = json.loads(data["arguments"])

            # Execute tool
            result = execute_tool(name, arguments)

            # Send result back
            await session.send_tool_result(call_id, json.dumps(result))

        session.on("tool.call", on_tool_call)

        # Send audio and create response
        await session.send_audio(audio_chunk)
        await session.commit_audio()
        await session.create_response()

asyncio.run(main())
```

**Runtime session updates:**

```python
from openai_apis import RealtimeSession

async def main():
    async with RealtimeSession() as session:
        # Update voice at runtime
        await session.update_session(voice="alloy", temperature=0.8)

        # Update instructions
        await session.update_session(
            instructions="You are now speaking in a more formal tone."
        )

        # Send audio and create response with new settings
        await session.send_audio(audio_chunk)
        await session.commit_audio()
        await session.create_response()

asyncio.run(main())
```

**Accessing per-session audit log:**

```python
from openai_apis import RealtimeSession
from pathlib import Path

async def main():
    async with RealtimeSession() as session:
        # Work with session
        await session.send_audio(audio_chunk)
        await session.commit_audio()
        await session.create_response()

        # Export audit trail
        session.audit_log.export_to_file(Path("session_audit.json"))

        # Or access events directly
        for event in session.audit_log.events:
            print(f"{event.timestamp}: {event.event_type}")

asyncio.run(main())
```

**Response interruption (barge-in) and conversation history:**

```python
from openai_apis import RealtimeSession, RealtimeConfig

async def main():
    config = RealtimeConfig(
        voice="sage",
        language="hu",
        instructions="You are a helpful assistant."
    )

    async with RealtimeSession(config) as session:
        # Track conversation history automatically
        def on_user_transcript(event):
            print(f"User: {event.transcript}")

        def on_assistant_transcript(event):
            print(f"Assistant: {event.transcript}")

        session.on("transcript.input", on_user_transcript)
        session.on("transcript.output", on_assistant_transcript)

        # Handle interruption detection (VAD auto-interrupt)
        def on_interrupted(data):
            print(f"⚠️ Response {data['response_id']} interrupted by user speech")
            # Stop audio playback here
            stop_audio_playback()

        session.on("response.interrupted", on_interrupted)

        # Send user audio
        await session.send_audio(audio_chunk)
        await session.commit_audio()
        await session.create_response()

        # Wait for response...
        await asyncio.sleep(2)

        # Manual cancellation (push-to-talk interruption)
        if user_pressed_button():
            await session.cancel_response()
            print("✋ Response cancelled by user")

        # Get conversation history at any time
        history = session.get_conversation_history()
        print("\n📜 Conversation history:")
        for turn in history:
            print(f"  {turn['role']}: {turn['content']}")

        # Clear history for fresh conversation
        await session.clear_conversation()
        print("🗑️ History cleared")

asyncio.run(main())
```

**VAD-based automatic interruption detection:**

```python
from openai_apis import RealtimeSession, RealtimeConfig, VADConfig

async def main():
    # Enable server VAD for automatic turn detection
    config = RealtimeConfig(
        voice="sage",
        vad=VADConfig(mode="server_vad", threshold=0.7, silence_duration_ms=800)
    )

    async with RealtimeSession(config) as session:
        # Detect when user starts speaking during assistant response
        def on_speech_started(data):
            print("🎤 User started speaking")

        session.on("input_audio_buffer.speech_started", on_speech_started)

        # Automatic interruption event (triggered by VAD)
        def on_auto_interrupt(data):
            response_id = data["response_id"]
            trigger = data["trigger"]  # "vad_speech_started"
            print(f"⚡ Auto-interrupted {response_id} via {trigger}")
            # Server handles cancellation automatically - just stop playback
            stop_audio_playback()

        session.on("response.interrupted", on_auto_interrupt)

        # Track response lifecycle
        def on_response_created(data):
            print(f"🚀 Response {data['id']} started")

        def on_response_done(data):
            status = data["status"]  # "completed" or "cancelled"
            print(f"✅ Response {data['response_id']} finished: {status}")

        session.on("response.created", on_response_created)
        session.on("response.done", on_response_done)

        # Normal conversation flow
        await session.send_audio(audio_chunk)
        await session.commit_audio()
        await session.create_response()

asyncio.run(main())
```

---

## MCP Plugin System

Model Context Protocol (MCP) plugin architecture for extensible tool integration. The MCP system provides an abstract plugin interface, a plugin manager for registration and dispatch, and stub implementations for filesystem and Gmail operations.

### MCPPlugin

Abstract base class for MCP plugins. Subclasses define plugin metadata, tool definitions, and execution logic.

**Import:** `from openai_apis import MCPPlugin`

**Abstract Members:**

- `name` (property) - Unique plugin identifier (e.g., "filesystem", "gmail")
- `description` (property) - Human-readable plugin description
- `get_tools()` - Returns list of tool definitions in OpenAI function-calling JSON Schema format
- `execute_tool(name, arguments)` - Async method that executes a named tool with given arguments

**Tool Definition Format:**

Each tool definition is a dict with the following structure:

```python
{
    "type": "function",
    "name": "tool_name",
    "description": "Tool description",
    "parameters": {
        "type": "object",
        "properties": {
            "param1": {"type": "string", "description": "Parameter description"},
            # ... more parameters
        },
        "required": ["param1"]
    }
}
```

**Example Implementation:**

```python
from openai_apis import MCPPlugin

class CustomPlugin(MCPPlugin):
    @property
    def name(self) -> str:
        return "custom"

    @property
    def description(self) -> str:
        return "Custom plugin for demonstration"

    def get_tools(self) -> list[dict]:
        return [
            {
                "type": "function",
                "name": "custom_action",
                "description": "Performs a custom action",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "text": {
                            "type": "string",
                            "description": "Input text to process"
                        }
                    },
                    "required": ["text"]
                }
            }
        ]

    async def execute_tool(self, name: str, arguments: dict) -> str:
        if name == "custom_action":
            text = arguments["text"]
            return f"Processed: {text.upper()}"
        raise ValueError(f"Unknown tool: {name}")
```

### MCPPluginManager

Plugin registry and dispatcher for managing MCP plugins, aggregating tools, and routing tool execution.

**Import:** `from openai_apis import MCPPluginManager`

**Methods:**

#### `__init__()`

Initialize an empty plugin manager.

```python
manager = MCPPluginManager()
```

#### `register(plugin: MCPPlugin) -> None`

Register an MCP plugin.

**Raises:**
- `TypeError` - If plugin is not an MCPPlugin instance
- `ValueError` - If plugin name is already registered or any tool name collides with existing tools

**Example:**

```python
from openai_apis import MCPPluginManager, FileSystemPlugin, GmailPlugin

manager = MCPPluginManager()
manager.register(FileSystemPlugin())
manager.register(GmailPlugin())
```

#### `get_all_tools() -> list[dict]`

Aggregate tool definitions from all registered plugins.

**Returns:** List of tool definition dicts in OpenAI function-calling format.

**Example:**

```python
tools = manager.get_all_tools()
for tool in tools:
    print(f"{tool['name']}: {tool['description']}")
```

#### `async execute(tool_name: str, arguments: dict) -> str`

Dispatch tool execution to the appropriate plugin.

**Parameters:**
- `tool_name` - Name of the tool to execute
- `arguments` - Dict of tool arguments matching the tool's parameters schema

**Returns:** String result from the tool execution.

**Raises:**
- `KeyError` - If tool_name is not registered

**Example:**

```python
result = await manager.execute("read_file", {"path": "/tmp/data.txt"})
print(result)
```

#### `populate_tool_registry(registry: ToolRegistry) -> None`

Register all MCP plugin tools into a ToolRegistry for Realtime API integration.

This method bridges MCP plugins into the Realtime API's `ToolRegistry` so MCP tools appear as regular function-calling tools. The ToolRegistry handles JSON serialization and deserialization automatically.

**Parameters:**
- `registry` - ToolRegistry instance to populate

**Example:**

```python
from openai_apis import MCPPluginManager, ToolRegistry, FileSystemPlugin

# Create manager and register plugins
manager = MCPPluginManager()
manager.register(FileSystemPlugin())

# Bridge to ToolRegistry
registry = ToolRegistry()
manager.populate_tool_registry(registry)

# Now MCP tools are available in the registry
print(registry.tool_names)  # ['read_file', 'write_file']
```

**Properties:**

- `plugin_names` - List of registered plugin names (sorted)
- `__len__()` - Number of registered plugins
- `__bool__()` - True if any plugins are registered

**Full Example:**

```python
import asyncio
from openai_apis import MCPPluginManager, FileSystemPlugin, GmailPlugin

async def main():
    # Initialize manager
    manager = MCPPluginManager()

    # Register plugins
    manager.register(FileSystemPlugin())
    manager.register(GmailPlugin())

    # Inspect registered plugins
    print(f"Registered plugins: {manager.plugin_names}")
    print(f"Plugin count: {len(manager)}")
    print(f"Has plugins: {bool(manager)}")

    # Get all tools
    tools = manager.get_all_tools()
    print(f"Available tools: {[t['name'] for t in tools]}")

    # Execute a tool (will raise NotImplementedError for stubs)
    try:
        result = await manager.execute("read_file", {"path": "/tmp/test.txt"})
        print(result)
    except NotImplementedError as e:
        print(f"Tool not implemented: {e}")

asyncio.run(main())
```

### FileSystemPlugin

Stub MCP plugin for file system operations. Provides tool definitions but raises `NotImplementedError` on execution (placeholder for future implementation).

**Import:** `from openai_apis import FileSystemPlugin`

**Plugin Name:** `"filesystem"`

**Tools:**
- `read_file(path: str)` - Read contents of a file
- `write_file(path: str, content: str)` - Write contents to a file

**Example:**

```python
from openai_apis import MCPPluginManager, FileSystemPlugin

manager = MCPPluginManager()
manager.register(FileSystemPlugin())

# Get tool definitions
tools = manager.get_all_tools()
print([t['name'] for t in tools])  # ['read_file', 'write_file']

# Execution raises NotImplementedError
try:
    result = await manager.execute("read_file", {"path": "/tmp/data.txt"})
except NotImplementedError as e:
    print(f"Not implemented: {e}")
```

### GmailPlugin

Stub MCP plugin for Gmail operations. Provides tool definitions but raises `NotImplementedError` on execution (placeholder for future implementation).

**Import:** `from openai_apis import GmailPlugin`

**Plugin Name:** `"gmail"`

**Tools:**
- `send_email(to: str, subject: str, body: str)` - Send an email via Gmail
- `read_emails(max_results: int = None)` - Read recent emails from Gmail inbox

**Example:**

```python
from openai_apis import MCPPluginManager, GmailPlugin

manager = MCPPluginManager()
manager.register(GmailPlugin())

# Get tool definitions
tools = manager.get_all_tools()
print([t['name'] for t in tools])  # ['send_email', 'read_emails']

# Execution raises NotImplementedError
try:
    result = await manager.execute("send_email", {
        "to": "user@example.com",
        "subject": "Test",
        "body": "Hello"
    })
except NotImplementedError as e:
    print(f"Not implemented: {e}")
```

**Integration with Realtime API:**

```python
import asyncio
from openai_apis import (
    MCPPluginManager,
    FileSystemPlugin,
    GmailPlugin,
    ToolRegistry,
    RealtimeSession,
    RealtimeConfig
)

async def main():
    # Create MCP plugin manager and register plugins
    mcp_manager = MCPPluginManager()
    mcp_manager.register(FileSystemPlugin())
    mcp_manager.register(GmailPlugin())

    # Create ToolRegistry and populate with MCP tools
    registry = ToolRegistry()
    mcp_manager.populate_tool_registry(registry)

    # Create Realtime session with MCP tools
    config = RealtimeConfig(tools=registry)

    async with RealtimeSession(config=config) as session:
        # MCP tools are now available to the Realtime API
        print(f"Available tools: {registry.tool_names}")

        # Session will automatically execute MCP tools when called by the model
        # (Note: stub plugins will raise NotImplementedError)

asyncio.run(main())
```

---

## Session Infrastructure

Base classes and utilities for session lifecycle management.

### SessionState

Enumeration of session states for lifecycle management.

**Type:** `enum.Enum`

#### States

| State | Value | Description |
|-------|-------|-------------|
| `CREATED` | `"created"` | Initial state after construction |
| `CONNECTING` | `"connecting"` | Connection establishment in progress |
| `CONNECTED` | `"connected"` | Session is active and ready for use |
| `DISCONNECTING` | `"disconnecting"` | Cleanup/disconnection in progress |
| `CLOSED` | `"closed"` | Terminal state, session is closed |

#### Valid Transitions

```
CREATED → CONNECTING → CONNECTED → DISCONNECTING → CLOSED
CREATED → CLOSED (direct close without connecting)
```

Once in `CLOSED` state, no further transitions are allowed.

#### Usage

```python
from openai_apis import SessionState, BaseSession

async with MySession() as session:
    print(session.state)  # SessionState.CONNECTED

    # Check state
    if session.state == SessionState.CONNECTED:
        # Do something
        pass
```

---

### InvalidStateTransition

Exception raised when an invalid session state transition is attempted.

**Type:** Exception class (extends `Exception`)

#### Usage

```python
from openai_apis import InvalidStateTransition

try:
    # Attempting invalid transition
    session._transition_to(SessionState.CONNECTED)
except InvalidStateTransition as e:
    print(f"Invalid transition: {e}")
```

---

### BaseSession

Abstract base class for all API sessions with lifecycle management.

**Type:** Abstract class

#### Constructor

```python
BaseSession(config: Optional[BaseConfig] = None)
```

**Parameters:**
- `config` (`Optional[BaseConfig]`): Session configuration. If `None`, uses default `BaseConfig()`.

#### Properties

| Property | Type | Description |
|----------|------|-------------|
| `session_id` | `str` | Auto-generated UUID for this session |
| `state` | `SessionState` | Current session state |
| `audit_log` | `SessionAuditLog` | Per-session audit log |

#### Abstract Methods

Subclasses must implement:

**`async _connect() -> None`**

Establish connection. Called during `__aenter__`.
- State will be `CONNECTING` when this is called
- If this raises, state will be set to `CLOSED`

**`async _disconnect() -> None`**

Tear down connection. Called during `__aexit__`.
- State will be `DISCONNECTING` when this is called
- State is guaranteed to be `CLOSED` after this, even if it raises

#### Methods

**`on(event: str, callback: Callable) -> None`**

Register a callback for an event.

- **Parameters:**
  - `event` (`str`): Event name
  - `callback` (`Callable`): Callable to invoke when event is emitted

**`_emit(event: str, data: Any = None) -> None`**

Emit an event, calling all registered callbacks. (For subclass use)

- **Parameters:**
  - `event` (`str`): Event name
  - `data` (`Any`): Data to pass to callbacks

**`_transition_to(new_state: SessionState) -> None`**

Transition to a new state with validation. (For subclass use)

- **Parameters:**
  - `new_state` (`SessionState`): Target state
- **Raises:** `InvalidStateTransition` if transition is not allowed

#### Built-in Events

| Event | Emitted When | Data |
|-------|--------------|------|
| `state_changed` | State transitions occur | `{"from": SessionState, "to": SessionState}` |
| `closed` | Session closes | `{"session_id": str}` |

#### Async Context Manager

`BaseSession` supports `async with` syntax for automatic lifecycle management:

```python
async with MySession() as session:
    # Session is CONNECTED
    # Use session...
# Session is CLOSED
```

**Flow:**
1. `__aenter__`: CREATED → CONNECTING → `_connect()` → CONNECTED
2. Context body executes
3. `__aexit__`: CONNECTED → DISCONNECTING → `_disconnect()` → CLOSED

If `_connect()` raises, state is set to `CLOSED` and exception propagates.
State is guaranteed to be `CLOSED` after exit, even if `_disconnect()` raises.

#### Usage Example

```python
from openai_apis import BaseSession, BaseConfig, SessionState

class MyCustomSession(BaseSession):
    def __init__(self, config: Optional[BaseConfig] = None):
        super().__init__(config)
        # Your initialization here
        self.connection = None

    async def _connect(self) -> None:
        """Establish connection (called automatically in async with)."""
        # Connection logic here
        self.connection = await create_connection()
        self._logger.info(f"Connected: {self.session_id}")

    async def _disconnect(self) -> None:
        """Tear down connection (called automatically on exit)."""
        # Cleanup logic here
        if self.connection:
            await self.connection.close()
        self._logger.info(f"Disconnected: {self.session_id}")

# Usage with automatic lifecycle management
async with MyCustomSession() as session:
    # Session is now in CONNECTED state
    print(f"Session ID: {session.session_id}")
    print(f"State: {session.state}")  # SessionState.CONNECTED

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

#### State Machine Rules

- **CREATED → CONNECTING**: Normal startup
- **CREATED → CLOSED**: Direct close without connecting
- **CONNECTING → CONNECTED**: Successful connection
- **CONNECTING → CLOSED**: Connection failure
- **CONNECTED → DISCONNECTING**: Normal shutdown
- **CONNECTED → CLOSED**: Forced close
- **DISCONNECTING → CLOSED**: Cleanup complete
- **CLOSED** is terminal (no transitions out)

Use `session.on("state_changed", callback)` to monitor state transitions.

---

## Logging & Audit

Comprehensive logging and audit trail infrastructure.

### SessionAuditLog

Per-session structured audit log with in-memory event storage. Thread-safe and async-safe.

**Type:** Class

#### Constructor

```python
SessionAuditLog(session_id: str)
```

**Parameters:**
- `session_id` (`str`): Session identifier

#### Properties

| Property | Type | Description |
|----------|------|-------------|
| `session_id` | `str` | Session identifier |
| `events` | `list[AuditEvent]` | List of all audit events (thread-safe copy) |

#### Methods

**`log(event_type: str, data: Optional[dict] = None, duration_ms: Optional[float] = None) -> None`**

Log an audit event.

- **Parameters:**
  - `event_type` (`str`): Event type string (e.g., "session.created", "audio.received")
  - `data` (`Optional[dict]`): Arbitrary event data dict
  - `duration_ms` (`Optional[float]`): Optional duration in milliseconds

**`measure(event_type: str, data: Optional[dict] = None)`**

Context manager to automatically measure and log operation duration.

- **Parameters:**
  - `event_type` (`str`): Event type string
  - `data` (`Optional[dict]`): Arbitrary event data dict
- **Returns:** Context manager that logs event with duration on exit

**`export_json() -> str`**

Export audit log as JSON string.

- **Returns:** `str` - JSON string with all events

**`export_to_file(path: Path) -> None`**

Export audit log to JSON file.

- **Parameters:**
  - `path` (`Path`): Output file path

#### Usage

```python
from openai_apis import SessionAuditLog
from pathlib import Path

# Create audit log (usually owned by a BaseSession)
audit_log = SessionAuditLog("session-123")

# Log events
audit_log.log("user.action", {"action": "button_click", "button_id": "submit"})
audit_log.log("api.call", {"endpoint": "/transcribe", "status": 200}, duration_ms=150.5)

# Measure operation duration automatically
with audit_log.measure("database.query", {"table": "users"}):
    result = query_database()

# Access events
for event in audit_log.events:
    print(f"{event.timestamp}: {event.event_type}")

# Export to file
audit_log.export_to_file(Path("audit_log.json"))

# Export as JSON string
json_str = audit_log.export_json()
```

---

### AuditEvent

Single audit event with timestamp and optional duration.

**Type:** `@dataclass`

#### Fields

| Field | Type | Description |
|-------|------|-------------|
| `timestamp` | `datetime` | Event timestamp (UTC) |
| `session_id` | `str` | Session identifier |
| `event_type` | `str` | Event type string |
| `data` | `dict` | Event data dictionary |
| `duration_ms` | `Optional[float]` | Optional duration in milliseconds |

#### Usage

```python
from openai_apis import AuditEvent
from datetime import datetime

event = AuditEvent(
    timestamp=datetime.utcnow(),
    session_id="session-123",
    event_type="api.call",
    data={"endpoint": "/transcribe", "status": 200},
    duration_ms=150.5
)

print(f"{event.event_type}: {event.duration_ms}ms")
```

---

### Global Logging Functions

Global logging functions for backward compatibility and non-session events.

**`get_logger(name: str) -> logging.Logger`**

Get a logger instance for a module.

- **Parameters:**
  - `name` (`str`): Logger name (usually `__name__`)
- **Returns:** `logging.Logger`

**`set_correlation_id(corr_id: Optional[str]) -> None`**

Set correlation ID for request tracing.

- **Parameters:**
  - `corr_id` (`Optional[str]`): Correlation ID or None to clear

**`log_audit_event(event_type: str, action: str, user_id: Optional[str] = None, session_id: Optional[str] = None, details: Optional[dict] = None, status: str = "success") -> None`**

Log a global audit event (non-session).

- **Parameters:**
  - `event_type` (`str`): Event type
  - `action` (`str`): Action description
  - `user_id` (`Optional[str]`): User identifier
  - `session_id` (`Optional[str]`): Session identifier
  - `details` (`Optional[dict]`): Additional details
  - `status` (`str`): Event status (default: "success")

**`log_performance(operation: str, duration_ms: float, details: Optional[dict] = None) -> None`**

Log performance metrics.

- **Parameters:**
  - `operation` (`str`): Operation name
  - `duration_ms` (`float`): Duration in milliseconds
  - `details` (`Optional[dict]`): Additional details

**`log_api_call(endpoint: str, method: str, status_code: int, duration_ms: float, details: Optional[dict] = None) -> None`**

Log API call metrics.

- **Parameters:**
  - `endpoint` (`str`): API endpoint
  - `method` (`str`): HTTP method
  - `status_code` (`int`): Response status code
  - `duration_ms` (`float`): Duration in milliseconds
  - `details` (`Optional[dict]`): Additional details

**`setup_logging(log_level: str = "INFO", log_dir: str = "logs") -> None`**

Setup logging configuration.

- **Parameters:**
  - `log_level` (`str`): Log level (default: "INFO")
  - `log_dir` (`str`): Log directory (default: "logs")

#### Usage

```python
from openai_apis import (
    get_logger,
    set_correlation_id,
    log_audit_event,
    log_performance,
    log_api_call,
    setup_logging
)

# Setup logging
setup_logging(log_level="DEBUG", log_dir="logs")

# Get logger
logger = get_logger(__name__)
logger.info("Application started")

# Set correlation ID for request tracking
set_correlation_id("req-12345")

# Log audit event
log_audit_event(
    event_type="transcription",
    action="audio_transcribed",
    user_id="user-123",
    details={"duration": 5.2, "language": "hu"}
)

# Log performance
log_performance(
    operation="transcribe_audio",
    duration_ms=1234.5,
    details={"audio_length_s": 5.2}
)

# Log API call
log_api_call(
    endpoint="/v1/audio/transcriptions",
    method="POST",
    status_code=200,
    duration_ms=1234.5,
    details={"model": "gpt-4o-mini-transcribe"}
)
```

#### Log Files

Structured logging creates the following files in the log directory:

- **`app.log`**: Main application logs (JSON format)
- **`error.log`**: Error-level logs only (JSON format)
- **`audit.log`**: Global audit trail (JSON format)
- **`console`**: Human-readable console output

For complete logging documentation, see [docs/LOGGING_AUDIT_TRAIL.md](./LOGGING_AUDIT_TRAIL.md).

---

## Web Server Example (FastAPI)

The `examples/web_server/` directory provides a production-ready FastAPI web server demonstrating REST and WebSocket endpoints for all three core APIs (TTS, Transcription, Realtime). This example shows how to integrate `openai_apis` into a web application.

### Overview

The web server exposes:
- **REST endpoint**: `POST /api/tts` for text-to-speech synthesis
- **WebSocket endpoints**: `WS /ws/transcription` and `WS /ws/realtime` for streaming transcription and realtime voice
- **System endpoints**: `GET /api/health` and `GET /api/config` for monitoring and client configuration

### Running the Server

```bash
# Install with web extras
uv sync --extra web

# Run the server
python examples/web_server/run.py

# Or with custom host/port
python examples/web_server/run.py --host 0.0.0.0 --port 8080

# With auto-reload for development
python examples/web_server/run.py --reload
```

The server will be available at `http://localhost:8000` by default.

### Endpoints

#### POST /api/tts

Synthesize text to speech using OpenAI TTS.

**Request Body (JSON):**
```json
{
  "text": "Hello, world!",
  "voice": "ash",
  "speed": 1.0,
  "model": "gpt-4o-mini-tts",
  "output_format": "base64",
  "instructions": "Speak with excitement"
}
```

**Parameters:**
- `text` (required): Text to synthesize (1-4096 characters)
- `voice` (optional): Voice name (default: "ash")
- `speed` (optional): Speech speed 0.25-4.0 (default: 1.0)
- `model` (optional): TTS model (default: "gpt-4o-mini-tts")
- `output_format` (optional): "base64" for JSON response, "pcm" for raw binary (default: "base64")
- `instructions` (optional): Voice steering instructions (gpt-4o-mini-tts only)

**Response (output_format="base64"):**
```json
{
  "audio": "base64-encoded-audio-data",
  "sample_rate": 24000,
  "channels": 1,
  "format": "pcm16",
  "text_length": 13,
  "audio_duration_seconds": 1.234
}
```

**Response (output_format="pcm"):**
- Content-Type: `audio/pcm`
- Headers: `X-Sample-Rate`, `X-Channels`, `X-Format`, `X-Duration-Seconds`
- Body: Raw PCM16 audio bytes

**Example:**
```bash
# Base64 JSON response
curl -X POST http://localhost:8000/api/tts \
  -H "Content-Type: application/json" \
  -d '{"text": "Hello world", "voice": "sage"}'

# Raw PCM binary
curl -X POST http://localhost:8000/api/tts \
  -H "Content-Type: application/json" \
  -d '{"text": "Hello world", "output_format": "pcm"}' \
  --output audio.pcm
```

#### WS /ws/transcription

WebSocket endpoint for streaming speech-to-text transcription.

**Query Parameters:**
- `language` (optional): ISO-639-1 language code (default: "hu")
- `model` (optional): Transcription model (default: "gpt-realtime-whisper")

**Client → Server Messages:**
```json
{"type": "audio", "data": "base64-encoded-pcm16-audio"}
{"type": "commit"}
{"type": "close"}
```

**Server → Client Messages:**
```json
{"type": "session_ready"}
{"type": "transcript.delta", "delta": "partial text", "item_id": "..."}
{"type": "transcript.completed", "transcript": "final text", "item_id": "..."}
{"type": "error", "message": "error description"}
```

**Usage Flow:**
1. Connect to `ws://localhost:8000/ws/transcription?language=en`
2. Server sends `{"type": "session_ready"}`
3. Client sends audio chunks: `{"type": "audio", "data": "<base64-pcm16>"}`
4. Client commits audio buffer: `{"type": "commit"}`
5. Server streams transcript deltas and completion
6. Client sends `{"type": "close"}` or disconnects to end session

**Example (JavaScript):**
```javascript
const ws = new WebSocket('ws://localhost:8000/ws/transcription?language=en');

ws.onmessage = (event) => {
  const msg = JSON.parse(event.data);
  if (msg.type === 'transcript.completed') {
    console.log('Transcript:', msg.transcript);
  }
};

// Send audio (assuming you have PCM16 audio as ArrayBuffer)
const audioBase64 = btoa(String.fromCharCode(...new Uint8Array(audioBuffer)));
ws.send(JSON.stringify({ type: 'audio', data: audioBase64 }));
ws.send(JSON.stringify({ type: 'commit' }));
```

#### WS /ws/realtime

WebSocket endpoint for full-duplex realtime voice conversation (voice-to-voice).

**Query Parameters:**
- `voice` (optional): Voice name (default: "ash")
- `language` (optional): Language code (default: "hu")
- `instructions` (optional): System instructions for the agent

**Client → Server Messages:**
```json
{"type": "audio", "data": "base64-encoded-pcm16-audio"}
{"type": "commit"}
{"type": "cancel"}
{"type": "close"}
```

**Server → Client Messages:**
```json
{"type": "session_ready"}
{"type": "transcription", "text": "user speech transcription"}
{"type": "response_audio", "data": "base64-audio-chunk"}
{"type": "response_audio_done"}
{"type": "response_text_delta", "text": "partial assistant text"}
{"type": "response_text", "text": "complete assistant text"}
{"type": "response_done"}
{"type": "error", "message": "error description"}
```

**Usage Flow:**
1. Connect to `ws://localhost:8000/ws/realtime?voice=sage&language=en`
2. Server sends `{"type": "session_ready"}`
3. Client sends audio chunks: `{"type": "audio", "data": "<base64-pcm16>"}`
4. Client commits and requests response: `{"type": "commit"}`
5. Server sends `{"type": "transcription"}` with user's speech
6. Server streams audio (`response_audio`) and text (`response_text_delta`)
7. Server signals completion: `{"type": "response_audio_done"}` and `{"type": "response_done"}`
8. Client can interrupt: `{"type": "cancel"}`
9. Repeat steps 3-8 for multi-turn conversation

**Example (JavaScript):**
```javascript
const ws = new WebSocket('ws://localhost:8000/ws/realtime?voice=sage&language=en');
const audioChunks = [];

ws.onmessage = (event) => {
  const msg = JSON.parse(event.data);

  if (msg.type === 'transcription') {
    console.log('You said:', msg.text);
  } else if (msg.type === 'response_audio') {
    // Decode and queue audio for playback
    const audioBytes = Uint8Array.from(atob(msg.data), c => c.charCodeAt(0));
    audioChunks.push(audioBytes);
  } else if (msg.type === 'response_audio_done') {
    // Play accumulated audio
    playAudio(audioChunks);
    audioChunks.length = 0;
  }
};

// Send audio, then commit to trigger response
ws.send(JSON.stringify({ type: 'audio', data: audioBase64 }));
ws.send(JSON.stringify({ type: 'commit' }));

// Cancel in-progress response
ws.send(JSON.stringify({ type: 'cancel' }));
```

#### GET /api/health

Health check endpoint for monitoring.

**Response:**
```json
{
  "status": "healthy",
  "api_key_configured": true
}
```

#### GET /api/config

Client configuration endpoint exposing available voices, models, and defaults.

**Response:**
```json
{
  "tts": {
    "voices": ["alloy", "ash", "ballad", "coral", "echo", "fable", "nova", "onyx", "sage", "shimmer", "verse", "marin", "cedar"],
    "models": ["gpt-4o-mini-tts", "tts-1", "tts-1-hd"],
    "output_formats": ["pcm", "mp3", "opus", "aac", "flac", "wav"],
    "defaults": {"voice": "ash", "model": "gpt-4o-mini-tts", "speed": 1.0}
  },
  "transcription": {
    "models": ["gpt-realtime-whisper", "gpt-4o-mini-transcribe", "gpt-4o-transcribe", "whisper-1"],
    "defaults": {"model": "gpt-realtime-whisper", "language": "hu"}
  },
  "realtime": {
    "voices": ["alloy", "ash", "ballad", "coral", "echo", "sage", "shimmer", "verse"],
    "models": ["gpt-realtime-mini", "gpt-4o-realtime-preview"],
    "defaults": {"voice": "ash", "model": "gpt-realtime-mini", "language": "hu"}
  }
}
```

### Architecture

The web server follows a clean architecture:

```
examples/web_server/
├── __init__.py          # Package marker
├── app.py               # FastAPI app factory, CORS, system endpoints
├── routes/
│   ├── __init__.py      # Route exports
│   ├── tts.py           # POST /api/tts
│   ├── transcription.py # WS /ws/transcription
│   └── realtime.py      # WS /ws/realtime
└── run.py               # Entry point with uvicorn
```

**Key Design Patterns:**
- **Application Factory**: `create_app()` for testability and configuration
- **Router Separation**: Each API module has its own router
- **Pydantic Models**: Request/response validation via `TTSRequest`, `TTSResponse`
- **Session Management**: WebSocket handlers use `async with` context managers for automatic cleanup
- **Event Forwarding**: Session callbacks use `asyncio.ensure_future()` to bridge sync callbacks with async WebSocket sends

### Data Flow

#### TTS Endpoint
```
Client HTTP POST → Pydantic validation (TTSRequest)
                 → TTSConfig creation
                 → TTSRegistry.create(config)
                 → provider.synthesize(text, voice, speed)
                 → numpy array → bytes
                 → Response (PCM binary or base64 JSON)
```

#### Transcription WebSocket
```
Client WebSocket ↔ FastAPI Handler ↔ TranscriptionSession (openai_apis)
  {"type":"audio"} → session.send_audio(bytes)
  {"type":"commit"} → session.commit_audio()
  Session event "transcript.delta" → {"type":"transcript.delta"} to client
  Session event "transcript.completed" → {"type":"transcript.completed"} to client
```

#### Realtime WebSocket
```
Client WebSocket ↔ FastAPI Handler ↔ RealtimeSession (openai_apis)
  {"type":"audio"} → session.send_audio(bytes)
  {"type":"commit"} → session.commit_audio() + session.create_response()
  {"type":"cancel"} → session.cancel_response()
  Session events → Typed events (AudioDelta, TranscriptCompleted, etc.) → JSON to client
```

### CORS Configuration

The server includes CORS middleware configured for local development:

```python
cors_origins = [
    "http://localhost:8000",
    "http://localhost:3000",
    "http://127.0.0.1:8000",
    "http://127.0.0.1:3000",
]
```

Override with `create_app(cors_origins=[...])` for production deployments.

### Testing

The web server includes comprehensive tests in `tests/test_web_server.py` and `tests/api/test_web_server_schema.py`:

- Import validation
- Health and config endpoint tests
- TTS endpoint with mocked synthesis
- WebSocket transcription with event mocking
- WebSocket realtime with full event flow
- CORS header validation
- Error handling (invalid requests, disconnections)

Run tests:
```bash
pytest tests/test_web_server.py -v
pytest tests/api/test_web_server_schema.py -v
```

### Dependencies

The web server requires the `[web]` extra:

```toml
[project.optional-dependencies]
web = [
    "fastapi>=0.115.6",
    "uvicorn[standard]>=0.34.0",
    "python-multipart>=0.0.20",
]
```

Install with:
```bash
pip install -e ".[web]"
# or
uv sync --extra web
```

### Production Deployment

For production deployments, consider:

1. **Environment Variables**: Set `OPENAI_API_KEY` via environment or secrets management
2. **CORS Origins**: Configure `cors_origins` for your frontend domain
3. **HTTPS**: Deploy behind a reverse proxy (nginx, Caddy) with TLS termination
4. **Scalability**: Use multiple uvicorn workers: `uvicorn app:app --workers 4`
5. **Monitoring**: Integrate health endpoint into your monitoring system
6. **Rate Limiting**: Add rate limiting middleware to prevent abuse
7. **Authentication**: Add authentication middleware for securing endpoints
8. **Logging**: Configure structured logging and integrate with your log aggregation system

**Example Production Start:**
```bash
uvicorn examples.web_server.app:create_app \
  --factory \
  --host 0.0.0.0 \
  --port 8000 \
  --workers 4 \
  --proxy-headers \
  --forwarded-allow-ips='*'
```

### See Also

- **[examples/web_server/app.py](../examples/web_server/app.py)** - Application factory implementation
- **[examples/web_server/routes/](../examples/web_server/routes/)** - Endpoint implementations
- **[tests/test_web_server.py](../tests/test_web_server.py)** - Web server tests
- **[FastAPI Documentation](https://fastapi.tiangolo.com/)** - FastAPI framework reference

---

## Import Reference

Complete reference of all public exports from the `openai_apis` package.

### Public API (Recommended)

The following symbols are exported from the package root (`openai_apis.__init__.py`):

```python
from openai_apis import (
    # Core sessions (recommended for new code)
    TranscriptionSession,
    TranscriptionConfig,
    RealtimeSession,
    RealtimeConfig,
    TTSProvider,          # Alias for BaseTTSProvider
    TTSConfig,
    TTSRegistry,

    # Shared config
    AudioFormat,
    VADConfig,

    # Tools & plugins
    ToolRegistry,
    MCPPlugin,
    MCPPluginManager,

    # Session base (advanced usage)
    BaseSession,
    SessionState,
    SessionAuditLog,
)
```

### Submodule Imports (Advanced/Legacy)

For advanced usage or backward compatibility, additional symbols are available via submodule imports:

#### Infrastructure (Internal)

```python
from openai_apis._config import BaseConfig
from openai_apis._session import InvalidStateTransition
from openai_apis._logging import (
    AuditEvent,
    get_logger,
    set_correlation_id,
    log_audit_event,
    log_performance,
    log_api_call,
    setup_logging,
)
```

#### Transcription API

```python
from openai_apis.transcription import (
    TranscriptionAPI,        # Stateless API (legacy)
    TranscriptionConfig,
    TranscriptionSession,    # WebSocket session (recommended, also in public API)
    transcribe_audio,        # async convenience function
    transcribe_file,         # async convenience function
    transcribe_audio_sync,   # sync convenience function
    transcribe_file_sync,    # sync convenience function
)
```

#### TTS API

```python
from openai_apis.tts import (
    TTSAPI,                  # Alias for OpenAITTSProvider
    TTSConfig,               # Also in public API
    TTSRegistry,             # Also in public API
    OpenAITTSProvider,       # Direct provider access
    ElevenLabsTTSProvider,   # Stub provider
    BaseTTSProvider,         # Use TTSProvider from public API instead
    TTSProvider,             # Public alias for BaseTTSProvider
    TTSSynthesisError,       # Exception for TTS errors
    synthesize_text,         # async convenience function
    synthesize_to_file,      # async convenience function
    synthesize_text_sync,    # sync convenience function
    synthesize_to_file_sync, # sync convenience function
    register_provider,       # registry function (backward-compat)
    get_provider,            # registry function (backward-compat)
)
```

#### Realtime Voice API

```python
from openai_apis.realtime import (
    RealtimeSession,         # Also in public API
    RealtimeVoiceAPI,        # Backward-compatible alias for RealtimeSession
    RealtimeConfig,          # Also in public API
    RealtimeAgentState,      # Internal state manager
    ToolRegistry,            # Also in public API
)

# Event types for streaming callbacks
from openai_apis.realtime.events import (
    AudioDelta,
    AudioDone,
    TranscriptDelta,
    TranscriptCompleted,
    ErrorEvent,
    ConversationItem,        # Conversation history entry
)

# Submodule imports also supported (legacy path)
from openai_apis.realtime import (
    RealtimeSession,
    RealtimeVoiceAPI,    # backward-compatible alias
    RealtimeConfig,
    RealtimeAgentState,
    ToolRegistry,        # Tool/function calling registry
    AudioDelta,
    AudioDone,
    TranscriptDelta,
    TranscriptCompleted,
    ErrorEvent,
    ConversationItem,    # Conversation history entry
)

# Event types can also be imported from the events module
from openai_apis.realtime.events import (
    AudioDelta,
    AudioDone,
    TranscriptDelta,
    TranscriptCompleted,
    ErrorEvent,
    ConversationItem,    # Conversation history entry
)
```

**Note:** Realtime module requires `websockets` library. Install with:

```bash
pip install openai-apis[audio]  # includes websockets
```

### Complete Import Example

```python
# Import everything at once
from openai_apis import (
    # Configuration
    BaseConfig, AudioFormat, VADConfig,

    # Session infrastructure
    BaseSession, SessionState, InvalidStateTransition,

    # Logging
    get_logger, SessionAuditLog, AuditEvent,
    log_audit_event, log_performance,

    # Transcription
    TranscriptionAPI, TranscriptionConfig,

    # TTS
    TTSAPI, TTSConfig, TTSRegistry, OpenAITTSProvider, ElevenLabsTTSProvider, BaseTTSProvider, TTSSynthesisError,

    # Realtime
    RealtimeSession, RealtimeVoiceAPI, RealtimeConfig, RealtimeAgentState,
    AudioDelta, AudioDone, TranscriptDelta, TranscriptCompleted, ErrorEvent,
)
```

---

## See Also

- **[Architecture Documentation](./ARCHITECTURE.md)** - System architecture, module relationships, and data flow
- **[Logging & Audit Trail](./LOGGING_AUDIT_TRAIL.md)** - Complete logging and audit documentation
- **[Technical Specifications](../specs.md)** - Full technical specifications and design decisions
- **[CLAUDE.md](../CLAUDE.md)** - Development guidelines and patterns for contributors

---

**Version:** 1.0
**Last Updated:** 2026-05-15
