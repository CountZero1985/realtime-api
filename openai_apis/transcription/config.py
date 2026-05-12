"""Configuration for transcription settings."""
from dataclasses import dataclass
from typing import Optional
from openai_apis._config import BaseConfig


@dataclass
class TranscriptionConfig(BaseConfig):
    """Configuration for transcription settings."""

    # Model settings
    model: str = "gpt-4o-mini-transcribe"  # or "whisper-1"
    language: Optional[str] = "hu"  # ISO-639-1 code, None for auto-detect

    # Audio settings (for validation)
    expected_sample_rate: int = 24000
    expected_channels: int = 1

    # Response settings
    response_format: str = "text"  # text, json, verbose_json, srt, vtt

    # Optional parameters
    temperature: float = 0.0  # 0-1, lower = more deterministic
    prompt: Optional[str] = None  # Context to guide transcription
