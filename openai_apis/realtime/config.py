"""Configuration for Realtime API session."""
from dataclasses import dataclass
from typing import Optional, List
from openai_apis._config import BaseConfig


@dataclass
class RealtimeConfig(BaseConfig):
    """Configuration for Realtime API session.

    Attributes:
        model: Realtime model identifier
        voice: Voice for TTS (sage, ash, alloy, echo, shimmer)
        speed: Speech speed (0.25-4.0)
        transcription_model: Model for speech-to-text transcription
        language: Language code for transcription (ISO-639-1, e.g., "hu", "en")
        keywords: Optional domain-specific keywords for transcription steering.
                  Sent as comma-separated prompt to improve recognition of technical terms.
        sample_rate: Audio sample rate in Hz
        chunk_duration_s: Audio chunk duration in seconds
        channels: Number of audio channels (1 = mono)
        instructions: System instructions for the agent
        modalities: Enabled modalities (["text", "audio"])
        temperature: Sampling temperature
        max_response_output_tokens: Maximum response tokens ("inf" or integer)
    """

    # Model settings
    model: str = "gpt-4o-mini-realtime-preview-2024-12-17"

    # Voice settings
    voice: str = "sage"  # sage, ash, alloy, echo, shimmer
    speed: float = 1.1  # 0.25 - 4.0

    # Transcription settings
    transcription_model: str = "gpt-4o-mini-transcribe"
    language: str = "hu"  # Hungarian by default
    keywords: Optional[List[str]] = None  # Domain-specific keywords for transcription steering

    # Audio settings
    sample_rate: int = 24000
    chunk_duration_s: float = 0.5
    channels: int = 1

    # Session settings
    instructions: str = "segíts a kizárólag magyarul beszélő felhasználónak"
    modalities: List[str] = None  # ["text", "audio"]
    temperature: float = 0.8
    max_response_output_tokens: str = "inf"

    def __post_init__(self):
        super().__post_init__()
        if self.modalities is None:
            self.modalities = ["text", "audio"]
