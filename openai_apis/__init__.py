"""
OpenAI APIs - Unified interface for OpenAI voice/text services.

Quick start examples::

    # Realtime transcription
    async with TranscriptionSession(TranscriptionConfig(language="hu")) as session:
        session.on("transcript.delta", print)
        await session.send_audio(chunk)

    # Realtime voice
    async with RealtimeSession(RealtimeConfig(voice="ash")) as session:
        session.on("audio.delta", play_audio)
        await session.send_audio(chunk)

    # TTS
    tts = TTSRegistry.create(TTSConfig(voice="sage"))
    audio = await tts.synthesize("Szia!")
"""

__version__ = "0.1.0"

# Core sessions
from openai_apis.transcription import TranscriptionSession, TranscriptionConfig
from openai_apis.realtime import RealtimeSession, RealtimeConfig
from openai_apis.tts import TTSProvider, TTSConfig, TTSRegistry

# Shared config
from openai_apis._config import AudioFormat, VADConfig

# Tools & plugins
from openai_apis.realtime.tools import ToolRegistry
from openai_apis.mcp import MCPPlugin, MCPPluginManager

# Session base (advanced usage)
from openai_apis._session import BaseSession, SessionState
from openai_apis._logging import SessionAuditLog

__all__ = [
    # Core sessions
    "TranscriptionSession",
    "TranscriptionConfig",
    "RealtimeSession",
    "RealtimeConfig",
    "TTSProvider",
    "TTSConfig",
    "TTSRegistry",
    # Shared config
    "AudioFormat",
    "VADConfig",
    # Tools & plugins
    "ToolRegistry",
    "MCPPlugin",
    "MCPPluginManager",
    # Session base (advanced usage)
    "BaseSession",
    "SessionState",
    "SessionAuditLog",
]
