#!/usr/bin/env python3
"""
Comprehensive unit tests for OpenAITTSProvider.

Tests all new functionality added in issue #12:
- Instruction-based voice steering for gpt-4o-mini-tts
- Full 13-voice list support
- Audit logging on streaming calls
- TTSSynthesisError exception handling
- Registry integration
"""

import pytest
import asyncio
import time
import numpy as np
from pathlib import Path
from unittest.mock import Mock, AsyncMock, patch, MagicMock, call

from openai_apis.tts.openai_provider import (
    OpenAITTSProvider,
    TTSSynthesisError,
    OPENAI_TTS_VOICES,
)
from openai_apis.tts.config import TTSConfig
from openai_apis.tts._registry import get_provider, register_provider


# Fixtures

@pytest.fixture
def mock_env_key(monkeypatch):
    """Set OPENAI_API_KEY in environment."""
    monkeypatch.setenv("OPENAI_API_KEY", "test-key-12345")


@pytest.fixture
def tts_provider(mock_env_key):
    """Create an OpenAITTSProvider instance."""
    return OpenAITTSProvider()


@pytest.fixture
def gpt4o_mini_tts_provider(mock_env_key):
    """Create a provider configured with gpt-4o-mini-tts."""
    config = TTSConfig(
        model="gpt-4o-mini-tts",
        voice="ash",
        speed=1.0,
        instructions="Speak in a warm, friendly tone"
    )
    return OpenAITTSProvider(config=config)


# Test Classes

class TestOpenAITTSProviderInit:
    """Test OpenAITTSProvider initialization."""

    def test_init_with_env_key(self, mock_env_key):
        """Provider initializes with env var API key."""
        provider = OpenAITTSProvider()
        assert provider.client is not None
        assert provider.sync_client is not None

    def test_init_with_config_key(self):
        """Provider initializes with explicit API key."""
        config = TTSConfig(api_key="explicit-test-key")
        provider = OpenAITTSProvider(config=config)
        assert provider.client is not None

    def test_init_no_key_raises(self, monkeypatch):
        """ValueError when no API key available."""
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        with patch('openai_apis.tts.openai_provider.load_dotenv'):
            with pytest.raises(ValueError, match="OPENAI_API_KEY not set"):
                OpenAITTSProvider(config=TTSConfig(api_key=None))

    def test_init_audit_event_logged(self, mock_env_key):
        """Audit event fired on initialization."""
        with patch('openai_apis.tts.openai_provider.log_audit_event') as mock_audit:
            provider = OpenAITTSProvider()
            mock_audit.assert_called_once()
            call_args = mock_audit.call_args
            assert call_args[1]['event_type'] == 'tts_init'
            assert call_args[1]['action'] == 'tts_api_initialized'

    def test_default_config_values(self, tts_provider):
        """Verify default config values."""
        assert tts_provider.config.model == "gpt-4o-mini-tts"
        assert tts_provider.config.voice == "ash"
        assert tts_provider.config.speed == 1.0
        assert tts_provider.config.output_format == "pcm"
        assert tts_provider.config.instructions is None


class TestSupportedVoices:
    """Test supported voices list."""

    def test_all_13_voices_listed(self, tts_provider):
        """Exactly 13 voices in supported_voices."""
        voices = tts_provider.supported_voices
        assert len(voices) == 13

    def test_voices_contain_all_required(self, tts_provider):
        """All 13 specific voices present."""
        voices = tts_provider.supported_voices
        expected_voices = [
            "alloy", "ash", "ballad", "coral", "echo",
            "fable", "nova", "onyx", "sage", "shimmer",
            "verse", "marin", "cedar",
        ]
        assert set(voices) == set(expected_voices)

    def test_validate_voice_accepts_all_13(self, tts_provider):
        """_validate_voice() passes for each voice."""
        for voice in OPENAI_TTS_VOICES:
            tts_provider._validate_voice(voice)  # Should not raise

    def test_validate_voice_rejects_unknown(self, tts_provider):
        """ValueError for unknown voice."""
        with pytest.raises(ValueError, match="Invalid voice"):
            tts_provider._validate_voice("unknown_voice")


class TestInstructionSteering:
    """Test instruction-based voice steering."""

    @pytest.mark.asyncio
    async def test_instructions_passed_to_api_for_gpt4o_mini_tts(self, gpt4o_mini_tts_provider):
        """Instructions kwarg included for gpt-4o-mini-tts."""
        mock_response = Mock()
        mock_response.read = Mock(return_value=b"audio")
        gpt4o_mini_tts_provider.client.audio.speech.create = AsyncMock(return_value=mock_response)

        await gpt4o_mini_tts_provider._synthesize_bytes("Test text", instructions="Be cheerful")

        call_kwargs = gpt4o_mini_tts_provider.client.audio.speech.create.call_args[1]
        assert "instructions" in call_kwargs
        assert call_kwargs["instructions"] == "Be cheerful"

    @pytest.mark.asyncio
    async def test_instructions_from_config(self, gpt4o_mini_tts_provider):
        """Config.instructions used when no override."""
        mock_response = Mock()
        mock_response.read = Mock(return_value=b"audio")
        gpt4o_mini_tts_provider.client.audio.speech.create = AsyncMock(return_value=mock_response)

        await gpt4o_mini_tts_provider._synthesize_bytes("Test text")

        call_kwargs = gpt4o_mini_tts_provider.client.audio.speech.create.call_args[1]
        assert call_kwargs["instructions"] == "Speak in a warm, friendly tone"

    @pytest.mark.asyncio
    async def test_instructions_not_passed_for_tts1(self, mock_env_key):
        """Instructions kwarg NOT included for tts-1."""
        config = TTSConfig(model="tts-1", instructions="Should not be passed")
        provider = OpenAITTSProvider(config=config)

        mock_response = Mock()
        mock_response.read = Mock(return_value=b"audio")
        provider.client.audio.speech.create = AsyncMock(return_value=mock_response)

        await provider._synthesize_bytes("Test text")

        call_kwargs = provider.client.audio.speech.create.call_args[1]
        assert "instructions" not in call_kwargs

    @pytest.mark.asyncio
    async def test_instructions_override(self, gpt4o_mini_tts_provider):
        """Method param overrides config.instructions."""
        mock_response = Mock()
        mock_response.read = Mock(return_value=b"audio")
        gpt4o_mini_tts_provider.client.audio.speech.create = AsyncMock(return_value=mock_response)

        await gpt4o_mini_tts_provider._synthesize_bytes("Test", instructions="Override")

        call_kwargs = gpt4o_mini_tts_provider.client.audio.speech.create.call_args[1]
        assert call_kwargs["instructions"] == "Override"

    @pytest.mark.asyncio
    async def test_instructions_none_not_passed(self, mock_env_key):
        """No instructions kwarg when instructions is None."""
        config = TTSConfig(model="gpt-4o-mini-tts", instructions=None)
        provider = OpenAITTSProvider(config=config)

        mock_response = Mock()
        mock_response.read = Mock(return_value=b"audio")
        provider.client.audio.speech.create = AsyncMock(return_value=mock_response)

        await provider._synthesize_bytes("Test text")

        call_kwargs = provider.client.audio.speech.create.call_args[1]
        assert "instructions" not in call_kwargs


class TestSynthesize:
    """Test synthesize() method."""

    @pytest.mark.asyncio
    async def test_synthesize_returns_numpy_pcm16(self, tts_provider):
        """Returns int16 numpy array."""
        mock_audio_bytes = np.array([1, 2, 3, 4], dtype=np.int16).tobytes()
        with patch.object(tts_provider, '_synthesize_bytes', return_value=mock_audio_bytes):
            result = await tts_provider.synthesize("Test")
            assert isinstance(result, np.ndarray)
            assert result.dtype == np.int16
            np.testing.assert_array_equal(result, np.array([1, 2, 3, 4], dtype=np.int16))

    @pytest.mark.asyncio
    async def test_synthesize_empty_text_raises(self, tts_provider):
        """ValueError for empty text."""
        with pytest.raises(ValueError, match="Text cannot be empty"):
            await tts_provider.synthesize("")

    @pytest.mark.asyncio
    async def test_synthesize_voice_override(self, tts_provider):
        """Voice param passed through."""
        mock_audio_bytes = np.array([1], dtype=np.int16).tobytes()
        with patch.object(tts_provider, '_synthesize_bytes', return_value=mock_audio_bytes) as mock_synth:
            await tts_provider.synthesize("Test", voice="sage")
            assert mock_synth.call_args[0][1] == "sage"

    @pytest.mark.asyncio
    async def test_synthesize_speed_override(self, tts_provider):
        """Speed param passed through."""
        mock_audio_bytes = np.array([1], dtype=np.int16).tobytes()
        with patch.object(tts_provider, '_synthesize_bytes', return_value=mock_audio_bytes) as mock_synth:
            await tts_provider.synthesize("Test", speed=2.0)
            assert mock_synth.call_args[0][2] == 2.0

    @pytest.mark.asyncio
    async def test_synthesize_non_pcm_raises(self, mock_env_key):
        """NotImplementedError for non-PCM format."""
        config = TTSConfig(output_format="mp3")
        provider = OpenAITTSProvider(config=config)
        with patch.object(provider, '_synthesize_bytes', return_value=b"mp3 data"):
            with pytest.raises(NotImplementedError, match="requires external decoder"):
                await provider.synthesize("Test")


class TestSynthesizeStream:
    """Test synthesize_stream() method."""

    @pytest.mark.asyncio
    async def test_stream_yields_chunks(self, tts_provider):
        """Yields bytes chunks."""
        async def mock_iter_bytes():
            yield b"chunk1"
            yield b"chunk2"

        mock_response = MagicMock()
        mock_response.iter_bytes = mock_iter_bytes
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=None)

        tts_provider.client.audio.speech.with_streaming_response.create = Mock(return_value=mock_response)

        chunks = []
        async for chunk in tts_provider.synthesize_stream("Test"):
            chunks.append(chunk)

        assert chunks == [b"chunk1", b"chunk2"]

    @pytest.mark.asyncio
    async def test_stream_empty_text_raises(self, tts_provider):
        """ValueError for empty text."""
        with pytest.raises(ValueError, match="Text cannot be empty"):
            async for _ in tts_provider.synthesize_stream(""):
                pass

    @pytest.mark.asyncio
    async def test_stream_audit_events_logged(self, tts_provider):
        """Audit start and complete events."""
        async def mock_iter_bytes():
            yield b"chunk1"

        mock_response = MagicMock()
        mock_response.iter_bytes = mock_iter_bytes
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=None)

        tts_provider.client.audio.speech.with_streaming_response.create = Mock(return_value=mock_response)

        with patch('openai_apis.tts.openai_provider.log_audit_event') as mock_audit:
            chunks = []
            async for chunk in tts_provider.synthesize_stream("Test"):
                chunks.append(chunk)

            # Should have start and complete events
            calls = mock_audit.call_args_list
            actions = [call[1]['action'] for call in calls]
            assert 'stream_synthesis_started' in actions
            assert 'stream_synthesis_completed' in actions

    @pytest.mark.asyncio
    async def test_stream_error_logs_audit(self, tts_provider):
        """Audit error event on failure."""
        tts_provider.client.audio.speech.with_streaming_response.create = Mock(
            side_effect=Exception("API error")
        )

        with patch('openai_apis.tts.openai_provider.log_audit_event') as mock_audit:
            with pytest.raises(TTSSynthesisError):
                async for _ in tts_provider.synthesize_stream("Test"):
                    pass

            # Should have start and failed events
            calls = mock_audit.call_args_list
            actions = [call[1]['action'] for call in calls]
            assert 'stream_synthesis_started' in actions
            assert 'stream_synthesis_failed' in actions

    @pytest.mark.asyncio
    async def test_stream_with_instructions(self, gpt4o_mini_tts_provider):
        """Instructions passed to API."""
        async def mock_iter_bytes():
            yield b"chunk1"

        mock_response = MagicMock()
        mock_response.iter_bytes = mock_iter_bytes
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=None)

        gpt4o_mini_tts_provider.client.audio.speech.with_streaming_response.create = Mock(
            return_value=mock_response
        )

        chunks = []
        async for chunk in gpt4o_mini_tts_provider.synthesize_stream("Test", instructions="Be calm"):
            chunks.append(chunk)

        call_kwargs = gpt4o_mini_tts_provider.client.audio.speech.with_streaming_response.create.call_args[1]
        assert call_kwargs["instructions"] == "Be calm"


class TestSynthesizeToFile:
    """Test synthesize_to_file() method."""

    @pytest.mark.asyncio
    async def test_to_file_pcm_creates_wav(self, tts_provider, tmp_path):
        """Writes valid WAV for pcm format."""
        out_file = tmp_path / "output.wav"
        mock_audio_bytes = np.array([1, 2, 3], dtype=np.int16).tobytes()

        with patch.object(tts_provider, '_synthesize_bytes', return_value=mock_audio_bytes):
            result = await tts_provider.synthesize_to_file("Test", out_file)
            assert result == out_file
            assert out_file.exists()

    @pytest.mark.asyncio
    async def test_to_file_mp3_writes_raw(self, mock_env_key, tmp_path):
        """Writes raw bytes for mp3 format."""
        config = TTSConfig(output_format="mp3")
        provider = OpenAITTSProvider(config=config)
        out_file = tmp_path / "output.mp3"

        with patch.object(provider, '_synthesize_bytes', return_value=b"mp3 data"):
            result = await provider.synthesize_to_file("Test", out_file)
            assert result.exists()
            assert result.read_bytes() == b"mp3 data"

    @pytest.mark.asyncio
    async def test_to_file_returns_path(self, tts_provider, tmp_path):
        """Returns Path object."""
        out_file = tmp_path / "output.wav"
        with patch.object(tts_provider, '_synthesize_bytes', return_value=b"audio"):
            result = await tts_provider.synthesize_to_file("Test", out_file)
            assert isinstance(result, Path)

    @pytest.mark.asyncio
    async def test_to_file_empty_text_raises(self, tts_provider, tmp_path):
        """ValueError for empty text."""
        with pytest.raises(ValueError, match="Text cannot be empty"):
            await tts_provider.synthesize_to_file("", tmp_path / "out.wav")


class TestSynthesizeBatch:
    """Test synthesize_batch() method."""

    @pytest.mark.asyncio
    async def test_batch_parallel_execution(self, tts_provider):
        """All texts processed via asyncio.gather."""
        mock_audio = np.array([1, 2], dtype=np.int16)
        with patch.object(tts_provider, 'synthesize', return_value=mock_audio) as mock_synth:
            texts = ["Text 1", "Text 2", "Text 3"]
            results = await tts_provider.synthesize_batch(texts)

            assert len(results) == 3
            assert mock_synth.call_count == 3

    @pytest.mark.asyncio
    async def test_batch_empty_list(self, tts_provider):
        """Returns empty list."""
        results = await tts_provider.synthesize_batch([])
        assert results == []

    @pytest.mark.asyncio
    async def test_batch_preserves_order(self, tts_provider):
        """Results match input order."""
        async def mock_synthesize(text, voice=None, speed=None, instructions=None):
            await asyncio.sleep(0.01)
            return np.array([len(text)], dtype=np.int16)

        with patch.object(tts_provider, 'synthesize', side_effect=mock_synthesize):
            texts = ["A", "BB", "CCC"]
            results = await tts_provider.synthesize_batch(texts)

            assert len(results) == 3
            assert results[0][0] == 1
            assert results[1][0] == 2
            assert results[2][0] == 3

    def test_batch_sync_wrapper(self, tts_provider):
        """Sync wrapper delegates correctly."""
        mock_results = [np.array([1]), np.array([2])]
        with patch('asyncio.run', return_value=mock_results):
            results = tts_provider.synthesize_batch_sync(["T1", "T2"])
            assert results == mock_results


class TestErrorHandling:
    """Test error handling."""

    @pytest.mark.asyncio
    async def test_api_error_raises_tts_synthesis_error(self, tts_provider):
        """API errors wrapped in TTSSynthesisError."""
        tts_provider.client.audio.speech.create = AsyncMock(side_effect=Exception("API error"))

        with pytest.raises(TTSSynthesisError, match="TTS synthesis failed"):
            await tts_provider._synthesize_bytes("Test")

    @pytest.mark.asyncio
    async def test_stream_api_error_raises_tts_synthesis_error(self, tts_provider):
        """Streaming errors wrapped."""
        tts_provider.client.audio.speech.with_streaming_response.create = Mock(
            side_effect=Exception("Stream error")
        )

        with pytest.raises(TTSSynthesisError, match="Streaming TTS synthesis failed"):
            async for _ in tts_provider.synthesize_stream("Test"):
                pass

    def test_speed_validation_boundaries(self, tts_provider):
        """0.25 and 4.0 accepted, outside rejected."""
        tts_provider._validate_speed(0.25)
        tts_provider._validate_speed(4.0)

        with pytest.raises(ValueError):
            tts_provider._validate_speed(0.24)

        with pytest.raises(ValueError):
            tts_provider._validate_speed(4.01)


class TestRegistry:
    """Test provider registry integration."""

    def test_openai_provider_registered(self):
        """get_provider("openai") returns OpenAITTSProvider."""
        provider_class = get_provider("openai")
        assert provider_class is OpenAITTSProvider

    def test_unknown_provider_raises(self):
        """KeyError for unknown name."""
        with pytest.raises(KeyError, match="Unknown TTS provider"):
            get_provider("unknown_provider")


class TestTTSConfig:
    """Test TTSConfig dataclass."""

    def test_instructions_field_exists(self, monkeypatch):
        """TTSConfig has instructions field defaulting to None."""
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        config = TTSConfig()
        assert hasattr(config, 'instructions')
        assert config.instructions is None

    def test_instructions_field_set(self):
        """TTSConfig accepts custom instructions string."""
        config = TTSConfig(instructions="Speak slowly and clearly")
        assert config.instructions == "Speak slowly and clearly"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--cov=openai_apis.tts.openai_provider", "--cov-report=term-missing"])
