#!/usr/bin/env python3
"""
Standalone CLI Interface Module for Agent Interaction

This module provides a clean, text-based interface for interacting with
OpenAI Agents SDK agents. It handles conversation history, streaming responses,
and provides both interactive and single-query modes.

Example usage:
    from examples.cli_app import CLI
    from examples.agents.team import assisstant_agent

    # Interactive mode
    cli = CLI(agent=assisstant_agent)
    cli.run()

    # Single query mode
    response = await cli.query("Mi az idő?")
    print(response)
"""

import asyncio
import time
from typing import Any, Optional, Dict, List, Callable
from dataclasses import dataclass, field
from agents import Agent, Runner
from agents.voice.workflow import VoiceWorkflowHelper
from openai_apis._logging import get_logger, set_correlation_id, log_audit_event, log_performance


@dataclass
class CLIConfig:
    """Configuration for CLI interface behavior."""

    # Display settings
    prompt_prefix: str = "Felhasználó: "
    agent_prefix: str = "Ügynök: "
    separator: str = "---"

    # Commands
    help_command: str = "h"
    quit_command: str = "q"
    exit_keywords: List[str] = field(default_factory=lambda: ["exit", "kilépés"])

    # Messages
    welcome_message: Optional[str] = "Asszisztens indítása szöveges módban"
    goodbye_message: str = "Kilépés..."
    shutdown_message: str = "A program véget ért."

    # History display
    show_history_header: bool = True
    history_header: str = "--- Előzmények ---"
    history_footer: str = "------------------"
    history_item_format: str = "{index}. [{role}] {content}"

    # Help text
    help_text: str = (
        "\n---\n"
        "Parancsok:\n"
        "  <üzenet> - szöveges üzenet küldése\n"
        "  h - előzmények\n"
        "  q - kilépés\n"
        "---"
    )

    # Stream output settings
    enable_streaming: bool = True
    flush_on_chunk: bool = True


class ConversationHistory:
    """Manages conversation history in OpenAI SDK format."""

    def __init__(self) -> None:
        """Initialize an empty conversation history."""
        self._history: List[Dict[str, str]] = []

    def add_user_message(self, content: str) -> None:
        """Add a user message to the history."""
        self._history.append({"role": "user", "content": content})

    def add_assistant_message(self, content: str) -> None:
        """Add an assistant message to the history."""
        self._history.append({"role": "assistant", "content": content})

    def get_history(self) -> List[Dict[str, str]]:
        """Get the full conversation history."""
        return self._history.copy()

    def clear(self) -> None:
        """Clear the conversation history."""
        self._history.clear()

    def __len__(self) -> int:
        return len(self._history)

    def __getitem__(self, index: int) -> Dict[str, str]:
        return self._history[index]

    def __iter__(self):
        return iter(self._history)


class CLI:
    """Clean text-based interface for agent interaction."""

    def __init__(
        self,
        agent: Agent[Any],
        config: Optional[CLIConfig] = None,
        state: Optional[Dict[str, Any]] = None,
        on_error: Optional[Callable[[Exception], None]] = None,
        on_response_start: Optional[Callable[[], None]] = None,
        on_response_end: Optional[Callable[[str], None]] = None,
    ) -> None:
        """Initialize the CLI interface."""
        self.agent = agent
        self.config = config or CLIConfig()
        self.history = ConversationHistory()
        self.state = state or {}
        self._on_error = on_error
        self._on_response_start = on_response_start
        self._on_response_end = on_response_end
        self._running = False
        self.logger = get_logger(__name__)

        self.logger.info(
            f"CLI initialized for agent: {agent.name}",
            extra={"extra_data": {"agent_name": agent.name}}
        )

    async def query(
        self,
        message: str,
        add_to_history: bool = True,
        stream: bool = True,
    ) -> str:
        """Send a single query and get the response."""
        # Set correlation ID for this query
        corr_id = set_correlation_id()
        start_time = time.time()

        self.logger.info(
            f"Query started: {message[:50]}...",
            extra={"extra_data": {"message_length": len(message), "stream": stream}}
        )

        if add_to_history:
            self.history.add_user_message(message)

        try:
            context = self._get_context()
            input_messages = self.history.get_history() if add_to_history else [{"role": "user", "content": message}]
            result = Runner.run_streamed(self.agent, input_messages, context=context)

            full_response = ""
            if self._on_response_start:
                self._on_response_start()

            if stream and self.config.enable_streaming:
                async for chunk in VoiceWorkflowHelper.stream_text_from(result):
                    full_response += chunk
                    print(chunk, end="", flush=self.config.flush_on_chunk)
                print()
            else:
                async for chunk in VoiceWorkflowHelper.stream_text_from(result):
                    full_response += chunk

            if add_to_history:
                self.history.add_assistant_message(full_response)
            if self._on_response_end:
                self._on_response_end(full_response)

            # Log successful query
            duration_ms = (time.time() - start_time) * 1000
            self.logger.info(
                f"Query completed successfully",
                extra={"extra_data": {
                    "response_length": len(full_response),
                    "duration_ms": duration_ms
                }}
            )

            log_audit_event(
                event_type="cli_query",
                action="query_completed",
                details={
                    "message_length": len(message),
                    "response_length": len(full_response),
                    "duration_ms": duration_ms,
                    "stream_mode": stream
                },
                status="success"
            )

            log_performance(
                operation="cli_query",
                duration_ms=duration_ms,
                details={"message_length": len(message), "response_length": len(full_response)}
            )

            return full_response
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            self.logger.error(
                f"Query failed: {str(e)}",
                extra={"extra_data": {"error": str(e), "duration_ms": duration_ms}},
                exc_info=True
            )

            log_audit_event(
                event_type="cli_query",
                action="query_failed",
                details={"error": str(e), "duration_ms": duration_ms},
                status="error"
            )

            if self._on_error:
                self._on_error(e)
            raise

    async def run(self) -> None:
        """Run the interactive CLI session."""
        if self.config.welcome_message:
            print(self.config.welcome_message)

        self._running = True
        try:
            while self._running:
                print(self.config.help_text)
                user_input = input(self.config.prompt_prefix).strip()

                if user_input.lower() == self.config.quit_command:
                    print(self.config.goodbye_message)
                    break
                if user_input.lower() == self.config.help_command:
                    self._display_history()
                    continue
                if not user_input:
                    continue
                if user_input.lower() in self.config.exit_keywords:
                    print(self.config.goodbye_message)
                    break

                print(self.config.agent_prefix, end="", flush=True)
                try:
                    await self.query(message=user_input, add_to_history=True, stream=True)
                except Exception as e:
                    print(f"\n[HIBA] {type(e).__name__}: {e}")
                    if self._on_error:
                        self._on_error(e)
        finally:
            self._running = False
            print(self.config.shutdown_message)

    def run_sync(self) -> None:
        """Run the interactive CLI session synchronously."""
        asyncio.run(self.run())

    def get_history(self) -> List[Dict[str, str]]:
        return self.history.get_history()

    def clear_history(self) -> None:
        self.history.clear()

    def set_state(self, key: str, value: Any) -> None:
        self.state[key] = value

    def get_state(self, key: str, default: Any = None) -> Any:
        return self.state.get(key, default)

    def clear_state(self) -> None:
        self.state.clear()

    def stop(self) -> None:
        self._running = False

    def _display_history(self) -> None:
        if self.config.show_history_header:
            print(f"\n{self.config.history_header}")
        for i, msg in enumerate(self.history, start=1):
            formatted = self.config.history_item_format.format(
                index=i, role=msg["role"], content=msg["content"]
            )
            print(formatted)
        if self.config.show_history_header:
            print(f"{self.config.history_footer}\n")

    def _get_context(self) -> Dict[str, Any]:
        return dict(self.state)


def start_cli(agent: Agent[Any], config: Optional[CLIConfig] = None) -> None:
    """Start an interactive CLI session with the given agent."""
    cli = CLI(agent=agent, config=config)
    cli.run_sync()


if __name__ == "__main__":
    print("CLI module - import this to use with your agents")
    print("\nExample:")
    print("  from examples.cli_app import CLI")
    print("  from examples.agents.team import assisstant_agent")
    print("  cli = CLI(agent=assisstant_agent)")
    print("  cli.run_sync()")
