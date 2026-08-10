"""Transcription (STT) REST endpoint."""

import tempfile
import os
from typing import Optional
from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from pydantic import BaseModel

from openai_apis.transcription import TranscriptionAPI, TranscriptionConfig
from openai_apis._logging import get_logger

router = APIRouter(prefix="/api", tags=["transcription"])
logger = get_logger(__name__)


class TranscriptionResponse(BaseModel):
    """Response model for transcription endpoint."""
    text: str
    language: Optional[str] = None
    model: str


@router.post("/transcribe", response_model=TranscriptionResponse)
async def transcribe_audio(
    file: UploadFile = File(..., description="Audio file (WAV, MP3, M4A, etc.)"),
    model: str = Form("gpt-4o-mini-transcribe", description="Model: gpt-4o-mini-transcribe or whisper-1"),
    language: Optional[str] = Form("hu", description="Language code (ISO-639-1), e.g., 'hu', 'en'"),
    temperature: float = Form(0.0, description="Accepted for compatibility; not currently applied"),
    prompt: Optional[str] = Form(None, description="Optional context to guide transcription"),
) -> TranscriptionResponse:
    """
    Transcribe audio file to text.

    Accepts audio file upload and returns transcribed text.
    Supports WAV, MP3, M4A, and other common audio formats.
    """
    logger.info(f"Transcription request: file={file.filename}, model={model}, language={language}")

    # Validate file
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided")

    # Save uploaded file to temp location
    suffix = os.path.splitext(file.filename)[1] or ".wav"

    try:
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as temp_file:
            content = await file.read()
            temp_file.write(content)
            temp_path = temp_file.name

        # Create config and API.
        # TranscriptionConfig has no temperature field, so passing the form
        # value raised TypeError and turned every request into a 500.
        config = TranscriptionConfig(
            model=model,
            language=language if language else None,
            prompt=prompt,
        )

        api = TranscriptionAPI(config=config)

        # Transcribe
        text = await api.transcribe_file(temp_path)

        logger.info(f"Transcription completed: {len(text)} chars")

        return TranscriptionResponse(
            text=text,
            language=language,
            model=model,
        )

    except ValueError as e:
        logger.error(f"Transcription validation error: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Transcription failed: {e}")
        raise HTTPException(status_code=500, detail=f"Transcription failed: {str(e)}")
    finally:
        # Cleanup temp file
        try:
            if 'temp_path' in locals():
                os.unlink(temp_path)
        except Exception:
            pass
