"""
Realtime Voice API - WebSocket-based realtime voice sessions.

Requires optional audio dependencies (websocket-client, numpy, sounddevice).
Install with: pip install openai-apis[audio]
"""
from openai_apis.realtime.config import RealtimeConfig
from openai_apis.realtime.events import TranscriptDelta, TranscriptCompleted, ErrorEvent

try:
    from openai_apis.realtime.session import RealtimeVoiceAPI, RealtimeAgentState
except ImportError:
    RealtimeVoiceAPI = None
    RealtimeAgentState = None

__all__ = [
    "RealtimeVoiceAPI",
    "RealtimeAgentState",
    "RealtimeConfig",
    "TranscriptDelta",
    "TranscriptCompleted",
    "ErrorEvent",
]
