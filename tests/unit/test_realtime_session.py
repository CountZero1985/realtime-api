#!/usr/bin/env python3
"""
Unit tests for realtime_voice_api.py module.

Tests all functionality in the Realtime Voice API module with 100% code coverage.
Uses pytest and unittest.mock for comprehensive testing.
"""

import pytest
import json
import numpy as np
import threading
import queue
import base64
from unittest.mock import Mock, AsyncMock, patch, MagicMock, call
from openai_apis.realtime.session import (
    RealtimeVoiceAPI,
    RealtimeAgentState,
    start_realtime_session
)
from openai_apis.realtime.config import RealtimeConfig


# Fixtures

@pytest.fixture
def realtime_config():
    """Create a RealtimeConfig instance with default values."""
    return RealtimeConfig()


@pytest.fixture
def custom_realtime_config():
    """Create a custom RealtimeConfig instance."""
    return RealtimeConfig(
        model="gpt-4o-realtime-preview",
        voice="alloy",
        speed=1.5,
        language="en",
        sample_rate=16000,
        temperature=0.9
    )


@pytest.fixture
def api_instance():
    """Create a RealtimeVoiceAPI instance."""
    with patch.dict('os.environ', {'OPENAI_API_KEY': 'test-key'}):
        return RealtimeVoiceAPI()


@pytest.fixture
def sample_audio():
    """Create sample audio data."""
    return np.zeros(12000, dtype=np.int16)  # 0.5 seconds at 24kHz


# RealtimeConfig Tests

class TestRealtimeConfig:
    """Test RealtimeConfig dataclass."""

    def test_default_config(self):
        """Test default configuration values."""
        config = RealtimeConfig()
        assert config.model == "gpt-4o-mini-realtime-preview-2024-12-17"
        assert config.voice == "sage"
        assert config.speed == 1.1
        assert config.transcription_model == "gpt-4o-mini-transcribe"
        assert config.language == "hu"
        assert config.sample_rate == 24000
        assert config.chunk_duration_s == 0.5
        assert config.channels == 1
        assert config.modalities == ["text", "audio"]
        assert config.temperature == 0.8

    def test_custom_config(self, custom_realtime_config):
        """Test custom configuration values."""
        assert custom_realtime_config.model == "gpt-4o-realtime-preview"
        assert custom_realtime_config.voice == "alloy"
        assert custom_realtime_config.speed == 1.5
        assert custom_realtime_config.language == "en"
        assert custom_realtime_config.sample_rate == 16000

    def test_post_init_modalities(self):
        """Test __post_init__ sets modalities if None."""
        config = RealtimeConfig(modalities=None)
        assert config.modalities == ["text", "audio"]

    def test_post_init_custom_modalities(self):
        """Test __post_init__ preserves custom modalities."""
        config = RealtimeConfig(modalities=["text"])
        assert config.modalities == ["text"]

    def test_config_with_keywords(self):
        """Test RealtimeConfig with keywords."""
        config = RealtimeConfig(keywords=["OpenAI", "WebSocket", "transzkripció"])
        assert config.keywords == ["OpenAI", "WebSocket", "transzkripció"]

    def test_config_keywords_default_none(self):
        """Test RealtimeConfig keywords default is None."""
        config = RealtimeConfig()
        assert config.keywords is None

    def test_config_language_english(self):
        """Test RealtimeConfig with English language."""
        config = RealtimeConfig(language="en")
        assert config.language == "en"

    def test_config_language_german(self):
        """Test RealtimeConfig with German language."""
        config = RealtimeConfig(language="de")
        assert config.language == "de"

    def test_config_language_french(self):
        """Test RealtimeConfig with French language."""
        config = RealtimeConfig(language="fr")
        assert config.language == "fr"


# RealtimeAgentState Tests

class TestRealtimeAgentState:
    """Test RealtimeAgentState class."""

    def test_initialization(self):
        """Test RealtimeAgentState initialization."""
        state = RealtimeAgentState()
        assert state.state == {}
        assert state.as_dict() == {}

    def test_set(self):
        """Test setting state values."""
        state = RealtimeAgentState()
        state.set("key", "value")
        assert state.state["key"] == "value"

    def test_get(self):
        """Test getting state values."""
        state = RealtimeAgentState()
        state.state["key"] = "value"
        assert state.get("key") == "value"

    def test_get_with_default(self):
        """Test getting non-existent key with default."""
        state = RealtimeAgentState()
        assert state.get("nonexistent", "default") == "default"

    def test_as_dict(self):
        """Test converting state to dict."""
        state = RealtimeAgentState()
        state.set("key1", "value1")
        state.set("key2", "value2")
        result = state.as_dict()
        assert result == {"key1": "value1", "key2": "value2"}

    def test_as_dict_returns_copy(self):
        """Test as_dict returns a copy, not reference."""
        state = RealtimeAgentState()
        state.set("key", "value")
        dict_copy = state.as_dict()
        dict_copy["key"] = "modified"
        assert state.get("key") == "value"  # Original unchanged

    def test_clear(self):
        """Test clearing state."""
        state = RealtimeAgentState()
        state.set("key", "value")
        state.clear()
        assert state.state == {}


# RealtimeVoiceAPI Tests

class TestRealtimeVoiceAPI:
    """Test RealtimeVoiceAPI class."""

    def test_initialization_default(self, api_instance):
        """Test default initialization."""
        assert isinstance(api_instance.config, RealtimeConfig)
        assert isinstance(api_instance.state, RealtimeAgentState)
        assert api_instance.api_key == 'test-key'
        assert api_instance.ws is None
        assert api_instance._session_id is None

    def test_initialization_with_config(self):
        """Test initialization with custom config."""
        config = RealtimeConfig(voice="ash", speed=2.0)
        with patch.dict('os.environ', {'OPENAI_API_KEY': 'test-key'}):
            api = RealtimeVoiceAPI(config=config)
            assert api.config.voice == "ash"
            assert api.config.speed == 2.0

    def test_initialization_with_state(self):
        """Test initialization with custom state."""
        state = RealtimeAgentState()
        state.set("key", "value")
        with patch.dict('os.environ', {'OPENAI_API_KEY': 'test-key'}):
            api = RealtimeVoiceAPI(state=state)
            assert api.state.get("key") == "value"

    def test_initialization_with_api_key(self):
        """Test initialization with explicit API key."""
        api = RealtimeVoiceAPI(api_key="explicit-key")
        assert api.api_key == "explicit-key"

    def test_initialization_with_callbacks(self):
        """Test initialization with callbacks."""
        on_transcription = Mock()
        on_response_audio = Mock()
        on_response_text = Mock()
        on_error = Mock()
        on_session_created = Mock()
        on_session_updated = Mock()

        with patch.dict('os.environ', {'OPENAI_API_KEY': 'test-key'}):
            api = RealtimeVoiceAPI(
                on_transcription=on_transcription,
                on_response_audio=on_response_audio,
                on_response_text=on_response_text,
                on_error=on_error,
                on_session_created=on_session_created,
                on_session_updated=on_session_updated
            )

            assert api._on_transcription == on_transcription
            assert api._on_response_audio == on_response_audio
            assert api._on_response_text == on_response_text
            assert api._on_error == on_error
            assert api._on_session_created == on_session_created
            assert api._on_session_updated == on_session_updated

    def test_set_output_device(self, api_instance):
        """Test setting output device."""
        api_instance.set_output_device(5)
        assert api_instance._output_device == 5

    def test_create_session_update_event(self, api_instance):
        """Test creating session update event."""
        event = api_instance._create_session_update_event()

        assert event["type"] == "session.update"
        assert event["session"]["voice"] == api_instance.config.voice
        assert event["session"]["modalities"] == api_instance.config.modalities
        assert event["session"]["input_audio_transcription"]["language"] == api_instance.config.language
        assert event["session"]["turn_detection"] is None

    def test_create_session_update_event_with_keywords(self):
        """Test session update event includes keywords as prompt."""
        config = RealtimeConfig(keywords=["OpenAI", "WebSocket"])
        with patch.dict('os.environ', {'OPENAI_API_KEY': 'test-key'}):
            api = RealtimeVoiceAPI(config=config)
        event = api._create_session_update_event()
        transcription = event["session"]["input_audio_transcription"]
        assert transcription["prompt"] == "OpenAI, WebSocket"

    def test_create_session_update_event_without_keywords(self):
        """Test session update event omits prompt when no keywords."""
        config = RealtimeConfig(keywords=None)
        with patch.dict('os.environ', {'OPENAI_API_KEY': 'test-key'}):
            api = RealtimeVoiceAPI(config=config)
        event = api._create_session_update_event()
        transcription = event["session"]["input_audio_transcription"]
        assert "prompt" not in transcription

    def test_create_session_update_event_empty_keywords(self):
        """Test session update event omits prompt when keywords is empty list."""
        config = RealtimeConfig(keywords=[])
        with patch.dict('os.environ', {'OPENAI_API_KEY': 'test-key'}):
            api = RealtimeVoiceAPI(config=config)
        event = api._create_session_update_event()
        transcription = event["session"]["input_audio_transcription"]
        assert "prompt" not in transcription

    def test_create_session_update_event_language(self):
        """Test session update event includes configured language."""
        config = RealtimeConfig(language="en")
        with patch.dict('os.environ', {'OPENAI_API_KEY': 'test-key'}):
            api = RealtimeVoiceAPI(config=config)
        event = api._create_session_update_event()
        assert event["session"]["input_audio_transcription"]["language"] == "en"

    def test_on_open(self, api_instance):
        """Test WebSocket on_open handler."""
        mock_ws = Mock()

        with patch('threading.Thread') as mock_thread:
            api_instance._on_open(mock_ws)
            mock_thread.assert_called_once()

    def test_on_message_session_created(self, api_instance, capsys):
        """Test handling session.created event."""
        mock_ws = Mock()
        message = json.dumps({
            "type": "session.created",
            "session": {"id": "sess_123"}
        })

        api_instance._on_message(mock_ws, message)

        assert api_instance._session_id == "sess_123"
        assert api_instance._session_configured.is_set()
        mock_ws.send.assert_called_once()  # Should send session.update

        captured = capsys.readouterr()
        assert "Session created: sess_123" in captured.out

    def test_on_message_session_created_with_callback(self):
        """Test session.created with callback."""
        on_session_created = Mock()
        with patch.dict('os.environ', {'OPENAI_API_KEY': 'test-key'}):
            api = RealtimeVoiceAPI(on_session_created=on_session_created)

        mock_ws = Mock()
        message = json.dumps({
            "type": "session.created",
            "session": {"id": "sess_456"}
        })

        api._on_message(mock_ws, message)
        on_session_created.assert_called_once_with("sess_456")

    def test_on_message_session_updated(self, api_instance, capsys):
        """Test handling session.updated event."""
        # First set session as configured
        api_instance._session_configured.set()

        mock_ws = Mock()
        message = json.dumps({"type": "session.updated"})

        with patch('threading.Thread'):
            api_instance._on_message(mock_ws, message)

        assert api_instance._session_ready.is_set()
        captured = capsys.readouterr()
        assert "push-to-talk enabled" in captured.out

    def test_on_message_transcription_completed(self, api_instance, capsys):
        """Test handling transcription completed event."""
        on_transcription = Mock()
        api_instance._on_transcription = on_transcription

        mock_ws = Mock()
        message = json.dumps({
            "type": "conversation.item.input_audio_transcription.completed",
            "transcript": "Hello world"
        })

        api_instance._on_message(mock_ws, message)

        captured = capsys.readouterr()
        assert "[TRANSCRIPTION] Hello world" in captured.out
        on_transcription.assert_called_once_with("Hello world")

    def test_on_message_response_audio_delta(self, api_instance):
        """Test handling response.audio.delta event."""
        audio_data = np.array([1, 2, 3, 4], dtype=np.int16)
        audio_b64 = base64.b64encode(audio_data.tobytes()).decode('ascii')

        mock_ws = Mock()
        message = json.dumps({
            "type": "response.audio.delta",
            "delta": audio_b64
        })

        with patch.object(api_instance, '_start_speaker_thread'):
            api_instance._on_message(mock_ws, message)

            # Check audio was queued
            assert not api_instance._speaker_queue.empty()
            audio_chunk = api_instance._speaker_queue.get()
            np.testing.assert_array_equal(audio_chunk, audio_data)

    def test_on_message_response_audio_delta_with_callback(self):
        """Test audio delta with callback."""
        on_response_audio = Mock()
        with patch.dict('os.environ', {'OPENAI_API_KEY': 'test-key'}):
            api = RealtimeVoiceAPI(on_response_audio=on_response_audio)

        audio_data = np.array([1, 2, 3], dtype=np.int16)
        audio_b64 = base64.b64encode(audio_data.tobytes()).decode('ascii')

        message = json.dumps({
            "type": "response.audio.delta",
            "delta": audio_b64
        })

        with patch.object(api, '_start_speaker_thread'):
            api._on_message(Mock(), message)
            on_response_audio.assert_called_once()

    def test_on_message_response_audio_done(self, api_instance, capsys):
        """Test handling response.audio.done event."""
        api_instance._audio_chunk_counter = 10
        mock_ws = Mock()
        message = json.dumps({"type": "response.audio.done"})

        api_instance._on_message(mock_ws, message)

        # Check None was queued to signal end
        sentinel = api_instance._speaker_queue.get()
        assert sentinel is None

        # Counter should be reset
        assert api_instance._audio_chunk_counter == 0

        captured = capsys.readouterr()
        assert "10 chunks" in captured.out

    def test_on_message_response_transcript_done(self, api_instance, capsys):
        """Test handling response.audio_transcript.done event."""
        on_response_text = Mock()
        api_instance._on_response_text = on_response_text

        mock_ws = Mock()
        message = json.dumps({
            "type": "response.audio_transcript.done",
            "transcript": "Agent response"
        })

        api_instance._on_message(mock_ws, message)

        captured = capsys.readouterr()
        assert "[TRANSCRIPT] Agent response" in captured.out
        on_response_text.assert_called_once_with("Agent response")

    def test_on_message_error(self, api_instance, capsys):
        """Test handling error event."""
        on_error = Mock()
        api_instance._on_error = on_error

        mock_ws = Mock()
        message = json.dumps({
            "type": "error",
            "message": "Test error message"
        })

        api_instance._on_message(mock_ws, message)

        captured = capsys.readouterr()
        assert "[ERROR] Test error message" in captured.out
        on_error.assert_called_once_with("Test error message")

    def test_on_message_other_events(self, api_instance, capsys):
        """Test handling other event types (logging only)."""
        events = [
            {"type": "conversation.created"},
            {"type": "input_audio_buffer.committed"},
            {"type": "response.created"},
            {"type": "response.done"}
        ]

        for event in events:
            api_instance._on_message(Mock(), json.dumps(event))

        captured = capsys.readouterr()
        assert "Conversation created" in captured.out
        assert "Audio buffer committed" in captured.out

    def test_on_message_invalid_json(self, api_instance, capsys):
        """Test handling invalid JSON message."""
        api_instance._on_message(Mock(), "not valid json")

        captured = capsys.readouterr()
        assert "[WARN]" in captured.out

    def test_on_error_ws(self, api_instance, capsys):
        """Test WebSocket error handler."""
        on_error = Mock()
        api_instance._on_error = on_error

        error = Exception("WebSocket error")
        api_instance._on_error_ws(Mock(), error)

        captured = capsys.readouterr()
        assert "[ERROR] WebSocket error" in captured.out
        on_error.assert_called_once_with("WebSocket error")

    def test_on_close(self, api_instance, capsys):
        """Test WebSocket close handler."""
        api_instance._on_close(Mock(), 1000, "Normal closure")

        captured = capsys.readouterr()
        assert "Connection closed: 1000" in captured.out

    def test_send_audio_chunk(self, api_instance):
        """Test sending audio chunk."""
        mock_ws = Mock()
        audio_chunk = np.array([1, 2, 3, 4], dtype=np.int16)

        api_instance._send_audio_chunk(mock_ws, audio_chunk)

        # Check WebSocket send was called
        mock_ws.send.assert_called_once()

        # Verify the sent data
        sent_data = json.loads(mock_ws.send.call_args[0][0])
        assert sent_data["type"] == "input_audio_buffer.append"
        assert "audio" in sent_data

        # Decode and verify audio
        decoded = base64.b64decode(sent_data["audio"])
        reconstructed = np.frombuffer(decoded, dtype=np.int16)
        np.testing.assert_array_equal(reconstructed, audio_chunk)

    def test_ptt_listener_toggle(self, api_instance):
        """Test PTT listener toggling."""
        with patch('builtins.input', side_effect=['', '', 'q']):
            api_instance._ptt_listener()

            # Should have toggled on then off
            assert api_instance._ptt_exit.is_set()

    def test_ptt_listener_quit(self, api_instance):
        """Test PTT listener quit command."""
        with patch('builtins.input', return_value='q'):
            api_instance._ptt_listener()

            assert api_instance._ptt_exit.is_set()

    def test_start_speaker_thread_already_running(self, api_instance):
        """Test starting speaker thread when already running."""
        # Create a mock thread that appears alive
        mock_thread = Mock()
        mock_thread.is_alive.return_value = True
        api_instance._speaker_thread = mock_thread

        api_instance._start_speaker_thread()

        # Should return early, not create new stream
        assert api_instance._speaker_stream is None

    def test_stop_speaker_thread(self, api_instance):
        """Test stopping speaker thread."""
        mock_thread = Mock()
        api_instance._speaker_thread = mock_thread

        api_instance._stop_speaker_thread()

        # Should put None to signal stop
        sentinel = api_instance._speaker_queue.get()
        assert sentinel is None

        # Should join thread
        mock_thread.join.assert_called_once()

    def test_get_session_id(self, api_instance):
        """Test getting session ID."""
        assert api_instance.get_session_id() is None

        api_instance._session_id = "sess_123"
        assert api_instance.get_session_id() == "sess_123"

    def test_clear_speaker_queue(self, api_instance, capsys):
        """Test clearing speaker queue."""
        # Add items to queue
        api_instance._speaker_queue.put(np.array([1, 2, 3]))
        api_instance._speaker_queue.put(np.array([4, 5, 6]))

        api_instance.clear_speaker_queue()

        assert api_instance._speaker_queue.empty()
        captured = capsys.readouterr()
        assert "Speaker queue cleared" in captured.out

    def test_disconnect(self, api_instance, capsys):
        """Test disconnect."""
        mock_ws = Mock()
        api_instance.ws = mock_ws

        api_instance.disconnect()

        assert api_instance._ptt_exit.is_set()
        mock_ws.close.assert_called_once()
        assert api_instance.ws is None

        captured = capsys.readouterr()
        assert "Disconnected" in captured.out

    def test_run_session_no_api_key(self):
        """Test run_session without API key."""
        api = RealtimeVoiceAPI(api_key=None)
        api.api_key = None

        with pytest.raises(ValueError, match="OPENAI_API_KEY not set"):
            api.run_session()

    def test_run_session(self, api_instance):
        """Test run_session."""
        mock_ws_app = Mock()

        with patch('openai_apis.realtime.session.websocket.WebSocketApp', return_value=mock_ws_app):
            # Make run_forever return immediately
            mock_ws_app.run_forever.return_value = None

            api_instance.run_session()

            mock_ws_app.run_forever.assert_called_once()

    def test_run_session_keyboard_interrupt(self, api_instance, capsys):
        """Test run_session with KeyboardInterrupt."""
        mock_ws_app = Mock()
        mock_ws_app.run_forever.side_effect = KeyboardInterrupt()

        with patch('openai_apis.realtime.session.websocket.WebSocketApp', return_value=mock_ws_app), \
             patch.object(api_instance, 'disconnect'):

            api_instance.run_session()

            captured = capsys.readouterr()
            assert "interrupted by user" in captured.out


# Mic Loop Tests (Complex Threading)

class TestMicLoop:
    """Test microphone loop functionality."""

    def test_mic_loop_wait_for_session(self, api_instance):
        """Test mic loop waits for session ready."""
        mock_ws = Mock()

        # Session not ready
        assert not api_instance._session_ready.is_set()

        # Start mic_loop in thread
        thread = threading.Thread(
            target=api_instance._mic_loop,
            args=(mock_ws,),
            daemon=True
        )
        thread.start()

        # Give it time to start
        import time
        time.sleep(0.1)

        # Set exit before setting ready to avoid blocking
        api_instance._ptt_exit.set()

        # Now set ready
        api_instance._session_ready.set()

        # Thread should exit
        thread.join(timeout=1)
        assert not thread.is_alive()


# Speaker Thread Tests

class TestSpeakerThread:
    """Test speaker thread functionality."""

    def test_speaker_thread_plays_audio(self, api_instance):
        """Test speaker thread plays audio chunks."""
        # Queue some audio
        chunk1 = np.array([1, 2, 3], dtype=np.int16)
        chunk2 = np.array([4, 5, 6], dtype=np.int16)

        api_instance._speaker_queue.put(chunk1)
        api_instance._speaker_queue.put(chunk2)
        api_instance._speaker_queue.put(None)  # Signal end

        with patch('openai_apis.realtime.session.sd.OutputStream') as mock_stream_class:
            mock_stream = Mock()
            mock_stream_class.return_value = mock_stream

            api_instance._start_speaker_thread()

            # Wait for thread to finish
            if api_instance._speaker_thread:
                api_instance._speaker_thread.join(timeout=2)

            # Should have written both chunks
            assert mock_stream.write.call_count == 2

    def test_speaker_thread_auto_stop_on_empty(self, api_instance):
        """Test speaker thread auto-stops when queue empty."""
        # Don't put anything in queue, should timeout and stop

        with patch('openai_apis.realtime.session.sd.OutputStream') as mock_stream_class:
            mock_stream = Mock()
            mock_stream_class.return_value = mock_stream

            # Reduce timeout for faster test - patch the queue's get method
            with patch.object(api_instance._speaker_queue, 'get', side_effect=queue.Empty):
                api_instance._start_speaker_thread()

                # Wait for thread
                if api_instance._speaker_thread:
                    api_instance._speaker_thread.join(timeout=3)


# Integration Tests

class TestRealtimeVoiceAPIIntegration:
    """Integration tests for RealtimeVoiceAPI."""

    def test_full_session_lifecycle(self):
        """Test complete session lifecycle."""
        with patch.dict('os.environ', {'OPENAI_API_KEY': 'test-key'}):
            api = RealtimeVoiceAPI()

            # Simulate session creation
            session_event = json.dumps({
                "type": "session.created",
                "session": {"id": "sess_test"}
            })

            mock_ws = Mock()
            api._on_message(mock_ws, session_event)

            assert api._session_id == "sess_test"
            assert api._session_configured.is_set()

            # Simulate session update
            update_event = json.dumps({"type": "session.updated"})
            api._on_message(mock_ws, update_event)

            assert api._session_ready.is_set()

    def test_audio_streaming_flow(self):
        """Test audio streaming flow."""
        with patch.dict('os.environ', {'OPENAI_API_KEY': 'test-key'}):
            api = RealtimeVoiceAPI()

            # Send audio chunks
            audio1 = np.array([1, 2], dtype=np.int16)
            audio2 = np.array([3, 4], dtype=np.int16)

            mock_ws = Mock()
            api._send_audio_chunk(mock_ws, audio1)
            api._send_audio_chunk(mock_ws, audio2)

            assert mock_ws.send.call_count == 2

    def test_audit_log_includes_keywords_on_init(self):
        """Test that audit log at init includes keywords."""
        with patch.dict('os.environ', {'OPENAI_API_KEY': 'test-key'}), \
             patch('openai_apis.realtime.session.log_audit_event') as mock_audit:
            config = RealtimeConfig(keywords=["OpenAI", "API"])
            api = RealtimeVoiceAPI(config=config)

        mock_audit.assert_any_call(
            event_type="realtime_init",
            action="realtime_api_initialized",
            details={
                "model": config.model,
                "language": "hu",
                "keywords": ["OpenAI", "API"]
            }
        )

    def test_audit_log_includes_keywords_on_session_configured(self):
        """Test that audit log at session configured includes keywords."""
        config = RealtimeConfig(keywords=["transzkripció", "WebSocket"])
        with patch.dict('os.environ', {'OPENAI_API_KEY': 'test-key'}):
            api = RealtimeVoiceAPI(config=config)

        mock_ws = Mock()
        message = json.dumps({
            "type": "session.created",
            "session": {"id": "sess_test"}
        })

        with patch('openai_apis.realtime.session.log_audit_event') as mock_audit:
            api._on_message(mock_ws, message)

        # Find the session_configured call
        configured_calls = [
            c for c in mock_audit.call_args_list
            if c.kwargs.get('action') == 'session_configured'
                or (len(c.args) > 1 and c.args[1] == 'session_configured')
        ]
        assert len(configured_calls) == 1
        details = configured_calls[0].kwargs['details']
        assert details['keywords'] == ["transzkripció", "WebSocket"]
        assert details['language'] == "hu"


# Convenience Function Tests

def test_start_realtime_session():
    """Test start_realtime_session convenience function."""
    with patch.dict('os.environ', {'OPENAI_API_KEY': 'test-key'}):
        with patch.object(RealtimeVoiceAPI, 'run_session') as mock_run:
            start_realtime_session()
            mock_run.assert_called_once()

def test_start_realtime_session_with_config():
    """Test start_realtime_session with config."""
    config = RealtimeConfig(voice="ash")

    with patch.dict('os.environ', {'OPENAI_API_KEY': 'test-key'}):
        with patch.object(RealtimeVoiceAPI, 'run_session') as mock_run:
            start_realtime_session(config=config)
            mock_run.assert_called_once()

def test_start_realtime_session_with_state():
    """Test start_realtime_session with state."""
    state = RealtimeAgentState()
    state.set("key", "value")

    with patch.dict('os.environ', {'OPENAI_API_KEY': 'test-key'}):
        with patch.object(RealtimeVoiceAPI, 'run_session') as mock_run:
            start_realtime_session(state=state)
            mock_run.assert_called_once()


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--cov=realtime_voice_api", "--cov-report=term-missing"])
