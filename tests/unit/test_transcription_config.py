"""Unit tests for TranscriptionConfig validation."""
import pytest
from openai_apis.transcription.config import (
    TranscriptionConfig,
    SUPPORTED_TRANSCRIPTION_MODELS,
    SUPPORTED_LANGUAGES,
)
from openai_apis._config import VADConfig


class TestTranscriptionConfigDefaults:
    """Test default values."""

    def test_defaults(self, monkeypatch):
        """All fields have expected defaults."""
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        config = TranscriptionConfig()
        assert config.model == "gpt-realtime-whisper"
        assert config.language == "hu"
        assert isinstance(config.vad, VADConfig)
        assert config.keywords == []
        assert config.prompt is None
        assert config.include_logprobs is False

    def test_inherits_base_config_fields(self, monkeypatch):
        """BaseConfig fields (api_key, timeout, audio_format) inherited."""
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
        config = TranscriptionConfig()
        assert config.api_key == "sk-test"
        assert config.timeout == 30.0
        assert config.audio_format.sample_rate == 24000

    def test_vad_default_is_vadconfig_instance(self):
        """Default vad is a VADConfig instance with its own defaults."""
        config = TranscriptionConfig()
        assert isinstance(config.vad, VADConfig)
        assert config.vad.mode == "server_vad"


class TestTranscriptionConfigModelValidation:
    """Test model validation."""

    def test_all_supported_models_accepted(self):
        for model in SUPPORTED_TRANSCRIPTION_MODELS:
            config = TranscriptionConfig(model=model)
            assert config.model == model

    def test_invalid_model_rejected(self):
        with pytest.raises(ValueError, match="model must be one of"):
            TranscriptionConfig(model="nonexistent-model")


class TestTranscriptionConfigLanguageValidation:
    """Test language ISO 639-1 validation."""

    def test_hungarian_accepted(self):
        config = TranscriptionConfig(language="hu")
        assert config.language == "hu"

    def test_english_accepted(self):
        config = TranscriptionConfig(language="en")
        assert config.language == "en"

    def test_none_accepted_for_auto_detect(self):
        config = TranscriptionConfig(language=None)
        assert config.language is None

    def test_invalid_language_rejected(self):
        with pytest.raises(ValueError, match="language must be a valid ISO 639-1 code"):
            TranscriptionConfig(language="xxx")


class TestTranscriptionConfigVAD:
    """Test VADConfig integration."""

    def test_custom_vad_config(self):
        vad = VADConfig(mode="semantic_vad", eagerness="high")
        config = TranscriptionConfig(vad=vad)
        assert config.vad.mode == "semantic_vad"
        assert config.vad.eagerness == "high"

    def test_vad_disabled(self):
        vad = VADConfig(mode="disabled")
        config = TranscriptionConfig(vad=vad)
        assert config.vad.mode == "disabled"


class TestTranscriptionConfigKeywords:
    """Test keywords list support."""

    def test_default_empty_list(self):
        config = TranscriptionConfig()
        assert config.keywords == []

    def test_custom_keywords(self):
        config = TranscriptionConfig(keywords=["Budapest", "OpenAI"])
        assert config.keywords == ["Budapest", "OpenAI"]

    def test_keywords_list_is_independent(self):
        """Each instance gets its own list (no mutable default sharing)."""
        config1 = TranscriptionConfig()
        config2 = TranscriptionConfig()
        config1.keywords.append("test")
        assert config2.keywords == []


class TestTranscriptionConfigCustomValues:
    """Test creating TranscriptionConfig with custom valid values."""

    def test_custom_all_fields(self):
        vad = VADConfig(mode="semantic_vad", eagerness="low")
        config = TranscriptionConfig(
            model="whisper-1",
            language="en",
            vad=vad,
            keywords=["hello", "world"],
            prompt="Technical discussion about AI",
            include_logprobs=True,
        )
        assert config.model == "whisper-1"
        assert config.language == "en"
        assert config.vad.mode == "semantic_vad"
        assert config.keywords == ["hello", "world"]
        assert config.prompt == "Technical discussion about AI"
        assert config.include_logprobs is True
