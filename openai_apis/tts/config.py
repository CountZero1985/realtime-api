"""Configuration for TTS settings."""
from dataclasses import dataclass
from typing import Optional
from openai_apis._config import BaseConfig


# Supported output formats for TTS
SUPPORTED_OUTPUT_FORMATS = ("pcm", "mp3", "opus", "aac", "flac", "wav")


@dataclass
class TTSConfig(BaseConfig):
    """Configuration for TTS settings.

    Args:
        provider: Provider identifier (must be registered in the registry).
        model: TTS model name.
        voice: Voice name (validated against provider's supported_voices).
        speed: Speech speed multiplier (0.25–4.0).
        output_format: Audio output format. Supported: pcm, mp3, opus, aac, flac, wav.
        instructions: Voice steering instructions (OpenAI gpt-4o-mini-tts specific).
        language: Language hint (ISO-639-1 code).
        sample_rate: Sample rate in Hz (only relevant for PCM format).

    Raises:
        ValueError: If speed, voice, output_format, or provider is invalid.
    """

    # Provider
    provider: str = "openai"

    # Model settings
    model: str = "gpt-4o-mini-tts"  # or "tts-1", "tts-1-hd"

    # Voice settings
    voice: str = "ash"  # ash, sage, alloy, echo, shimmer, etc.
    speed: float = 1.0  # 0.25 - 4.0 (normal speech speed)
    instructions: Optional[str] = None  # Instruction-based voice steering (gpt-4o-mini-tts only)

    # Audio settings
    output_format: str = "pcm"  # pcm, mp3, opus, aac, flac, wav
    sample_rate: int = 24000  # Only for PCM format

    # Language
    language: str = "hu"  # ISO-639-1 language hint

    def __post_init__(self):
        super().__post_init__()

        # Validate speed: 0.25 ≤ speed ≤ 4.0
        if not (0.25 <= self.speed <= 4.0):
            raise ValueError(
                f"speed must be between 0.25 and 4.0, got {self.speed}"
            )

        # Validate output_format
        if self.output_format not in SUPPORTED_OUTPUT_FORMATS:
            raise ValueError(
                f"output_format must be one of {SUPPORTED_OUTPUT_FORMATS}, got '{self.output_format}'"
            )

        # Validate provider (must be registered)
        from openai_apis.tts._registry import get_provider
        try:
            provider_class = get_provider(self.provider)
        except KeyError:
            raise ValueError(
                f"Unknown provider '{self.provider}'. Provider must be registered in the registry."
            )

        # Validate voice (must be in provider's supported_voices)
        # Instantiate the provider class to access its supported_voices property
        # Use a lightweight check via the class constant instead
        if self.provider == "openai":
            from openai_apis.tts.openai_provider import OPENAI_TTS_VOICES
            if self.voice not in OPENAI_TTS_VOICES:
                raise ValueError(
                    f"Invalid voice '{self.voice}'. Must be one of: {', '.join(OPENAI_TTS_VOICES)}"
                )
