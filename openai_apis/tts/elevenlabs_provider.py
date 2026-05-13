"""ElevenLabs TTS provider stub."""
from pathlib import Path
from typing import Optional, AsyncIterator, Union

try:
    import numpy as np
except ImportError:
    np = None

from openai_apis.tts.base import BaseTTSProvider

ELEVENLABS_TTS_VOICES: list[str] = ["rachel", "adam", "bella"]


class ElevenLabsTTSProvider(BaseTTSProvider):
    """Stub ElevenLabs TTS provider — raises NotImplementedError on all methods."""

    def __init__(self, config=None):
        """Initialize stub provider. Config is stored but not used."""
        self.config = config

    @property
    def provider_name(self) -> str:
        return "elevenlabs"

    @property
    def supported_voices(self) -> list[str]:
        return list(ELEVENLABS_TTS_VOICES)

    async def synthesize(
        self, text: str, voice: Optional[str] = None, speed: Optional[float] = None
    ) -> "np.ndarray":
        raise NotImplementedError("ElevenLabs provider not yet implemented")

    async def synthesize_stream(
        self, text: str, voice: Optional[str] = None, speed: Optional[float] = None
    ) -> AsyncIterator[bytes]:
        raise NotImplementedError("ElevenLabs provider not yet implemented")
        yield  # pragma: no cover — makes it a generator

    async def synthesize_to_file(
        self,
        text: str,
        file_path: Union[str, Path],
        voice: Optional[str] = None,
        speed: Optional[float] = None,
    ) -> Path:
        raise NotImplementedError("ElevenLabs provider not yet implemented")
