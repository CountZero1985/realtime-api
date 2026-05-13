"""Unit tests for TTSRegistry."""
import pytest
from openai_apis.tts._registry import TTSRegistry, register_provider, get_provider
from openai_apis.tts.base import BaseTTSProvider
from openai_apis.tts.openai_provider import OpenAITTSProvider
from openai_apis.tts.elevenlabs_provider import ElevenLabsTTSProvider


class TestTTSRegistryListProviders:
    """Test list_providers returns registered names."""

    def test_openai_in_list(self):
        assert "openai" in TTSRegistry.list_providers()

    def test_elevenlabs_in_list(self):
        assert "elevenlabs" in TTSRegistry.list_providers()

    def test_returns_sorted_list(self):
        providers = TTSRegistry.list_providers()
        assert providers == sorted(providers)

    def test_returns_list_of_strings(self):
        providers = TTSRegistry.list_providers()
        assert all(isinstance(p, str) for p in providers)


class TestTTSRegistryGet:
    """Test get() retrieves provider classes."""

    def test_get_openai(self):
        cls = TTSRegistry.get("openai")
        assert cls is OpenAITTSProvider

    def test_get_elevenlabs(self):
        cls = TTSRegistry.get("elevenlabs")
        assert cls is ElevenLabsTTSProvider

    def test_get_unknown_raises_key_error(self):
        with pytest.raises(KeyError, match="Unknown TTS provider"):
            TTSRegistry.get("nonexistent")


class TestTTSRegistryRegister:
    """Test register() adds providers."""

    def test_register_custom_provider(self):
        """Register a custom provider, verify it's retrievable, then clean up."""

        class DummyProvider(BaseTTSProvider):
            @property
            def provider_name(self): return "dummy"
            @property
            def supported_voices(self): return ["v1"]
            async def synthesize(self, text, voice=None, speed=None): ...
            async def synthesize_stream(self, text, voice=None, speed=None):
                yield b""
            async def synthesize_to_file(self, text, file_path, voice=None, speed=None):
                from pathlib import Path
                return Path(file_path)

        TTSRegistry.register("dummy", DummyProvider)
        try:
            assert TTSRegistry.get("dummy") is DummyProvider
            assert "dummy" in TTSRegistry.list_providers()
        finally:
            # Clean up to avoid polluting other tests
            TTSRegistry._providers.pop("dummy", None)


class TestTTSRegistryCreate:
    """Test create() factory method."""

    def test_create_openai_provider(self, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
        from openai_apis.tts.config import TTSConfig
        config = TTSConfig(provider="openai")
        provider = TTSRegistry.create(config)
        assert isinstance(provider, OpenAITTSProvider)
        assert isinstance(provider, BaseTTSProvider)

    def test_create_elevenlabs_provider(self):
        from openai_apis.tts.config import TTSConfig
        config = TTSConfig(provider="elevenlabs", voice="rachel")
        provider = TTSRegistry.create(config)
        assert isinstance(provider, ElevenLabsTTSProvider)
        assert isinstance(provider, BaseTTSProvider)

    def test_create_unknown_raises(self):
        with pytest.raises(KeyError):
            from openai_apis.tts.config import TTSConfig
            # Must bypass config validation to test registry.create directly
            # Since TTSConfig validates provider, we mock it
            from unittest.mock import MagicMock
            fake_config = MagicMock()
            fake_config.provider = "nonexistent"
            TTSRegistry.create(fake_config)


class TestElevenLabsStub:
    """Test ElevenLabsTTSProvider stub behavior."""

    def test_provider_name(self):
        provider = ElevenLabsTTSProvider()
        assert provider.provider_name == "elevenlabs"

    def test_supported_voices(self):
        provider = ElevenLabsTTSProvider()
        assert provider.supported_voices == ["rachel", "adam", "bella"]

    def test_is_base_tts_provider(self):
        provider = ElevenLabsTTSProvider()
        assert isinstance(provider, BaseTTSProvider)

    @pytest.mark.asyncio
    async def test_synthesize_raises_not_implemented(self):
        provider = ElevenLabsTTSProvider()
        with pytest.raises(NotImplementedError, match="ElevenLabs provider not yet implemented"):
            await provider.synthesize("hello")

    @pytest.mark.asyncio
    async def test_synthesize_stream_raises_not_implemented(self):
        provider = ElevenLabsTTSProvider()
        with pytest.raises(NotImplementedError, match="ElevenLabs provider not yet implemented"):
            async for _ in provider.synthesize_stream("hello"):
                pass

    @pytest.mark.asyncio
    async def test_synthesize_to_file_raises_not_implemented(self):
        provider = ElevenLabsTTSProvider()
        with pytest.raises(NotImplementedError, match="ElevenLabs provider not yet implemented"):
            await provider.synthesize_to_file("hello", "out.wav")

    def test_synthesize_sync_raises_not_implemented(self):
        provider = ElevenLabsTTSProvider()
        with pytest.raises(NotImplementedError, match="ElevenLabs provider not yet implemented"):
            provider.synthesize_sync("hello")


class TestBackwardCompatFunctions:
    """Test backward-compat free functions still work."""

    def test_get_provider_returns_openai(self):
        cls = get_provider("openai")
        assert cls is OpenAITTSProvider

    def test_register_provider_works(self):
        class Tmp(BaseTTSProvider):
            @property
            def provider_name(self): return "tmp"
            @property
            def supported_voices(self): return []
            async def synthesize(self, text, voice=None, speed=None): ...
            async def synthesize_stream(self, text, voice=None, speed=None):
                yield b""
            async def synthesize_to_file(self, text, file_path, voice=None, speed=None):
                from pathlib import Path
                return Path(file_path)

        register_provider("tmp", Tmp)
        try:
            assert get_provider("tmp") is Tmp
        finally:
            TTSRegistry._providers.pop("tmp", None)
