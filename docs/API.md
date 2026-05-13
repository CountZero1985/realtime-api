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
- [TTS API](#tts-api)
  - [TTSConfig](#ttsconfig)
  - [BaseTTSProvider](#basettsproider)
  - [OpenAITTSProvider (TTSAPI)](#openaitts provider-ttsapi)
- [Realtime Voice API](#realtime-voice-api)
  - [RealtimeConfig](#realtimeconfig)
  - [RealtimeAgentState](#realtimeagentstate)
  - [RealtimeVoiceAPI](#realtimevoiceapi)
- [Session Infrastructure](#session-infrastructure)
  - [SessionState](#sessionstate)
  - [InvalidStateTransition](#invalidstatetransition)
  - [BaseSession](#basesession)
- [Logging & Audit](#logging--audit)
  - [SessionAuditLog](#sessionauditlog)
  - [AuditEvent](#auditevent)
  - [Global Logging Functions](#global-logging-functions)
- [Import Reference](#import-reference)

---

## Overview

The `openai_apis` package provides a unified Python interface for OpenAI's voice and text services, with three core API modules:

- **Transcription API** - Speech-to-text using Whisper models
- **TTS API** - Text-to-speech synthesis with multiple voices
- **Realtime Voice API** - Low-latency WebSocket-based voice interaction

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

### Transcription (Speech-to-Text)

```python
from openai_apis import TranscriptionAPI
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

```python
from openai_apis import TTSAPI
import numpy as np

# Initialize API
api = TTSAPI()

# Synthesize text to audio (async)
audio = await api.synthesize("Hello, how are you?")
# audio is numpy array (int16, mono, 24kHz) ready for playback

# Save to file (sync)
api.synthesize_to_file_sync("Hello world!", "output.mp3")
```

### Realtime Voice (WebSocket)

```python
from openai_apis import RealtimeVoiceAPI

def on_transcription(text):
    print(f"User said: {text}")

def on_response_text(text):
    print(f"Assistant: {text}")

# Initialize API with callbacks
api = RealtimeVoiceAPI(
    on_transcription=on_transcription,
    on_response_text=on_response_text
)

# Run interactive session (push-to-talk)
api.run_session_sync()
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
| `model` | `str` | `"gpt-4o-mini-transcribe"` | `"gpt-4o-mini-transcribe"`, `"whisper-1"` | Model to use for transcription |
| `language` | `Optional[str]` | `"hu"` | ISO-639-1 code or `None` | Language code (None for auto-detect) |
| `expected_sample_rate` | `int` | `24000` | > 0 | Expected sample rate for validation |
| `expected_channels` | `int` | `1` | > 0 | Expected channels for validation |
| `response_format` | `str` | `"text"` | `"text"`, `"json"`, `"verbose_json"`, `"srt"`, `"vtt"` | Response format |
| `temperature` | `float` | `0.0` | 0.0-1.0 | Sampling temperature (lower = more deterministic) |
| `prompt` | `Optional[str]` | `None` | Any string | Context to guide transcription |

Plus all fields from `BaseConfig` (`api_key`, `timeout`, `audio_format`).

#### Usage

```python
from openai_apis import TranscriptionConfig

# Use defaults (gpt-4o-mini-transcribe, Hungarian, 24kHz mono)
config = TranscriptionConfig()

# Custom model and language
config = TranscriptionConfig(
    model="whisper-1",
    language="en",
    temperature=0.2
)

# Auto-detect language
config = TranscriptionConfig(language=None)
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
    temperature=0.2
)
api = TranscriptionAPI(config)

files = ["file1.wav", "file2.mp3", "file3.m4a"]
transcripts = await api.transcribe_batch(files)

for file, text in zip(files, transcripts):
    print(f"{file}: {text}")
```

---

## TTS API

Text-to-speech synthesis using OpenAI's TTS models. Provider-based architecture for extensibility.

### TTSConfig

Configuration for TTS settings. Extends `BaseConfig`.

**Type:** `@dataclass`

#### Fields

| Field | Type | Default | Valid Values | Description |
|-------|------|---------|--------------|-------------|
| `model` | `str` | `"gpt-4o-mini-tts"` | `"gpt-4o-mini-tts"`, `"tts-1"`, `"tts-1-hd"` | TTS model |
| `voice` | `str` | `"ash"` | `"ash"`, `"sage"`, `"alloy"`, `"echo"`, `"shimmer"` | Voice to use |
| `speed` | `float` | `4.0` | 0.25-4.0 | Speech speed multiplier |
| `output_format` | `str` | `"pcm"` | `"pcm"`, `"mp3"`, `"opus"`, `"aac"`, `"flac"` | Output audio format |
| `sample_rate` | `int` | `24000` | > 0 | Sample rate (PCM format only) |

Plus all fields from `BaseConfig` (`api_key`, `timeout`, `audio_format`).

#### Usage

```python
from openai_apis import TTSConfig

# Use defaults (gpt-4o-mini-tts, ash voice, 4.0x speed, PCM)
config = TTSConfig()

# Custom voice and speed
config = TTSConfig(
    voice="sage",
    speed=1.5,
    output_format="mp3"
)

# High quality TTS
config = TTSConfig(
    model="tts-1-hd",
    voice="alloy",
    speed=1.0
)
```

---

### BaseTTSProvider

Abstract base class for TTS providers. Defines the provider interface that all TTS providers must implement. Provides concrete sync wrapper methods that delegate to the async abstract methods.

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

**`async synthesize_stream(text: str, voice: Optional[str] = None, speed: Optional[float] = None) -> AsyncIterator[bytes]`**

Synthesize text to audio with streaming (async).

- **Parameters:**
  - `text` (`str`): Text to synthesize
  - `voice` (`Optional[str]`): Voice override (provider-specific)
  - `speed` (`Optional[float]`): Speed multiplier override
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

- **Returns:** `["ash", "sage", "alloy", "echo", "shimmer"]`

**`provider_name` (property) -> str**

Provider identifier.

- **Returns:** `"openai"`

#### Async Methods

**`synthesize(text, voice=None, speed=None) -> np.ndarray`**

Synthesize text to speech as numpy array.

- **Parameters:**
  - `text` (`str`): Text to synthesize
  - `voice` (`Optional[str]`): Voice override
  - `speed` (`Optional[float]`): Speed override
- **Returns:** `np.ndarray` - Audio data (int16, mono, 24kHz for PCM)
- **Raises:** `ValueError` if text is empty

**`synthesize_to_file(text, file_path, voice=None, speed=None) -> Path`**

Synthesize text and save to file.

- **Parameters:**
  - `text` (`str`): Text to synthesize
  - `file_path` (`Union[str, Path]`): Output file path
  - `voice` (`Optional[str]`): Voice override
  - `speed` (`Optional[float]`): Speed override
- **Returns:** `Path` - Path to the saved audio file
- **Raises:** `ValueError` if text is empty

**`synthesize_stream(text, voice=None, speed=None) -> AsyncIterator[bytes]`**

Synthesize text with streaming audio chunks.

- **Parameters:**
  - `text` (`str`): Text to synthesize
  - `voice` (`Optional[str]`): Voice override
  - `speed` (`Optional[float]`): Speed override
- **Yields:** `bytes` - Audio chunks
- **Raises:** `ValueError` if text is empty

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
from openai_apis import TTSAPI

api = TTSAPI()

# Synthesize to numpy array (async)
audio = await api.synthesize("Hello, how are you?")
# audio is int16 numpy array, ready for playback

# Synthesize to file (sync)
api.synthesize_to_file_sync("Hello world!", "output.mp3")
```

**Streaming synthesis:**

```python
from openai_apis import OpenAITTSProvider

api = OpenAITTSProvider()

async for audio_chunk in api.synthesize_stream("Long text to synthesize..."):
    # Play or process each chunk as it arrives
    play_audio(audio_chunk)
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
| `model` | `str` | `"gpt-4o-mini-realtime-preview-2024-12-17"` | Realtime model |
| `voice` | `str` | `"sage"` | Voice (sage, ash, alloy, echo, shimmer) |
| `speed` | `float` | `1.1` | Speech speed (0.25-4.0) |
| `transcription_model` | `str` | `"gpt-4o-mini-transcribe"` | Model for transcription |
| `language` | `str` | `"hu"` | Language code (ISO-639-1) |
| `sample_rate` | `int` | `24000` | Audio sample rate in Hz |
| `chunk_duration_s` | `float` | `0.5` | Audio chunk duration in seconds |
| `channels` | `int` | `1` | Audio channels (1 = mono) |
| `instructions` | `str` | `"segíts a kizárólag magyarul beszélő felhasználónak"` | System instructions |
| `modalities` | `List[str]` | `["text", "audio"]` | Enabled modalities |
| `temperature` | `float` | `0.8` | Sampling temperature |
| `max_response_output_tokens` | `str` | `"inf"` | Max response tokens |

Plus all fields from `BaseConfig` (`api_key`, `timeout`, `audio_format`).

#### Usage

```python
from openai_apis import RealtimeConfig

# Use defaults (Hungarian, sage voice)
config = RealtimeConfig()

# English conversation with custom voice
config = RealtimeConfig(
    language="en",
    voice="alloy",
    instructions="You are a helpful assistant.",
    temperature=0.7
)

# Text-only mode (no audio)
config = RealtimeConfig(modalities=["text"])
```

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

### RealtimeVoiceAPI

WebSocket-based realtime voice interaction API.

**Constructor:**

```python
RealtimeVoiceAPI(
    config: Optional[RealtimeConfig] = None,
    state: Optional[RealtimeAgentState] = None,
    api_key: Optional[str] = None,
    on_transcription: Optional[Callable[[str], None]] = None,
    on_response_audio: Optional[Callable[[np.ndarray], None]] = None,
    on_response_text: Optional[Callable[[str], None]] = None,
    on_error: Optional[Callable[[str], None]] = None,
    on_session_created: Optional[Callable[[str], None]] = None,
    on_session_updated: Optional[Callable[[], None]] = None
)
```

**Parameters:**
- `config` (`Optional[RealtimeConfig]`): Realtime configuration
- `state` (`Optional[RealtimeAgentState]`): Custom state manager
- `api_key` (`Optional[str]`): API key (defaults to OPENAI_API_KEY env var)
- `on_transcription` (`Optional[Callable[[str], None]]`): Callback when user speech is transcribed
- `on_response_audio` (`Optional[Callable[[np.ndarray], None]]`): Callback for response audio chunks
- `on_response_text` (`Optional[Callable[[str], None]]`): Callback for response text transcript
- `on_error` (`Optional[Callable[[str], None]]`): Callback for error handling
- `on_session_created` (`Optional[Callable[[str], None]]`): Callback when session is created (receives session_id)
- `on_session_updated` (`Optional[Callable[[], None]]`): Callback when session is updated/configured

**Attributes:**
- `config` (`RealtimeConfig`): Current configuration
- `state` (`RealtimeAgentState`): State manager
- `ws` (`Optional[websocket.WebSocketApp]`): WebSocket connection (None until connected)

#### Methods

**`set_output_device(device_index: int) -> None`**

Set the audio output device for response playback.

- **Parameters:**
  - `device_index` (`int`): Device index from sounddevice.query_devices()

**`run_session_sync() -> None`**

Run interactive realtime session (blocking). Uses push-to-talk: press Enter to start/stop recording.

- **Returns:** `None`
- **Raises:** Various exceptions if connection or audio I/O fails

#### Usage Examples

**Basic realtime session:**

```python
from openai_apis import RealtimeVoiceAPI

def on_transcription(text):
    print(f"User: {text}")

def on_response_text(text):
    print(f"Assistant: {text}")

api = RealtimeVoiceAPI(
    on_transcription=on_transcription,
    on_response_text=on_response_text
)

# Run interactive session (push-to-talk with Enter key)
api.run_session_sync()
```

**With custom state and error handling:**

```python
from openai_apis import RealtimeVoiceAPI, RealtimeAgentState, RealtimeConfig

state = RealtimeAgentState()
state.set("user_preferences", {"language": "en"})

config = RealtimeConfig(
    language="en",
    voice="alloy",
    instructions="You are a friendly assistant."
)

def on_error(error_msg):
    print(f"Error: {error_msg}")

def on_session_created(session_id):
    print(f"Session started: {session_id}")

api = RealtimeVoiceAPI(
    config=config,
    state=state,
    on_error=on_error,
    on_session_created=on_session_created,
    on_response_audio=lambda audio: play_audio(audio)
)

api.run_session_sync()
```

**Custom audio output device:**

```python
import sounddevice as sd

# List available devices
print(sd.query_devices())

api = RealtimeVoiceAPI()
api.set_output_device(2)  # Use device index 2
api.run_session_sync()
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

## Import Reference

Complete reference of all public exports from the `openai_apis` package.

### Infrastructure

```python
from openai_apis import (
    # Configuration
    BaseConfig,
    AudioFormat,
    VADConfig,

    # Session management
    BaseSession,
    SessionState,
    InvalidStateTransition,

    # Logging & audit
    get_logger,
    set_correlation_id,
    log_audit_event,
    log_performance,
    log_api_call,
    setup_logging,
    SessionAuditLog,
    AuditEvent,
)
```

### Transcription API

```python
from openai_apis import (
    TranscriptionAPI,
    TranscriptionConfig,
)

# Submodule imports also supported
from openai_apis.transcription import (
    TranscriptionAPI,
    TranscriptionConfig,
    transcribe_audio,       # async convenience function
    transcribe_file,        # async convenience function
    transcribe_audio_sync,  # sync convenience function
    transcribe_file_sync,   # sync convenience function
)
```

### TTS API

```python
from openai_apis import (
    TTSAPI,              # Alias for OpenAITTSProvider
    TTSConfig,
    OpenAITTSProvider,
    BaseTTSProvider,
)

# Submodule imports also supported
from openai_apis.tts import (
    TTSAPI,
    TTSConfig,
    OpenAITTSProvider,
    BaseTTSProvider,
    synthesize_text,         # async convenience function
    synthesize_to_file,      # async convenience function
    synthesize_text_sync,    # sync convenience function
    synthesize_to_file_sync, # sync convenience function
    register_provider,       # registry function
    get_provider,            # registry function
)
```

### Realtime Voice API

```python
from openai_apis import (
    RealtimeVoiceAPI,
    RealtimeConfig,
    RealtimeAgentState,
)

# Submodule imports also supported
from openai_apis.realtime import (
    RealtimeVoiceAPI,
    RealtimeConfig,
    RealtimeAgentState,
)
```

**Note:** Realtime imports may be `None` if optional audio dependencies (`websocket-client`, `sounddevice`, `numpy`) are not installed. Install with:

```bash
pip install openai-apis[audio]
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
    TTSAPI, TTSConfig, OpenAITTSProvider, BaseTTSProvider,

    # Realtime
    RealtimeVoiceAPI, RealtimeConfig, RealtimeAgentState,
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
**Last Updated:** 2025-12-26
