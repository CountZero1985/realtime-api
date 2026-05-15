#!/usr/bin/env python3
"""
Verification script for the minimal public API (issue #33).

This script verifies that:
1. All __all__ items are importable from openai_apis
2. __all__ contains exactly 15 items as specified
3. Removed items are NOT importable from top level
4. Removed items ARE still importable from submodules
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent))

def test_all_items_importable():
    """Test that all items in __all__ are importable."""
    print("✓ Testing __all__ items are importable...")

    # Import from top level
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

    print("  ✓ All __all__ items are importable")
    return True


def test_all_length():
    """Test that __all__ contains exactly 15 items."""
    print("✓ Testing __all__ length...")

    import openai_apis

    expected = 15
    actual = len(openai_apis.__all__)

    if actual != expected:
        print(f"  ✗ Expected {expected} items in __all__, got {actual}")
        print(f"    Items: {openai_apis.__all__}")
        return False

    print(f"  ✓ __all__ contains exactly {expected} items")
    return True


def test_removed_items_not_in_top_level():
    """Test that removed items are NOT importable from top level."""
    print("✓ Testing removed items are NOT in top level...")

    removed_items = [
        "TranscriptionAPI",
        "TTSAPI",
        "OpenAITTSProvider",
        "BaseTTSProvider",
        "ElevenLabsTTSProvider",
        "TTSSynthesisError",
        "register_provider",
        "get_provider",
        "RealtimeVoiceAPI",
        "RealtimeAgentState",
        "TranscriptDelta",
        "TranscriptCompleted",
        "ErrorEvent",
        "AudioDelta",
        "AudioDone",
        "ConversationItem",
        "InvalidStateTransition",
        "BaseConfig",
        "AuditEvent",
        "get_logger",
        "set_correlation_id",
        "log_audit_event",
        "log_performance",
        "log_api_call",
        "setup_logging",
        "FileSystemPlugin",
        "GmailPlugin",
    ]

    import openai_apis

    failed = []
    for item in removed_items:
        if hasattr(openai_apis, item):
            failed.append(item)

    if failed:
        print(f"  ✗ These items should not be in top level: {failed}")
        return False

    print(f"  ✓ All {len(removed_items)} removed items are correctly absent")
    return True


def test_removed_items_still_in_submodules():
    """Test that removed items ARE still importable from submodules."""
    print("✓ Testing removed items are still in submodules...")

    # Test transcription submodule
    from openai_apis.transcription import TranscriptionAPI, TranscriptionConfig
    assert TranscriptionAPI is not None
    print("  ✓ TranscriptionAPI still in openai_apis.transcription")

    # Test TTS submodule
    from openai_apis.tts import (
        TTSAPI, OpenAITTSProvider, BaseTTSProvider,
        ElevenLabsTTSProvider, TTSSynthesisError,
        register_provider, get_provider
    )
    assert TTSAPI is not None
    assert OpenAITTSProvider is not None
    assert BaseTTSProvider is not None
    print("  ✓ TTS provider implementations still in openai_apis.tts")

    # Test realtime submodule
    from openai_apis.realtime import RealtimeVoiceAPI, RealtimeAgentState
    assert RealtimeVoiceAPI is not None
    assert RealtimeAgentState is not None
    print("  ✓ RealtimeVoiceAPI still in openai_apis.realtime")

    # Test realtime events
    from openai_apis.realtime.events import (
        TranscriptDelta, TranscriptCompleted, ErrorEvent,
        AudioDelta, AudioDone, ConversationItem
    )
    assert TranscriptDelta is not None
    print("  ✓ Event types still in openai_apis.realtime.events")

    # Test internal modules
    from openai_apis._session import InvalidStateTransition
    from openai_apis._config import BaseConfig
    from openai_apis._logging import AuditEvent, get_logger
    assert InvalidStateTransition is not None
    assert BaseConfig is not None
    assert AuditEvent is not None
    print("  ✓ Internal classes still in private modules")

    # Test MCP plugins
    from openai_apis.mcp import FileSystemPlugin, GmailPlugin
    assert FileSystemPlugin is not None
    assert GmailPlugin is not None
    print("  ✓ Specific plugins still in openai_apis.mcp")

    return True


def test_wildcard_import():
    """Test that 'from openai_apis import *' exposes only __all__ items."""
    print("✓ Testing wildcard import...")

    # Create a namespace for wildcard import
    namespace = {}
    exec("from openai_apis import *", namespace)

    # Remove builtins
    namespace = {k: v for k, v in namespace.items() if not k.startswith("__")}

    import openai_apis
    expected_set = set(openai_apis.__all__)
    actual_set = set(namespace.keys())

    if actual_set != expected_set:
        print(f"  ✗ Wildcard import mismatch:")
        print(f"    Expected: {expected_set}")
        print(f"    Actual: {actual_set}")
        print(f"    Missing: {expected_set - actual_set}")
        print(f"    Extra: {actual_set - expected_set}")
        return False

    print(f"  ✓ Wildcard import exposes exactly __all__ items")
    return True


def main():
    """Run all verification tests."""
    print("\n" + "="*70)
    print("Verifying openai_apis public API (issue #33)")
    print("="*70 + "\n")

    tests = [
        test_all_items_importable,
        test_all_length,
        test_removed_items_not_in_top_level,
        test_removed_items_still_in_submodules,
        test_wildcard_import,
    ]

    results = []
    for test in tests:
        try:
            results.append(test())
            print()
        except Exception as e:
            print(f"  ✗ Test failed with exception: {e}")
            import traceback
            traceback.print_exc()
            results.append(False)
            print()

    print("="*70)
    if all(results):
        print("✓ ALL TESTS PASSED")
        print("="*70 + "\n")
        return 0
    else:
        print("✗ SOME TESTS FAILED")
        print("="*70 + "\n")
        return 1


if __name__ == "__main__":
    sys.exit(main())
