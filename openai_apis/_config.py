"""Base configuration for all API sessions."""
import os
from dataclasses import dataclass, field
from typing import Optional, Literal


@dataclass(frozen=True)
class AudioFormat:
    """Immutable audio format specification."""
    sample_rate: int = 24000
    channels: int = 1
    dtype: str = "int16"
    encoding: str = "pcm16"

    def __post_init__(self):
        if self.sample_rate <= 0:
            raise ValueError(f"sample_rate must be positive, got {self.sample_rate}")
        if self.channels <= 0:
            raise ValueError(f"channels must be positive, got {self.channels}")
        valid_dtypes = ("int16", "float32")
        if self.dtype not in valid_dtypes:
            raise ValueError(f"dtype must be one of {valid_dtypes}, got '{self.dtype}'")
        valid_encodings = ("pcm16", "g711_ulaw", "g711_alaw")
        if self.encoding not in valid_encodings:
            raise ValueError(f"encoding must be one of {valid_encodings}, got '{self.encoding}'")


@dataclass
class VADConfig:
    """Voice Activity Detection configuration."""
    mode: Literal["server_vad", "semantic_vad", "disabled"] = "server_vad"
    threshold: float = 0.5
    prefix_padding_ms: int = 300
    silence_duration_ms: int = 500
    eagerness: Literal["low", "medium", "high", "auto"] = "auto"

    def __post_init__(self):
        valid_modes = ("server_vad", "semantic_vad", "disabled")
        if self.mode not in valid_modes:
            raise ValueError(f"mode must be one of {valid_modes}, got '{self.mode}'")
        if self.mode == "server_vad":
            if not (0.0 <= self.threshold <= 1.0):
                raise ValueError(f"threshold must be between 0.0 and 1.0, got {self.threshold}")
            if self.prefix_padding_ms < 0:
                raise ValueError(f"prefix_padding_ms must be non-negative, got {self.prefix_padding_ms}")
            if self.silence_duration_ms < 0:
                raise ValueError(f"silence_duration_ms must be non-negative, got {self.silence_duration_ms}")
        if self.mode == "semantic_vad":
            valid_eagerness = ("low", "medium", "high", "auto")
            if self.eagerness not in valid_eagerness:
                raise ValueError(f"eagerness must be one of {valid_eagerness}, got '{self.eagerness}'")


@dataclass
class BaseConfig:
    """Base configuration for all API sessions."""
    api_key: Optional[str] = None
    timeout: float = 30.0
    audio_format: AudioFormat = field(default_factory=AudioFormat)

    def __post_init__(self):
        if self.api_key is None:
            self.api_key = os.environ.get("OPENAI_API_KEY")
        if self.timeout <= 0:
            raise ValueError(f"timeout must be positive, got {self.timeout}")
