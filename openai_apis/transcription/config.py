"""Configuration for transcription settings."""
from dataclasses import dataclass, field
from typing import Optional
from openai_apis._config import BaseConfig, VADConfig


# Valid transcription models
SUPPORTED_TRANSCRIPTION_MODELS = (
    "gpt-realtime-whisper",
    "gpt-4o-mini-transcribe",
    "gpt-4o-transcribe",
    "whisper-1",
)

# ISO 639-1 language codes (subset of most common codes supported by OpenAI Whisper)
SUPPORTED_LANGUAGES = (
    "af", "am", "ar", "as", "az", "ba", "be", "bg", "bn", "bo", "br", "bs",
    "ca", "cs", "cy", "da", "de", "el", "en", "es", "et", "eu", "fa", "fi",
    "fo", "fr", "gl", "gu", "ha", "haw", "he", "hi", "hr", "ht", "hu", "hy",
    "id", "is", "it", "ja", "jw", "ka", "kk", "km", "kn", "ko", "la", "lb",
    "ln", "lo", "lt", "lv", "mg", "mi", "mk", "ml", "mn", "mr", "ms", "mt",
    "my", "ne", "nl", "nn", "no", "oc", "pa", "pl", "ps", "pt", "ro", "ru",
    "sa", "sd", "si", "sk", "sl", "sn", "so", "sq", "sr", "su", "sv", "sw",
    "ta", "te", "tg", "th", "tk", "tl", "tr", "tt", "uk", "ur", "uz", "vi",
    "yi", "yo", "yue", "zh",
)


@dataclass
class TranscriptionConfig(BaseConfig):
    """Configuration for transcription settings.

    Args:
        model: Transcription model name. Valid: gpt-realtime-whisper, gpt-4o-mini-transcribe,
            gpt-4o-transcribe, whisper-1.
        language: ISO 639-1 language code. Default: "hu" (Hungarian). None for auto-detect.
        vad: Voice Activity Detection configuration.
        keywords: Keyword list for steering transcription accuracy.
        prompt: Context prompt to guide transcription accuracy.
        include_logprobs: Whether to request log probabilities from the API.

    Raises:
        ValueError: If model is not in SUPPORTED_TRANSCRIPTION_MODELS.
        ValueError: If language is not a valid ISO 639-1 code (when not None).
    """

    # Model settings
    model: str = "gpt-realtime-whisper"
    language: Optional[str] = "hu"  # ISO 639-1 code, None for auto-detect

    # VAD settings
    vad: VADConfig = field(default_factory=VADConfig)

    # Keyword steering
    keywords: list[str] = field(default_factory=list)

    # Context prompt
    prompt: Optional[str] = None

    # Log probabilities
    include_logprobs: bool = False

    def __post_init__(self):
        super().__post_init__()

        # Validate model
        if self.model not in SUPPORTED_TRANSCRIPTION_MODELS:
            raise ValueError(
                f"model must be one of {SUPPORTED_TRANSCRIPTION_MODELS}, got '{self.model}'"
            )

        # Validate language (ISO 639-1) — None is allowed for auto-detect
        if self.language is not None and self.language not in SUPPORTED_LANGUAGES:
            raise ValueError(
                f"language must be a valid ISO 639-1 code or None, got '{self.language}'"
            )
