"""OpenAI APIs - Unified interface for OpenAI voice/text services."""

__version__ = "0.1.0"

# Core logging (used by all modules)
from openai_apis.logging_config import (
    get_logger,
    set_correlation_id,
    log_audit_event,
    log_performance,
    log_api_call,
    setup_logging,
)

# CLI interface
from openai_apis.cli.interface import CLI, CLIConfig

# Voice interfaces
from openai_apis.voice.agent_framework import AgentFrameworkAPI, VoiceConfig
from openai_apis.voice.realtime_session import RealtimeVoiceAPI, RealtimeConfig
from openai_apis.voice.workflow import StreamingVoiceWorkflow

# Audio processing
from openai_apis.audio.transcription import TranscriptionAPI, TranscriptionConfig
from openai_apis.audio.synthesis import TTSAPI, TTSConfig

# Agent team
from openai_apis.agents.team import assisstant_agent, tools_agent
from openai_apis.agents.tools import websearch_tool, get_current_time, display_text_terminal

# Utilities
from openai_apis.utils.audio_io import record_audio, AudioPlayer
from openai_apis.utils.time_format import magyar_ido_szoveggel

__all__ = [
    # Logging
    "get_logger",
    "set_correlation_id",
    "log_audit_event",
    "log_performance",
    "log_api_call",
    "setup_logging",
    # CLI
    "CLI",
    "CLIConfig",
    # Voice
    "AgentFrameworkAPI",
    "VoiceConfig",
    "RealtimeVoiceAPI",
    "RealtimeConfig",
    "StreamingVoiceWorkflow",
    # Audio
    "TranscriptionAPI",
    "TranscriptionConfig",
    "TTSAPI",
    "TTSConfig",
    # Agents
    "assisstant_agent",
    "tools_agent",
    "websearch_tool",
    "get_current_time",
    "display_text_terminal",
    # Utils
    "record_audio",
    "AudioPlayer",
    "magyar_ido_szoveggel",
]
