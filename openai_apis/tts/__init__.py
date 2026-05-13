"""Text-to-Speech (TTS) API - Provider-based TTS system."""
from openai_apis.tts.openai_provider import OpenAITTSProvider, TTSSynthesisError
from openai_apis.tts.elevenlabs_provider import ElevenLabsTTSProvider
from openai_apis.tts.config import TTSConfig
from openai_apis.tts.base import BaseTTSProvider
from openai_apis.tts._registry import TTSRegistry, register_provider, get_provider

# Backward compatibility alias
TTSAPI = OpenAITTSProvider

__all__ = [
    "OpenAITTSProvider",
    "ElevenLabsTTSProvider",
    "TTSAPI",
    "TTSConfig",
    "BaseTTSProvider",
    "TTSSynthesisError",
    "TTSRegistry",
    "register_provider",
    "get_provider",
]
