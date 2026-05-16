"""FastAPI web server example for openai_apis core modules."""

import os
from typing import Optional
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

load_dotenv()


def create_app(
    cors_origins: Optional[list[str]] = None,
) -> FastAPI:
    """Create and configure the FastAPI application.

    Args:
        cors_origins: Allowed CORS origins. Defaults to localhost:8000 and :3000.

    Returns:
        Configured FastAPI app.
    """
    app = FastAPI(
        title="OpenAI APIs Web Server Example",
        description="REST and WebSocket endpoints for TTS, Transcription, and Realtime voice.",
        version="1.0.0",
    )

    # CORS
    if cors_origins is None:
        cors_origins = [
            "http://localhost:8000",
            "http://localhost:3000",
            "http://127.0.0.1:8000",
            "http://127.0.0.1:3000",
        ]

    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Import and include routers
    from examples.web_server.routes import tts_router, transcription_router, realtime_router
    app.include_router(tts_router)
    app.include_router(transcription_router)
    app.include_router(realtime_router)

    # GET /api/health
    @app.get("/api/health", tags=["system"])
    async def health_check():
        api_key_configured = bool(os.environ.get("OPENAI_API_KEY"))
        return {
            "status": "healthy",
            "api_key_configured": api_key_configured,
        }

    # GET /api/config
    @app.get("/api/config", tags=["system"])
    async def get_config():
        from openai_apis.tts.openai_provider import OPENAI_TTS_VOICES
        from openai_apis.tts.config import SUPPORTED_OUTPUT_FORMATS
        from openai_apis.realtime.config import SUPPORTED_REALTIME_VOICES, SUPPORTED_REALTIME_MODELS
        from openai_apis.transcription.config import SUPPORTED_TRANSCRIPTION_MODELS

        return {
            "tts": {
                "voices": list(OPENAI_TTS_VOICES),
                "models": ["gpt-4o-mini-tts", "tts-1", "tts-1-hd"],
                "output_formats": list(SUPPORTED_OUTPUT_FORMATS),
                "defaults": {"voice": "ash", "model": "gpt-4o-mini-tts", "speed": 1.0},
            },
            "transcription": {
                "models": list(SUPPORTED_TRANSCRIPTION_MODELS),
                "defaults": {"model": "gpt-realtime-whisper", "language": "hu"},
            },
            "realtime": {
                "voices": list(SUPPORTED_REALTIME_VOICES),
                "models": list(SUPPORTED_REALTIME_MODELS),
                "defaults": {"voice": "ash", "model": "gpt-realtime-mini", "language": "hu"},
            },
        }

    return app
