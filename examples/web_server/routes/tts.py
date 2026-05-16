"""TTS REST endpoint — POST /api/tts."""

import base64
from typing import Optional
from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field

from openai_apis import TTSRegistry, TTSConfig

router = APIRouter(tags=["tts"])


class TTSRequest(BaseModel):
    """Request body for POST /api/tts."""
    text: str = Field(..., min_length=1, max_length=4096, description="Text to synthesize")
    voice: str = Field("ash", description="TTS voice name")
    speed: float = Field(1.0, ge=0.25, le=4.0, description="Speech speed")
    model: str = Field("gpt-4o-mini-tts", description="TTS model")
    output_format: str = Field("base64", description="'pcm' for raw binary, 'base64' for JSON with base64 audio")
    instructions: Optional[str] = Field(None, description="Voice steering instructions (gpt-4o-mini-tts only)")


class TTSResponse(BaseModel):
    """Response body for POST /api/tts (base64 format)."""
    audio: str
    sample_rate: int = 24000
    channels: int = 1
    format: str = "pcm16"
    text_length: int
    audio_duration_seconds: float


@router.post("/api/tts")
async def synthesize(request: TTSRequest):
    """Synthesize text to speech.

    Returns audio as raw PCM binary (output_format='pcm')
    or base64-encoded JSON (output_format='base64').
    """
    try:
        config = TTSConfig(
            model=request.model,
            voice=request.voice,
            speed=request.speed,
            output_format="pcm",
        )
        tts = TTSRegistry.create(config)
        audio_np = await tts.synthesize(
            request.text,
            voice=request.voice,
            speed=request.speed,
            instructions=request.instructions,
        )
        audio_bytes = audio_np.tobytes()
        audio_duration = len(audio_np) / 24000

        if request.output_format == "pcm":
            return Response(
                content=audio_bytes,
                media_type="audio/pcm",
                headers={
                    "X-Sample-Rate": "24000",
                    "X-Channels": "1",
                    "X-Format": "pcm16",
                    "X-Duration-Seconds": f"{audio_duration:.3f}",
                },
            )
        else:
            audio_b64 = base64.b64encode(audio_bytes).decode("ascii")
            return TTSResponse(
                audio=audio_b64,
                text_length=len(request.text),
                audio_duration_seconds=round(audio_duration, 3),
            )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"TTS synthesis failed: {e}")
