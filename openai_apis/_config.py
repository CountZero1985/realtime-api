"""Base configuration for all API sessions."""
import os
from dataclasses import dataclass, field
from typing import Optional, Literal


@dataclass(frozen=True)
class AudioFormat:
    """Immutable audio format specification.

    Defines audio parameters used across all API modules. Frozen dataclass
    ensures format specifications cannot be accidentally modified after creation.

    Args:
        sample_rate: Audio sample rate in Hz. Default: 24000 Hz (OpenAI standard).
        channels: Number of audio channels. Default: 1 (mono).
        dtype: NumPy dtype for audio data. Valid: "int16", "float32". Default: "int16".
        encoding: Audio encoding format. Valid: "pcm16", "g711_ulaw", "g711_alaw". Default: "pcm16".

    Raises:
        ValueError: If any parameter is invalid (negative values, unsupported dtype/encoding).

    Example:
        >>> # Use defaults (24kHz, mono, int16, pcm16)
        >>> fmt = AudioFormat()
        >>>
        >>> # Custom format for higher quality
        >>> fmt = AudioFormat(sample_rate=48000, channels=2, dtype="float32")
    """
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
    """Voice Activity Detection configuration.

    Configures how voice activity is detected in realtime audio streams.
    Supports server-side VAD, semantic VAD, or disabled detection.

    Args:
        mode: VAD mode. Options:
            - "server_vad": Server-side silence detection (uses threshold/padding/silence params)
            - "semantic_vad": Semantic turn detection (uses eagerness param)
            - "disabled": No VAD, continuous processing
        threshold: Activation threshold for server_vad mode (0.0-1.0). Higher = more sensitive.
        prefix_padding_ms: Audio padding before speech starts (server_vad only).
        silence_duration_ms: Silence duration to trigger turn end (server_vad only).
        eagerness: Turn detection eagerness for semantic_vad mode. Options: "low", "medium", "high", "auto".

    Raises:
        ValueError: If parameters are invalid for the selected mode.

    Example:
        >>> # Server-side VAD (default)
        >>> vad = VADConfig(mode="server_vad", threshold=0.7, silence_duration_ms=800)
        >>>
        >>> # Semantic turn detection
        >>> vad = VADConfig(mode="semantic_vad", eagerness="high")
        >>>
        >>> # Disable VAD for continuous processing
        >>> vad = VADConfig(mode="disabled")
    """
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
    """Base configuration for all API sessions.

    Shared configuration inherited by all API-specific config classes
    (TranscriptionConfig, TTSConfig, RealtimeConfig). Provides common
    parameters like API key, timeout, and audio format.

    Args:
        api_key: OpenAI API key. If None, reads from OPENAI_API_KEY environment variable.
        timeout: Request timeout in seconds. Must be positive.
        audio_format: Audio format specification. Defaults to AudioFormat() (24kHz, mono, int16, pcm16).

    Raises:
        ValueError: If timeout is not positive.

    Example:
        >>> # API key from environment
        >>> config = BaseConfig()
        >>>
        >>> # Explicit API key and custom timeout
        >>> config = BaseConfig(api_key="sk-...", timeout=60.0)
        >>>
        >>> # Custom audio format
        >>> fmt = AudioFormat(sample_rate=48000)
        >>> config = BaseConfig(audio_format=fmt)
    """
    api_key: Optional[str] = None
    timeout: float = 30.0
    audio_format: AudioFormat = field(default_factory=AudioFormat)

    def __post_init__(self):
        # Load API key from environment if not provided, but don't validate yet
        # Validation happens in the actual API/Session classes when needed
        if self.api_key is None:
            self.api_key = os.environ.get("OPENAI_API_KEY")
        if self.timeout <= 0:
            raise ValueError(f"timeout must be positive, got {self.timeout}")
