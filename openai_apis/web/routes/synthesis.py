"""TTS (Text-to-Speech) REST endpoint."""

import base64
from typing import Optional, Literal
from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field

from openai_apis.tts import TTSAPI, TTSConfig
from openai_apis._logging import get_logger

router = APIRouter(prefix="/api", tags=["synthesis"])
logger = get_logger(__name__)

VALID_VOICES = ["ash", "sage", "alloy", "echo", "shimmer"]
VALID_MODELS = ["gpt-4o-mini-tts", "tts-1", "tts-1-hd"]


class SynthesisRequest(BaseModel):
    """Request model for TTS synthesis."""
    text: str = Field(..., min_length=1, max_length=4096, description="Text to synthesize")
    voice: Literal["ash", "sage", "alloy", "echo", "shimmer"] = Field(
        "ash", description="Voice to use"
    )
    speed: float = Field(1.0, ge=0.25, le=4.0, description="Speech speed (0.25 - 4.0)")
    model: Literal["gpt-4o-mini-tts", "tts-1", "tts-1-hd"] = Field(
        "gpt-4o-mini-tts", description="TTS model"
    )
    output_format: Literal["pcm", "base64"] = Field(
        "base64", description="Output format: 'pcm' for raw binary, 'base64' for JSON"
    )


class SynthesisResponse(BaseModel):
    """Response model for TTS synthesis (base64 format)."""
    audio: str  # base64-encoded PCM audio
    sample_rate: int = 24000
    channels: int = 1
    format: str = "pcm16"
    text_length: int
    audio_duration_seconds: float


@router.post("/synthesize")
async def synthesize_text(request: SynthesisRequest):
    """
    Synthesize text to speech.

    Returns audio as either:
    - Raw PCM binary (output_format='pcm')
    - Base64-encoded JSON (output_format='base64')

    Audio format: 24kHz, mono, 16-bit PCM.
    """
    logger.info(
        f"TTS request: text_len={len(request.text)}, voice={request.voice}, "
        f"speed={request.speed}, model={request.model}"
    )

    try:
        # Create config and API
        config = TTSConfig(
            model=request.model,
            voice=request.voice,
            speed=request.speed,
            output_format="pcm",
            sample_rate=24000,
        )

        api = TTSAPI(config=config)

        # Synthesize
        audio_np = await api.synthesize(request.text)

        # Calculate duration
        audio_bytes = audio_np.tobytes()
        audio_duration = len(audio_np) / 24000

        logger.info(f"TTS completed: {len(audio_bytes)} bytes, {audio_duration:.2f}s")

        if request.output_format == "pcm":
            # Return raw PCM binary
            return Response(
                content=audio_bytes,
                media_type="audio/pcm",
                headers={
                    "X-Sample-Rate": "24000",
                    "X-Channels": "1",
                    "X-Format": "pcm16",
                    "X-Duration-Seconds": f"{audio_duration:.3f}",
                }
            )
        else:
            # Return base64-encoded JSON
            audio_b64 = base64.b64encode(audio_bytes).decode("ascii")
            return SynthesisResponse(
                audio=audio_b64,
                sample_rate=24000,
                channels=1,
                format="pcm16",
                text_length=len(request.text),
                audio_duration_seconds=audio_duration,
            )

    except ValueError as e:
        logger.error(f"TTS validation error: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"TTS failed: {e}")
        raise HTTPException(status_code=500, detail=f"TTS synthesis failed: {str(e)}")


@router.get("/voices")
async def get_voices():
    """Get available TTS voices."""
    return {
        "voices": VALID_VOICES,
        "default": "ash",
    }


@router.get("/tts-models")
async def get_tts_models():
    """Get available TTS models."""
    return {
        "models": VALID_MODELS,
        "default": "gpt-4o-mini-tts",
    }
