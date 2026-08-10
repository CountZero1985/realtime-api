"""Unit tests for RealtimeConfig validation and to_session_update()."""
import pytest
from openai_apis.realtime.config import (
    RealtimeConfig,
    SUPPORTED_REALTIME_MODELS,
    SUPPORTED_REALTIME_VOICES,
)
from openai_apis._config import VADConfig, AudioFormat


class TestRealtimeConfigDefaults:
    """Test default values."""

    def test_defaults(self, monkeypatch):
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        config = RealtimeConfig()
        assert config.model == "gpt-realtime-mini"
        assert config.instructions is None
        assert config.voice == "ash"
        assert config.language == "hu"
        assert isinstance(config.vad, VADConfig)
        assert config.temperature == 0.8
        assert config.max_response_output_tokens == "inf"
        assert config.input_audio_transcription is True
        assert config.modalities == ["audio"]
        assert config.reasoning_effort is None
        assert config.tools == []

    def test_inherits_base_config_fields(self, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
        config = RealtimeConfig()
        assert config.api_key == "sk-test"
        assert config.timeout == 30.0
        assert isinstance(config.audio_format, AudioFormat)

    def test_vad_default_is_vadconfig_instance(self):
        config = RealtimeConfig()
        assert isinstance(config.vad, VADConfig)
        assert config.vad.mode == "server_vad"

    def test_tools_default_empty_list(self):
        config = RealtimeConfig()
        assert config.tools == []

    def test_tools_list_is_independent(self):
        config1 = RealtimeConfig()
        config2 = RealtimeConfig()
        config1.tools.append({"type": "function"})
        assert config2.tools == []

    def test_modalities_list_is_independent(self):
        config1 = RealtimeConfig()
        config2 = RealtimeConfig()
        config1.modalities.append("video")  # just testing independence
        assert config2.modalities == ["audio"]


class TestRealtimeConfigModelValidation:
    def test_all_supported_models_accepted(self):
        for model in SUPPORTED_REALTIME_MODELS:
            config = RealtimeConfig(model=model)
            assert config.model == model

    def test_invalid_model_rejected(self):
        with pytest.raises(ValueError, match="model must be one of"):
            RealtimeConfig(model="nonexistent-model")


class TestRealtimeConfigVoiceValidation:
    def test_all_supported_voices_accepted(self):
        for voice in SUPPORTED_REALTIME_VOICES:
            config = RealtimeConfig(voice=voice)
            assert config.voice == voice

    def test_invalid_voice_rejected(self):
        with pytest.raises(ValueError, match="voice must be one of"):
            RealtimeConfig(voice="nonexistent_voice")


class TestRealtimeConfigTemperatureValidation:
    def test_lower_bound(self):
        config = RealtimeConfig(temperature=0.6)
        assert config.temperature == 0.6

    def test_upper_bound(self):
        config = RealtimeConfig(temperature=1.2)
        assert config.temperature == 1.2

    def test_default_value(self):
        config = RealtimeConfig()
        assert config.temperature == 0.8

    def test_too_low(self):
        with pytest.raises(ValueError, match="temperature must be between 0.6 and 1.2"):
            RealtimeConfig(temperature=0.5)

    def test_too_high(self):
        with pytest.raises(ValueError, match="temperature must be between 0.6 and 1.2"):
            RealtimeConfig(temperature=1.3)


class TestRealtimeConfigMaxTokensValidation:
    def test_inf_string(self):
        config = RealtimeConfig(max_response_output_tokens="inf")
        assert config.max_response_output_tokens == "inf"

    def test_positive_integer(self):
        config = RealtimeConfig(max_response_output_tokens=4096)
        assert config.max_response_output_tokens == 4096

    def test_zero_rejected(self):
        with pytest.raises(ValueError, match="must be a positive integer"):
            RealtimeConfig(max_response_output_tokens=0)

    def test_negative_rejected(self):
        with pytest.raises(ValueError, match="must be a positive integer"):
            RealtimeConfig(max_response_output_tokens=-1)

    def test_invalid_string_rejected(self):
        with pytest.raises(ValueError, match="must be 'inf' or a positive integer"):
            RealtimeConfig(max_response_output_tokens="unlimited")

    def test_non_int_non_str_type_rejected(self):
        """Non-int, non-str types (e.g. float) are rejected."""
        with pytest.raises(ValueError, match="must be 'inf' or a positive integer"):
            RealtimeConfig(max_response_output_tokens=3.14)


class TestRealtimeConfigModalitiesValidation:
    def test_default_modalities(self):
        config = RealtimeConfig()
        assert config.modalities == ["audio"]

    def test_text_only(self):
        config = RealtimeConfig(modalities=["text"])
        assert config.modalities == ["text"]

    def test_audio_only(self):
        config = RealtimeConfig(modalities=["audio"])
        assert config.modalities == ["audio"]

    def test_invalid_modality(self):
        with pytest.raises(ValueError, match="modalities must only contain"):
            RealtimeConfig(modalities=["audio", "video"])


class TestRealtimeConfigToSessionUpdate:
    """Test to_session_update() output against the GA session schema.

    GA differs from the beta schema in four ways that these tests pin down:
    a `type: "realtime"` discriminator, audio settings nested under
    `audio.input` / `audio.output`, `modalities` renamed to
    `output_modalities`, and no `temperature` field at all.
    """

    def test_basic_structure(self):
        config = RealtimeConfig()
        result = config.to_session_update()
        assert result["type"] == "session.update"
        assert "session" in result

    def test_session_type_is_realtime(self):
        config = RealtimeConfig()
        result = config.to_session_update()
        assert result["session"]["type"] == "realtime"

    def test_model_in_output(self):
        config = RealtimeConfig()
        result = config.to_session_update()
        assert result["session"]["model"] == "gpt-realtime-mini"

    def test_voice_nested_under_audio_output(self):
        config = RealtimeConfig(voice="sage")
        result = config.to_session_update()
        assert result["session"]["audio"]["output"]["voice"] == "sage"

    def test_output_modalities_in_output(self):
        config = RealtimeConfig()
        result = config.to_session_update()
        assert result["session"]["output_modalities"] == ["audio"]
        assert "modalities" not in result["session"]

    def test_audio_format_from_base_config(self):
        config = RealtimeConfig()
        result = config.to_session_update()
        expected = {"type": "audio/pcm", "rate": 24000}
        assert result["session"]["audio"]["input"]["format"] == expected
        assert result["session"]["audio"]["output"]["format"] == expected

    def test_temperature_not_sent(self):
        """GA has no session-level temperature; the field is kept but unused."""
        config = RealtimeConfig(temperature=0.9)
        result = config.to_session_update()
        assert "temperature" not in result["session"]
        assert config.temperature == 0.9

    def test_no_beta_fields_remain(self):
        """Guard against a partial migration leaving beta keys behind."""
        config = RealtimeConfig()
        session = config.to_session_update()["session"]
        for beta_key in (
            "modalities",
            "input_audio_format",
            "output_audio_format",
            "temperature",
            "max_response_output_tokens",
            "turn_detection",
            "input_audio_transcription",
            "voice",
        ):
            assert beta_key not in session, f"beta field '{beta_key}' still sent"

    def test_max_tokens_inf(self):
        config = RealtimeConfig(max_response_output_tokens="inf")
        result = config.to_session_update()
        assert result["session"]["max_output_tokens"] == "inf"

    def test_max_tokens_integer(self):
        config = RealtimeConfig(max_response_output_tokens=4096)
        result = config.to_session_update()
        assert result["session"]["max_output_tokens"] == 4096

    def test_instructions_included_when_set(self):
        config = RealtimeConfig(instructions="Be helpful")
        result = config.to_session_update()
        assert result["session"]["instructions"] == "Be helpful"

    def test_instructions_omitted_when_none(self):
        config = RealtimeConfig(instructions=None)
        result = config.to_session_update()
        assert "instructions" not in result["session"]

    def test_vad_disabled_sets_turn_detection_null(self):
        """Explicit null under audio.input is what disables server VAD."""
        config = RealtimeConfig(vad=VADConfig(mode="disabled"))
        result = config.to_session_update()
        audio_input = result["session"]["audio"]["input"]
        assert "turn_detection" in audio_input
        assert audio_input["turn_detection"] is None

    def test_vad_server_vad(self):
        vad = VADConfig(mode="server_vad", threshold=0.7, prefix_padding_ms=200, silence_duration_ms=800)
        config = RealtimeConfig(vad=vad)
        result = config.to_session_update()
        td = result["session"]["audio"]["input"]["turn_detection"]
        assert td["type"] == "server_vad"
        assert td["threshold"] == 0.7
        assert td["prefix_padding_ms"] == 200
        assert td["silence_duration_ms"] == 800

    def test_vad_semantic_vad(self):
        vad = VADConfig(mode="semantic_vad", eagerness="high")
        config = RealtimeConfig(vad=vad)
        result = config.to_session_update()
        td = result["session"]["audio"]["input"]["turn_detection"]
        assert td["type"] == "semantic_vad"
        assert td["eagerness"] == "high"

    def test_input_transcription_enabled(self):
        config = RealtimeConfig(input_audio_transcription=True, language="hu")
        result = config.to_session_update()
        transcription = result["session"]["audio"]["input"]["transcription"]
        assert transcription["model"] == "whisper-1"
        assert transcription["language"] == "hu"

    def test_input_transcription_disabled(self):
        config = RealtimeConfig(input_audio_transcription=False)
        result = config.to_session_update()
        assert result["session"]["audio"]["input"]["transcription"] is None

    def test_reasoning_omitted_when_none(self):
        config = RealtimeConfig()
        result = config.to_session_update()
        assert "reasoning" not in result["session"]

    def test_reasoning_effort_included_when_set(self):
        config = RealtimeConfig(reasoning_effort="minimal")
        result = config.to_session_update()
        assert result["session"]["reasoning"] == {"effort": "minimal"}

    def test_tools_included_when_provided(self):
        tools = [{"type": "function", "name": "get_weather", "description": "Get weather"}]
        config = RealtimeConfig(tools=tools)
        result = config.to_session_update()
        assert result["session"]["tools"] == tools

    def test_tools_omitted_when_empty(self):
        config = RealtimeConfig(tools=[])
        result = config.to_session_update()
        assert "tools" not in result["session"]

    def test_custom_audio_format_encoding(self):
        """G.711 maps to its own GA media type and carries no rate."""
        fmt = AudioFormat(encoding="g711_ulaw")
        config = RealtimeConfig(audio_format=fmt)
        result = config.to_session_update()
        assert result["session"]["audio"]["input"]["format"] == {"type": "audio/pcmu"}
        assert result["session"]["audio"]["output"]["format"] == {"type": "audio/pcmu"}

    def test_custom_sample_rate_in_format(self):
        config = RealtimeConfig(audio_format=AudioFormat(sample_rate=16000))
        result = config.to_session_update()
        assert result["session"]["audio"]["input"]["format"]["rate"] == 16000


class TestRealtimeConfigCustomValues:
    def test_custom_all_fields(self):
        vad = VADConfig(mode="semantic_vad", eagerness="low")
        tools = [{"type": "function", "name": "test"}]
        config = RealtimeConfig(
            model="gpt-4o-realtime-preview",
            instructions="Custom instructions",
            voice="sage",
            language="en",
            vad=vad,
            temperature=1.0,
            max_response_output_tokens=4096,
            input_audio_transcription=False,
            modalities=["text"],
            tools=tools,
        )
        assert config.model == "gpt-4o-realtime-preview"
        assert config.instructions == "Custom instructions"
        assert config.voice == "sage"
        assert config.language == "en"
        assert config.vad.mode == "semantic_vad"
        assert config.temperature == 1.0
        assert config.max_response_output_tokens == 4096
        assert config.input_audio_transcription is False
        assert config.modalities == ["text"]
        assert config.tools == tools
