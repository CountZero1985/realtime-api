"""FastAPI web server for OpenAI APIs frontend."""

import os
from pathlib import Path
from typing import Optional

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import uvicorn

from openai_apis.web.routes import (
    transcription_router,
    synthesis_router,
    chat_router,
    realtime_router,
)
from openai_apis._logging import get_logger, setup_logging

logger = get_logger(__name__)

# Static files directory
STATIC_DIR = Path(__file__).parent / "static"


def create_app(
    title: str = "OpenAI APIs Web Frontend",
    description: str = "Web interface for real-time voice, transcription, and TTS",
    cors_origins: Optional[list[str]] = None,
) -> FastAPI:
    """
    Create and configure the FastAPI application.

    Args:
        title: API title for documentation.
        description: API description.
        cors_origins: List of allowed CORS origins. Defaults to localhost.

    Returns:
        Configured FastAPI application.
    """
    # Setup logging
    setup_logging()

    app = FastAPI(
        title=title,
        description=description,
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
    )

    # CORS middleware
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

    # Include routers
    app.include_router(transcription_router)
    app.include_router(synthesis_router)
    app.include_router(chat_router)
    app.include_router(realtime_router)

    # Health check endpoint
    @app.get("/health", tags=["system"])
    async def health_check():
        """Health check endpoint."""
        api_key_configured = bool(os.environ.get("OPENAI_API_KEY"))
        return {
            "status": "healthy",
            "api_key_configured": api_key_configured,
        }

    # Configuration endpoint
    @app.get("/api/config", tags=["system"])
    async def get_config():
        """Get available configuration options."""
        return {
            "voices": ["ash", "sage", "alloy", "echo", "shimmer"],
            "tts_models": ["gpt-4o-mini-tts", "tts-1", "tts-1-hd"],
            "stt_models": ["gpt-4o-mini-transcribe", "whisper-1"],
            "languages": [
                {"code": "hu", "name": "Hungarian"},
                {"code": "en", "name": "English"},
                {"code": "de", "name": "German"},
                {"code": "fr", "name": "French"},
                {"code": "es", "name": "Spanish"},
                {"code": "it", "name": "Italian"},
                {"code": "pl", "name": "Polish"},
                {"code": "pt", "name": "Portuguese"},
                {"code": "ru", "name": "Russian"},
                {"code": "ja", "name": "Japanese"},
                {"code": "ko", "name": "Korean"},
                {"code": "zh", "name": "Chinese"},
            ],
            "defaults": {
                "voice": "ash",
                "tts_model": "gpt-4o-mini-tts",
                "stt_model": "gpt-4o-mini-transcribe",
                "language": "hu",
                "speed": 1.0,
                "temperature": 0.8,
            },
        }

    # Mount static files (must be after API routes)
    if STATIC_DIR.exists():
        app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

        # Serve index.html at root
        @app.get("/", include_in_schema=False)
        async def serve_frontend():
            """Serve the frontend HTML."""
            index_path = STATIC_DIR / "index.html"
            if index_path.exists():
                return FileResponse(str(index_path))
            return {"message": "Frontend not found. API is available at /docs"}

    logger.info(f"FastAPI app created: {title}")

    return app


def run_server(
    host: str = "0.0.0.0",
    port: int = 8000,
    reload: bool = False,
    log_level: str = "info",
) -> None:
    """
    Run the web server.

    Args:
        host: Host to bind to.
        port: Port to listen on.
        reload: Enable auto-reload for development.
        log_level: Uvicorn log level.
    """
    logger.info(f"Starting web server on {host}:{port}")

    app = create_app()

    uvicorn.run(
        app,
        host=host,
        port=port,
        reload=reload,
        log_level=log_level,
    )


# Create default app instance for uvicorn
app = create_app()


if __name__ == "__main__":
    run_server()
