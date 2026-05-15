"""
OpenAI APIs - Unified interface for OpenAI voice/text services.

This package supports modular installation via optional extras:

- Core dependencies: openai, websockets, python-dotenv
- Optional extras:
  - [audio]: Adds sounddevice, numpy, websocket-client for transcription/TTS/realtime
  - [web]: Adds fastapi, uvicorn, python-multipart, aiofiles for web features
  - [agents]: Adds openai-agents for agent orchestration
  - [dev]: Adds pytest, pytest-asyncio, pytest-cov, httpx for testing
  - [all]: Installs all optional dependencies

Install with: pip install openai-apis[audio] or uv sync --extra audio

Note: Some imports (e.g., RealtimeVoiceAPI) may be None if optional dependencies
are not installed. Features that require optional dependencies will raise helpful
ImportError messages if used without the required packages.
"""

__version__ = "0.1.0"

# Shared infrastructure
from openai_apis._logging import (
    get_logger,
    set_correlation_id,
    log_audit_event,
    log_performance,
    log_api_call,
    setup_logging,
    SessionAuditLog,
    AuditEvent,
)
from openai_apis._session import BaseSession, SessionState, InvalidStateTransition
from openai_apis._config import BaseConfig, AudioFormat, VADConfig

# Transcription (M2)
from openai_apis.transcription import TranscriptionAPI, TranscriptionConfig, TranscriptionSession

# TTS (M1)
from openai_apis.tts import (
    TTSAPI,
    TTSConfig,
    OpenAITTSProvider,
    ElevenLabsTTSProvider,
    BaseTTSProvider,
    TTSSynthesisError,
    TTSRegistry,
    register_provider,
    get_provider,
)

# Realtime (M3)
from openai_apis.realtime import (
    RealtimeSession,
    RealtimeVoiceAPI,
    RealtimeConfig,
    RealtimeAgentState,
)
from openai_apis.realtime.events import TranscriptDelta, TranscriptCompleted, ErrorEvent

__all__ = [
    # Infrastructure
    "BaseSession",
    "SessionState",
    "InvalidStateTransition",
    "BaseConfig",
    "AudioFormat",
    "VADConfig",
    "get_logger",
    "set_correlation_id",
    "log_audit_event",
    "log_performance",
    "log_api_call",
    "setup_logging",
    "SessionAuditLog",
    "AuditEvent",
    # Transcription
    "TranscriptionAPI",
    "TranscriptionConfig",
    "TranscriptionSession",
    # TTS
    "TTSAPI",
    "TTSConfig",
    "OpenAITTSProvider",
    "ElevenLabsTTSProvider",
    "BaseTTSProvider",
    "TTSSynthesisError",
    "TTSRegistry",
    "register_provider",
    "get_provider",
    # Realtime
    "RealtimeSession",
    "RealtimeVoiceAPI",
    "RealtimeConfig",
    "RealtimeAgentState",
    "TranscriptDelta",
    "TranscriptCompleted",
    "ErrorEvent",
]
