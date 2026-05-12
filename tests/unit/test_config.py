"""Unit tests for configuration classes in openai_apis._config."""
import os
import pytest
from dataclasses import FrozenInstanceError, dataclass
from openai_apis import AudioFormat, VADConfig, BaseConfig


class TestAudioFormat:
    """Test cases for AudioFormat dataclass."""

    def test_defaults(self):
        """Verify default values."""
        audio_format = AudioFormat()
        assert audio_format.sample_rate == 24000
        assert audio_format.channels == 1
        assert audio_format.dtype == "int16"
        assert audio_format.encoding == "pcm16"

    def test_immutability(self):
        """Assigning to a field raises FrozenInstanceError."""
        audio_format = AudioFormat()
        with pytest.raises(FrozenInstanceError):
            audio_format.sample_rate = 48000

    def test_custom_values(self):
        """Create with custom valid values."""
        audio_format = AudioFormat(
            sample_rate=48000,
            channels=2,
            dtype="float32",
            encoding="g711_ulaw"
        )
        assert audio_format.sample_rate == 48000
        assert audio_format.channels == 2
        assert audio_format.dtype == "float32"
        assert audio_format.encoding == "g711_ulaw"

    def test_invalid_sample_rate_zero(self):
        """ValueError for sample_rate=0."""
        with pytest.raises(ValueError, match="sample_rate must be positive"):
            AudioFormat(sample_rate=0)

    def test_invalid_sample_rate_negative(self):
        """ValueError for negative sample_rate."""
        with pytest.raises(ValueError, match="sample_rate must be positive"):
            AudioFormat(sample_rate=-100)

    def test_invalid_channels(self):
        """ValueError for channels=0."""
        with pytest.raises(ValueError, match="channels must be positive"):
            AudioFormat(channels=0)

    def test_invalid_dtype(self):
        """ValueError for unsupported dtype."""
        with pytest.raises(ValueError, match="dtype must be one of"):
            AudioFormat(dtype="int32")

    def test_invalid_encoding(self):
        """ValueError for unsupported encoding."""
        with pytest.raises(ValueError, match="encoding must be one of"):
            AudioFormat(encoding="mp3")


class TestVADConfig:
    """Test cases for VADConfig dataclass."""

    def test_defaults(self):
        """Verify default values."""
        vad_config = VADConfig()
        assert vad_config.mode == "server_vad"
        assert vad_config.threshold == 0.5
        assert vad_config.prefix_padding_ms == 300
        assert vad_config.silence_duration_ms == 500
        assert vad_config.eagerness == "auto"

    def test_server_vad_mode(self):
        """Valid server_vad config."""
        vad_config = VADConfig(
            mode="server_vad",
            threshold=0.7,
            prefix_padding_ms=200,
            silence_duration_ms=400
        )
        assert vad_config.mode == "server_vad"
        assert vad_config.threshold == 0.7
        assert vad_config.prefix_padding_ms == 200
        assert vad_config.silence_duration_ms == 400

    def test_semantic_vad_mode(self):
        """Valid semantic_vad config with eagerness."""
        vad_config = VADConfig(mode="semantic_vad", eagerness="high")
        assert vad_config.mode == "semantic_vad"
        assert vad_config.eagerness == "high"

    def test_disabled_mode(self):
        """mode='disabled' works."""
        vad_config = VADConfig(mode="disabled")
        assert vad_config.mode == "disabled"

    def test_invalid_mode(self):
        """ValueError for unknown mode."""
        with pytest.raises(ValueError, match="mode must be one of"):
            VADConfig(mode="invalid_mode")

    def test_server_vad_threshold_out_of_range_high(self):
        """ValueError for threshold > 1.0."""
        with pytest.raises(ValueError, match="threshold must be between 0.0 and 1.0"):
            VADConfig(mode="server_vad", threshold=1.5)

    def test_server_vad_threshold_out_of_range_low(self):
        """ValueError for threshold < 0.0."""
        with pytest.raises(ValueError, match="threshold must be between 0.0 and 1.0"):
            VADConfig(mode="server_vad", threshold=-0.1)

    def test_server_vad_negative_prefix_padding(self):
        """ValueError for negative prefix_padding_ms."""
        with pytest.raises(ValueError, match="prefix_padding_ms must be non-negative"):
            VADConfig(mode="server_vad", prefix_padding_ms=-10)

    def test_server_vad_negative_silence_duration(self):
        """ValueError for negative silence_duration_ms."""
        with pytest.raises(ValueError, match="silence_duration_ms must be non-negative"):
            VADConfig(mode="server_vad", silence_duration_ms=-100)

    def test_semantic_vad_invalid_eagerness(self):
        """ValueError for invalid eagerness."""
        with pytest.raises(ValueError, match="eagerness must be one of"):
            VADConfig(mode="semantic_vad", eagerness="invalid")


class TestBaseConfig:
    """Test cases for BaseConfig dataclass."""

    def test_defaults(self):
        """Verify default values including audio_format type."""
        config = BaseConfig()
        assert config.api_key is None or isinstance(config.api_key, str)  # Could be from env
        assert config.timeout == 30.0
        assert isinstance(config.audio_format, AudioFormat)
        assert config.audio_format.sample_rate == 24000

    def test_api_key_from_env(self, monkeypatch):
        """When api_key=None, reads OPENAI_API_KEY from environment."""
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test-key-123")
        config = BaseConfig()
        assert config.api_key == "sk-test-key-123"

    def test_api_key_explicit(self, monkeypatch):
        """Explicit api_key takes precedence over env var."""
        monkeypatch.setenv("OPENAI_API_KEY", "sk-env-key")
        config = BaseConfig(api_key="sk-explicit-key")
        assert config.api_key == "sk-explicit-key"

    def test_api_key_none_when_no_env(self, monkeypatch):
        """api_key stays None when env var not set."""
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        config = BaseConfig()
        assert config.api_key is None

    def test_audio_format_default_instance(self):
        """Default audio_format is AudioFormat with defaults."""
        config = BaseConfig()
        assert isinstance(config.audio_format, AudioFormat)
        assert config.audio_format.sample_rate == 24000
        assert config.audio_format.channels == 1

    def test_custom_audio_format(self):
        """Passing custom AudioFormat works."""
        custom_format = AudioFormat(sample_rate=48000, channels=2)
        config = BaseConfig(audio_format=custom_format)
        assert config.audio_format.sample_rate == 48000
        assert config.audio_format.channels == 2

    def test_invalid_timeout_zero(self):
        """ValueError for timeout = 0."""
        with pytest.raises(ValueError, match="timeout must be positive"):
            BaseConfig(timeout=0)

    def test_invalid_timeout_negative(self):
        """ValueError for timeout < 0."""
        with pytest.raises(ValueError, match="timeout must be positive"):
            BaseConfig(timeout=-5.0)

    def test_subclass_inherits_audio_format(self):
        """A subclass dataclass inherits audio_format field."""
        @dataclass
        class SubConfig(BaseConfig):
            extra_field: str = "test"

        sub_config = SubConfig()
        assert isinstance(sub_config.audio_format, AudioFormat)
        assert sub_config.audio_format.sample_rate == 24000
        assert sub_config.extra_field == "test"
