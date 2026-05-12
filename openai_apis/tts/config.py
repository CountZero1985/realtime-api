"""Configuration for TTS settings."""
from dataclasses import dataclass
from typing import Optional
from openai_apis._config import BaseConfig


@dataclass
class TTSConfig(BaseConfig):
    """Configuration for TTS settings."""

    # Model settings
    model: str = "gpt-4o-mini-tts"  # or "tts-1", "tts-1-hd"

    # Voice settings
    voice: str = "ash"  # ash, sage, alloy, echo, shimmer
    speed: float = 4.0  # 0.25 - 4.0

    # Audio settings
    output_format: str = "pcm"  # pcm, mp3, opus, aac, flac
    sample_rate: int = 24000  # Only for PCM format
