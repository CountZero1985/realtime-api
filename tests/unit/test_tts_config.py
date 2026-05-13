"""Unit tests for TTSConfig validation."""
import pytest
from openai_apis.tts.config import TTSConfig, SUPPORTED_OUTPUT_FORMATS
from openai_apis.tts.openai_provider import OPENAI_TTS_VOICES


class TestTTSConfigDefaults:
    """Test default values."""

    def test_defaults(self, monkeypatch):
        """All fields have expected defaults."""
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        config = TTSConfig()
        assert config.provider == "openai"
        assert config.model == "gpt-4o-mini-tts"
        assert config.voice == "ash"
        assert config.speed == 1.0
        assert config.output_format == "pcm"
        assert config.instructions is None
        assert config.language == "hu"
        assert config.sample_rate == 24000

    def test_inherits_base_config_fields(self, monkeypatch):
        """BaseConfig fields (api_key, timeout, audio_format) inherited."""
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
        config = TTSConfig()
        assert config.api_key == "sk-test"
        assert config.timeout == 30.0
        assert config.audio_format.sample_rate == 24000


class TestTTSConfigSpeedValidation:
    """Test speed validation (0.25–4.0)."""

    def test_speed_lower_bound(self):
        config = TTSConfig(speed=0.25)
        assert config.speed == 0.25

    def test_speed_upper_bound(self):
        config = TTSConfig(speed=4.0)
        assert config.speed == 4.0

    def test_speed_normal(self):
        config = TTSConfig(speed=1.5)
        assert config.speed == 1.5

    def test_speed_too_low(self):
        with pytest.raises(ValueError, match="speed must be between 0.25 and 4.0"):
            TTSConfig(speed=0.24)

    def test_speed_too_high(self):
        with pytest.raises(ValueError, match="speed must be between 0.25 and 4.0"):
            TTSConfig(speed=4.01)

    def test_speed_zero(self):
        with pytest.raises(ValueError, match="speed must be between 0.25 and 4.0"):
            TTSConfig(speed=0.0)

    def test_speed_negative(self):
        with pytest.raises(ValueError, match="speed must be between 0.25 and 4.0"):
            TTSConfig(speed=-1.0)


class TestTTSConfigVoiceValidation:
    """Test voice validation against provider's supported_voices."""

    def test_all_openai_voices_accepted(self):
        for voice in OPENAI_TTS_VOICES:
            config = TTSConfig(voice=voice)
            assert config.voice == voice

    def test_invalid_voice_rejected(self):
        with pytest.raises(ValueError, match="Invalid voice"):
            TTSConfig(voice="nonexistent_voice")


class TestTTSConfigOutputFormatValidation:
    """Test output_format validation."""

    def test_all_supported_formats_accepted(self):
        for fmt in SUPPORTED_OUTPUT_FORMATS:
            config = TTSConfig(output_format=fmt)
            assert config.output_format == fmt

    def test_invalid_format_rejected(self):
        with pytest.raises(ValueError, match="output_format must be one of"):
            TTSConfig(output_format="ogg")


class TestTTSConfigProviderValidation:
    """Test provider validation against registry."""

    def test_openai_provider_accepted(self):
        config = TTSConfig(provider="openai")
        assert config.provider == "openai"

    def test_unknown_provider_rejected(self):
        with pytest.raises(ValueError, match="Unknown provider"):
            TTSConfig(provider="nonexistent_provider")


class TestTTSConfigCustomValues:
    """Test creating TTSConfig with custom valid values."""

    def test_custom_all_fields(self):
        config = TTSConfig(
            provider="openai",
            model="tts-1-hd",
            voice="sage",
            speed=2.0,
            output_format="mp3",
            instructions="Speak slowly",
            language="en",
            sample_rate=48000,
        )
        assert config.provider == "openai"
        assert config.model == "tts-1-hd"
        assert config.voice == "sage"
        assert config.speed == 2.0
        assert config.output_format == "mp3"
        assert config.instructions == "Speak slowly"
        assert config.language == "en"
        assert config.sample_rate == 48000


class TestTTSConfigElevenLabsProvider:
    """Test ElevenLabs provider validation in TTSConfig."""

    def test_elevenlabs_provider_accepted(self):
        config = TTSConfig(provider="elevenlabs", voice="rachel")
        assert config.provider == "elevenlabs"

    def test_elevenlabs_valid_voices(self):
        for voice in ["rachel", "adam", "bella"]:
            config = TTSConfig(provider="elevenlabs", voice=voice)
            assert config.voice == voice

    def test_elevenlabs_invalid_voice_rejected(self):
        with pytest.raises(ValueError, match="Invalid voice"):
            TTSConfig(provider="elevenlabs", voice="ash")  # ash is OpenAI-only
