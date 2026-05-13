"""TTS provider registry."""
from typing import Dict, Type
from openai_apis.tts.base import BaseTTSProvider

_providers: Dict[str, Type[BaseTTSProvider]] = {}


def register_provider(name: str, provider_class: Type[BaseTTSProvider]) -> None:
    """
    Register a TTS provider.

    Args:
        name: Provider name (e.g., "openai", "elevenlabs").
        provider_class: Provider class inheriting from BaseTTSProvider.
    """
    _providers[name] = provider_class


def get_provider(name: str) -> Type[BaseTTSProvider]:
    """
    Get a registered TTS provider class.

    Args:
        name: Provider name.

    Returns:
        Provider class.

    Raises:
        KeyError: If provider is not registered.
    """
    if name not in _providers:
        raise KeyError(f"Unknown TTS provider: {name}")
    return _providers[name]


# Auto-register built-in providers
def _register_builtins() -> None:
    """Register built-in TTS providers."""
    from openai_apis.tts.openai_provider import OpenAITTSProvider
    register_provider("openai", OpenAITTSProvider)


_register_builtins()
