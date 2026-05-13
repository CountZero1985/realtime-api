#!/usr/bin/env python3
"""
TTS API Module - Stateless Text-to-Speech Endpoint

This module provides a clean, stateless API for text-to-speech synthesis
using OpenAI's TTS models. No conversation history or state management.

Features:
- Stateless text-to-speech synthesis
- 13 voice options (alloy, ash, ballad, coral, echo, fable, nova, onyx, sage, shimmer, verse, marin, cedar)
- Speed control (0.25 - 4.0)
- Instruction-based voice steering (gpt-4o-mini-tts only)
- Multiple output formats (numpy array, file, streaming)
- Configurable streaming chunk size with re-chunking buffer
- Backpressure control for streaming via asyncio.Event
- Async and sync interfaces
- Comprehensive audit logging for streaming
- Clean error handling with TTSSynthesisError

Requirements:
- Requires numpy for audio processing (install with: pip install openai-apis[audio])

Example usage:
    from openai_apis.tts import OpenAITTSProvider, TTSConfig

    # Async usage
    api = OpenAITTSProvider()
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
try:
    import numpy as np
except ImportError:
    np = None
from typing import Optional, Union, AsyncIterator
from dataclasses import asdict
from pathlib import Path
from dotenv import load_dotenv
from openai import AsyncOpenAI, OpenAI
from openai_apis._logging import get_logger, set_correlation_id, log_audit_event, log_performance, log_api_call
from openai_apis.tts.config import TTSConfig
from openai_apis.tts.base import BaseTTSProvider


class TTSSynthesisError(Exception):
    """Raised when TTS synthesis fails due to API or processing errors."""
    pass


# OpenAI TTS supported voices
OPENAI_TTS_VOICES: list[str] = [
    "alloy", "ash", "ballad", "coral", "echo",
    "fable", "nova", "onyx", "sage", "shimmer",
    "verse", "marin", "cedar",
]


class OpenAITTSProvider(BaseTTSProvider):
    """
    Stateless text-to-speech synthesis API using OpenAI.

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
            "OpenAITTSProvider initialized",
            extra={"extra_data": {"config": asdict(self.config)}}
        )

        log_audit_event(
            event_type="tts_init",
            action="tts_api_initialized",
            details={"model": self.config.model, "voice": self.config.voice}
        )

    @property
    def supported_voices(self) -> list[str]:
        """List of voices supported by OpenAI TTS."""
        return list(OPENAI_TTS_VOICES)

    @property
    def provider_name(self) -> str:
        """Provider identifier."""
        return "openai"

    async def synthesize(
        self,
        text: str,
        voice: Optional[str] = None,
        speed: Optional[float] = None,
        instructions: Optional[str] = None
    ) -> "np.ndarray":
        """
        Synthesize text to speech as numpy array (async).

        Args:
            text: Text to synthesize.
            voice: Optional voice (overrides config).
            speed: Optional speed (overrides config).
            instructions: Optional instruction-based voice steering (overrides config).

        Returns:
            Audio data as numpy array (int16, mono, 24kHz for PCM).

        Raises:
            ValueError: If text is empty or parameters are invalid.
            TTSSynthesisError: If synthesis fails.
        """
        if np is None:
            raise ImportError(
                "numpy is required for this feature. "
                "Install it with: pip install openai-apis[audio]"
            )

        if not text or not text.strip():
            raise ValueError("Text cannot be empty")

        # Get audio bytes
        audio_bytes = await self._synthesize_bytes(text, voice, speed, instructions)

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
        speed: Optional[float] = None,
        instructions: Optional[str] = None
    ) -> Path:
        """
        Synthesize text to speech and save to file (async).

        Args:
            text: Text to synthesize.
            file_path: Output file path (extension determines format).
            voice: Optional voice (overrides config).
            speed: Optional speed (overrides config).
            instructions: Optional instruction-based voice steering (overrides config).

        Returns:
            Path to saved file.

        Raises:
            ValueError: If text is empty or parameters are invalid.
            TTSSynthesisError: If synthesis fails.
        """
        if not text or not text.strip():
            raise ValueError("Text cannot be empty")

        file_path = Path(file_path)

        # Get audio bytes
        audio_bytes = await self._synthesize_bytes(text, voice, speed, instructions)

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
        speed: Optional[float] = None,
        instructions: Optional[str] = None,
        chunk_size: Optional[int] = None,
        backpressure_event: Optional[asyncio.Event] = None,
    ) -> AsyncIterator[bytes]:
        """
        Synthesize text to speech with streaming (async).

        Args:
            text: Text to synthesize.
            voice: Optional voice (overrides config).
            speed: Optional speed (overrides config).
            instructions: Optional instruction-based voice steering (overrides config).
            chunk_size: Optional chunk size override (bytes). If None, uses config default.
                API response bytes are buffered and yielded in uniform chunks of this size.
            backpressure_event: Optional asyncio.Event for backpressure control.
                When provided, the generator awaits this event before yielding each chunk.
                Consumer should set() the event to allow streaming, and clear() to pause.
                The event must be set initially, or the generator will block.

        Yields:
            Audio chunks as bytes.

        Raises:
            ValueError: If text is empty or parameters are invalid.
            TTSSynthesisError: If synthesis fails.
        """
        if not text or not text.strip():
            raise ValueError("Text cannot be empty")

        # Prepare parameters
        voice_param = voice or self.config.voice
        speed_param = speed or self.config.speed
        effective_chunk_size = chunk_size or self.config.chunk_size

        # Validate parameters
        self._validate_voice(voice_param)
        self._validate_speed(speed_param)

        corr_id = set_correlation_id()
        start_time = time.time()

        self.logger.info(
            f"Streaming synthesis: {len(text)} chars",
            extra={"extra_data": {"text_length": len(text), "voice": voice_param, "model": self.config.model, "chunk_size": effective_chunk_size}}
        )

        log_audit_event(
            event_type="tts",
            action="stream_synthesis_started",
            details={"text_length": len(text), "voice": voice_param, "speed": speed_param, "model": self.config.model, "chunk_size": effective_chunk_size}
        )

        total_bytes = 0
        chunk_count = 0
        try:
            # Build API call kwargs
            api_kwargs = {
                "model": self.config.model,
                "voice": voice_param,
                "speed": speed_param,
                "input": text,
                "response_format": self.config.output_format,
            }

            # Add instructions for gpt-4o-mini-tts
            instr = instructions or self.config.instructions
            if instr and self.config.model == "gpt-4o-mini-tts":
                api_kwargs["instructions"] = instr

            # Buffer for re-chunking API response to uniform chunk sizes
            buffer = bytearray()

            async with self.client.audio.speech.with_streaming_response.create(**api_kwargs) as response:
                async for raw_chunk in response.iter_bytes():
                    buffer.extend(raw_chunk)

                    # Yield chunks of exactly effective_chunk_size (except final chunk)
                    while len(buffer) >= effective_chunk_size:
                        out_chunk = bytes(buffer[:effective_chunk_size])
                        del buffer[:effective_chunk_size]
                        total_bytes += len(out_chunk)
                        chunk_count += 1

                        # Apply backpressure if event provided
                        if backpressure_event is not None:
                            await backpressure_event.wait()

                        yield out_chunk

                # Yield remaining bytes in buffer (final partial chunk)
                if buffer:
                    final_chunk = bytes(buffer)
                    total_bytes += len(final_chunk)
                    chunk_count += 1

                    # Apply backpressure if event provided
                    if backpressure_event is not None:
                        await backpressure_event.wait()

                    yield final_chunk

            duration_ms = (time.time() - start_time) * 1000
            log_audit_event(
                event_type="tts",
                action="stream_synthesis_completed",
                details={"text_length": len(text), "total_bytes": total_bytes, "chunk_count": chunk_count, "chunk_size": effective_chunk_size, "duration_ms": duration_ms},
                status="success"
            )
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            log_audit_event(
                event_type="tts",
                action="stream_synthesis_failed",
                details={"error": str(e), "duration_ms": duration_ms},
                status="error"
            )
            raise TTSSynthesisError(f"Streaming TTS synthesis failed: {e}") from e

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
        speed: Optional[float] = None,
        instructions: Optional[str] = None
    ) -> bytes:
        """
        Internal method to synthesize text and return raw bytes.

        Args:
            text: Text to synthesize.
            voice: Optional voice (overrides config).
            speed: Optional speed (overrides config).
            instructions: Optional instruction-based voice steering (overrides config).

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

            # Build API call kwargs
            api_kwargs = {
                "model": self.config.model,
                "voice": voice_param,
                "speed": speed_param,
                "input": text,
                "response_format": self.config.output_format,
            }

            # Add instructions for gpt-4o-mini-tts
            instr = instructions or self.config.instructions
            if instr and self.config.model == "gpt-4o-mini-tts":
                api_kwargs["instructions"] = instr

            response = await self.client.audio.speech.create(**api_kwargs)

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

            raise TTSSynthesisError(f"TTS synthesis failed: {e}") from e

    def _validate_voice(self, voice: str) -> None:
        """Validate voice parameter."""
        if voice not in OPENAI_TTS_VOICES:
            raise ValueError(
                f"Invalid voice '{voice}'. Must be one of: {', '.join(OPENAI_TTS_VOICES)}"
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
        >>> from openai_apis.tts import synthesize_text
        >>> audio = await synthesize_text("Szia! Hogy vagy?")
    """
    config = TTSConfig(model=model, voice=voice, speed=speed, output_format="pcm")
    api = OpenAITTSProvider(config=config)
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
        >>> from openai_apis.tts import synthesize_to_file
        >>> path = await synthesize_to_file("Hello!", "output.wav")
    """
    config = TTSConfig(model=model, voice=voice, speed=speed, output_format="pcm")
    api = OpenAITTSProvider(config=config)
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
    print("  from openai_apis.tts import OpenAITTSProvider")
    print("  api = OpenAITTSProvider()")
    print("  audio = await api.synthesize('Hello world!')")
    print("\nExample (sync):")
    print("  from openai_apis.tts import synthesize_text_sync")
    print("  audio = synthesize_text_sync('Hello world!')")
    print("\nExample (file):")
    print("  from openai_apis.tts import synthesize_to_file_sync")
    print("  path = synthesize_to_file_sync('Hello!', 'output.wav')")
