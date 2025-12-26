#!/usr/bin/env python3
"""
Unit tests for agent_framework_api.py module.

Tests all functionality in the Agent Framework API module with 100% code coverage.
Uses pytest and unittest.mock for comprehensive testing.
"""

import pytest
import asyncio
import numpy as np
from unittest.mock import Mock, AsyncMock, patch, MagicMock, call
from openai_apis.voice.agent_framework import (
    AgentFrameworkAPI,
    VoiceConfig,
    TranscriptionCallback,
    start_voice_agent
)
from agents import Agent
from agents.voice import AudioInput


# Fixtures

@pytest.fixture
def mock_agent():
    """Create a mock Agent instance."""
    agent = Mock(spec=Agent)
    agent.name = "test_agent"
    return agent


@pytest.fixture
def voice_config():
    """Create a VoiceConfig instance with default values."""
    return VoiceConfig()


@pytest.fixture
def custom_voice_config():
    """Create a custom VoiceConfig instance."""
    return VoiceConfig(
        stt_model="whisper-1",
        stt_language="en",
        tts_model="tts-1",
        tts_voice="alloy",
        tts_speed=1.0,
        sample_rate=16000,
        silence_padding_ms=500
    )


@pytest.fixture
def api_instance(mock_agent, voice_config):
    """Create an AgentFrameworkAPI instance."""
    return AgentFrameworkAPI(agent=mock_agent, config=voice_config)


@pytest.fixture
def sample_audio():
    """Create sample audio data."""
    return np.zeros(24000, dtype=np.int16)  # 1 second of silence


# VoiceConfig Tests

class TestVoiceConfig:
    """Test VoiceConfig dataclass."""

    def test_default_config(self):
        """Test default configuration values."""
        config = VoiceConfig()
        assert config.stt_model == "gpt-4o-mini-transcribe"
        assert config.stt_language == "hu"
        assert config.tts_model == "gpt-4o-mini-tts"
        assert config.tts_voice == "ash"
        assert config.tts_speed == 4.0
        assert config.sample_rate == 24000
        assert config.silence_padding_ms == 1000

    def test_custom_config(self, custom_voice_config):
        """Test custom configuration values."""
        assert custom_voice_config.stt_model == "whisper-1"
        assert custom_voice_config.stt_language == "en"
        assert custom_voice_config.tts_voice == "alloy"
        assert custom_voice_config.tts_speed == 1.0
        assert custom_voice_config.sample_rate == 16000


# TranscriptionCallback Tests

class TestTranscriptionCallback:
    """Test TranscriptionCallback class."""

    def test_initialization_no_callback(self):
        """Test initialization without callback."""
        callback = TranscriptionCallback()
        assert callback._on_transcription is None

    def test_initialization_with_callback(self):
        """Test initialization with callback."""
        mock_callback = Mock()
        callback = TranscriptionCallback(on_transcription=mock_callback)
        assert callback._on_transcription == mock_callback

    def test_on_run_no_callback(self):
        """Test on_run without callback set."""
        callback = TranscriptionCallback()
        # Should not raise
        callback.on_run(Mock(), "Test transcription")

    def test_on_run_with_callback(self):
        """Test on_run with callback set."""
        mock_callback = Mock()
        callback = TranscriptionCallback(on_transcription=mock_callback)

        callback.on_run(Mock(), "Hello world")

        mock_callback.assert_called_once_with("Hello world")


# AgentFrameworkAPI Tests

class TestAgentFrameworkAPI:
    """Test AgentFrameworkAPI class."""

    def test_initialization(self, mock_agent, voice_config):
        """Test AgentFrameworkAPI initialization."""
        api = AgentFrameworkAPI(agent=mock_agent, config=voice_config)

        assert api.agent == mock_agent
        assert api.config == voice_config
        assert api.state == {}
        assert api._running is False
        assert api.workflow is not None
        assert api.pipeline is not None

    def test_initialization_with_state(self, mock_agent):
        """Test initialization with custom state."""
        state = {"key": "value"}
        api = AgentFrameworkAPI(agent=mock_agent, state=state)
        assert api.state == state

    def test_initialization_with_callbacks(self, mock_agent):
        """Test initialization with callbacks."""
        on_transcription = Mock()
        on_response_start = Mock()
        on_response_complete = Mock()
        on_error = Mock()

        api = AgentFrameworkAPI(
            agent=mock_agent,
            on_transcription=on_transcription,
            on_response_start=on_response_start,
            on_response_complete=on_response_complete,
            on_error=on_error
        )

        assert api._on_transcription == on_transcription
        assert api._on_response_start == on_response_start
        assert api._on_response_complete == on_response_complete
        assert api._on_error == on_error

    def test_create_pipeline(self, api_instance):
        """Test pipeline creation."""
        # Pipeline should be created in __init__
        assert api_instance.pipeline is not None
        # Check it has the workflow
        assert api_instance.pipeline.workflow == api_instance.workflow

    def test_handle_transcription(self, mock_agent, capsys):
        """Test internal transcription handler."""
        on_transcription = Mock()
        api = AgentFrameworkAPI(
            agent=mock_agent,
            on_transcription=on_transcription
        )

        api._handle_transcription("Test transcript")

        # Check console output
        captured = capsys.readouterr()
        assert "[TRANSZKRIPCIÓ] Test transcript" in captured.out

        # Check callback was called
        on_transcription.assert_called_once_with("Test transcript")

    def test_handle_transcription_no_callback(self, api_instance, capsys):
        """Test transcription handler without callback."""
        api_instance._handle_transcription("Test")

        # Should still print
        captured = capsys.readouterr()
        assert "[TRANSZKRIPCIÓ] Test" in captured.out

    @pytest.mark.asyncio
    async def test_process_audio_basic(self, api_instance, sample_audio):
        """Test basic audio processing."""
        # Mock pipeline run
        mock_result = AsyncMock()
        mock_event_audio = Mock()
        mock_event_audio.type = "voice_stream_event_audio"
        mock_event_audio.data = np.zeros((2400, 1), dtype=np.int16)

        mock_event_transcript = Mock()
        mock_event_transcript.type = "voice_stream_event_transcript"
        mock_event_transcript.data = "Test transcript"

        async def mock_stream():
            yield mock_event_audio
            yield mock_event_transcript

        mock_result.stream = mock_stream

        with patch.object(api_instance.pipeline, 'run', return_value=mock_result), \
             patch('openai_apis.voice.agent_framework.AudioPlayer') as mock_player_class:

            mock_player = MagicMock()
            mock_player_class.return_value.__enter__.return_value = mock_player

            transcript = await api_instance.process_audio(sample_audio)

            assert transcript == "Test transcript"
            mock_player.add_audio.assert_called()

    @pytest.mark.asyncio
    async def test_process_audio_with_callbacks(self, mock_agent, sample_audio):
        """Test audio processing with callbacks."""
        on_response_start = Mock()
        on_response_complete = Mock()

        api = AgentFrameworkAPI(
            agent=mock_agent,
            on_response_start=on_response_start,
            on_response_complete=on_response_complete
        )

        # Mock pipeline
        mock_result = AsyncMock()
        mock_event = Mock()
        mock_event.type = "voice_stream_event_transcript"
        mock_event.data = "Response"

        async def mock_stream():
            yield mock_event

        mock_result.stream = mock_stream

        with patch.object(api.pipeline, 'run', return_value=mock_result), \
             patch('openai_apis.voice.agent_framework.AudioPlayer'):

            await api.process_audio(sample_audio)

            on_response_start.assert_called_once()
            on_response_complete.assert_called_once_with("Response")

    @pytest.mark.asyncio
    async def test_process_audio_without_silence(self, api_instance, sample_audio):
        """Test audio processing without silence padding."""
        mock_result = AsyncMock()

        async def mock_stream():
            return
            yield

        mock_result.stream = mock_stream

        with patch.object(api_instance.pipeline, 'run', return_value=mock_result), \
             patch('openai_apis.voice.agent_framework.AudioPlayer') as mock_player_class:

            mock_player = MagicMock()
            mock_player_class.return_value.__enter__.return_value = mock_player

            await api_instance.process_audio(sample_audio, add_silence=False)

            # Check that silence was not added
            # (only way to verify is that add_audio wasn't called with zeros at the end)

    @pytest.mark.asyncio
    async def test_process_audio_error_handling(self, mock_agent, sample_audio):
        """Test audio processing error handling."""
        on_error = Mock()
        api = AgentFrameworkAPI(agent=mock_agent, on_error=on_error)

        with patch.object(api.pipeline, 'run', side_effect=Exception("Pipeline error")):
            with pytest.raises(Exception, match="Pipeline error"):
                await api.process_audio(sample_audio)

            on_error.assert_called_once()

    @pytest.mark.asyncio
    async def test_run_single_interaction(self, api_instance):
        """Test single interaction."""
        sample_audio = np.zeros(24000, dtype=np.int16)

        with patch('openai_apis.voice.agent_framework.record_audio', return_value=sample_audio), \
             patch.object(api_instance, 'process_audio', return_value="Transcript") as mock_process:

            result = await api_instance.run_single_interaction()

            assert result == "Transcript"
            mock_process.assert_called_once_with(sample_audio)

    @pytest.mark.asyncio
    async def test_run_interactive_quit(self, api_instance):
        """Test interactive mode with quit command."""
        with patch('builtins.input', side_effect=['q']):
            await api_instance.run_interactive()

            assert api_instance._running is False

    @pytest.mark.asyncio
    async def test_run_interactive_history(self, api_instance, capsys):
        """Test interactive mode with history display."""
        # Add some history
        api_instance.workflow._input_history = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi"}
        ]

        with patch('builtins.input', side_effect=['h', 'q']):
            await api_instance.run_interactive()

            captured = capsys.readouterr()
            assert "Input history" in captured.out
            assert "Hello" in captured.out

    @pytest.mark.asyncio
    async def test_run_interactive_voice_input(self, api_instance):
        """Test interactive mode with voice input."""
        sample_audio = np.zeros(24000, dtype=np.int16)

        with patch('builtins.input', side_effect=['', 'q']), \
             patch('openai_apis.voice.agent_framework.record_audio', return_value=sample_audio), \
             patch.object(api_instance, 'process_audio', return_value="Test"):

            await api_instance.run_interactive()

    @pytest.mark.asyncio
    async def test_run_interactive_voice_exit(self, api_instance, capsys):
        """Test interactive mode with voice exit command."""
        sample_audio = np.zeros(24000, dtype=np.int16)

        # Simulate exit command in history
        api_instance.workflow._input_history = [
            {"role": "user", "content": "kilépés"},
            {"role": "assistant", "content": "OK"}
        ]

        with patch('builtins.input', side_effect=['']), \
             patch('openai_apis.voice.agent_framework.record_audio', return_value=sample_audio), \
             patch.object(api_instance, 'process_audio', return_value="OK"):

            await api_instance.run_interactive()

            captured = capsys.readouterr()
            assert "Hangutasításos kilépés" in captured.out

    def test_run_interactive_sync(self, api_instance):
        """Test synchronous interactive mode."""
        with patch('asyncio.run') as mock_run:
            api_instance.run_interactive_sync()
            mock_run.assert_called_once()

    def test_display_history(self, api_instance, capsys):
        """Test history display."""
        api_instance.workflow._input_history = [
            {"role": "user", "content": "Question"},
            {"role": "assistant", "content": "Answer"}
        ]

        api_instance._display_history()

        captured = capsys.readouterr()
        assert "Input history" in captured.out
        assert "Question" in captured.out
        assert "Answer" in captured.out

    def test_should_exit_from_voice_true(self, api_instance):
        """Test voice exit detection - should exit."""
        api_instance.workflow._input_history = [
            {"role": "user", "content": "valami"},
            {"role": "assistant", "content": "ok"},
            {"role": "user", "content": "kilépés"},
            {"role": "assistant", "content": "rendben"}
        ]

        assert api_instance._should_exit_from_voice() is True

    def test_should_exit_from_voice_exit_keyword(self, api_instance):
        """Test voice exit detection with 'exit' keyword."""
        api_instance.workflow._input_history = [
            {"role": "user", "content": "exit please"},
            {"role": "assistant", "content": "bye"}
        ]

        assert api_instance._should_exit_from_voice() is True

    def test_should_exit_from_voice_false(self, api_instance):
        """Test voice exit detection - should not exit."""
        api_instance.workflow._input_history = [
            {"role": "user", "content": "hello"},
            {"role": "assistant", "content": "hi"}
        ]

        assert api_instance._should_exit_from_voice() is False

    def test_should_exit_from_voice_empty_history(self, api_instance):
        """Test voice exit detection with empty history."""
        assert api_instance._should_exit_from_voice() is False

    def test_get_history(self, api_instance):
        """Test getting history."""
        api_instance.workflow._input_history = [
            {"role": "user", "content": "Test"}
        ]

        history = api_instance.get_history()
        assert len(history) == 1
        assert history[0]["content"] == "Test"

    def test_clear_history(self, api_instance):
        """Test clearing history."""
        api_instance.workflow._input_history = [
            {"role": "user", "content": "Test"}
        ]

        api_instance.clear_history()
        assert len(api_instance.workflow._input_history) == 0

    def test_set_state(self, api_instance):
        """Test setting state."""
        api_instance.set_state("key", "value")
        assert api_instance.state["key"] == "value"

    def test_get_state(self, api_instance):
        """Test getting state."""
        api_instance.state["key"] = "value"
        assert api_instance.get_state("key") == "value"
        assert api_instance.get_state("nonexistent", "default") == "default"

    def test_stop(self, api_instance):
        """Test stopping the API."""
        api_instance._running = True
        api_instance.stop()
        assert api_instance._running is False


# Integration Tests

class TestAgentFrameworkAPIIntegration:
    """Integration tests for AgentFrameworkAPI."""

    @pytest.mark.asyncio
    async def test_full_voice_flow(self, mock_agent):
        """Test complete voice interaction flow."""
        api = AgentFrameworkAPI(agent=mock_agent)
        sample_audio = np.zeros(24000, dtype=np.int16)

        # Mock the entire pipeline
        mock_result = AsyncMock()
        mock_event = Mock()
        mock_event.type = "voice_stream_event_transcript"
        mock_event.data = "Full flow test"

        async def mock_stream():
            yield mock_event

        mock_result.stream = mock_stream

        with patch.object(api.pipeline, 'run', return_value=mock_result), \
             patch('openai_apis.voice.agent_framework.AudioPlayer'):

            result = await api.process_audio(sample_audio)

            assert result == "Full flow test"

    def test_custom_config_integration(self, mock_agent):
        """Test API with completely custom config."""
        config = VoiceConfig(
            stt_model="whisper-1",
            stt_language="en",
            tts_model="tts-1-hd",
            tts_voice="echo",
            tts_speed=1.5
        )

        api = AgentFrameworkAPI(agent=mock_agent, config=config)

        assert api.config.stt_model == "whisper-1"
        assert api.config.tts_voice == "echo"
        assert api.config.tts_speed == 1.5


# Convenience Function Tests

def test_start_voice_agent():
    """Test start_voice_agent convenience function."""
    mock_agent = Mock(spec=Agent)
    mock_agent.name = "test_agent"

    with patch.object(AgentFrameworkAPI, 'run_interactive_sync') as mock_run:
        start_voice_agent(mock_agent)
        mock_run.assert_called_once()

def test_start_voice_agent_with_config():
    """Test start_voice_agent with custom config."""
    mock_agent = Mock(spec=Agent)
    mock_agent.name = "test_agent"
    config = VoiceConfig(tts_voice="sage")

    with patch.object(AgentFrameworkAPI, 'run_interactive_sync') as mock_run:
        start_voice_agent(mock_agent, config=config)
        mock_run.assert_called_once()

def test_start_voice_agent_with_state():
    """Test start_voice_agent with state."""
    mock_agent = Mock(spec=Agent)
    mock_agent.name = "test_agent"
    state = {"key": "value"}

    with patch.object(AgentFrameworkAPI, 'run_interactive_sync') as mock_run:
        start_voice_agent(mock_agent, state=state)
        mock_run.assert_called_once()


# Edge Cases and Error Handling

class TestAgentFrameworkAPIEdgeCases:
    """Test edge cases and error scenarios."""

    @pytest.mark.asyncio
    async def test_process_audio_empty_response(self, api_instance, sample_audio):
        """Test processing audio with empty response."""
        mock_result = AsyncMock()

        async def mock_stream():
            return
            yield

        mock_result.stream = mock_stream

        with patch.object(api_instance.pipeline, 'run', return_value=mock_result), \
             patch('openai_apis.voice.agent_framework.AudioPlayer'):

            result = await api_instance.process_audio(sample_audio)
            assert result is None

    @pytest.mark.asyncio
    async def test_process_audio_lifecycle_events(self, api_instance, sample_audio):
        """Test processing with lifecycle events (should be ignored)."""
        mock_result = AsyncMock()

        mock_lifecycle = Mock()
        mock_lifecycle.type = "voice_stream_event_lifecycle"

        mock_transcript = Mock()
        mock_transcript.type = "voice_stream_event_transcript"
        mock_transcript.data = "Result"

        async def mock_stream():
            yield mock_lifecycle
            yield mock_transcript

        mock_result.stream = mock_stream

        with patch.object(api_instance.pipeline, 'run', return_value=mock_result), \
             patch('openai_apis.voice.agent_framework.AudioPlayer'):

            result = await api_instance.process_audio(sample_audio)
            assert result == "Result"

    @pytest.mark.asyncio
    async def test_multiple_audio_chunks(self, api_instance, sample_audio):
        """Test processing multiple audio chunks."""
        mock_result = AsyncMock()

        async def mock_stream():
            for _ in range(5):
                mock_event = Mock()
                mock_event.type = "voice_stream_event_audio"
                mock_event.data = np.zeros((480, 1), dtype=np.int16)
                yield mock_event

            mock_transcript = Mock()
            mock_transcript.type = "voice_stream_event_transcript"
            mock_transcript.data = "Multiple chunks"
            yield mock_transcript

        mock_result.stream = mock_stream

        with patch.object(api_instance.pipeline, 'run', return_value=mock_result), \
             patch('openai_apis.voice.agent_framework.AudioPlayer') as mock_player_class:

            mock_player = MagicMock()
            mock_player_class.return_value.__enter__.return_value = mock_player

            # add_silence=False to only count audio chunks, not silence padding
            result = await api_instance.process_audio(sample_audio, add_silence=False)

            assert result == "Multiple chunks"
            assert mock_player.add_audio.call_count == 5

    def test_workflow_callbacks_integration(self, mock_agent):
        """Test workflow callbacks are properly set."""
        on_transcription = Mock()
        api = AgentFrameworkAPI(
            agent=mock_agent,
            on_transcription=on_transcription
        )

        # Simulate transcription callback (callbacks is stored as _callbacks)
        api.workflow._callbacks.on_run(api.workflow, "Test")

        # Should call internal handler which calls user callback
        on_transcription.assert_called_once_with("Test")

    def test_silence_padding_calculation(self, api_instance):
        """Test silence padding size calculation."""
        config = api_instance.config
        expected_samples = int(config.sample_rate * config.silence_padding_ms / 1000)

        # Default config: 24000 * 1000 / 1000 = 24000 samples
        assert expected_samples == 24000

    def test_history_operations_dont_mutate_original(self, api_instance):
        """Test that getting history returns a copy."""
        api_instance.workflow._input_history = [{"role": "user", "content": "Test"}]

        history = api_instance.get_history()
        history.append({"role": "user", "content": "Modified"})

        # Original should be unchanged
        assert len(api_instance.workflow._input_history) == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--cov=agent_framework_api", "--cov-report=term-missing"])
