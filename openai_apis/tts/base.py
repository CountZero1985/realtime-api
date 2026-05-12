"""Abstract base class for TTS providers."""
from abc import ABC, abstractmethod
from typing import Optional, AsyncIterator
try:
    import numpy as np
except ImportError:
    np = None


class BaseTTSProvider(ABC):
    """Abstract base class for TTS providers."""

    @abstractmethod
    async def synthesize(self, text: str, voice: Optional[str] = None, speed: Optional[float] = None) -> "np.ndarray":
        """
        Synthesize text to speech as numpy array.

        Args:
            text: Text to synthesize.
            voice: Optional voice (provider-specific).
            speed: Optional speed multiplier.

        Returns:
            Audio data as numpy array.
        """
        ...

    @abstractmethod
    async def synthesize_stream(self, text: str, voice: Optional[str] = None, speed: Optional[float] = None) -> AsyncIterator[bytes]:
        """
        Synthesize text to speech with streaming.

        Args:
            text: Text to synthesize.
            voice: Optional voice (provider-specific).
            speed: Optional speed multiplier.

        Yields:
            Audio chunks as bytes.
        """
        ...
