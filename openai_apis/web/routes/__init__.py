"""Web routes for OpenAI APIs."""

from openai_apis.web.routes.transcription import router as transcription_router
from openai_apis.web.routes.synthesis import router as synthesis_router
from openai_apis.web.routes.chat import router as chat_router
from openai_apis.web.routes.realtime import router as realtime_router

__all__ = [
    "transcription_router",
    "synthesis_router",
    "chat_router",
    "realtime_router",
]
