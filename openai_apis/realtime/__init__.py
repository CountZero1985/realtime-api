"""Realtime Voice API - Async WebSocket-based realtime voice sessions."""
from openai_apis.realtime.config import RealtimeConfig
from openai_apis.realtime.events import (
    TranscriptDelta, TranscriptCompleted, ErrorEvent,
    AudioDelta, AudioDone, ConversationItem,
)
from openai_apis.realtime.session import RealtimeSession, RealtimeAgentState
from openai_apis.realtime.tools import ToolRegistry

# Backward compatibility alias
RealtimeVoiceAPI = RealtimeSession

__all__ = [
    "RealtimeSession",
    "RealtimeVoiceAPI",  # backward compat
    "RealtimeAgentState",
    "RealtimeConfig",
    "ToolRegistry",
    "TranscriptDelta",
    "TranscriptCompleted",
    "ErrorEvent",
    "AudioDelta",
    "AudioDone",
    "ConversationItem",
]
