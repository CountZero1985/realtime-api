"""Typed event objects for realtime API streaming events."""

from dataclasses import dataclass


@dataclass
class TranscriptDelta:
    """Partial transcription event (~200-500ms intervals).

    Emitted for both user input transcription deltas
    (conversation.item.input_audio_transcription.delta) and
    assistant response transcript deltas (response.audio_transcript.delta).
    """
    item_id: str
    delta: str
    accumulated: str  # Full text accumulated so far for this item_id


@dataclass
class TranscriptCompleted:
    """Final transcription for a completed speech turn.

    Emitted for conversation.item.input_audio_transcription.completed
    and response.audio_transcript.done events.
    """
    item_id: str
    transcript: str
    duration_ms: float  # Time from first delta to completed event for this item_id


@dataclass
class ErrorEvent:
    """Transcription/realtime error event."""
    code: str
    message: str


@dataclass
class AudioDelta:
    """Output audio chunk from model response.

    Emitted for response.audio.delta events with base64-decoded PCM16 bytes.
    """
    audio_bytes: bytes      # Decoded PCM16 bytes
    item_id: str
    response_id: str


@dataclass
class AudioDone:
    """Output audio stream completion marker.

    Emitted for response.audio.done events when all audio chunks
    for a response item have been delivered.
    """
    item_id: str
    response_id: str
