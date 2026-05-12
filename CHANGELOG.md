# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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

### Notes

- Example applications (`voice_agent.py`, `cli_agent.py`, `realtime_websocket.py`) temporarily non-functional pending refactoring
- Tests for CLI and agent framework temporarily disabled (will be restored when modules are re-integrated)
- This is a breaking change for existing code using the old module structure

## [0.1.0] - Previous Release

### Added

- Initial release with voice agent system
- OpenAI Realtime API integration
- Multi-agent system support
- Hungarian language optimization
- Comprehensive logging with audit trail
