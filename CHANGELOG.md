# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- **MCP Plugin System** - Implemented Model Context Protocol plugin stub system as new `openai_apis/mcp/` subpackage (issue #29):
  - **`MCPPlugin` abstract base class**: Abstract interface in `openai_apis/mcp/base.py` with four abstract members: `name` (plugin identifier), `description` (human-readable description), `get_tools()` (returns tool definitions in OpenAI function-calling JSON Schema format), and `execute_tool()` (async tool execution handler)
  - **`MCPPluginManager` class**: Plugin registry and dispatcher in `openai_apis/mcp/manager.py` with `register()` for plugin registration, `get_all_tools()` for tool aggregation, `execute()` for tool dispatch, and `populate_tool_registry()` for ToolRegistry integration
  - **Stub plugins**: `FileSystemPlugin` (read_file, write_file tools) and `GmailPlugin` (send_email, read_emails tools) in `openai_apis/mcp/plugins/` - both raise `NotImplementedError` on execution (placeholder for future implementation)
  - **ToolRegistry integration**: `populate_tool_registry()` bridges MCP tools into Realtime API's `ToolRegistry` so MCP tools appear as regular function-calling tools
  - **Validation and error handling**: Registration validates plugin types, detects duplicate plugin names and tool name collisions across plugins, raises clear `TypeError` and `ValueError` exceptions
  - **Helper properties**: `plugin_names` (sorted list), `__len__`, `__bool__` for convenient manager inspection
  - **Design patterns**: Follows `BaseTTSProvider` ABC pattern for plugin base class, `ElevenLabsTTSProvider` stub pattern for plugin stubs, and `ToolRegistry` pattern for manager
  - Exported from package root: `from openai_apis import MCPPlugin, MCPPluginManager, FileSystemPlugin, GmailPlugin`
  - Comprehensive unit tests in `tests/unit/test_mcp_base.py`, `tests/unit/test_mcp_manager.py`, and `tests/unit/test_mcp_plugins.py` covering ABC contract, registration, dispatch, ToolRegistry integration, and stub behavior

- **ToolRegistry for Realtime API** - Implemented comprehensive tool/function calling registry system (issue #28):
  - **`ToolRegistry` class**: New registry in `openai_apis/realtime/tools.py` for managing tool definitions and handlers
  - **Tool registration**: `register(name, description, parameters, handler)` method for registering tools with JSON Schema parameters
  - **API format conversion**: `to_api_format()` method converts tool definitions to OpenAI Realtime API format
  - **Automatic execution**: `execute(name, arguments)` method handles tool execution with support for both sync and async handlers
  - **RealtimeConfig integration**: `tools` field now accepts `ToolRegistry | list[dict]` with automatic conversion to API format
  - **RealtimeSession auto-execution**: When `ToolRegistry` is provided via config, tool calls are automatically executed, results are sent back, and responses are triggered
  - **Comprehensive audit logging**: Tool execution logged with `tool.execution.started`, `tool.execution.completed`, and `tool.execution.failed` events including duration metrics
  - **Helper properties**: `tool_names` (sorted list), `__len__`, `__bool__` for convenient registry inspection
  - **Error handling**: Failed tool executions are caught, logged, and error results are sent back to the model for graceful recovery
  - Exported from package root: `from openai_apis import ToolRegistry`
  - Comprehensive unit tests in `tests/unit/test_realtime_tools.py` covering registration, API format conversion, execution (sync/async), config integration, session integration, and audit logging

### Added

- **Audio Streaming with Typed Events** - Enhanced realtime audio streaming with typed event objects and comprehensive audit logging (issue #27):
  - **Typed audio events**: New `AudioDelta` and `AudioDone` dataclasses in `openai_apis/realtime/events.py`
  - **`AudioDelta`**: Output audio chunk events with `audio_bytes` (decoded PCM16), `item_id`, and `response_id`
  - **`AudioDone`**: Audio stream completion marker with `item_id` and `response_id`
  - **Audio output audit logging**: Automatic tracking of output audio streaming with `audio.output_completed` events including chunk count, total bytes, audio duration (seconds), and streaming duration (milliseconds)
  - **Audio input audit logging**: Per-chunk logging via `audio.chunk_sent` events with cumulative chunk count and total bytes; commit summary via `audio.buffer_committed` events with total statistics and audio duration
  - **Counter reset on commit**: Input audio counters automatically reset after `commit_audio()` for clean push-to-talk turn tracking
  - **Duration calculations**: Audio duration calculated from byte count and audio format (sample rate, channels, PCM16 = 2 bytes/sample)
  - **Per-item accumulation**: Output audio statistics tracked per `item_id` from first delta to done event
  - **Breaking change**: `audio.delta` callbacks now receive `AudioDelta` objects instead of raw `bytes` (access via `.audio_bytes`); `audio.done` callbacks receive `AudioDone` objects instead of `dict` (access via `.item_id` and `.response_id`)
  - Comprehensive unit tests in `tests/unit/test_realtime_session.py` covering typed events, multi-chunk scenarios, and audit logging

### Changed

- **RealtimeConfig modernization** - Updated `RealtimeConfig` to match OpenAI Realtime API specifications (issue #26):
  - **Default model change**: Changed default `model` from `"gpt-4o-mini-realtime-preview-2024-12-17"` to `"gpt-realtime-mini"`
  - **Default voice change**: Changed default `voice` from `"sage"` to `"ash"`
  - **New fields**: Added `vad` (VADConfig), `input_audio_transcription` (bool), and `tools` (list[dict])
  - **Removed fields**: Removed `speed`, `transcription_model`, `sample_rate`, `chunk_duration_s`, and `channels` (audio format now handled by `BaseConfig.audio_format`)
  - **Field validation**: Added `__post_init__` validation for model, voice, temperature (0.6-1.2), max_response_output_tokens, and modalities
  - **Supported models**: gpt-realtime-mini, gpt-4o-mini-realtime-preview-2024-12-17, gpt-4o-realtime-preview, gpt-4o-realtime-preview-2024-12-17
  - **Supported voices**: alloy, ash, ballad, coral, echo, sage, shimmer, verse
  - **New method**: Added `to_session_update()` method that converts config to OpenAI Realtime API `session.update` event format
  - **VAD integration**: Voice Activity Detection now configurable via `VADConfig` field with support for server_vad, semantic_vad, and disabled modes
  - **Tools support**: Function calling tools can now be provided via `tools` field (JSON Schema format)
  - **Session update delegation**: `RealtimeSession._create_session_update_payload()` now delegates to `config.to_session_update()`
  - **Breaking change**: Old fields (`speed`, `transcription_model`, `sample_rate`, `chunk_duration_s`, `channels`, `keywords`) removed - users must migrate to new field structure
  - Comprehensive unit tests in `tests/unit/test_realtime_config.py` with 100% coverage

- **RealtimeSession async WebSocket rewrite** - Replaced synchronous `RealtimeVoiceAPI` with async `RealtimeSession` inheriting from `BaseSession` (issue #25):
  - **Architecture change**: New `RealtimeSession` class uses async `websockets` library instead of synchronous `websocket-client` + threading
  - **BaseSession integration**: Full lifecycle management with state machine (CREATED → CONNECTING → CONNECTED → DISCONNECTING → CLOSED)
  - **Async context manager**: Use `async with RealtimeSession() as session:` for automatic connection/disconnection
  - **Pure protocol client**: Removed audio I/O (mic/speaker) from core library - now belongs in examples (matches TranscriptionSession pattern)
  - **Async API methods**: `send_audio()`, `commit_audio()`, `create_response()`, `update_session()`, `send_tool_result()` are all async
  - **Event-driven callbacks**: Register callbacks via `session.on(event, callback)` for all realtime events
  - **Supported events**:
    - `audio.delta`: Output audio chunk (bytes, base64-decoded)
    - `audio.done`: Output audio stream complete
    - `transcript.input`: Input transcription with `TranscriptCompleted` data
    - `transcript.output`: Output transcription with `TranscriptCompleted` data
    - `transcript.delta`: Partial transcription with `TranscriptDelta` data
    - `tool.call`: Tool/function call request (dict with call_id, name, arguments)
    - `response.done`: Response generation complete
    - `error`: Error from server (`ErrorEvent`)
    - `session.created`/`session.updated`: Server session lifecycle events
  - **Automatic reconnection**: Exponential backoff with configurable max attempts and delay
  - **Per-session audit logging**: All events logged via `session.audit_log` property
  - **Backward compatibility**: `RealtimeVoiceAPI` maintained as alias for `RealtimeSession` in imports
  - **Removed methods**: `run_session_sync()`, `set_output_device()` (application-level features moved to examples)
  - **Breaking change**: Old synchronous API with built-in audio I/O is no longer available - users must migrate to async API
  - Comprehensive unit tests in `tests/unit/test_realtime_session.py` covering lifecycle, API methods, event handling, and reconnection

### Changed

- **TranscriptionConfig modernization** - Updated `TranscriptionConfig` with new fields and validation (issue #19):
  - **Default model change**: Changed default `model` from `"gpt-4o-mini-transcribe"` to `"gpt-realtime-whisper"`
  - **New fields**: Added `vad` (VADConfig), `keywords` (list[str]), and `include_logprobs` (bool)
  - **Removed fields**: Removed `expected_sample_rate`, `expected_channels`, `response_format`, and `temperature` (audio format now handled by `BaseConfig.audio_format`)
  - **Model validation**: Added `__post_init__` validation for supported transcription models (gpt-realtime-whisper, gpt-4o-mini-transcribe, gpt-4o-transcribe, whisper-1)
  - **Language validation**: Added ISO 639-1 language code validation with support for 100+ languages
  - **VAD integration**: Transcription sessions now support Voice Activity Detection via `VADConfig` field
  - **Keyword steering**: New `keywords` field allows steering transcription accuracy for domain-specific terms
  - **Log probabilities**: New `include_logprobs` field enables requesting log probabilities from the API
  - Comprehensive unit tests in `tests/unit/test_transcription_config.py` with 100% coverage

### Added

- **Transcription Module Enhanced Test Coverage** - Expanded unit test suite to achieve 90%+ coverage for all transcription module files (issue #23):
  - **TranscriptionAPI tests**: Added 11 new test methods covering numpy-not-installed ImportError guards, language=None and prompt=None parameter handling, string path inputs, JSON response edge cases, temp file cleanup on errors, config validation (timeout, audio_format, api_key from env), and package-level import verification
  - **TranscriptionSession WebSocket tests**: Added 24 new test methods covering `_handle_message()` event routing (session.created, session.updated, buffer.committed, invalid JSON, exception handling), `_receive_loop()` exception handlers (ConnectionClosed triggering reconnect, generic exceptions, CancelledError), full `_reconnect()` flow (success on first attempt, all attempts failing, partial failures, audit logging), `_disconnect()` edge cases (None task/websocket), `_connect()` non-matching messages, send_audio edge cases (empty chunks, multiple chunks), session.update payload verification (language, model, turn_detection), and class constants validation
  - **Coverage results**: `config.py` 100%, `session.py` 90%, `ws_session.py` 99%, aggregate transcription module 93%+
  - **Total test count**: 116 passing tests across 2 test files (`test_transcription.py` with 54 tests, `test_transcription_session.py` with 59 tests)
  - All tests use mocked OpenAI API calls and WebSocket connections (no real network requests)

- **VAD Configuration for TranscriptionSession** - Added Voice Activity Detection configuration to TranscriptionSession (issue #21):
  - **`vad_config` field in `TranscriptionConfig`**: New optional field for VAD configuration (None = disabled/push-to-talk)
  - **`update_vad()` method**: Runtime VAD mode switching via new `session.update_vad(vad_config)` method
  - **Three VAD modes supported**: `server_vad` (threshold-based), `semantic_vad` (eagerness-based), `disabled` (push-to-talk)
  - **Automatic turn_detection serialization**: Internal `_vad_config_to_turn_detection()` method converts VADConfig to OpenAI Realtime API format
  - **Session.update event**: VAD settings sent via `session.update` WebSocket event to OpenAI API
  - **Runtime switching**: VAD mode can be changed during active session via `update_vad()` method
  - **State validation**: `update_vad()` requires CONNECTED state, raises `InvalidStateTransition` otherwise
  - **Audit logging**: VAD updates logged with `vad.updated` event type and mode information
  - **Backward compatible**: Default config (no vad_config) maintains push-to-talk behavior with `turn_detection: null`
  - Comprehensive unit tests in `tests/unit/test_transcription_session.py::TestVADConfiguration` covering all modes, JSON serialization, and runtime switching

- **Language Configuration and Keyword Steering** - Added keyword steering support to Realtime API transcription (issue #22):
  - **`keywords` field in `RealtimeConfig`**: New optional field (`Optional[List[str]]`, default `None`) for domain-specific keyword steering
  - **Keyword prompt propagation**: Keywords are sent via `input_audio_transcription.prompt` field in `session.update` WebSocket event
  - **Flexible keyword format**: Keywords joined with `", "` for OpenAI API (comma-separated list for `whisper-1`, free-text hint for `gpt-4o-transcribe`-series)
  - **Enhanced audit logging**: Both `language` and `keywords` now logged in `realtime_init` and `session_configured` audit events
  - **Comprehensive testing**: Unit tests for keyword configuration, session update event propagation, and audit logging
  - **Multi-language support**: Existing `language` field (default `"hu"`) now properly documented and tested with multiple languages (en, de, fr)
  - **Smart field omission**: `prompt` field only included in session update when keywords are non-empty (omitted for `None` or empty list)
  - New unit tests in `tests/unit/test_realtime_session.py` covering all keyword and language scenarios
- **Delta Event Streaming with Typed Callbacks** - Implemented streaming transcript events for Realtime API (issue #20):
  - **Typed event objects**: New `TranscriptDelta`, `TranscriptCompleted`, and `ErrorEvent` dataclasses in `openai_apis/realtime/events.py`
  - **`TranscriptDelta`**: Partial transcription events (~200-500ms intervals) with `item_id`, `delta` text, and `accumulated` full text
  - **`TranscriptCompleted`**: Final transcription with `item_id`, complete `transcript`, and `duration_ms` from first delta
  - **`ErrorEvent`**: Error events with `code` and `message` fields
  - **Delta text accumulation**: Per-item text accumulation via internal `_delta_accumulator` dict in `RealtimeVoiceAPI`
  - **Event callback system**: New `session.on(event, callback)` method for registering typed event handlers
    - `"transcript.delta"`: Receives `TranscriptDelta` for user input and assistant response deltas
    - `"transcript.completed"`: Receives `TranscriptCompleted` when transcription finishes
    - `"error"`: Receives `ErrorEvent` for error handling
  - **Async-safe callback invocation**: `_emit_event()` method handles callback invocation with per-callback error isolation
  - **Comprehensive audit logging**: All delta and completed events logged with `item_id`, text lengths, and duration metrics
  - **WebSocket event handling**: Extended `_on_message()` to process `conversation.item.input_audio_transcription.delta` and `response.audio_transcript.delta` events
  - **Duration tracking**: Automatic measurement from first delta to completion per `item_id`
  - **Multiple callback support**: Multiple callbacks can be registered for the same event type
  - **Robust error handling**: Failing callbacks don't block other callbacks from executing
  - New exports: `TranscriptDelta`, `TranscriptCompleted`, `ErrorEvent` available from package root
  - Comprehensive unit tests in `tests/unit/test_realtime_events.py` covering all event types, accumulation logic, and error scenarios

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
