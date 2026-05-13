"""Unit tests for BaseTTSProvider abstract base class."""

import pytest
import asyncio
import numpy as np
from pathlib import Path
from typing import AsyncIterator, Optional, Union
from unittest.mock import patch, AsyncMock, MagicMock

from openai_apis.tts.base import BaseTTSProvider
from openai_apis.tts.openai_provider import OpenAITTSProvider


class ConcreteTTSProvider(BaseTTSProvider):
    """Minimal concrete implementation for testing the ABC."""

    async def synthesize(self, text, voice=None, speed=None):
        return np.array([1, 2, 3], dtype=np.int16)

    async def synthesize_stream(self, text, voice=None, speed=None):
        yield b"chunk1"
        yield b"chunk2"

    async def synthesize_to_file(self, text, file_path, voice=None, speed=None):
        return Path(file_path)

    @property
    def supported_voices(self):
        return ["voice_a", "voice_b"]

    @property
    def provider_name(self):
        return "test_provider"


class TestBaseTTSProviderContract:
    """Test that BaseTTSProvider cannot be instantiated without all abstract methods."""

    def test_cannot_instantiate_abc_directly(self):
        with pytest.raises(TypeError):
            BaseTTSProvider()

    def test_missing_synthesize_raises(self):
        class Incomplete(BaseTTSProvider):
            async def synthesize_stream(self, text, voice=None, speed=None):
                yield b""
            async def synthesize_to_file(self, text, file_path, voice=None, speed=None):
                return Path(file_path)
            @property
            def supported_voices(self): return []
            @property
            def provider_name(self): return "x"
        with pytest.raises(TypeError):
            Incomplete()

    def test_missing_supported_voices_raises(self):
        class Incomplete(BaseTTSProvider):
            async def synthesize(self, text, voice=None, speed=None):
                return np.array([])
            async def synthesize_stream(self, text, voice=None, speed=None):
                yield b""
            async def synthesize_to_file(self, text, file_path, voice=None, speed=None):
                return Path(file_path)
            @property
            def provider_name(self): return "x"
        with pytest.raises(TypeError):
            Incomplete()

    def test_missing_provider_name_raises(self):
        class Incomplete(BaseTTSProvider):
            async def synthesize(self, text, voice=None, speed=None):
                return np.array([])
            async def synthesize_stream(self, text, voice=None, speed=None):
                yield b""
            async def synthesize_to_file(self, text, file_path, voice=None, speed=None):
                return Path(file_path)
            @property
            def supported_voices(self): return []
        with pytest.raises(TypeError):
            Incomplete()

    def test_concrete_implementation_instantiates(self):
        provider = ConcreteTTSProvider()
        assert provider.provider_name == "test_provider"
        assert provider.supported_voices == ["voice_a", "voice_b"]


class TestBaseTTSProviderSyncWrappers:
    """Test the concrete sync wrapper methods."""

    def test_synthesize_sync_delegates_to_synthesize(self):
        provider = ConcreteTTSProvider()
        result = provider.synthesize_sync("hello")
        assert isinstance(result, np.ndarray)
        np.testing.assert_array_equal(result, np.array([1, 2, 3], dtype=np.int16))

    def test_synthesize_to_file_sync_delegates(self, tmp_path):
        provider = ConcreteTTSProvider()
        out = tmp_path / "out.wav"
        result = provider.synthesize_to_file_sync("hello", out)
        assert result == out


class TestOpenAITTSProviderProperties:
    """Test that OpenAITTSProvider implements the new abstract properties."""

    def test_provider_name(self):
        with patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"}):
            api = OpenAITTSProvider()
            assert api.provider_name == "openai"

    def test_supported_voices(self):
        with patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"}):
            api = OpenAITTSProvider()
            voices = api.supported_voices
            assert isinstance(voices, list)
            assert len(voices) == 13  # Verify 13 voices
            # Check all 13 voices are present
            expected_voices = ["alloy", "ash", "ballad", "coral", "echo",
                               "fable", "nova", "onyx", "sage", "shimmer",
                               "verse", "marin", "cedar"]
            for voice in expected_voices:
                assert voice in voices

    def test_is_instance_of_base(self):
        with patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"}):
            api = OpenAITTSProvider()
            assert isinstance(api, BaseTTSProvider)
