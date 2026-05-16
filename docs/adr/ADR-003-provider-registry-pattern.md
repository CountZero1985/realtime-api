# ADR-003: TTS Provider Registry Pattern

## Status
Accepted

## Context
The TTS module needs to support multiple providers (OpenAI, ElevenLabs, potentially more). We considered several approaches:

1. **Direct instantiation** — caller chooses which provider class to use
2. **Simple factory function** — `create_tts(provider_name)` with if/else logic
3. **Class-based registry** — providers register themselves, factory creates instances from config

Direct instantiation couples callers to specific implementations. A simple factory requires modifying factory code for each new provider. We needed an approach that allows adding providers without modifying existing code.

## Decision
Implement a class-based registry pattern via `TTSRegistry`:

```python
class TTSRegistry:
    _providers: dict[str, type[BaseTTSProvider]] = {}

    @classmethod
    def register(cls, name: str, provider_class: type) -> None: ...

    @classmethod
    def get(cls, name: str) -> type: ...

    @classmethod
    def create(cls, config: TTSConfig) -> BaseTTSProvider: ...

    @classmethod
    def list_providers(cls) -> list[str]: ...
```

Key design choices:
- **Class methods** on `TTSRegistry` (no instance needed, acts as singleton)
- **`BaseTTSProvider`** abstract base class defines the provider interface (`synthesize`, `synthesize_stream`, `synthesize_to_file`, `provider_name`, `supported_voices`)
- **`TTSConfig.provider`** field selects which registered provider to instantiate
- **Built-in registration** in `_register_builtins()` for OpenAI and ElevenLabs providers
- **Validation at config time** — `TTSConfig.__post_init__` validates voice against provider's supported voices

## Consequences

**Easier:**
- Adding new TTS providers (implement `BaseTTSProvider`, call `TTSRegistry.register()`)
- Switching providers via configuration (change `TTSConfig.provider` field)
- Validating configuration at construction time
- Listing available providers for UI/CLI

**More difficult:**
- Provider classes must be imported/registered before use (registration order matters)
- Class-level state (`_providers` dict) makes testing stateful (need cleanup between tests)
- Provider interface is fixed — all providers must implement the same abstract methods
