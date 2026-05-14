# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- **TranscriptionSession WebSocket Client** - Implemented async WebSocket client for real-time transcription via OpenAI Realtime API (issue #18):
  - **`TranscriptionSession` class**: New WebSocket-based session in `openai_apis/transcription/ws_session.py` inheriting from `BaseSession`
  - **Real-time audio streaming**: Send audio chunks via `send_audio()` with base64-encoded PCM16 format
  - **Push-to-talk mode**: Commit audio buffer via `commit_audio()` to trigger transcription
  - **Streaming transcription**: Receive partial transcripts via `transcript.delta` callback and complete transcripts via `transcript.completed` callback
  - **Reconnection logic**: Automatic reconnection with exponential backoff (configurable max attempts and delay)
  - **Event-driven callbacks**: Support for `transcript.delta`, `transcript.completed`, `error`, `session.created`, `session.updated` events via `session.on()` method
  - **Comprehensive audit logging**: All session lifecycle events, audio chunks, and server responses logged to per-session audit trail
  - **State machine integration**: Full lifecycle management (CREATED → CONNECTING → CONNECTED → DISCONNECTING → CLOSED)
  - **Async context manager**: Use `async with TranscriptionSession() as session:` for automatic connection/disconnection
  - Connects to `wss://api.openai.com/v1/realtime` with `gpt-4o-mini-realtime-preview-2024-12-17` model
  - Comprehensive unit tests in `tests/unit/test_transcription_session.py` with 100% coverage

- **TTS Module Enhanced Test Coverage** - Expanded unit test suite to achieve 93%+ coverage (issue #16):
  - **Convenience function tests**: Added tests for module-level convenience functions (`synthesize_text`, `synthesize_to_file`, `synthesize_text_sync`, `synthesize_to_file_sync`) in `test_tts_openai_provider.py`
  - **Edge case coverage**: Added tests for Unicode text, very long text (10,000 chars), and whitespace-only input validation
  - **Import error handling**: Added test for numpy ImportError guard in `synthesize()` method
  - **Audio duration calculation**: Added test for non-PCM formats where `audio_duration_seconds` returns None
  - **Backpressure final chunk**: Added test for backpressure event handling on final partial chunk in streaming
  - **Audit logging paths**: Added tests for `_synthesize_bytes` success and failure audit event logging
  - **Custom provider voice validation**: Added test for unknown-but-registered provider voice validation skip in `test_tts_config.py`
  - Coverage results: `openai_provider.py` 93%, `config.py` 100%, `_registry.py` 100%, `base.py` 92%, aggregate TTS module 93%+
  - Total TTS test suite: 111 passing tests across 4 test files

### Added

- **TTS Streaming Enhancements** - Added configurable chunk size and backpressure support for `synthesize_stream()` (issue #15):
  - **`chunk_size` field in `TTSConfig`**: New field (default: 1024 bytes) for configurable streaming chunk size with validation (must be > 0)
  - **Re-chunking buffer**: API response bytes are buffered and yielded in uniform chunks of exactly `chunk_size` bytes (except potentially the final chunk)
  - **`chunk_size` parameter**: Optional parameter on `synthesize_stream()` to override config default on a per-call basis
  - **Backpressure control**: New `backpressure_event` parameter (optional `asyncio.Event`) allows consumers to pause/resume streaming by clearing/setting the event
  - **Enhanced audit logging**: `chunk_size` and `chunk_count` now included in streaming audit events (`stream_synthesis_started`, `stream_synthesis_completed`)
  - **Updated abstract interface**: `BaseTTSProvider.synthesize_stream()` signature now includes `chunk_size` parameter
  - Comprehensive unit tests in `tests/unit/test_tts_openai_provider.py` covering chunk size validation, re-chunking, and backpressure handling

- **TTS Provider Registry and ElevenLabs stub** - Refactored TTS provider system (issue #14):
  - **TTSRegistry class**: New class-based registry with `register()`, `get()`, `create()`, and `list_providers()` methods
  - **ElevenLabsTTSProvider stub**: Stub implementation for ElevenLabs provider with 3 voices (rachel, adam, bella)
  - **Provider-agnostic voice validation**: `TTSConfig` now validates voices against any registered provider
  - **Auto-registration**: Built-in providers (OpenAI, ElevenLabs) are auto-registered on module import
  - **Backward-compatible free functions**: `register_provider()` and `get_provider()` functions maintained as thin wrappers
  - Comprehensive unit tests in `tests/unit/test_tts_registry.py` covering all registry operations

- **TTSConfig validation** - Added `__post_init__` validation to `TTSConfig` (issue #13):
  - **New fields**: Added `provider` (default: "openai") and `language` (default: "hu") fields
  - **Speed validation**: Validates `speed` is between 0.25 and 4.0 on initialization
  - **Voice validation**: Validates `voice` against provider's `supported_voices` list
  - **Output format validation**: Validates `output_format` against supported formats ("pcm", "mp3", "opus", "aac", "flac", "wav")
  - **Provider validation**: Validates `provider` is registered in the provider registry
  - Raises `ValueError` with clear error messages for all invalid configurations
  - New test file `tests/unit/test_tts_config.py` with comprehensive validation tests

### Added

- **OpenAI TTS Provider - Full Implementation** - Completed `OpenAITTSProvider` with all features from issue #12:
  - **13 voice support**: Added 8 new voices (ballad, coral, fable, nova, onyx, verse, marin, cedar) to existing 5 voices, total 13 voices now supported
  - **Instruction-based voice steering**: New `instructions` field in `TTSConfig` for voice customization with `gpt-4o-mini-tts` model
  - **Enhanced error handling**: New `TTSSynthesisError` exception for clear API error reporting
  - **Streaming audit logging**: Added comprehensive audit events for `synthesize_stream()` (start, complete, error events)
  - **Provider registry**: `OpenAITTSProvider` now auto-registered as "openai" provider in `_registry.py`
  - **Comprehensive tests**: New `tests/unit/test_tts_openai_provider.py` with 100% coverage of all features

### Changed

- **TTSConfig speed default**: Changed `speed` default from `4.0` (maximum speed) to `1.0` (normal speech speed) for more sensible default behavior
- **BaseTTSProvider abstract base class enhancements** - Expanded `BaseTTSProvider` in `openai_apis/tts/base.py` with complete provider interface:
  - Added `synthesize_to_file()` abstract method for saving audio directly to files
  - Added `supported_voices` abstract property for listing available voices
  - Added `provider_name` abstract property for provider identification (e.g., "openai", "elevenlabs")
  - Added concrete sync wrapper methods `synthesize_sync()` and `synthesize_to_file_sync()` that delegate to async methods
  - Subclasses now only need to implement async abstract methods; sync wrappers are inherited automatically
  - `OpenAITTSProvider` now implements `supported_voices` (returns `["ash", "sage", "alloy", "echo", "shimmer"]`) and `provider_name` (returns `"openai"`)
  - Removed redundant sync wrapper methods from `OpenAITTSProvider` to use inherited base class versions
  - Comprehensive unit tests added in `tests/unit/test_tts_base.py` covering abstract contract, sync wrappers, and OpenAI provider properties

### Added

- **Comprehensive API documentation** - Added complete API reference and architecture documentation:
  - `docs/API.md`: Full API reference covering all three core modules (Transcription, TTS, Realtime), configuration classes (AudioFormat, VADConfig, BaseConfig), session infrastructure (BaseSession, SessionState), and logging/audit system
  - `docs/ARCHITECTURE.md`: System architecture documentation with package structure, module relationships, data flow diagrams, session lifecycle state machine, and provider pattern explanation
  - Both documents include code examples, method signatures, parameter descriptions, and usage patterns

### Changed

- **Dependency restructuring** - Reorganized package dependencies for modular installation:
  - **Core dependencies**: Only `openai`, `websockets`, and `python-dotenv` required for basic imports
  - **Optional extras**:
    - `audio`: Adds `sounddevice`, `numpy`, `websocket-client` for transcription, TTS, and realtime features
    - `web`: Adds `fastapi`, `uvicorn`, `python-multipart`, `aiofiles` for web server functionality
    - `agents`: Adds `openai-agents` for agent orchestration features
    - `dev`: Adds `pytest`, `pytest-asyncio`, `pytest-cov`, `httpx` for development and testing
    - `all`: Installs all optional dependencies
  - Conditional imports: `numpy`, `sounddevice`, and `websocket-client` now imported lazily with helpful error messages
  - Install with: `pip install openai-apis[audio]` or `uv sync --extra audio` for full functionality

### Added

- **Example applications restored** - Moved application-level code from git history into `examples/` directory:
  - **Example scripts**: `cli_agent.py`, `voice_agent.py`, `realtime_websocket.py` now fully functional
  - **Agent modules**: `examples/agents/` with team configuration, tools, and Hungarian prompts
  - **Utility modules**: `examples/utils/` with audio I/O and time formatting utilities
  - **CLI interface**: `examples/cli_app.py` for text-based agent interactions
  - **Voice pipeline**: `examples/voice_pipeline.py` with `AgentFrameworkAPI` and `StreamingVoiceWorkflow`
  - All examples use `sys.path.insert()` pattern for cross-example imports
  - Comprehensive docstrings added to all example modules and scripts

- **AudioFormat and VADConfig configuration classes** - Added shared configuration types to `_config.py`:
  - `AudioFormat`: Frozen dataclass for immutable audio format specifications (sample_rate, channels, dtype, encoding)
  - `VADConfig`: Voice Activity Detection configuration with support for server_vad, semantic_vad, and disabled modes
  - `BaseConfig` extended with `audio_format` field (defaults to 24kHz, mono, int16, pcm16)
  - `__post_init__` validation for all configuration classes ensures invalid values are caught early
  - All submodule configs (`TranscriptionConfig`, `TTSConfig`, `RealtimeConfig`) automatically inherit `audio_format`
  - Comprehensive unit tests in `tests/unit/test_config.py` with 100% coverage

- **Per-session audit logging system** - Implemented `SessionAuditLog` and `AuditEvent` classes for structured per-session event tracking:
  - `SessionAuditLog`: Thread-safe in-memory event storage with automatic timestamp and duration tracking
  - `AuditEvent`: Dataclass for audit events with timestamp, session_id, event_type, data, and duration_ms
  - `measure()` context manager for automatic duration tracking (e.g., `with audit_log.measure("api.call"): ...`)
  - `export_json()` and `export_to_file()` methods for exporting session audit trails
  - Integrated into `BaseSession` - all sessions now have `session.audit_log` property
  - Event types use dot-separated naming (e.g., "session.created", "session.state_transition")
  - Backward-compatible global `log_audit_event()` function maintained for non-session code

- **BaseSession lifecycle management** - Implemented full `BaseSession` abstract class with:
  - State machine with 5 states (created → connecting → connected → disconnecting → closed)
  - Async context manager support (`async with`) for automatic connection/disconnection
  - Automatic UUID session ID generation
  - Per-session audit logging integration via `SessionAuditLog`
  - Event callback registry system (`on`/`_emit` methods)
  - `SessionState` enum and `InvalidStateTransition` exception for state validation
  - Comprehensive unit tests with 100% coverage

### Changed

- **Major package restructuring** - Reorganized `openai_apis` package from flat 7-subpackage structure to clean 3-module library architecture:
  - **New structure**: `transcription/`, `tts/`, `realtime/` plus shared infrastructure (`_config.py`, `_logging.py`, `_session.py`)
  - **Removed modules**: `audio/`, `cli/`, `voice/`, `agents/`, `utils/`, `web/` (to be moved to examples in future release)
  - **Migration notes**:
    - `openai_apis.audio.transcription` → `openai_apis.transcription`
    - `openai_apis.audio.synthesis.TTSAPI` → `openai_apis.tts.OpenAITTSProvider` (backward-compatible `TTSAPI` alias maintained)
    - `openai_apis.voice.realtime_session` → `openai_apis.realtime`
    - `openai_apis.logging_config` → `openai_apis._logging` (private module)
  - Provider-based TTS architecture introduced with `BaseTTSProvider` abstract class
  - All configuration classes now inherit from `BaseConfig`
  - Consistent session management pattern across all APIs

### Fixed

- Cleaned up import paths and module organization for better maintainability
- Standardized configuration pattern across all API modules

### Fixed

- **Example applications restored** - Fixed broken example scripts by restoring application-level code to `examples/` directory
- Updated imports throughout examples to use new package structure (`openai_apis._logging` instead of `openai_apis.logging_config`)

### Notes

- This is a breaking change for existing code using the old module structure (pre-v1.0)

## [0.1.0] - Previous Release

### Added

- Initial release with voice agent system
- OpenAI Realtime API integration
- Multi-agent system support
- Hungarian language optimization
- Comprehensive logging with audit trail
