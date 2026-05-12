"""OpenAI APIs - Unified interface for OpenAI voice/text services."""

__version__ = "0.1.0"

# Shared infrastructure
from openai_apis._logging import (
    get_logger,
    set_correlation_id,
    log_audit_event,
    log_performance,
    log_api_call,
    setup_logging,
)
from openai_apis._session import BaseSession, SessionState, InvalidStateTransition
from openai_apis._config import BaseConfig

# Transcription (M2)
from openai_apis.transcription import TranscriptionAPI, TranscriptionConfig

# TTS (M1)
from openai_apis.tts import TTSAPI, TTSConfig, OpenAITTSProvider, BaseTTSProvider

# Realtime (M3)
from openai_apis.realtime import RealtimeVoiceAPI, RealtimeConfig, RealtimeAgentState

__all__ = [
    # Infrastructure
    "BaseSession",
    "SessionState",
    "InvalidStateTransition",
    "BaseConfig",
    "get_logger",
    "set_correlation_id",
    "log_audit_event",
    "log_performance",
    "log_api_call",
    "setup_logging",
    # Transcription
    "TranscriptionAPI",
    "TranscriptionConfig",
    # TTS
    "TTSAPI",
    "TTSConfig",
    "OpenAITTSProvider",
    "BaseTTSProvider",
    # Realtime
    "RealtimeVoiceAPI",
    "RealtimeConfig",
    "RealtimeAgentState",
]
