"""Web server route definitions."""

from examples.web_server.routes.tts import router as tts_router
from examples.web_server.routes.transcription import router as transcription_router
from examples.web_server.routes.realtime import router as realtime_router

__all__ = ["tts_router", "transcription_router", "realtime_router"]
