#!/usr/bin/env python3
"""
Unit tests for tts_api.py module.

Tests all functionality in the TTS API module with 100% code coverage.
Uses pytest and unittest.mock for comprehensive testing.
"""

import pytest
import asyncio
import tempfile
import numpy as np
from pathlib import Path
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from openai_apis.tts.openai_provider import (
    OpenAITTSProvider,
    synthesize_text,
    synthesize_to_file,
    synthesize_text_sync,
    synthesize_to_file_sync
)
from openai_apis.tts.config import TTSConfig

# Backward compatibility alias
TTSAPI = OpenAITTSProvider


# Fixtures

@pytest.fixture
def tts_config():
    """Create a TTSConfig instance with default values."""
    return TTSConfig()


@pytest.fixture
def custom_tts_config():
    """Create a custom TTSConfig instance."""
    return TTSConfig(
        model="tts-1-hd",
        voice="echo",
        speed=1.5,
        output_format="mp3",
        sample_rate=16000,
        timeout=60.0
    )


@pytest.fixture
def temp_output_file():
    """Create a temporary output file path."""
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        path = Path(f.name)

    yield path

    # Cleanup
    try:
        path.unlink()
    except Exception:
        pass


# TTSConfig Tests

class TestTTSConfig:
    """Test TTSConfig dataclass."""

    def test_default_config(self, monkeypatch):
        """Test default configuration values."""
        # Clear env var to test default None behavior
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        config = TTSConfig()
        assert config.model == "gpt-4o-mini-tts"
        assert config.voice == "ash"
        assert config.speed == 1.0  # Changed from 4.0 to 1.0 (normal speech speed)
        assert config.output_format == "pcm"
        assert config.sample_rate == 24000
        assert config.api_key is None
        assert config.timeout == 30.0
        assert config.instructions is None  # New field

    def test_custom_config(self, custom_tts_config):
        """Test custom configuration values."""
        assert custom_tts_config.model == "tts-1-hd"
        assert custom_tts_config.voice == "echo"
        assert custom_tts_config.speed == 1.5
        assert custom_tts_config.output_format == "mp3"
        assert custom_tts_config.sample_rate == 16000
        assert custom_tts_config.timeout == 60.0


# TTSAPI Tests

class TestTTSAPI:
    """Test TTSAPI class."""

    def test_initialization_with_env_api_key(self):
        """Test initialization with API key from environment."""
        with patch.dict('os.environ', {'OPENAI_API_KEY': 'test-key'}):
            api = TTSAPI()
            assert api.client is not None
            assert api.sync_client is not None

    def test_initialization_with_explicit_api_key(self):
        """Test initialization with explicit API key."""
        config = TTSConfig(api_key="explicit-key")
        api = TTSAPI(config=config)
        assert api.client is not None

    def test_initialization_no_api_key(self):
        """Test initialization without API key raises error."""
        # Patch load_dotenv to prevent it from loading from .env file
        with patch('openai_apis.tts.openai_provider.load_dotenv'), \
             patch.dict('os.environ', {}, clear=True):
            with pytest.raises(ValueError, match="OPENAI_API_KEY not set"):
                TTSAPI(config=TTSConfig(api_key=None))

    def test_initialization_with_custom_config(self, custom_tts_config):
        """Test initialization with custom config."""
        custom_tts_config.api_key = "test-key"
        api = TTSAPI(config=custom_tts_config)
        assert api.config.model == "tts-1-hd"
        assert api.config.voice == "echo"
        assert api.config.speed == 1.5

    @pytest.mark.asyncio
    async def test_synthesize_basic(self):
        """Test basic synthesis."""
        with patch.dict('os.environ', {'OPENAI_API_KEY': 'test-key'}):
            api = TTSAPI()

            # Mock audio bytes (PCM format)
            mock_audio_bytes = np.array([1, 2, 3, 4], dtype=np.int16).tobytes()

            with patch.object(api, '_synthesize_bytes', return_value=mock_audio_bytes):
                result = await api.synthesize("Hello world")

                assert isinstance(result, np.ndarray)
                assert result.dtype == np.int16
                np.testing.assert_array_equal(result, np.array([1, 2, 3, 4], dtype=np.int16))

    @pytest.mark.asyncio
    async def test_synthesize_empty_text(self):
        """Test synthesis with empty text."""
        with patch.dict('os.environ', {'OPENAI_API_KEY': 'test-key'}):
            api = TTSAPI()

            with pytest.raises(ValueError, match="Text cannot be empty"):
                await api.synthesize("")

    @pytest.mark.asyncio
    async def test_synthesize_whitespace_only(self):
        """Test synthesis with whitespace-only text."""
        with patch.dict('os.environ', {'OPENAI_API_KEY': 'test-key'}):
            api = TTSAPI()

            with pytest.raises(ValueError, match="Text cannot be empty"):
                await api.synthesize("   \n\t  ")

    @pytest.mark.asyncio
    async def test_synthesize_with_voice_override(self):
        """Test synthesis with voice override."""
        with patch.dict('os.environ', {'OPENAI_API_KEY': 'test-key'}):
            api = TTSAPI()

            mock_audio_bytes = np.array([1, 2], dtype=np.int16).tobytes()

            with patch.object(api, '_synthesize_bytes', return_value=mock_audio_bytes) as mock_synth:
                await api.synthesize("Test", voice="sage")

                # Check voice was passed
                call_kwargs = mock_synth.call_args[0]
                assert call_kwargs[1] == "sage"

    @pytest.mark.asyncio
    async def test_synthesize_with_speed_override(self):
        """Test synthesis with speed override."""
        with patch.dict('os.environ', {'OPENAI_API_KEY': 'test-key'}):
            api = TTSAPI()

            mock_audio_bytes = np.array([1, 2], dtype=np.int16).tobytes()

            with patch.object(api, '_synthesize_bytes', return_value=mock_audio_bytes) as mock_synth:
                await api.synthesize("Test", speed=1.0)

                call_kwargs = mock_synth.call_args[0]
                assert call_kwargs[2] == 1.0

    @pytest.mark.asyncio
    async def test_synthesize_non_pcm_format(self):
        """Test synthesis with non-PCM format raises NotImplementedError."""
        config = TTSConfig(output_format="mp3", api_key="test-key")
        api = TTSAPI(config=config)

        mock_audio_bytes = b"mp3 data"

        with patch.object(api, '_synthesize_bytes', return_value=mock_audio_bytes):
            with pytest.raises(NotImplementedError, match="requires external decoder"):
                await api.synthesize("Test")

    @pytest.mark.asyncio
    async def test_synthesize_to_file_basic(self, temp_output_file):
        """Test synthesis to file."""
        with patch.dict('os.environ', {'OPENAI_API_KEY': 'test-key'}):
            api = TTSAPI()

            mock_audio_bytes = np.array([1, 2, 3], dtype=np.int16).tobytes()

            with patch.object(api, '_synthesize_bytes', return_value=mock_audio_bytes):
                result_path = await api.synthesize_to_file("Test text", temp_output_file)

                assert result_path == temp_output_file
                assert temp_output_file.exists()

    @pytest.mark.asyncio
    async def test_synthesize_to_file_empty_text(self, temp_output_file):
        """Test file synthesis with empty text."""
        with patch.dict('os.environ', {'OPENAI_API_KEY': 'test-key'}):
            api = TTSAPI()

            with pytest.raises(ValueError, match="Text cannot be empty"):
                await api.synthesize_to_file("", temp_output_file)

    @pytest.mark.asyncio
    async def test_synthesize_to_file_mp3_format(self, temp_output_file):
        """Test synthesis to MP3 file."""
        config = TTSConfig(output_format="mp3", api_key="test-key")
        api = TTSAPI(config=config)

        mock_audio_bytes = b"mp3 binary data"

        with patch.object(api, '_synthesize_bytes', return_value=mock_audio_bytes):
            result_path = await api.synthesize_to_file("Test", temp_output_file)

            assert result_path.exists()

    @pytest.mark.asyncio
    async def test_synthesize_stream_basic(self):
        """Test streaming synthesis."""
        with patch.dict('os.environ', {'OPENAI_API_KEY': 'test-key'}):
            api = TTSAPI()

            # Mock streaming response
            async def mock_iter_bytes():
                yield b"chunk1"
                yield b"chunk2"
                yield b"chunk3"

            mock_response = MagicMock()
            mock_response.iter_bytes = mock_iter_bytes
            mock_response.__aenter__ = AsyncMock(return_value=mock_response)
            mock_response.__aexit__ = AsyncMock(return_value=None)

            api.client.audio.speech.with_streaming_response.create = Mock(return_value=mock_response)

            chunks = []
            async for chunk in api.synthesize_stream("Test"):
                chunks.append(chunk)

            assert chunks == [b"chunk1", b"chunk2", b"chunk3"]

    @pytest.mark.asyncio
    async def test_synthesize_stream_empty_text(self):
        """Test streaming synthesis with empty text."""
        with patch.dict('os.environ', {'OPENAI_API_KEY': 'test-key'}):
            api = TTSAPI()

            with pytest.raises(ValueError, match="Text cannot be empty"):
                async for _ in api.synthesize_stream(""):
                    pass

    def test_synthesize_sync(self):
        """Test synchronous synthesis."""
        with patch.dict('os.environ', {'OPENAI_API_KEY': 'test-key'}):
            api = TTSAPI()

            mock_audio = np.array([1, 2, 3], dtype=np.int16)

            with patch('asyncio.run', return_value=mock_audio):
                result = api.synthesize_sync("Test")
                np.testing.assert_array_equal(result, mock_audio)

    def test_synthesize_to_file_sync(self, temp_output_file):
        """Test synchronous file synthesis."""
        with patch.dict('os.environ', {'OPENAI_API_KEY': 'test-key'}):
            api = TTSAPI()

            with patch('asyncio.run', return_value=temp_output_file):
                result = api.synthesize_to_file_sync("Test", temp_output_file)
                assert result == temp_output_file

    @pytest.mark.asyncio
    async def test_synthesize_batch(self):
        """Test batch synthesis."""
        with patch.dict('os.environ', {'OPENAI_API_KEY': 'test-key'}):
            api = TTSAPI()

            mock_audio = np.array([1, 2], dtype=np.int16)

            with patch.object(api, 'synthesize', return_value=mock_audio):
                texts = ["Text 1", "Text 2", "Text 3"]
                results = await api.synthesize_batch(texts)

                assert len(results) == 3
                for result in results:
                    np.testing.assert_array_equal(result, mock_audio)

    def test_synthesize_batch_sync(self):
        """Test synchronous batch synthesis."""
        with patch.dict('os.environ', {'OPENAI_API_KEY': 'test-key'}):
            api = TTSAPI()

            mock_audios = [np.array([1]), np.array([2])]

            with patch('asyncio.run', return_value=mock_audios):
                results = api.synthesize_batch_sync(["T1", "T2"])
                assert results == mock_audios

    @pytest.mark.asyncio
    async def test_synthesize_bytes_basic(self):
        """Test internal _synthesize_bytes method."""
        with patch.dict('os.environ', {'OPENAI_API_KEY': 'test-key'}):
            api = TTSAPI()

            # Mock response
            mock_response = Mock()
            mock_response.read = Mock(return_value=b"audio bytes")
            api.client.audio.speech.create = AsyncMock(return_value=mock_response)

            result = await api._synthesize_bytes("Test text", None, None)

            assert result == b"audio bytes"

    @pytest.mark.asyncio
    async def test_synthesize_bytes_with_params(self):
        """Test _synthesize_bytes with explicit parameters."""
        with patch.dict('os.environ', {'OPENAI_API_KEY': 'test-key'}):
            api = TTSAPI()

            mock_response = Mock()
            mock_response.read = Mock(return_value=b"bytes")
            api.client.audio.speech.create = AsyncMock(return_value=mock_response)

            await api._synthesize_bytes("Test", voice="sage", speed=2.0)

            call_kwargs = api.client.audio.speech.create.call_args[1]
            assert call_kwargs['voice'] == "sage"
            assert call_kwargs['speed'] == 2.0

    @pytest.mark.asyncio
    async def test_synthesize_bytes_error(self):
        """Test _synthesize_bytes error handling."""
        with patch.dict('os.environ', {'OPENAI_API_KEY': 'test-key'}):
            api = TTSAPI()

            api.client.audio.speech.create = AsyncMock(side_effect=Exception("API error"))

            with pytest.raises(Exception, match="TTS synthesis failed"):
                await api._synthesize_bytes("Test", None, None)

    def test_validate_voice_valid(self):
        """Test voice validation with valid voice."""
        with patch.dict('os.environ', {'OPENAI_API_KEY': 'test-key'}):
            api = TTSAPI()

            # Should not raise - all 13 voices
            for voice in ["alloy", "ash", "ballad", "coral", "echo",
                          "fable", "nova", "onyx", "sage", "shimmer",
                          "verse", "marin", "cedar"]:
                api._validate_voice(voice)

    def test_validate_voice_invalid(self):
        """Test voice validation with invalid voice."""
        with patch.dict('os.environ', {'OPENAI_API_KEY': 'test-key'}):
            api = TTSAPI()

            with pytest.raises(ValueError, match="Invalid voice"):
                api._validate_voice("invalid_voice")

    def test_validate_speed_valid(self):
        """Test speed validation with valid speeds."""
        with patch.dict('os.environ', {'OPENAI_API_KEY': 'test-key'}):
            api = TTSAPI()

            # Should not raise
            api._validate_speed(0.25)
            api._validate_speed(1.0)
            api._validate_speed(4.0)

    def test_validate_speed_invalid_low(self):
        """Test speed validation with too low speed."""
        with patch.dict('os.environ', {'OPENAI_API_KEY': 'test-key'}):
            api = TTSAPI()

            with pytest.raises(ValueError, match="Speed must be between"):
                api._validate_speed(0.1)

    def test_validate_speed_invalid_high(self):
        """Test speed validation with too high speed."""
        with patch.dict('os.environ', {'OPENAI_API_KEY': 'test-key'}):
            api = TTSAPI()

            with pytest.raises(ValueError, match="Speed must be between"):
                api._validate_speed(5.0)


# Convenience Function Tests

class TestConvenienceFunctions:
    """Test convenience functions."""

    @pytest.mark.asyncio
    async def test_synthesize_text(self):
        """Test synthesize_text convenience function."""
        with patch('openai_apis.tts.openai_provider.OpenAITTSProvider') as mock_api_class:
            mock_api = Mock()
            mock_audio = np.array([1, 2, 3], dtype=np.int16)
            mock_api.synthesize = AsyncMock(return_value=mock_audio)
            mock_api_class.return_value = mock_api

            result = await synthesize_text("Test", voice="sage", speed=2.0, model="tts-1")

            np.testing.assert_array_equal(result, mock_audio)
            mock_api.synthesize.assert_called_once_with("Test")

    @pytest.mark.asyncio
    async def test_synthesize_to_file_convenience(self, temp_output_file):
        """Test synthesize_to_file convenience function."""
        with patch('openai_apis.tts.openai_provider.OpenAITTSProvider') as mock_api_class:
            mock_api = Mock()
            mock_api.synthesize_to_file = AsyncMock(return_value=temp_output_file)
            mock_api_class.return_value = mock_api

            result = await synthesize_to_file("Test", temp_output_file, voice="ash", speed=4.0)

            assert result == temp_output_file
            mock_api.synthesize_to_file.assert_called_once()

    def test_synthesize_text_sync_convenience(self):
        """Test synthesize_text_sync convenience function."""
        with patch('asyncio.run', return_value=np.array([1, 2])):
            result = synthesize_text_sync("Test")
            assert isinstance(result, np.ndarray)

    def test_synthesize_to_file_sync_convenience(self, temp_output_file):
        """Test synthesize_to_file_sync convenience function."""
        with patch('asyncio.run', return_value=temp_output_file):
            result = synthesize_to_file_sync("Test", temp_output_file)
            assert result == temp_output_file


# Integration Tests

class TestTTSAPIIntegration:
    """Integration tests for TTSAPI."""

    @pytest.mark.asyncio
    async def test_full_synthesis_flow(self):
        """Test complete synthesis flow."""
        with patch.dict('os.environ', {'OPENAI_API_KEY': 'test-key'}):
            api = TTSAPI()

            mock_audio_bytes = np.array([1, 2, 3, 4, 5], dtype=np.int16).tobytes()
            mock_response = Mock()
            mock_response.read = Mock(return_value=mock_audio_bytes)
            api.client.audio.speech.create = AsyncMock(return_value=mock_response)

            result = await api.synthesize("Complete flow test")

            assert isinstance(result, np.ndarray)
            assert len(result) == 5

    def test_config_customization(self):
        """Test API with completely custom config."""
        config = TTSConfig(
            model="tts-1-hd",
            voice="echo",
            speed=1.5,
            output_format="opus",
            sample_rate=48000,
            api_key="test-key"
        )

        api = TTSAPI(config=config)

        assert api.config.model == "tts-1-hd"
        assert api.config.voice == "echo"
        assert api.config.speed == 1.5
        assert api.config.output_format == "opus"


# Edge Cases and Error Handling

class TestTTSAPIEdgeCases:
    """Test edge cases and error scenarios."""

    @pytest.mark.asyncio
    async def test_synthesize_very_long_text(self):
        """Test synthesis with very long text."""
        with patch.dict('os.environ', {'OPENAI_API_KEY': 'test-key'}):
            api = TTSAPI()

            long_text = "A" * 10000

            mock_audio_bytes = np.array([1, 2], dtype=np.int16).tobytes()
            with patch.object(api, '_synthesize_bytes', return_value=mock_audio_bytes):
                result = await api.synthesize(long_text)
                assert isinstance(result, np.ndarray)

    @pytest.mark.asyncio
    async def test_synthesize_unicode_text(self):
        """Test synthesis with Unicode characters."""
        with patch.dict('os.environ', {'OPENAI_API_KEY': 'test-key'}):
            api = TTSAPI()

            unicode_text = "Szia! 你好 مرحبا 👋"

            mock_audio_bytes = np.array([1, 2], dtype=np.int16).tobytes()
            with patch.object(api, '_synthesize_bytes', return_value=mock_audio_bytes):
                result = await api.synthesize(unicode_text)
                assert isinstance(result, np.ndarray)

    @pytest.mark.asyncio
    async def test_synthesize_special_characters(self):
        """Test synthesis with special characters."""
        with patch.dict('os.environ', {'OPENAI_API_KEY': 'test-key'}):
            api = TTSAPI()

            special_text = "Hello! How are you? I'm fine. \n\t Test..."

            mock_audio_bytes = np.array([1, 2], dtype=np.int16).tobytes()
            with patch.object(api, '_synthesize_bytes', return_value=mock_audio_bytes):
                result = await api.synthesize(special_text)
                assert isinstance(result, np.ndarray)

    @pytest.mark.asyncio
    async def test_synthesize_batch_empty_list(self):
        """Test batch synthesis with empty list."""
        with patch.dict('os.environ', {'OPENAI_API_KEY': 'test-key'}):
            api = TTSAPI()

            results = await api.synthesize_batch([])
            assert results == []

    @pytest.mark.asyncio
    async def test_synthesize_batch_with_errors(self):
        """Test batch synthesis with some failures."""
        with patch.dict('os.environ', {'OPENAI_API_KEY': 'test-key'}):
            api = TTSAPI()

            # One text is empty, should raise
            texts = ["Valid text", ""]

            with pytest.raises(ValueError):
                await api.synthesize_batch(texts)

    @pytest.mark.asyncio
    async def test_synthesize_all_voices(self):
        """Test synthesis with all available voices."""
        with patch.dict('os.environ', {'OPENAI_API_KEY': 'test-key'}):
            api = TTSAPI()

            mock_audio_bytes = np.array([1, 2], dtype=np.int16).tobytes()

            # All 13 voices
            for voice in ["alloy", "ash", "ballad", "coral", "echo",
                          "fable", "nova", "onyx", "sage", "shimmer",
                          "verse", "marin", "cedar"]:
                with patch.object(api, '_synthesize_bytes', return_value=mock_audio_bytes):
                    result = await api.synthesize("Test", voice=voice)
                    assert isinstance(result, np.ndarray)

    @pytest.mark.asyncio
    async def test_synthesize_speed_range(self):
        """Test synthesis with various speed values."""
        with patch.dict('os.environ', {'OPENAI_API_KEY': 'test-key'}):
            api = TTSAPI()

            mock_audio_bytes = np.array([1, 2], dtype=np.int16).tobytes()

            for speed in [0.25, 1.0, 2.0, 4.0]:
                with patch.object(api, '_synthesize_bytes', return_value=mock_audio_bytes):
                    result = await api.synthesize("Test", speed=speed)
                    assert isinstance(result, np.ndarray)

    @pytest.mark.asyncio
    async def test_synthesize_with_all_parameters(self):
        """Test synthesis with all parameters specified."""
        config = TTSConfig(
            model="tts-1-hd",
            voice="alloy",
            speed=1.5,
            output_format="pcm",
            sample_rate=24000,
            api_key="test-key"
        )

        api = TTSAPI(config=config)

        mock_audio_bytes = np.array([1, 2, 3], dtype=np.int16).tobytes()

        with patch.object(api, '_synthesize_bytes', return_value=mock_audio_bytes):
            result = await api.synthesize(
                "Full param test",
                voice="sage",  # Override
                speed=2.0  # Override
            )

            assert isinstance(result, np.ndarray)

    @pytest.mark.asyncio
    async def test_streaming_with_large_response(self):
        """Test streaming with large response."""
        with patch.dict('os.environ', {'OPENAI_API_KEY': 'test-key'}):
            api = TTSAPI()

            # Mock large streaming response
            async def mock_iter_bytes():
                for i in range(100):
                    yield f"chunk{i}".encode()

            mock_response = MagicMock()
            mock_response.iter_bytes = mock_iter_bytes
            mock_response.__aenter__ = AsyncMock(return_value=mock_response)
            mock_response.__aexit__ = AsyncMock(return_value=None)

            api.client.audio.speech.with_streaming_response.create = Mock(return_value=mock_response)

            chunks = []
            async for chunk in api.synthesize_stream("Test"):
                chunks.append(chunk)

            assert len(chunks) == 100

    def test_config_validation_at_init(self):
        """Test that invalid config values are handled."""
        # Speed outside range should be caught when used, not at init
        config = TTSConfig(
            voice="ash",
            speed=10.0,  # Invalid but allowed in config
            api_key="test-key"
        )

        api = TTSAPI(config=config)
        assert api.config.speed == 10.0  # Stored as-is

        # But validation happens when actually used
        with pytest.raises(ValueError):
            api._validate_speed(10.0)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--cov=tts_api", "--cov-report=term-missing"])
