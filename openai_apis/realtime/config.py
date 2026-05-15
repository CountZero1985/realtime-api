"""Configuration for Realtime API session."""
from dataclasses import dataclass, field
from typing import Optional, Union
from openai_apis._config import BaseConfig, VADConfig


# Supported realtime models
SUPPORTED_REALTIME_MODELS = (
    "gpt-realtime-mini",
    "gpt-4o-mini-realtime-preview-2024-12-17",
    "gpt-4o-realtime-preview",
    "gpt-4o-realtime-preview-2024-12-17",
)

# Supported realtime voices
SUPPORTED_REALTIME_VOICES = ("alloy", "ash", "ballad", "coral", "echo", "sage", "shimmer", "verse")


@dataclass
class RealtimeConfig(BaseConfig):
    """Configuration for Realtime API session.

    Attributes:
        model: Realtime model identifier.
        instructions: System prompt / instructions for the agent.
        voice: Output voice for TTS.
        language: Language code for transcription (ISO-639-1).
        vad: Voice Activity Detection configuration.
        temperature: Model sampling temperature (0.6–1.2).
        max_response_output_tokens: Max output tokens ("inf" or positive integer).
        input_audio_transcription: Whether to request input audio transcription.
        modalities: Enabled modalities (["audio", "text"]).
        tools: Tool definitions (JSON Schema format for function calling).
    """

    # Model settings
    model: str = "gpt-realtime-mini"

    # Session settings
    instructions: Optional[str] = None
    voice: str = "ash"
    language: str = "hu"
    vad: VADConfig = field(default_factory=VADConfig)
    temperature: float = 0.8
    max_response_output_tokens: Union[int, str] = "inf"
    input_audio_transcription: bool = True
    modalities: list[str] = field(default_factory=lambda: ["audio", "text"])
    tools: Union[list[dict], "ToolRegistry"] = field(default_factory=list)

    def __post_init__(self):
        super().__post_init__()

        # Validate model
        if self.model not in SUPPORTED_REALTIME_MODELS:
            raise ValueError(
                f"model must be one of {SUPPORTED_REALTIME_MODELS}, got '{self.model}'"
            )

        # Validate voice
        if self.voice not in SUPPORTED_REALTIME_VOICES:
            raise ValueError(
                f"voice must be one of {SUPPORTED_REALTIME_VOICES}, got '{self.voice}'"
            )

        # Validate temperature (0.6–1.2 per OpenAI Realtime API docs)
        if not (0.6 <= self.temperature <= 1.2):
            raise ValueError(
                f"temperature must be between 0.6 and 1.2, got {self.temperature}"
            )

        # Validate max_response_output_tokens
        if isinstance(self.max_response_output_tokens, str):
            if self.max_response_output_tokens != "inf":
                raise ValueError(
                    f"max_response_output_tokens must be 'inf' or a positive integer, "
                    f"got '{self.max_response_output_tokens}'"
                )
        elif isinstance(self.max_response_output_tokens, int):
            if self.max_response_output_tokens <= 0:
                raise ValueError(
                    f"max_response_output_tokens must be a positive integer, "
                    f"got {self.max_response_output_tokens}"
                )
        else:
            raise ValueError(
                f"max_response_output_tokens must be 'inf' or a positive integer, "
                f"got {self.max_response_output_tokens!r}"
            )

        # Validate modalities
        valid_modalities = {"audio", "text"}
        for m in self.modalities:
            if m not in valid_modalities:
                raise ValueError(
                    f"modalities must only contain 'audio' and/or 'text', got '{m}'"
                )

    def to_session_update(self) -> dict:
        """Convert config to OpenAI Realtime API session.update event format.

        Returns:
            Dict with "type": "session.update" and "session" payload.
        """
        session = {
            "model": self.model,
            "voice": self.voice,
            "modalities": self.modalities,
            "input_audio_format": self.audio_format.encoding,
            "output_audio_format": self.audio_format.encoding,
            "temperature": self.temperature,
            "max_response_output_tokens": self.max_response_output_tokens,
        }

        if self.instructions is not None:
            session["instructions"] = self.instructions

        # Turn detection from VADConfig
        if self.vad.mode == "disabled":
            session["turn_detection"] = None
        elif self.vad.mode == "server_vad":
            session["turn_detection"] = {
                "type": "server_vad",
                "threshold": self.vad.threshold,
                "prefix_padding_ms": self.vad.prefix_padding_ms,
                "silence_duration_ms": self.vad.silence_duration_ms,
            }
        elif self.vad.mode == "semantic_vad":
            session["turn_detection"] = {
                "type": "semantic_vad",
                "eagerness": self.vad.eagerness,
            }

        # Input audio transcription
        if self.input_audio_transcription:
            transcription_config = {"model": "whisper-1"}
            if self.language:
                transcription_config["language"] = self.language
            session["input_audio_transcription"] = transcription_config
        else:
            session["input_audio_transcription"] = None

        # Tools
        if self.tools:
            from openai_apis.realtime.tools import ToolRegistry
            if isinstance(self.tools, ToolRegistry):
                session["tools"] = self.tools.to_api_format()
            else:
                session["tools"] = self.tools

        return {
            "type": "session.update",
            "session": session,
        }
