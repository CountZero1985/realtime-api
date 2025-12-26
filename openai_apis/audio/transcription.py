#!/usr/bin/env python3
"""
Transcription API Module - Stateless Speech-to-Text Endpoint

This module provides a clean, stateless API for speech-to-text transcription
using OpenAI's Whisper models. No conversation history or state management.

Features:
- Stateless audio transcription
- Support for 90+ languages
- Multiple Whisper model options
- Async and sync interfaces
- Direct numpy array or file path input
- Clean error handling

Example usage:
    from transcription_api import TranscriptionAPI, TranscriptionConfig

    # Async usage
    api = TranscriptionAPI()
    transcript = await api.transcribe(audio_data)
    print(transcript)

    # Sync usage
    transcript = api.transcribe_sync(audio_data)
    print(transcript)

    # From file
    transcript = await api.transcribe_file("recording.wav")
    print(transcript)
"""

import asyncio
import os
import tempfile
import wave
import time
import numpy as np
from typing import Optional, Union
from dataclasses import dataclass, asdict
from pathlib import Path
from dotenv import load_dotenv
from openai import AsyncOpenAI, OpenAI
from openai_apis.logging_config import get_logger, set_correlation_id, log_audit_event, log_performance, log_api_call


@dataclass
class TranscriptionConfig:
    """Configuration for transcription settings."""

    # Model settings
    model: str = "gpt-4o-mini-transcribe"  # or "whisper-1"
    language: Optional[str] = "hu"  # ISO-639-1 code, None for auto-detect

    # Audio settings (for validation)
    expected_sample_rate: int = 24000
    expected_channels: int = 1

    # OpenAI API settings
    api_key: Optional[str] = None
    timeout: float = 30.0  # seconds

    # Response settings
    response_format: str = "text"  # text, json, verbose_json, srt, vtt

    # Optional parameters
    temperature: float = 0.0  # 0-1, lower = more deterministic
    prompt: Optional[str] = None  # Context to guide transcription


class TranscriptionAPI:
    """
    Stateless speech-to-text transcription API.

    This class provides simple, stateless transcription of audio to text
    using OpenAI's Whisper models. No conversation history is maintained.

    Attributes:
        config: TranscriptionConfig instance.
        client: AsyncOpenAI client.
        sync_client: OpenAI sync client.
    """

    def __init__(self, config: Optional[TranscriptionConfig] = None):
        """
        Initialize the Transcription API.

        Args:
            config: Optional transcription configuration.
        """
        load_dotenv()

        self.config = config or TranscriptionConfig()
        api_key = self.config.api_key or os.environ.get("OPENAI_API_KEY")

        if not api_key:
            raise ValueError("OPENAI_API_KEY not set in config or environment")

        self.client = AsyncOpenAI(
            api_key=api_key,
            timeout=self.config.timeout
        )
        self.sync_client = OpenAI(
            api_key=api_key,
            timeout=self.config.timeout
        )

        # Logging
        self.logger = get_logger(__name__)
        self.logger.info(
            "TranscriptionAPI initialized",
            extra={"extra_data": {"config": asdict(self.config)}}
        )

        log_audit_event(
            event_type="transcription_init",
            action="transcription_api_initialized",
            details={"model": self.config.model, "language": self.config.language}
        )

    async def transcribe(
        self,
        audio: np.ndarray,
        language: Optional[str] = None,
        prompt: Optional[str] = None
    ) -> str:
        """
        Transcribe audio from numpy array (async).

        Args:
            audio: Audio data as numpy array (int16, mono, 24kHz recommended).
            language: Optional language code (overrides config).
            prompt: Optional context to guide transcription (overrides config).

        Returns:
            Transcribed text.

        Raises:
            ValueError: If audio format is invalid.
            Exception: If transcription fails.
        """
        corr_id = set_correlation_id()
        start_time = time.time()

        # Validate audio
        if not isinstance(audio, np.ndarray):
            raise ValueError("Audio must be a numpy array")

        if audio.dtype != np.int16:
            raise ValueError(f"Audio must be int16, got {audio.dtype}")

        # Ensure 1D array
        if audio.ndim == 2:
            if audio.shape[1] != 1:
                raise ValueError(f"Audio must be mono, got {audio.shape[1]} channels")
            audio = audio.flatten()

        audio_length = len(audio)
        audio_duration = audio_length / self.config.expected_sample_rate
        lang = language or self.config.language

        self.logger.info(
            f"Transcribing audio: {audio_duration:.2f}s",
            extra={"extra_data": {
                "audio_length": audio_length,
                "audio_duration_seconds": audio_duration,
                "language": lang
            }}
        )

        log_audit_event(
            event_type="transcription",
            action="transcription_started",
            details={
                "audio_length": audio_length,
                "audio_duration_seconds": audio_duration,
                "language": lang,
                "model": self.config.model
            }
        )

        # Create temporary WAV file
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_file:
            temp_path = temp_file.name
            try:
                # Write WAV file
                with wave.open(temp_path, 'wb') as wav_file:
                    wav_file.setnchannels(self.config.expected_channels)
                    wav_file.setsampwidth(2)  # 16-bit = 2 bytes
                    wav_file.setframerate(self.config.expected_sample_rate)
                    wav_file.writeframes(audio.tobytes())

                # Transcribe from file
                return await self.transcribe_file(
                    temp_path,
                    language=language,
                    prompt=prompt
                )
            finally:
                # Cleanup temp file
                try:
                    os.unlink(temp_path)
                except Exception:
                    pass

    async def transcribe_file(
        self,
        file_path: Union[str, Path],
        language: Optional[str] = None,
        prompt: Optional[str] = None
    ) -> str:
        """
        Transcribe audio from file (async).

        Args:
            file_path: Path to audio file (WAV, MP3, M4A, etc.).
            language: Optional language code (overrides config).
            prompt: Optional context to guide transcription (overrides config).

        Returns:
            Transcribed text.

        Raises:
            FileNotFoundError: If file doesn't exist.
            Exception: If transcription fails.
        """
        start_time = time.time()
        file_path = Path(file_path)

        if not file_path.exists():
            raise FileNotFoundError(f"Audio file not found: {file_path}")

        file_size = file_path.stat().st_size
        lang = language or self.config.language

        self.logger.info(
            f"Transcribing file: {file_path.name}",
            extra={"extra_data": {
                "file_path": str(file_path),
                "file_size": file_size,
                "language": lang
            }}
        )

        log_audit_event(
            event_type="transcription_file",
            action="file_transcription_started",
            details={
                "file_path": str(file_path),
                "file_size": file_size,
                "language": lang,
                "model": self.config.model
            }
        )

        # Prepare parameters
        params = {
            "model": self.config.model,
            "response_format": self.config.response_format,
            "temperature": self.config.temperature
        }

        # Add optional parameters
        if lang:
            params["language"] = lang

        prmpt = prompt or self.config.prompt
        if prmpt:
            params["prompt"] = prmpt

        # Transcribe
        try:
            api_start = time.time()

            with open(file_path, "rb") as audio_file:
                transcript = await self.client.audio.transcriptions.create(
                    file=audio_file,
                    **params
                )

            api_duration_ms = (time.time() - api_start) * 1000

            # Log API call
            log_api_call(
                api_name="OpenAI",
                method="POST",
                endpoint="/v1/audio/transcriptions",
                status_code=200,
                duration_ms=api_duration_ms
            )

            # Extract text based on response format
            if self.config.response_format == "text":
                result_text = transcript  # Already a string
            elif self.config.response_format == "json":
                result_text = transcript.get("text", "")
            elif self.config.response_format == "verbose_json":
                result_text = transcript.get("text", "")
            else:
                result_text = str(transcript)

            duration_ms = (time.time() - start_time) * 1000

            self.logger.info(
                f"Transcription completed: {len(result_text)} chars",
                extra={"extra_data": {
                    "transcript_length": len(result_text),
                    "duration_ms": duration_ms
                }}
            )

            log_audit_event(
                event_type="transcription_file",
                action="file_transcription_completed",
                details={
                    "file_path": str(file_path),
                    "transcript_length": len(result_text),
                    "duration_ms": duration_ms
                },
                status="success"
            )

            log_performance(
                operation="transcribe_file",
                duration_ms=duration_ms,
                details={
                    "file_size": file_size,
                    "transcript_length": len(result_text)
                }
            )

            return result_text

        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000

            self.logger.error(
                f"Transcription failed: {str(e)}",
                extra={"extra_data": {"error": str(e), "duration_ms": duration_ms}},
                exc_info=True
            )

            log_audit_event(
                event_type="transcription_file",
                action="file_transcription_failed",
                details={"error": str(e), "duration_ms": duration_ms},
                status="error"
            )

            log_api_call(
                api_name="OpenAI",
                method="POST",
                endpoint="/v1/audio/transcriptions",
                error=str(e)
            )

            raise Exception(f"Transcription failed: {e}") from e

    def transcribe_sync(
        self,
        audio: np.ndarray,
        language: Optional[str] = None,
        prompt: Optional[str] = None
    ) -> str:
        """
        Transcribe audio from numpy array (sync).

        Args:
            audio: Audio data as numpy array (int16, mono, 24kHz recommended).
            language: Optional language code (overrides config).
            prompt: Optional context to guide transcription (overrides config).

        Returns:
            Transcribed text.
        """
        return asyncio.run(self.transcribe(audio, language, prompt))

    def transcribe_file_sync(
        self,
        file_path: Union[str, Path],
        language: Optional[str] = None,
        prompt: Optional[str] = None
    ) -> str:
        """
        Transcribe audio from file (sync).

        Args:
            file_path: Path to audio file (WAV, MP3, M4A, etc.).
            language: Optional language code (overrides config).
            prompt: Optional context to guide transcription (overrides config).

        Returns:
            Transcribed text.
        """
        return asyncio.run(self.transcribe_file(file_path, language, prompt))

    async def transcribe_batch(
        self,
        audio_files: list[Union[str, Path]],
        language: Optional[str] = None,
        prompt: Optional[str] = None
    ) -> list[str]:
        """
        Transcribe multiple audio files in parallel (async).

        Args:
            audio_files: List of paths to audio files.
            language: Optional language code (overrides config).
            prompt: Optional context to guide transcription (overrides config).

        Returns:
            List of transcribed texts in same order as input.
        """
        tasks = [
            self.transcribe_file(file_path, language, prompt)
            for file_path in audio_files
        ]
        return await asyncio.gather(*tasks)

    def transcribe_batch_sync(
        self,
        audio_files: list[Union[str, Path]],
        language: Optional[str] = None,
        prompt: Optional[str] = None
    ) -> list[str]:
        """
        Transcribe multiple audio files in parallel (sync).

        Args:
            audio_files: List of paths to audio files.
            language: Optional language code (overrides config).
            prompt: Optional context to guide transcription (overrides config).

        Returns:
            List of transcribed texts in same order as input.
        """
        return asyncio.run(self.transcribe_batch(audio_files, language, prompt))


# Convenience functions
async def transcribe_audio(
    audio: np.ndarray,
    language: str = "hu",
    model: str = "gpt-4o-mini-transcribe"
) -> str:
    """
    Quick transcription of audio array.

    Args:
        audio: Audio data as numpy array (int16, mono, 24kHz).
        language: Language code (default: Hungarian).
        model: Whisper model to use.

    Returns:
        Transcribed text.

    Example:
        >>> import numpy as np
        >>> from transcription_api import transcribe_audio
        >>> audio = np.zeros(24000, dtype=np.int16)  # 1 second silence
        >>> text = await transcribe_audio(audio)
    """
    config = TranscriptionConfig(model=model, language=language)
    api = TranscriptionAPI(config=config)
    return await api.transcribe(audio)


async def transcribe_file(
    file_path: Union[str, Path],
    language: str = "hu",
    model: str = "gpt-4o-mini-transcribe"
) -> str:
    """
    Quick transcription of audio file.

    Args:
        file_path: Path to audio file.
        language: Language code (default: Hungarian).
        model: Whisper model to use.

    Returns:
        Transcribed text.

    Example:
        >>> from transcription_api import transcribe_file
        >>> text = await transcribe_file("recording.wav")
    """
    config = TranscriptionConfig(model=model, language=language)
    api = TranscriptionAPI(config=config)
    return await api.transcribe_file(file_path)


def transcribe_audio_sync(
    audio: np.ndarray,
    language: str = "hu",
    model: str = "gpt-4o-mini-transcribe"
) -> str:
    """Sync version of transcribe_audio."""
    return asyncio.run(transcribe_audio(audio, language, model))


def transcribe_file_sync(
    file_path: Union[str, Path],
    language: str = "hu",
    model: str = "gpt-4o-mini-transcribe"
) -> str:
    """Sync version of transcribe_file."""
    return asyncio.run(transcribe_file(file_path, language, model))


if __name__ == "__main__":
    print("Transcription API module")
    print("\nExample (async):")
    print("  from transcription_api import TranscriptionAPI")
    print("  api = TranscriptionAPI()")
    print("  text = await api.transcribe(audio_array)")
    print("\nExample (sync):")
    print("  from transcription_api import transcribe_audio_sync")
    print("  text = transcribe_audio_sync(audio_array)")
    print("\nExample (file):")
    print("  from transcription_api import transcribe_file_sync")
    print("  text = transcribe_file_sync('recording.wav')")
