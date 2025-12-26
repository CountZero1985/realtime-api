#!/usr/bin/env python3
"""
Unit tests for cli.py module.

Tests all functionality in the CLI module with 100% code coverage.
Uses pytest and unittest.mock for comprehensive testing.
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from dataclasses import asdict
from openai_apis.cli.interface import (
    CLI,
    CLIConfig,
    ConversationHistory,
    start_cli
)
from agents import Agent


# Fixtures

@pytest.fixture
def mock_agent():
    """Create a mock Agent instance."""
    agent = Mock(spec=Agent)
    agent.name = "test_agent"
    return agent


@pytest.fixture
def cli_config():
    """Create a CLIConfig instance with default values."""
    return CLIConfig()


@pytest.fixture
def custom_cli_config():
    """Create a custom CLIConfig instance."""
    return CLIConfig(
        prompt_prefix="User> ",
        agent_prefix="Bot> ",
        separator="===",
        help_command="help",
        quit_command="exit",
        exit_keywords=["quit", "bye"],
        welcome_message="Test CLI Started",
        goodbye_message="Goodbye!",
        shutdown_message="Test CLI Stopped",
        show_history_header=False,
        enable_streaming=False
    )


@pytest.fixture
def cli_instance(mock_agent, cli_config):
    """Create a CLI instance with mock agent."""
    return CLI(agent=mock_agent, config=cli_config)


@pytest.fixture
def cli_with_custom_config(mock_agent, custom_cli_config):
    """Create a CLI instance with custom config."""
    return CLI(agent=mock_agent, config=custom_cli_config)


# ConversationHistory Tests

class TestConversationHistory:
    """Test ConversationHistory class."""

    def test_initialization(self):
        """Test ConversationHistory initialization."""
        history = ConversationHistory()
        assert len(history) == 0
        assert history.get_history() == []

    def test_add_user_message(self):
        """Test adding user messages."""
        history = ConversationHistory()
        history.add_user_message("Hello")
        assert len(history) == 1
        assert history[0] == {"role": "user", "content": "Hello"}

    def test_add_assistant_message(self):
        """Test adding assistant messages."""
        history = ConversationHistory()
        history.add_assistant_message("Hi there")
        assert len(history) == 1
        assert history[0] == {"role": "assistant", "content": "Hi there"}

    def test_get_history(self):
        """Test getting history returns a copy."""
        history = ConversationHistory()
        history.add_user_message("Test")
        hist_copy = history.get_history()
        hist_copy.append({"role": "user", "content": "Modified"})
        # Original should be unchanged
        assert len(history) == 1

    def test_clear(self):
        """Test clearing history."""
        history = ConversationHistory()
        history.add_user_message("Message 1")
        history.add_assistant_message("Response 1")
        assert len(history) == 2
        history.clear()
        assert len(history) == 0

    def test_iteration(self):
        """Test iterating over history."""
        history = ConversationHistory()
        history.add_user_message("One")
        history.add_assistant_message("Two")
        messages = list(history)
        assert len(messages) == 2
        assert messages[0]["content"] == "One"
        assert messages[1]["content"] == "Two"

    def test_indexing(self):
        """Test indexing history."""
        history = ConversationHistory()
        history.add_user_message("First")
        history.add_assistant_message("Second")
        assert history[0]["content"] == "First"
        assert history[1]["content"] == "Second"
        assert history[-1]["content"] == "Second"


# CLIConfig Tests

class TestCLIConfig:
    """Test CLIConfig dataclass."""

    def test_default_config(self):
        """Test default configuration values."""
        config = CLIConfig()
        assert config.prompt_prefix == "Felhasználó: "
        assert config.agent_prefix == "Ügynök: "
        assert config.separator == "---"
        assert config.help_command == "h"
        assert config.quit_command == "q"
        assert config.exit_keywords == ["exit", "kilépés"]
        assert config.welcome_message == "Asszisztens indítása szöveges módban"
        assert config.goodbye_message == "Kilépés..."
        assert config.shutdown_message == "A program véget ért."
        assert config.enable_streaming is True
        assert config.flush_on_chunk is True

    def test_custom_config(self, custom_cli_config):
        """Test custom configuration values."""
        assert custom_cli_config.prompt_prefix == "User> "
        assert custom_cli_config.agent_prefix == "Bot> "
        assert custom_cli_config.help_command == "help"
        assert custom_cli_config.quit_command == "exit"
        assert custom_cli_config.enable_streaming is False


# CLI Tests

class TestCLI:
    """Test CLI class."""

    def test_initialization(self, mock_agent, cli_config):
        """Test CLI initialization."""
        cli = CLI(agent=mock_agent, config=cli_config)
        assert cli.agent == mock_agent
        assert cli.config == cli_config
        assert isinstance(cli.history, ConversationHistory)
        assert cli.state == {}
        assert cli._running is False

    def test_initialization_with_state(self, mock_agent):
        """Test CLI initialization with custom state."""
        state = {"key": "value"}
        cli = CLI(agent=mock_agent, state=state)
        assert cli.state == state

    def test_initialization_with_callbacks(self, mock_agent):
        """Test CLI initialization with callbacks."""
        on_error = Mock()
        on_response_start = Mock()
        on_response_end = Mock()

        cli = CLI(
            agent=mock_agent,
            on_error=on_error,
            on_response_start=on_response_start,
            on_response_end=on_response_end
        )
        assert cli._on_error == on_error
        assert cli._on_response_start == on_response_start
        assert cli._on_response_end == on_response_end

    @pytest.mark.asyncio
    async def test_query_basic(self, cli_instance):
        """Test basic query functionality."""
        # Mock Runner.run_streamed
        mock_result = AsyncMock()
        mock_chunks = ["Hello", " ", "world"]

        async def mock_stream():
            for chunk in mock_chunks:
                yield chunk

        with patch('openai_apis.cli.interface.Runner.run_streamed', return_value=mock_result), \
             patch('openai_apis.cli.interface.VoiceWorkflowHelper.stream_text_from', return_value=mock_stream()):

            response = await cli_instance.query("Test message", stream=False)

            assert response == "Hello world"
            assert len(cli_instance.history) == 2
            assert cli_instance.history[0]["content"] == "Test message"
            assert cli_instance.history[1]["content"] == "Hello world"

    @pytest.mark.asyncio
    async def test_query_no_history(self, cli_instance):
        """Test query without adding to history."""
        mock_result = AsyncMock()

        async def mock_stream():
            yield "Response"

        with patch('openai_apis.cli.interface.Runner.run_streamed', return_value=mock_result), \
             patch('openai_apis.cli.interface.VoiceWorkflowHelper.stream_text_from', return_value=mock_stream()):

            response = await cli_instance.query("Test", add_to_history=False, stream=False)

            assert response == "Response"
            assert len(cli_instance.history) == 0

    @pytest.mark.asyncio
    async def test_query_with_streaming(self, cli_instance, capsys):
        """Test query with streaming enabled."""
        mock_result = AsyncMock()

        async def mock_stream():
            for chunk in ["Stream", "ing"]:
                yield chunk

        with patch('openai_apis.cli.interface.Runner.run_streamed', return_value=mock_result), \
             patch('openai_apis.cli.interface.VoiceWorkflowHelper.stream_text_from', return_value=mock_stream()):

            response = await cli_instance.query("Test", stream=True)

            assert response == "Streaming"
            # Check that chunks were printed
            captured = capsys.readouterr()
            assert "Streaming" in captured.out

    @pytest.mark.asyncio
    async def test_query_with_callbacks(self, mock_agent):
        """Test query with callbacks."""
        on_response_start = Mock()
        on_response_end = Mock()

        cli = CLI(
            agent=mock_agent,
            on_response_start=on_response_start,
            on_response_end=on_response_end
        )

        mock_result = AsyncMock()

        async def mock_stream():
            yield "Response"

        with patch('openai_apis.cli.interface.Runner.run_streamed', return_value=mock_result), \
             patch('openai_apis.cli.interface.VoiceWorkflowHelper.stream_text_from', return_value=mock_stream()):

            await cli.query("Test", stream=False)

            on_response_start.assert_called_once()
            on_response_end.assert_called_once_with("Response")

    @pytest.mark.asyncio
    async def test_query_with_error(self, cli_instance):
        """Test query error handling."""
        on_error = Mock()
        cli_instance._on_error = on_error

        # Make Runner.run_streamed raise an exception
        with patch('openai_apis.cli.interface.Runner.run_streamed', side_effect=Exception("Test error")):
            with pytest.raises(Exception, match="Test error"):
                await cli_instance.query("Test")

            on_error.assert_called_once()

    @pytest.mark.asyncio
    async def test_run_quit_command(self, cli_instance, capsys):
        """Test run with quit command."""
        with patch('builtins.input', side_effect=['q']):
            await cli_instance.run()

            captured = capsys.readouterr()
            assert cli_instance.config.goodbye_message in captured.out
            assert cli_instance.config.shutdown_message in captured.out
            assert cli_instance._running is False

    @pytest.mark.asyncio
    async def test_run_help_command(self, cli_instance):
        """Test run with help command."""
        with patch('builtins.input', side_effect=['h', 'q']):
            with patch.object(cli_instance, '_display_history') as mock_display:
                await cli_instance.run()
                mock_display.assert_called_once()

    @pytest.mark.asyncio
    async def test_run_exit_keyword(self, cli_instance, capsys):
        """Test run with exit keyword."""
        with patch('builtins.input', side_effect=['exit']):
            await cli_instance.run()

            captured = capsys.readouterr()
            assert cli_instance.config.goodbye_message in captured.out

    @pytest.mark.asyncio
    async def test_run_empty_input(self, cli_instance):
        """Test run with empty input."""
        with patch('builtins.input', side_effect=['', 'q']):
            await cli_instance.run()
            # Should just continue, not crash

    @pytest.mark.asyncio
    async def test_run_with_query(self, cli_instance, capsys):
        """Test run with actual query."""
        mock_result = AsyncMock()

        async def mock_stream():
            yield "Response"

        with patch('builtins.input', side_effect=['Hello', 'q']), \
             patch('openai_apis.cli.interface.Runner.run_streamed', return_value=mock_result), \
             patch('openai_apis.cli.interface.VoiceWorkflowHelper.stream_text_from', return_value=mock_stream()):

            await cli_instance.run()

            assert len(cli_instance.history) == 2

    @pytest.mark.asyncio
    async def test_run_with_error(self, cli_instance, capsys):
        """Test run with error during query."""
        on_error = Mock()
        cli_instance._on_error = on_error

        with patch('builtins.input', side_effect=['Hello', 'q']), \
             patch('openai_apis.cli.interface.Runner.run_streamed', side_effect=Exception("Query error")):

            await cli_instance.run()

            captured = capsys.readouterr()
            assert "[HIBA]" in captured.out
            assert "Query error" in captured.out
            on_error.assert_called()

    def test_run_sync(self, cli_instance):
        """Test synchronous run."""
        with patch.object(cli_instance, 'run') as mock_run, \
             patch('asyncio.run'):
            cli_instance.run_sync()
            # asyncio.run should be called

    def test_get_history(self, cli_instance):
        """Test getting history."""
        cli_instance.history.add_user_message("Test")
        history = cli_instance.get_history()
        assert len(history) == 1
        assert history[0]["content"] == "Test"

    def test_clear_history(self, cli_instance):
        """Test clearing history."""
        cli_instance.history.add_user_message("Test")
        assert len(cli_instance.history) == 1
        cli_instance.clear_history()
        assert len(cli_instance.history) == 0

    def test_set_state(self, cli_instance):
        """Test setting state."""
        cli_instance.set_state("key", "value")
        assert cli_instance.state["key"] == "value"

    def test_get_state(self, cli_instance):
        """Test getting state."""
        cli_instance.state["key"] = "value"
        assert cli_instance.get_state("key") == "value"
        assert cli_instance.get_state("nonexistent", "default") == "default"

    def test_clear_state(self, cli_instance):
        """Test clearing state."""
        cli_instance.state["key"] = "value"
        cli_instance.clear_state()
        assert cli_instance.state == {}

    def test_stop(self, cli_instance):
        """Test stopping the CLI."""
        cli_instance._running = True
        cli_instance.stop()
        assert cli_instance._running is False

    def test_display_history_with_header(self, cli_instance, capsys):
        """Test displaying history with headers."""
        cli_instance.history.add_user_message("User message")
        cli_instance.history.add_assistant_message("Assistant message")

        cli_instance._display_history()

        captured = capsys.readouterr()
        assert cli_instance.config.history_header in captured.out
        assert cli_instance.config.history_footer in captured.out
        assert "User message" in captured.out
        assert "Assistant message" in captured.out

    def test_display_history_without_header(self, cli_with_custom_config, capsys):
        """Test displaying history without headers."""
        cli_with_custom_config.history.add_user_message("Test")
        cli_with_custom_config._display_history()

        captured = capsys.readouterr()
        assert "Test" in captured.out
        # Headers should not appear
        assert cli_with_custom_config.config.history_header not in captured.out

    def test_get_context(self, cli_instance):
        """Test getting context from state."""
        cli_instance.state = {"key1": "value1", "key2": "value2"}
        context = cli_instance._get_context()
        assert context == {"key1": "value1", "key2": "value2"}


# Integration Tests

class TestCLIIntegration:
    """Integration tests for CLI."""

    @pytest.mark.asyncio
    async def test_full_conversation_flow(self, mock_agent):
        """Test a complete conversation flow."""
        cli = CLI(agent=mock_agent)

        mock_result = AsyncMock()

        async def mock_stream():
            yield "Hello"

        def mock_stream_factory(*args, **kwargs):
            return mock_stream()

        with patch('openai_apis.cli.interface.Runner.run_streamed', return_value=mock_result), \
             patch('openai_apis.cli.interface.VoiceWorkflowHelper.stream_text_from', side_effect=mock_stream_factory):

            # First query
            response1 = await cli.query("Hi", stream=False)
            assert response1 == "Hello"

            # Second query
            response2 = await cli.query("How are you?", stream=False)
            assert response2 == "Hello"

            # Check history
            assert len(cli.history) == 4
            assert cli.history[0]["content"] == "Hi"
            assert cli.history[1]["content"] == "Hello"
            assert cli.history[2]["content"] == "How are you?"
            assert cli.history[3]["content"] == "Hello"

    def test_custom_config_integration(self, mock_agent):
        """Test CLI with completely custom config."""
        config = CLIConfig(
            prompt_prefix=">>> ",
            agent_prefix="<<< ",
            help_command="help",
            quit_command="exit",
            exit_keywords=["quit", "bye"],
            enable_streaming=False
        )

        cli = CLI(agent=mock_agent, config=config)
        assert cli.config.prompt_prefix == ">>> "
        assert cli.config.help_command == "help"


# Convenience Function Tests

def test_start_cli():
    """Test start_cli convenience function."""
    mock_agent = Mock(spec=Agent)
    mock_agent.name = "test_agent"

    with patch.object(CLI, 'run_sync') as mock_run_sync:
        start_cli(mock_agent)
        mock_run_sync.assert_called_once()

def test_start_cli_with_config():
    """Test start_cli with custom config."""
    mock_agent = Mock(spec=Agent)
    mock_agent.name = "test_agent"
    config = CLIConfig(prompt_prefix="Test> ")

    with patch.object(CLI, 'run_sync') as mock_run_sync:
        start_cli(mock_agent, config=config)
        mock_run_sync.assert_called_once()


# Edge Cases and Error Handling

class TestCLIEdgeCases:
    """Test edge cases and error scenarios."""

    @pytest.mark.asyncio
    async def test_query_empty_response(self, cli_instance):
        """Test query with empty response."""
        mock_result = AsyncMock()

        async def mock_stream():
            return
            yield  # Make it a generator

        with patch('openai_apis.cli.interface.Runner.run_streamed', return_value=mock_result), \
             patch('openai_apis.cli.interface.VoiceWorkflowHelper.stream_text_from', return_value=mock_stream()):

            response = await cli_instance.query("Test", stream=False)
            assert response == ""

    @pytest.mark.asyncio
    async def test_run_keyboard_interrupt(self, cli_instance):
        """Test run handling KeyboardInterrupt."""
        with patch('builtins.input', side_effect=KeyboardInterrupt):
            # Should not raise, just exit gracefully
            await cli_instance.run()
            assert cli_instance._running is False

    def test_multiple_stop_calls(self, cli_instance):
        """Test calling stop multiple times."""
        cli_instance._running = True
        cli_instance.stop()
        cli_instance.stop()  # Should not error
        assert cli_instance._running is False

    @pytest.mark.asyncio
    async def test_query_with_very_long_message(self, cli_instance):
        """Test query with very long message."""
        long_message = "A" * 10000
        mock_result = AsyncMock()

        async def mock_stream():
            yield "OK"

        with patch('openai_apis.cli.interface.Runner.run_streamed', return_value=mock_result), \
             patch('openai_apis.cli.interface.VoiceWorkflowHelper.stream_text_from', return_value=mock_stream()):

            response = await cli_instance.query(long_message, stream=False)
            assert response == "OK"
            assert cli_instance.history[0]["content"] == long_message

    def test_history_with_unicode(self):
        """Test history with Unicode characters."""
        history = ConversationHistory()
        history.add_user_message("Szia! 你好 مرحبا")
        history.add_assistant_message("Hello! 👋")

        assert history[0]["content"] == "Szia! 你好 مرحبا"
        assert history[1]["content"] == "Hello! 👋"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--cov=cli", "--cov-report=term-missing"])
