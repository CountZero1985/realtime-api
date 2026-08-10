"""Configuration for Realtime API session."""
from dataclasses import dataclass, field
from typing import Optional, Union
from openai_apis._config import BaseConfig, VADConfig


# Supported realtime models.
#
# Source: openai-python `types/realtime/realtime_session_create_request.py`.
# Only models usable with a `type: "realtime"` session are listed here.
#
# NOTE: `gpt-realtime-translate` is deliberately absent. It requires a
# `type: "translation"` session with a different event lifecycle (continuous
# output, no turn semantics), so it cannot be driven by RealtimeConfig.
SUPPORTED_REALTIME_MODELS = (
    # GA models
    "gpt-realtime",
    "gpt-realtime-1.5",
    "gpt-realtime-2",
    "gpt-realtime-2.1",
    "gpt-realtime-2.1-mini",
    "gpt-realtime-mini",
    # Legacy beta preview models
    "gpt-4o-mini-realtime-preview-2024-12-17",
    "gpt-4o-realtime-preview",
    "gpt-4o-realtime-preview-2024-12-17",
)

# Supported realtime voices ("marin" and "cedar" were added with the GA API)
SUPPORTED_REALTIME_VOICES = (
    "alloy", "ash", "ballad", "cedar", "coral", "echo", "marin", "sage", "shimmer", "verse",
)

# Reasoning effort levels for reasoning-capable models (e.g. gpt-realtime-2.x)
SUPPORTED_REASONING_EFFORTS = ("minimal", "low", "medium", "high", "xhigh")

# AudioFormat.encoding -> GA audio format object
_GA_AUDIO_FORMATS = {
    "pcm16": lambda rate: {"type": "audio/pcm", "rate": rate},
    "g711_ulaw": lambda _rate: {"type": "audio/pcmu"},
    "g711_alaw": lambda _rate: {"type": "audio/pcma"},
}


@dataclass
class RealtimeConfig(BaseConfig):
    """Configuration for Realtime API session.

    Attributes:
        model: Realtime model identifier.
        instructions: System prompt / instructions for the agent.
        voice: Output voice for TTS.
        language: Language code for transcription (ISO-639-1).
        vad: Voice Activity Detection configuration.
        temperature: Model sampling temperature (0.6–1.2). **Ignored under the GA
            API** — the GA session object has no `temperature` field. Kept for
            backwards compatibility; it is validated but never sent.
        max_response_output_tokens: Max output tokens ("inf" or positive integer).
            Sent as GA `max_output_tokens`.
        input_audio_transcription: Whether to request input audio transcription.
        modalities: Output modalities. Sent as GA `output_modalities`. The GA API
            accepts `["audio"]` or `["text"]`, **not both** — audio responses
            include a transcript anyway.
        reasoning_effort: Reasoning effort for reasoning-capable models
            (minimal/low/medium/high/xhigh). None omits the field.
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
    modalities: list[str] = field(default_factory=lambda: ["audio"])
    reasoning_effort: Optional[str] = None
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

        # The GA API rejects requesting both at once; audio responses already
        # carry a transcript, so ["audio"] is the useful choice.
        if set(self.modalities) == valid_modalities:
            raise ValueError(
                "modalities cannot contain both 'audio' and 'text' — the GA "
                "Realtime API does not allow it. Use ['audio'] (which also "
                "returns a transcript) or ['text']."
            )
        if not self.modalities:
            raise ValueError("modalities must not be empty")

        # Validate reasoning effort
        if self.reasoning_effort is not None:
            if self.reasoning_effort not in SUPPORTED_REASONING_EFFORTS:
                raise ValueError(
                    f"reasoning_effort must be one of {SUPPORTED_REASONING_EFFORTS}, "
                    f"got '{self.reasoning_effort}'"
                )

    def to_audio_format(self) -> dict:
        """Convert AudioFormat to the GA audio format object.

        Returns:
            Dict such as ``{"type": "audio/pcm", "rate": 24000}``.
        """
        return _GA_AUDIO_FORMATS[self.audio_format.encoding](self.audio_format.sample_rate)

    def to_turn_detection(self) -> Optional[dict]:
        """Convert VADConfig to the GA turn_detection object.

        Returns:
            The turn_detection dict, or None when VAD is disabled. None is
            meaningful on the wire: it tells the server to disable server-side
            turn detection, which is what client-driven turn taking requires.
        """
        if self.vad.mode == "server_vad":
            return {
                "type": "server_vad",
                "threshold": self.vad.threshold,
                "prefix_padding_ms": self.vad.prefix_padding_ms,
                "silence_duration_ms": self.vad.silence_duration_ms,
            }
        if self.vad.mode == "semantic_vad":
            return {
                "type": "semantic_vad",
                "eagerness": self.vad.eagerness,
            }
        return None

    def to_session_update(self) -> dict:
        """Convert config to a GA Realtime API session.update event.

        The GA session object nests audio settings under ``audio.input`` /
        ``audio.output`` instead of the flat beta fields, and renames
        ``modalities`` to ``output_modalities`` and
        ``max_response_output_tokens`` to ``max_output_tokens``. There is no
        ``temperature`` field, so :attr:`temperature` is not sent.

        Returns:
            Dict with "type": "session.update" and "session" payload.
        """
        audio_format = self.to_audio_format()

        audio_input: dict = {
            "format": audio_format,
            # Explicit null disables server VAD — required for client-driven turns.
            "turn_detection": self.to_turn_detection(),
        }

        if self.input_audio_transcription:
            transcription_config = {"model": "whisper-1"}
            if self.language:
                transcription_config["language"] = self.language
            audio_input["transcription"] = transcription_config
        else:
            audio_input["transcription"] = None

        session = {
            "type": "realtime",
            "model": self.model,
            "output_modalities": self.modalities,
            "audio": {
                "input": audio_input,
                "output": {
                    "format": audio_format,
                    "voice": self.voice,
                },
            },
            "max_output_tokens": self.max_response_output_tokens,
        }

        if self.instructions is not None:
            session["instructions"] = self.instructions

        if self.reasoning_effort is not None:
            session["reasoning"] = {"effort": self.reasoning_effort}

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
