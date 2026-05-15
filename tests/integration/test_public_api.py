#!/usr/bin/env python3
"""
Integration tests for the public API surface (issue #33).

Tests that verify the minimal public API is correctly exposed from openai_apis
and that imports work as expected in real-world usage scenarios.
"""

import pytest
import sys
from pathlib import Path


class TestPublicAPIImports:
    """Test that public API imports work correctly."""

    def test_top_level_import_all_items(self):
        """Test importing all __all__ items from top level."""
        # Import all public API items
        from openai_apis import (
            # Core sessions
            TranscriptionSession,
            TranscriptionConfig,
            RealtimeSession,
            RealtimeConfig,
            TTSProvider,
            TTSConfig,
            TTSRegistry,
            # Shared config
            AudioFormat,
            VADConfig,
            # Tools & plugins
            ToolRegistry,
            MCPPlugin,
            MCPPluginManager,
            # Session base (advanced usage)
            BaseSession,
            SessionState,
            SessionAuditLog,
        )

        # Verify all imports are not None
        assert TranscriptionSession is not None
        assert TranscriptionConfig is not None
        assert RealtimeSession is not None
        assert RealtimeConfig is not None
        assert TTSProvider is not None
        assert TTSConfig is not None
        assert TTSRegistry is not None
        assert AudioFormat is not None
        assert VADConfig is not None
        assert ToolRegistry is not None
        assert MCPPlugin is not None
        assert MCPPluginManager is not None
        assert BaseSession is not None
        assert SessionState is not None
        assert SessionAuditLog is not None

    def test_wildcard_import(self):
        """Test that wildcard import exposes only __all__ items."""
        # Create a clean namespace
        namespace = {}
        exec("from openai_apis import *", namespace)

        # Remove builtins
        imported_names = {k for k in namespace.keys() if not k.startswith("__")}

        # Expected public API items
        expected_names = {
            "TranscriptionSession",
            "TranscriptionConfig",
            "RealtimeSession",
            "RealtimeConfig",
            "TTSProvider",
            "TTSConfig",
            "TTSRegistry",
            "AudioFormat",
            "VADConfig",
            "ToolRegistry",
            "MCPPlugin",
            "MCPPluginManager",
            "BaseSession",
            "SessionState",
            "SessionAuditLog",
        }

        assert imported_names == expected_names, (
            f"Wildcard import mismatch:\n"
            f"  Expected: {expected_names}\n"
            f"  Got: {imported_names}\n"
            f"  Missing: {expected_names - imported_names}\n"
            f"  Extra: {imported_names - expected_names}"
        )

    def test_all_list_length(self):
        """Test that __all__ contains exactly 15 items."""
        import openai_apis

        expected_length = 15
        actual_length = len(openai_apis.__all__)

        assert actual_length == expected_length, (
            f"Expected __all__ to have {expected_length} items, "
            f"but got {actual_length}: {openai_apis.__all__}"
        )

    def test_version_string_exists(self):
        """Test that __version__ is defined."""
        import openai_apis

        assert hasattr(openai_apis, "__version__")
        assert isinstance(openai_apis.__version__, str)
        assert openai_apis.__version__ == "0.1.0"


class TestRemovedItemsNotInTopLevel:
    """Test that removed items are NOT accessible from top level."""

    def test_legacy_api_classes_removed(self):
        """Test that legacy API classes are not in top level."""
        import openai_apis

        removed_items = [
            "TranscriptionAPI",
            "TTSAPI",
            "RealtimeVoiceAPI",
        ]

        for item in removed_items:
            assert not hasattr(openai_apis, item), (
                f"{item} should not be in top-level openai_apis module"
            )

    def test_provider_implementations_removed(self):
        """Test that specific TTS provider implementations are not in top level."""
        import openai_apis

        removed_items = [
            "OpenAITTSProvider",
            "BaseTTSProvider",
            "ElevenLabsTTSProvider",
        ]

        for item in removed_items:
            assert not hasattr(openai_apis, item), (
                f"{item} should not be in top-level openai_apis module"
            )

    def test_internal_classes_removed(self):
        """Test that internal classes are not in top level."""
        import openai_apis

        removed_items = [
            "BaseConfig",
            "AuditEvent",
            "InvalidStateTransition",
            "get_logger",
            "set_correlation_id",
            "log_audit_event",
            "log_performance",
        ]

        for item in removed_items:
            assert not hasattr(openai_apis, item), (
                f"{item} should not be in top-level openai_apis module"
            )

    def test_event_classes_removed(self):
        """Test that event classes are not in top level."""
        import openai_apis

        removed_items = [
            "TranscriptDelta",
            "TranscriptCompleted",
            "ErrorEvent",
            "AudioDelta",
            "AudioDone",
            "ConversationItem",
        ]

        for item in removed_items:
            assert not hasattr(openai_apis, item), (
                f"{item} should not be in top-level openai_apis module"
            )

    def test_specific_plugins_removed(self):
        """Test that specific plugin implementations are not in top level."""
        import openai_apis

        removed_items = [
            "FileSystemPlugin",
            "GmailPlugin",
        ]

        for item in removed_items:
            assert not hasattr(openai_apis, item), (
                f"{item} should not be in top-level openai_apis module"
            )


class TestSubmoduleAccessibility:
    """Test that removed items are still accessible from submodules."""

    def test_transcription_submodule_access(self):
        """Test that transcription items are accessible from submodule."""
        from openai_apis.transcription import TranscriptionAPI, TranscriptionConfig

        assert TranscriptionAPI is not None
        assert TranscriptionConfig is not None

        # TranscriptionAPI should be a different name for TranscriptionSession
        from openai_apis import TranscriptionSession

        # They might be the same class or different, but both should exist
        assert TranscriptionAPI is not None
        assert TranscriptionSession is not None

    def test_tts_submodule_access(self):
        """Test that TTS provider implementations are accessible from submodule."""
        from openai_apis.tts import (
            TTSAPI,
            OpenAITTSProvider,
            BaseTTSProvider,
            TTSProvider,
            ElevenLabsTTSProvider,
            TTSSynthesisError,
            register_provider,
            get_provider,
        )

        assert TTSAPI is not None
        assert OpenAITTSProvider is not None
        assert BaseTTSProvider is not None
        assert TTSProvider is not None
        assert ElevenLabsTTSProvider is not None
        assert TTSSynthesisError is not None
        assert register_provider is not None
        assert get_provider is not None

        # TTSProvider should be an alias for BaseTTSProvider
        assert TTSProvider is BaseTTSProvider

    def test_realtime_submodule_access(self):
        """Test that realtime items are accessible from submodule."""
        from openai_apis.realtime import RealtimeVoiceAPI, RealtimeAgentState

        assert RealtimeVoiceAPI is not None
        assert RealtimeAgentState is not None

    def test_realtime_events_submodule_access(self):
        """Test that event classes are accessible from realtime.events."""
        from openai_apis.realtime.events import (
            TranscriptDelta,
            TranscriptCompleted,
            ErrorEvent,
            AudioDelta,
            AudioDone,
            ConversationItem,
        )

        assert TranscriptDelta is not None
        assert TranscriptCompleted is not None
        assert ErrorEvent is not None
        assert AudioDelta is not None
        assert AudioDone is not None
        assert ConversationItem is not None

    def test_internal_modules_access(self):
        """Test that internal classes are accessible from private modules."""
        from openai_apis._session import InvalidStateTransition
        from openai_apis._config import BaseConfig
        from openai_apis._logging import AuditEvent, get_logger

        assert InvalidStateTransition is not None
        assert BaseConfig is not None
        assert AuditEvent is not None
        assert get_logger is not None

    def test_mcp_specific_plugins_access(self):
        """Test that specific plugins are accessible from mcp submodule."""
        from openai_apis.mcp import FileSystemPlugin, GmailPlugin

        assert FileSystemPlugin is not None
        assert GmailPlugin is not None


class TestRealWorldUsageScenarios:
    """Test real-world usage scenarios with the new public API."""

    def test_transcription_session_creation(self):
        """Test creating a transcription session with public API."""
        from openai_apis import TranscriptionSession, TranscriptionConfig

        # Create config
        config = TranscriptionConfig(language="hu", model="gpt-4o-mini-transcribe")

        # Create session (don't connect, just test instantiation)
        session = TranscriptionSession(config=config)

        assert session is not None
        # Note: config is stored as _config (private attribute)
        assert session._config.language == "hu"
        assert session._config.model == "gpt-4o-mini-transcribe"

    def test_realtime_session_creation(self):
        """Test creating a realtime session with public API."""
        from openai_apis import RealtimeSession, RealtimeConfig

        # Create config
        config = RealtimeConfig(voice="ash", language="hu")

        # Create session (don't connect, just test instantiation)
        session = RealtimeSession(config=config)

        assert session is not None
        # Note: config is stored as _config (private attribute)
        assert session._config.voice == "ash"
        assert session._config.language == "hu"

    def test_tts_provider_creation_via_registry(self):
        """Test creating TTS provider via registry with public API."""
        from openai_apis import TTSRegistry, TTSConfig

        # Create config
        config = TTSConfig(provider="openai", voice="sage", speed=1.0)

        # Create provider via registry
        provider = TTSRegistry.create(config)

        assert provider is not None
        assert provider.config.voice == "sage"
        assert provider.config.speed == 1.0

    def test_audio_format_configuration(self):
        """Test using AudioFormat with public API."""
        from openai_apis import AudioFormat, TranscriptionConfig

        # Create custom audio format
        audio_format = AudioFormat(sample_rate=48000, channels=2, dtype="float32")

        # Use with config
        config = TranscriptionConfig(audio_format=audio_format)

        assert config.audio_format.sample_rate == 48000
        assert config.audio_format.channels == 2
        assert config.audio_format.dtype == "float32"

    def test_vad_configuration(self):
        """Test using VADConfig with public API."""
        from openai_apis import VADConfig, TranscriptionConfig

        # Create VAD config
        vad = VADConfig(mode="server_vad", threshold=0.7, silence_duration_ms=800)

        # Use with config
        config = TranscriptionConfig(vad=vad)

        assert config.vad.mode == "server_vad"
        assert config.vad.threshold == 0.7
        assert config.vad.silence_duration_ms == 800

    def test_session_state_enum(self):
        """Test using SessionState enum with public API."""
        from openai_apis import SessionState

        # Verify enum values
        assert hasattr(SessionState, "CREATED")
        assert hasattr(SessionState, "CONNECTING")
        assert hasattr(SessionState, "CONNECTED")
        assert hasattr(SessionState, "DISCONNECTING")
        assert hasattr(SessionState, "CLOSED")

    def test_tool_registry_access(self):
        """Test accessing ToolRegistry from public API."""
        from openai_apis import ToolRegistry

        # Verify ToolRegistry is accessible
        assert ToolRegistry is not None
        assert hasattr(ToolRegistry, "register")
        # Note: ToolRegistry uses 'execute' method, not 'get_tool'
        assert hasattr(ToolRegistry, "execute")

    def test_mcp_plugin_and_manager(self):
        """Test accessing MCP plugin infrastructure from public API."""
        from openai_apis import MCPPlugin, MCPPluginManager

        # Verify classes are accessible
        assert MCPPlugin is not None
        assert MCPPluginManager is not None


class TestDocstringExamples:
    """Test that examples in the module docstring work."""

    def test_docstring_transcription_example(self):
        """Test transcription example from module docstring."""
        from openai_apis import TranscriptionSession, TranscriptionConfig

        # Example from docstring (without actual async execution)
        config = TranscriptionConfig(language="hu")
        session = TranscriptionSession(config)

        assert session is not None
        assert session._config.language == "hu"

    def test_docstring_realtime_example(self):
        """Test realtime example from module docstring."""
        from openai_apis import RealtimeSession, RealtimeConfig

        # Example from docstring (without actual async execution)
        config = RealtimeConfig(voice="ash")
        session = RealtimeSession(config)

        assert session is not None
        assert session._config.voice == "ash"

    def test_docstring_tts_example(self):
        """Test TTS example from module docstring."""
        from openai_apis import TTSRegistry, TTSConfig

        # Example from docstring (without actual synthesis)
        config = TTSConfig(voice="sage")
        tts = TTSRegistry.create(config)

        assert tts is not None
        assert tts.config.voice == "sage"


class TestBackwardCompatibilityAliases:
    """Test backward compatibility aliases in submodules."""

    def test_tts_provider_alias(self):
        """Test that TTSProvider is an alias for BaseTTSProvider."""
        from openai_apis import TTSProvider
        from openai_apis.tts import BaseTTSProvider

        # TTSProvider should be the same as BaseTTSProvider
        assert TTSProvider is BaseTTSProvider

    def test_ttsapi_alias_in_submodule(self):
        """Test that TTSAPI is still available in tts submodule."""
        from openai_apis.tts import TTSAPI, OpenAITTSProvider

        # TTSAPI should be an alias for OpenAITTSProvider
        assert TTSAPI is OpenAITTSProvider


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
