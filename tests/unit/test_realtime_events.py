"""Unit tests for delta event streaming and callbacks (Issue #20)."""
import pytest
import json
import time
from unittest.mock import Mock, patch, MagicMock
from openai_apis.realtime.events import TranscriptDelta, TranscriptCompleted, ErrorEvent
from openai_apis.realtime import RealtimeSession, RealtimeConfig
# Backward compat alias for tests
RealtimeVoiceAPI = RealtimeSession


@pytest.fixture
def api():
    """Create a RealtimeVoiceAPI instance for testing."""
    with patch.dict('os.environ', {'OPENAI_API_KEY': 'test-key'}):
        return RealtimeVoiceAPI()


class TestTranscriptDeltaDataclass:
    """Test TranscriptDelta typed event object."""

    def test_fields(self):
        event = TranscriptDelta(item_id="item_1", delta="hello", accumulated="hello")
        assert event.item_id == "item_1"
        assert event.delta == "hello"
        assert event.accumulated == "hello"

    def test_empty_delta(self):
        event = TranscriptDelta(item_id="item_1", delta="", accumulated="")
        assert event.delta == ""
        assert event.accumulated == ""


class TestTranscriptCompletedDataclass:
    """Test TranscriptCompleted typed event object."""

    def test_fields(self):
        event = TranscriptCompleted(item_id="item_1", transcript="hello world", duration_ms=1234.5)
        assert event.item_id == "item_1"
        assert event.transcript == "hello world"
        assert event.duration_ms == 1234.5


class TestErrorEventDataclass:
    """Test ErrorEvent typed event object."""

    def test_fields(self):
        event = ErrorEvent(code="invalid_request", message="Bad input")
        assert event.code == "invalid_request"
        assert event.message == "Bad input"


class TestDeltaAccumulation:
    """Test delta text accumulation by item_id."""

    def test_accumulate_single_delta(self, api):
        result = api._accumulate_delta("item_1", "hello")
        assert result == "hello"

    def test_accumulate_multiple_deltas_same_item(self, api):
        api._accumulate_delta("item_1", "hel")
        api._accumulate_delta("item_1", "lo ")
        result = api._accumulate_delta("item_1", "world")
        assert result == "hello world"

    def test_accumulate_multiple_items(self, api):
        api._accumulate_delta("item_1", "hello")
        api._accumulate_delta("item_2", "world")
        assert api._delta_accumulator["item_1"]["accumulated"] == "hello"
        assert api._delta_accumulator["item_2"]["accumulated"] == "world"

    def test_complete_accumulation_returns_duration(self, api):
        api._accumulate_delta("item_1", "hello")
        time.sleep(0.01)  # Small delay to ensure measurable duration
        duration = api._complete_accumulation("item_1")
        assert duration > 0
        assert "item_1" not in api._delta_accumulator

    def test_complete_accumulation_unknown_item(self, api):
        duration = api._complete_accumulation("nonexistent")
        assert duration == 0.0


class TestDeltaEventCallbacks:
    """Test callback invocation for delta events."""

    def test_transcript_delta_callback_for_input_transcription(self, api):
        callback = Mock()
        api.on("transcript.delta", callback)

        message = json.dumps({
            "type": "conversation.item.input_audio_transcription.delta",
            "item_id": "item_1",
            "delta": "hello"
        })
        api._handle_message(message)

        callback.assert_called_once()
        event = callback.call_args[0][0]
        assert isinstance(event, TranscriptDelta)
        assert event.item_id == "item_1"
        assert event.delta == "hello"
        assert event.accumulated == "hello"

    def test_transcript_delta_callback_for_response_transcript(self, api):
        callback = Mock()
        api.on("transcript.delta", callback)

        message = json.dumps({
            "type": "response.output_audio_transcript.delta",
            "item_id": "item_2",
            "delta": "world"
        })
        api._handle_message(message)

        callback.assert_called_once()
        event = callback.call_args[0][0]
        assert isinstance(event, TranscriptDelta)
        assert event.item_id == "item_2"
        assert event.delta == "world"

    def test_transcript_delta_accumulation_across_messages(self, api):
        events_received = []
        api.on("transcript.delta", lambda e: events_received.append(e))

        for delta in ["hel", "lo ", "world"]:
            message = json.dumps({
                "type": "conversation.item.input_audio_transcription.delta",
                "item_id": "item_1",
                "delta": delta
            })
            api._handle_message(message)

        assert len(events_received) == 3
        assert events_received[0].accumulated == "hel"
        assert events_received[1].accumulated == "hello "
        assert events_received[2].accumulated == "hello world"

    def test_transcript_completed_callback(self, api):
        callback = Mock()
        api.on("transcript.input", callback)

        # First send a delta to start accumulation
        delta_msg = json.dumps({
            "type": "conversation.item.input_audio_transcription.delta",
            "item_id": "item_1",
            "delta": "hello"
        })
        api._handle_message(delta_msg)

        # Then send completed
        completed_msg = json.dumps({
            "type": "conversation.item.input_audio_transcription.completed",
            "item_id": "item_1",
            "transcript": "hello world"
        })
        api._handle_message(completed_msg)

        callback.assert_called_once()
        event = callback.call_args[0][0]
        assert isinstance(event, TranscriptCompleted)
        assert event.item_id == "item_1"
        assert event.transcript == "hello world"
        assert event.duration_ms >= 0

    def test_response_transcript_completed_callback(self, api):
        callback = Mock()
        api.on("transcript.output", callback)

        completed_msg = json.dumps({
            "type": "response.output_audio_transcript.done",
            "item_id": "item_1",
            "transcript": "response text"
        })
        api._handle_message(completed_msg)

        callback.assert_called_once()
        event = callback.call_args[0][0]
        assert isinstance(event, TranscriptCompleted)
        assert event.transcript == "response text"

    def test_error_event_callback(self, api):
        callback = Mock()
        api.on("error", callback)

        message = json.dumps({
            "type": "error",
            "error": {
                "code": "rate_limit",
                "message": "Too many requests"
            }
        })
        api._handle_message(message)

        callback.assert_called_once()
        event = callback.call_args[0][0]
        assert isinstance(event, ErrorEvent)
        assert event.code == "rate_limit"
        assert event.message == "Too many requests"

    def test_multiple_callbacks_same_event(self, api):
        cb1 = Mock()
        cb2 = Mock()
        api.on("transcript.delta", cb1)
        api.on("transcript.delta", cb2)

        message = json.dumps({
            "type": "conversation.item.input_audio_transcription.delta",
            "item_id": "item_1",
            "delta": "test"
        })
        api._handle_message(message)

        cb1.assert_called_once()
        cb2.assert_called_once()

    def test_callback_error_does_not_block_others(self, api):
        cb1 = Mock(side_effect=Exception("callback error"))
        cb2 = Mock()
        api.on("transcript.delta", cb1)
        api.on("transcript.delta", cb2)

        message = json.dumps({
            "type": "conversation.item.input_audio_transcription.delta",
            "item_id": "item_1",
            "delta": "test"
        })
        api._handle_message(message)

        cb1.assert_called_once()
        cb2.assert_called_once()  # Should still be called despite cb1 failing


class TestDeltaEventAuditLogging:
    """Test audit logging for delta and completed events."""

    def test_delta_event_audit_logged(self, api):
        message = json.dumps({
            "type": "conversation.item.input_audio_transcription.delta",
            "item_id": "item_1",
            "delta": "hello"
        })
        api._handle_message(message)

        # Check per-session audit log
        events = [e for e in api.audit_log.events
                  if e.event_type == "event.received.conversation.item.input_audio_transcription.delta"]
        assert len(events) >= 1

    def test_response_delta_event_audit_logged(self, api):
        message = json.dumps({
            "type": "response.output_audio_transcript.delta",
            "item_id": "item_2",
            "delta": "world"
        })
        api._handle_message(message)

        # Check per-session audit log
        events = [e for e in api.audit_log.events
                  if e.event_type == "event.received.response.output_audio_transcript.delta"]
        assert len(events) >= 1

    def test_completed_event_audit_logged(self, api):
        message = json.dumps({
            "type": "conversation.item.input_audio_transcription.completed",
            "item_id": "item_1",
            "transcript": "hello world"
        })
        api._handle_message(message)

        # Check per-session audit log for the received event
        events = [e for e in api.audit_log.events
                  if e.event_type == "event.received.conversation.item.input_audio_transcription.completed"]
        assert len(events) >= 1
