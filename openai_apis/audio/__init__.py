"""Audio processing APIs for transcription and synthesis."""

from openai_apis.audio.transcription import TranscriptionAPI, TranscriptionConfig
from openai_apis.audio.synthesis import TTSAPI, TTSConfig

__all__ = [
    "TranscriptionAPI",
    "TranscriptionConfig",
    "TTSAPI",
    "TTSConfig",
]
