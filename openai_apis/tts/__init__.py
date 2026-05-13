"""Text-to-Speech (TTS) API - Provider-based TTS system."""
from openai_apis.tts.openai_provider import OpenAITTSProvider, TTSSynthesisError
from openai_apis.tts.config import TTSConfig
from openai_apis.tts.base import BaseTTSProvider
from openai_apis.tts._registry import register_provider, get_provider

# Backward compatibility alias
TTSAPI = OpenAITTSProvider

__all__ = [
    "OpenAITTSProvider",
    "TTSAPI",
    "TTSConfig",
    "BaseTTSProvider",
    "TTSSynthesisError",
    "register_provider",
    "get_provider",
]
