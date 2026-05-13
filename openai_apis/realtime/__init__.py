"""
Realtime Voice API - WebSocket-based realtime voice sessions.

Requires optional audio dependencies (websocket-client, numpy, sounddevice).
Install with: pip install openai-apis[audio]
"""
from openai_apis.realtime.config import RealtimeConfig

try:
    from openai_apis.realtime.session import RealtimeVoiceAPI, RealtimeAgentState
except ImportError:
    RealtimeVoiceAPI = None
    RealtimeAgentState = None

__all__ = ["RealtimeVoiceAPI", "RealtimeAgentState", "RealtimeConfig"]
