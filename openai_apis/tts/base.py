"""Abstract base class for TTS providers."""
import asyncio
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional, AsyncIterator, Union

try:
    import numpy as np
except ImportError:
    np = None


class BaseTTSProvider(ABC):
    """Abstract base class for TTS providers.

    Defines the interface that all TTS providers must implement.
    Provides concrete sync wrapper methods that delegate to the async
    abstract methods, so subclasses only need to implement async versions.
    """

    @abstractmethod
    async def synthesize(
        self, text: str, voice: Optional[str] = None, speed: Optional[float] = None
    ) -> "np.ndarray":
        """Synthesize text to speech as numpy array.

        Args:
            text: Text to synthesize.
            voice: Optional voice override (provider-specific).
            speed: Optional speed multiplier override.

        Returns:
            Audio data as numpy array.
        """
        ...

    @abstractmethod
    async def synthesize_stream(
        self,
        text: str,
        voice: Optional[str] = None,
        speed: Optional[float] = None,
        chunk_size: Optional[int] = None,
    ) -> AsyncIterator[bytes]:
        """Synthesize text to speech with streaming.

        Args:
            text: Text to synthesize.
            voice: Optional voice override (provider-specific).
            speed: Optional speed multiplier override.
            chunk_size: Optional chunk size override (bytes). If None, uses config default.

        Yields:
            Audio chunks as bytes.
        """
        ...

    @abstractmethod
    async def synthesize_to_file(
        self,
        text: str,
        file_path: Union[str, Path],
        voice: Optional[str] = None,
        speed: Optional[float] = None,
    ) -> Path:
        """Synthesize text to speech and save to file.

        Args:
            text: Text to synthesize.
            file_path: Output file path.
            voice: Optional voice override (provider-specific).
            speed: Optional speed multiplier override.

        Returns:
            Path to the saved audio file.
        """
        ...

    @property
    @abstractmethod
    def supported_voices(self) -> list[str]:
        """List of voices supported by this provider."""
        ...

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Provider identifier (e.g. 'openai', 'elevenlabs')."""
        ...

    # Concrete sync wrappers

    def synthesize_sync(
        self, text: str, voice: Optional[str] = None, speed: Optional[float] = None
    ) -> "np.ndarray":
        """Synchronous wrapper for synthesize().

        Args:
            text: Text to synthesize.
            voice: Optional voice override (provider-specific).
            speed: Optional speed multiplier override.

        Returns:
            Audio data as numpy array.
        """
        return asyncio.run(self.synthesize(text, voice, speed))

    def synthesize_to_file_sync(
        self,
        text: str,
        file_path: Union[str, Path],
        voice: Optional[str] = None,
        speed: Optional[float] = None,
    ) -> Path:
        """Synchronous wrapper for synthesize_to_file().

        Args:
            text: Text to synthesize.
            file_path: Output file path.
            voice: Optional voice override (provider-specific).
            speed: Optional speed multiplier override.

        Returns:
            Path to the saved audio file.
        """
        return asyncio.run(self.synthesize_to_file(text, file_path, voice, speed))
