"""Text-to-Speech (TTS) API - Provider-based TTS system."""
from openai_apis.tts.openai_provider import OpenAITTSProvider
from openai_apis.tts.config import TTSConfig
from openai_apis.tts.base import BaseTTSProvider

# Backward compatibility alias
TTSAPI = OpenAITTSProvider

__all__ = ["OpenAITTSProvider", "TTSAPI", "TTSConfig", "BaseTTSProvider"]
