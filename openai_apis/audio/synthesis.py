#!/usr/bin/env python3
"""
TTS API Module - Stateless Text-to-Speech Endpoint

This module provides a clean, stateless API for text-to-speech synthesis
using OpenAI's TTS models. No conversation history or state management.

Features:
- Stateless text-to-speech synthesis
- Multiple voice options (ash, sage, alloy, echo, shimmer)
- Speed control (0.25 - 4.0)
- Multiple output formats (numpy array, file, streaming)
- Async and sync interfaces
- Clean error handling

Example usage:
    from tts_api import TTSAPI, TTSConfig

    # Async usage
    api = TTSAPI()
    audio = await api.synthesize("Szia! Hogy vagy?")
    # audio is numpy array ready for playback

    # Sync usage
    audio = api.synthesize_sync("Hello world!")

    # Save to file
    await api.synthesize_to_file("Text to save", "output.mp3")
"""

import asyncio
import os
import io
import wave
import time
import numpy as np
from typing import Optional, Union, AsyncIterator
from dataclasses import dataclass, asdict
from pathlib import Path
from dotenv import load_dotenv
from openai import AsyncOpenAI, OpenAI
from openai_apis.logging_config import get_logger, set_correlation_id, log_audit_event, log_performance, log_api_call


@dataclass
class TTSConfig:
    """Configuration for TTS settings."""

    # Model settings
    model: str = "gpt-4o-mini-tts"  # or "tts-1", "tts-1-hd"

    # Voice settings
    voice: str = "ash"  # ash, sage, alloy, echo, shimmer
    speed: float = 4.0  # 0.25 - 4.0

    # Audio settings
    output_format: str = "pcm"  # pcm, mp3, opus, aac, flac
    sample_rate: int = 24000  # Only for PCM format

    # OpenAI API settings
    api_key: Optional[str] = None
    timeout: float = 30.0  # seconds


class TTSAPI:
    """
    Stateless text-to-speech synthesis API.

    This class provides simple, stateless synthesis of text to speech
    using OpenAI's TTS models. No conversation history is maintained.

    Attributes:
        config: TTSConfig instance.
        client: AsyncOpenAI client.
        sync_client: OpenAI sync client.
    """

    def __init__(self, config: Optional[TTSConfig] = None):
        """
        Initialize the TTS API.

        Args:
            config: Optional TTS configuration.
        """
        load_dotenv()

        self.config = config or TTSConfig()
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
            "TTSAPI initialized",
            extra={"extra_data": {"config": asdict(self.config)}}
        )

        log_audit_event(
            event_type="tts_init",
            action="tts_api_initialized",
            details={"model": self.config.model, "voice": self.config.voice}
        )

    async def synthesize(
        self,
        text: str,
        voice: Optional[str] = None,
        speed: Optional[float] = None
    ) -> np.ndarray:
        """
        Synthesize text to speech as numpy array (async).

        Args:
            text: Text to synthesize.
            voice: Optional voice (overrides config).
            speed: Optional speed (overrides config).

        Returns:
            Audio data as numpy array (int16, mono, 24kHz for PCM).

        Raises:
            ValueError: If text is empty or parameters are invalid.
            Exception: If synthesis fails.
        """
        if not text or not text.strip():
            raise ValueError("Text cannot be empty")

        # Get audio bytes
        audio_bytes = await self._synthesize_bytes(text, voice, speed)

        # Convert to numpy array
        if self.config.output_format == "pcm":
            # PCM is raw audio, directly convert to int16
            audio_np = np.frombuffer(audio_bytes, dtype=np.int16)
            return audio_np
        else:
            # For other formats (mp3, opus, etc.), return as-is
            # User needs to decode with appropriate library
            raise NotImplementedError(
                f"Format {self.config.output_format} requires external decoder. "
                f"Use synthesize_to_file() instead or set output_format='pcm'"
            )

    async def synthesize_to_file(
        self,
        text: str,
        file_path: Union[str, Path],
        voice: Optional[str] = None,
        speed: Optional[float] = None
    ) -> Path:
        """
        Synthesize text to speech and save to file (async).

        Args:
            text: Text to synthesize.
            file_path: Output file path (extension determines format).
            voice: Optional voice (overrides config).
            speed: Optional speed (overrides config).

        Returns:
            Path to saved file.

        Raises:
            ValueError: If text is empty or parameters are invalid.
            Exception: If synthesis fails.
        """
        if not text or not text.strip():
            raise ValueError("Text cannot be empty")

        file_path = Path(file_path)

        # Get audio bytes
        audio_bytes = await self._synthesize_bytes(text, voice, speed)

        # Save to file
        if self.config.output_format == "pcm":
            # For PCM, create WAV file
            with wave.open(str(file_path), 'wb') as wav_file:
                wav_file.setnchannels(1)  # Mono
                wav_file.setsampwidth(2)  # 16-bit
                wav_file.setframerate(self.config.sample_rate)
                wav_file.writeframes(audio_bytes)
        else:
            # For other formats, write directly
            with open(file_path, 'wb') as f:
                f.write(audio_bytes)

        return file_path

    async def synthesize_stream(
        self,
        text: str,
        voice: Optional[str] = None,
        speed: Optional[float] = None
    ) -> AsyncIterator[bytes]:
        """
        Synthesize text to speech with streaming (async).

        Args:
            text: Text to synthesize.
            voice: Optional voice (overrides config).
            speed: Optional speed (overrides config).

        Yields:
            Audio chunks as bytes.

        Raises:
            ValueError: If text is empty or parameters are invalid.
            Exception: If synthesis fails.
        """
        if not text or not text.strip():
            raise ValueError("Text cannot be empty")

        # Prepare parameters
        voice_param = voice or self.config.voice
        speed_param = speed or self.config.speed

        # Validate parameters
        self._validate_voice(voice_param)
        self._validate_speed(speed_param)

        try:
            async with self.client.audio.speech.with_streaming_response.create(
                model=self.config.model,
                voice=voice_param,
                speed=speed_param,
                input=text,
                response_format=self.config.output_format
            ) as response:
                async for chunk in response.iter_bytes():
                    yield chunk

        except Exception as e:
            raise Exception(f"TTS synthesis failed: {e}") from e

    def synthesize_sync(
        self,
        text: str,
        voice: Optional[str] = None,
        speed: Optional[float] = None
    ) -> np.ndarray:
        """
        Synthesize text to speech as numpy array (sync).

        Args:
            text: Text to synthesize.
            voice: Optional voice (overrides config).
            speed: Optional speed (overrides config).

        Returns:
            Audio data as numpy array (int16, mono, 24kHz for PCM).
        """
        return asyncio.run(self.synthesize(text, voice, speed))

    def synthesize_to_file_sync(
        self,
        text: str,
        file_path: Union[str, Path],
        voice: Optional[str] = None,
        speed: Optional[float] = None
    ) -> Path:
        """
        Synthesize text to speech and save to file (sync).

        Args:
            text: Text to synthesize.
            file_path: Output file path.
            voice: Optional voice (overrides config).
            speed: Optional speed (overrides config).

        Returns:
            Path to saved file.
        """
        return asyncio.run(self.synthesize_to_file(text, file_path, voice, speed))

    async def synthesize_batch(
        self,
        texts: list[str],
        voice: Optional[str] = None,
        speed: Optional[float] = None
    ) -> list[np.ndarray]:
        """
        Synthesize multiple texts in parallel (async).

        Args:
            texts: List of texts to synthesize.
            voice: Optional voice (overrides config).
            speed: Optional speed (overrides config).

        Returns:
            List of audio arrays in same order as input.
        """
        tasks = [
            self.synthesize(text, voice, speed)
            for text in texts
        ]
        return await asyncio.gather(*tasks)

    def synthesize_batch_sync(
        self,
        texts: list[str],
        voice: Optional[str] = None,
        speed: Optional[float] = None
    ) -> list[np.ndarray]:
        """
        Synthesize multiple texts in parallel (sync).

        Args:
            texts: List of texts to synthesize.
            voice: Optional voice (overrides config).
            speed: Optional speed (overrides config).

        Returns:
            List of audio arrays in same order as input.
        """
        return asyncio.run(self.synthesize_batch(texts, voice, speed))

    # Internal methods

    async def _synthesize_bytes(
        self,
        text: str,
        voice: Optional[str] = None,
        speed: Optional[float] = None
    ) -> bytes:
        """
        Internal method to synthesize text and return raw bytes.

        Args:
            text: Text to synthesize.
            voice: Optional voice (overrides config).
            speed: Optional speed (overrides config).

        Returns:
            Raw audio bytes.
        """
        corr_id = set_correlation_id()
        start_time = time.time()

        # Prepare parameters
        voice_param = voice or self.config.voice
        speed_param = speed or self.config.speed

        # Validate parameters
        self._validate_voice(voice_param)
        self._validate_speed(speed_param)

        self.logger.info(
            f"Synthesizing text: {len(text)} chars",
            extra={"extra_data": {
                "text_length": len(text),
                "voice": voice_param,
                "speed": speed_param,
                "model": self.config.model
            }}
        )

        log_audit_event(
            event_type="tts",
            action="synthesis_started",
            details={
                "text_length": len(text),
                "voice": voice_param,
                "speed": speed_param,
                "model": self.config.model
            }
        )

        try:
            api_start = time.time()

            response = await self.client.audio.speech.create(
                model=self.config.model,
                voice=voice_param,
                speed=speed_param,
                input=text,
                response_format=self.config.output_format
            )

            # Read all bytes
            audio_bytes = response.read()

            api_duration_ms = (time.time() - api_start) * 1000
            total_duration_ms = (time.time() - start_time) * 1000

            # Log API call
            log_api_call(
                api_name="OpenAI",
                method="POST",
                endpoint="/v1/audio/speech",
                status_code=200,
                duration_ms=api_duration_ms
            )

            audio_length = len(audio_bytes)

            # Calculate audio duration if PCM format
            if self.config.output_format == "pcm":
                audio_duration_seconds = audio_length / (self.config.sample_rate * 2)  # 2 bytes per sample
            else:
                audio_duration_seconds = None

            self.logger.info(
                f"Synthesis completed: {audio_length} bytes",
                extra={"extra_data": {
                    "audio_length": audio_length,
                    "audio_duration_seconds": audio_duration_seconds,
                    "duration_ms": total_duration_ms
                }}
            )

            log_audit_event(
                event_type="tts",
                action="synthesis_completed",
                details={
                    "text_length": len(text),
                    "audio_length": audio_length,
                    "audio_duration_seconds": audio_duration_seconds,
                    "duration_ms": total_duration_ms,
                    "voice": voice_param
                },
                status="success"
            )

            log_performance(
                operation="synthesize_text",
                duration_ms=total_duration_ms,
                details={
                    "text_length": len(text),
                    "audio_length": audio_length,
                    "audio_duration_seconds": audio_duration_seconds
                }
            )

            return audio_bytes

        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000

            self.logger.error(
                f"TTS synthesis failed: {str(e)}",
                extra={"extra_data": {"error": str(e), "duration_ms": duration_ms}},
                exc_info=True
            )

            log_audit_event(
                event_type="tts",
                action="synthesis_failed",
                details={"error": str(e), "duration_ms": duration_ms},
                status="error"
            )

            log_api_call(
                api_name="OpenAI",
                method="POST",
                endpoint="/v1/audio/speech",
                error=str(e)
            )

            raise Exception(f"TTS synthesis failed: {e}") from e

    def _validate_voice(self, voice: str) -> None:
        """Validate voice parameter."""
        valid_voices = ["ash", "sage", "alloy", "echo", "shimmer"]
        if voice not in valid_voices:
            raise ValueError(
                f"Invalid voice '{voice}'. Must be one of: {', '.join(valid_voices)}"
            )

    def _validate_speed(self, speed: float) -> None:
        """Validate speed parameter."""
        if not 0.25 <= speed <= 4.0:
            raise ValueError(f"Speed must be between 0.25 and 4.0, got {speed}")


# Convenience functions
async def synthesize_text(
    text: str,
    voice: str = "ash",
    speed: float = 4.0,
    model: str = "gpt-4o-mini-tts"
) -> np.ndarray:
    """
    Quick synthesis of text to audio array.

    Args:
        text: Text to synthesize.
        voice: Voice to use (default: ash).
        speed: Speech speed (default: 4.0).
        model: TTS model to use.

    Returns:
        Audio data as numpy array (int16, mono, 24kHz).

    Example:
        >>> from tts_api import synthesize_text
        >>> audio = await synthesize_text("Szia! Hogy vagy?")
    """
    config = TTSConfig(model=model, voice=voice, speed=speed, output_format="pcm")
    api = TTSAPI(config=config)
    return await api.synthesize(text)


async def synthesize_to_file(
    text: str,
    file_path: Union[str, Path],
    voice: str = "ash",
    speed: float = 4.0,
    model: str = "gpt-4o-mini-tts"
) -> Path:
    """
    Quick synthesis of text to file.

    Args:
        text: Text to synthesize.
        file_path: Output file path.
        voice: Voice to use (default: ash).
        speed: Speech speed (default: 4.0).
        model: TTS model to use.

    Returns:
        Path to saved file.

    Example:
        >>> from tts_api import synthesize_to_file
        >>> path = await synthesize_to_file("Hello!", "output.wav")
    """
    config = TTSConfig(model=model, voice=voice, speed=speed, output_format="pcm")
    api = TTSAPI(config=config)
    return await api.synthesize_to_file(text, file_path)


def synthesize_text_sync(
    text: str,
    voice: str = "ash",
    speed: float = 4.0,
    model: str = "gpt-4o-mini-tts"
) -> np.ndarray:
    """Sync version of synthesize_text."""
    return asyncio.run(synthesize_text(text, voice, speed, model))


def synthesize_to_file_sync(
    text: str,
    file_path: Union[str, Path],
    voice: str = "ash",
    speed: float = 4.0,
    model: str = "gpt-4o-mini-tts"
) -> Path:
    """Sync version of synthesize_to_file."""
    return asyncio.run(synthesize_to_file(text, file_path, voice, speed, model))


if __name__ == "__main__":
    print("TTS API module")
    print("\nExample (async):")
    print("  from tts_api import TTSAPI")
    print("  api = TTSAPI()")
    print("  audio = await api.synthesize('Hello world!')")
    print("\nExample (sync):")
    print("  from tts_api import synthesize_text_sync")
    print("  audio = synthesize_text_sync('Hello world!')")
    print("\nExample (file):")
    print("  from tts_api import synthesize_to_file_sync")
    print("  path = synthesize_to_file_sync('Hello!', 'output.wav')")
