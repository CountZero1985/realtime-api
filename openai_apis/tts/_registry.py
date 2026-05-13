"""TTS provider registry."""
from typing import Dict, Type, Optional
from openai_apis.tts.base import BaseTTSProvider


class TTSRegistry:
    """Registry for TTS providers using factory pattern.

    Providers register themselves by name. The create() factory
    instantiates a provider from a TTSConfig based on its .provider field.
    """

    _providers: Dict[str, Type[BaseTTSProvider]] = {}

    @classmethod
    def register(cls, name: str, provider_class: Type[BaseTTSProvider]) -> None:
        """Register a TTS provider class.

        Args:
            name: Provider name (e.g., "openai", "elevenlabs").
            provider_class: Provider class inheriting from BaseTTSProvider.
        """
        cls._providers[name] = provider_class

    @classmethod
    def get(cls, name: str) -> Type[BaseTTSProvider]:
        """Get a registered TTS provider class by name.

        Args:
            name: Provider name.

        Returns:
            Provider class.

        Raises:
            KeyError: If provider is not registered.
        """
        if name not in cls._providers:
            available = ", ".join(sorted(cls._providers.keys()))
            raise KeyError(
                f"Unknown TTS provider: '{name}'. Available: {available}"
            )
        return cls._providers[name]

    @classmethod
    def create(cls, config: "TTSConfig") -> BaseTTSProvider:
        """Create a TTS provider instance from config.

        Uses config.provider to look up the provider class, then
        instantiates it with the config.

        Args:
            config: TTSConfig with provider field set.

        Returns:
            Instantiated TTS provider.

        Raises:
            KeyError: If config.provider is not registered.
        """
        provider_class = cls.get(config.provider)
        return provider_class(config=config)

    @classmethod
    def list_providers(cls) -> list[str]:
        """List all registered provider names.

        Returns:
            Sorted list of registered provider names.
        """
        return sorted(cls._providers.keys())


# Backward-compat free functions (delegate to class)
def register_provider(name: str, provider_class: Type[BaseTTSProvider]) -> None:
    """Register a TTS provider (backward-compat wrapper)."""
    TTSRegistry.register(name, provider_class)


def get_provider(name: str) -> Type[BaseTTSProvider]:
    """Get a registered TTS provider class (backward-compat wrapper)."""
    return TTSRegistry.get(name)


# Auto-register built-in providers
def _register_builtins() -> None:
    """Register built-in TTS providers."""
    from openai_apis.tts.openai_provider import OpenAITTSProvider
    from openai_apis.tts.elevenlabs_provider import ElevenLabsTTSProvider

    TTSRegistry.register("openai", OpenAITTSProvider)
    TTSRegistry.register("elevenlabs", ElevenLabsTTSProvider)


_register_builtins()
