#!/usr/bin/env python3
"""
Interactive CLI Application — openai_apis demo

This module provides both:
1. Legacy text-based agent interface (CLI, CLIConfig, ConversationHistory) for backward compatibility
2. Multi-mode interactive CLI demonstrating TranscriptionSession, RealtimeSession, and TTSProvider

Usage (multi-mode):
    python examples/cli_app.py transcription --language hu
    python examples/cli_app.py voice --language hu --voice ash
    python examples/cli_app.py tts --language hu --voice sage

Usage (legacy agent CLI):
    from examples.cli_app import CLI
    from examples.agents.team import assisstant_agent
    cli = CLI(agent=assisstant_agent)
    cli.run_sync()
"""

import sys
import asyncio
import argparse
import time
import numpy as np
from typing import Any, Optional, Dict, List, Callable
from dataclasses import dataclass, field
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Import only what's needed for multi-mode CLI at module level
from openai_apis._logging import get_logger, set_correlation_id, log_audit_event, log_performance
from openai_apis import (
    TranscriptionSession, TranscriptionConfig,
    RealtimeSession, RealtimeConfig,
    TTSConfig, TTSRegistry,
    VADConfig, AudioFormat,
    SessionAuditLog,
)
from openai_apis.realtime.events import AudioDelta, AudioDone, TranscriptCompleted
from examples.utils.audio_io import record_audio, AudioPlayer
from dotenv import load_dotenv

load_dotenv()

# Lazy imports for legacy CLI classes to avoid circular dependencies
# These are imported inside functions that need them


# ============================================================================
# Legacy CLI classes for backward compatibility with cli_agent.py
# ============================================================================

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
        agent: "Any",  # Type hint as string to avoid circular import
        config: Optional[CLIConfig] = None,
        state: Optional[Dict[str, Any]] = None,
        on_error: Optional[Callable[[Exception], None]] = None,
        on_response_start: Optional[Callable[[], None]] = None,
        on_response_end: Optional[Callable[[str], None]] = None,
    ) -> None:
        """Initialize the CLI interface."""
        # Lazy import to avoid circular dependencies
        from agents import Agent

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
        # Lazy imports to avoid circular dependencies
        from agents import Runner
        from agents.voice.workflow import VoiceWorkflowHelper

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


def start_cli(agent: "Any", config: Optional[CLIConfig] = None) -> None:
    """Start an interactive CLI session with the given agent."""
    cli = CLI(agent=agent, config=config)
    cli.run_sync()


# ============================================================================
# New multi-mode CLI functions
# ============================================================================

def export_audit_log(audit_log: SessionAuditLog, mode: str) -> None:
    """Export session audit log to JSON file."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"audit_{mode}_{timestamp}.json"
    logs_dir = Path("logs")
    logs_dir.mkdir(exist_ok=True)
    path = logs_dir / filename
    audit_log.export_to_file(path)
    print(f"[Audit log mentve: {path}]")


async def run_transcription_mode(language: str) -> None:
    """Run transcription mode: microphone → TranscriptionSession → text output."""
    print(f"\n=== Transzkripció mód ({language}) ===")
    print("Nyomj <Enter>-t a felvételhez, vagy 'q' a kilépéshez.")

    config = TranscriptionConfig(
        language=language,
        vad=VADConfig(mode="disabled")  # Push-to-talk mode
    )

    transcript_done = asyncio.Event()

    def on_transcript_delta(data: dict) -> None:
        print(data.get("delta", ""), end="", flush=True)

    def on_transcript_completed(data: dict) -> None:
        print(f"\n[Transzkripció] {data['transcript']}")
        transcript_done.set()

    session = None
    try:
        async with TranscriptionSession(config=config) as session:
            session.on("transcript.delta", on_transcript_delta)
            session.on("transcript.completed", on_transcript_completed)

            while True:
                try:
                    user_input = input("\n> ").strip()
                    if user_input.lower() == 'q':
                        print("Kilépés...")
                        break

                    print("🎤 Felvétel... (nyomj Ctrl+C a leállításhoz)")
                    audio_data = record_audio()

                    # Convert numpy array to bytes and send in chunks
                    audio_bytes = audio_data.tobytes()
                    chunk_size = 4800  # 100ms at 24kHz mono int16
                    for i in range(0, len(audio_bytes), chunk_size):
                        chunk = audio_bytes[i:i + chunk_size]
                        await session.send_audio(chunk)

                    # Commit and wait for result
                    await session.commit_audio()
                    await asyncio.wait_for(transcript_done.wait(), timeout=10.0)
                    transcript_done.clear()

                except asyncio.TimeoutError:
                    print("\n[Hiba] Időtúllépés - nincs transzkripció")
                except KeyboardInterrupt:
                    print("\n[Felvétel megszakítva]")
                    continue

    except KeyboardInterrupt:
        print("\nKilépés...")
    finally:
        if session is not None:
            export_audit_log(session.audit_log, "transcription")


async def run_voice_mode(language: str, voice: str) -> None:
    """Run voice chat mode: microphone → RealtimeSession → AI voice response."""
    print(f"\n=== Hang mód ({language}, {voice}) ===")
    print("Nyomj <Enter>-t a beszédhez, vagy 'q' a kilépéshez.")

    config = RealtimeConfig(
        language=language,
        voice=voice,
        vad=VADConfig(mode="disabled")  # Push-to-talk mode
    )

    response_done = asyncio.Event()
    player: Optional[AudioPlayer] = None

    def on_audio_delta(event: AudioDelta) -> None:
        if player:
            audio_np = np.frombuffer(event.audio_bytes, dtype=np.int16)
            player.add_audio(audio_np)

    def on_audio_done(event: AudioDone) -> None:
        response_done.set()

    def on_input_transcript(event: TranscriptCompleted) -> None:
        print(f"\n[Te] {event.transcript}")

    def on_output_transcript(event: TranscriptCompleted) -> None:
        print(f"[Asszisztens] {event.transcript}")

    def on_error(data: dict) -> None:
        print(f"\n[Hiba] {data.get('error', {}).get('message', 'Unknown error')}")

    session = None
    try:
        async with RealtimeSession(config=config) as session:
            session.on("audio.delta", on_audio_delta)
            session.on("audio.done", on_audio_done)
            session.on("transcript.input", on_input_transcript)
            session.on("transcript.output", on_output_transcript)
            session.on("error", on_error)

            with AudioPlayer() as audio_player:
                player = audio_player

                while True:
                    try:
                        user_input = input("\n> ").strip()
                        if user_input.lower() == 'q':
                            print("Kilépés...")
                            break

                        print("🎤 Beszélj... (nyomj Ctrl+C a leállításhoz)")
                        audio_data = record_audio()

                        # Send audio in chunks
                        audio_bytes = audio_data.tobytes()
                        chunk_size = 4800  # 100ms at 24kHz mono int16
                        for i in range(0, len(audio_bytes), chunk_size):
                            chunk = audio_bytes[i:i + chunk_size]
                            await session.send_audio(chunk)

                        # Commit audio and request response
                        await session.commit_audio()
                        await session.create_response()

                        # Wait for AI response
                        await asyncio.wait_for(response_done.wait(), timeout=30.0)
                        response_done.clear()

                    except asyncio.TimeoutError:
                        print("\n[Hiba] Időtúllépés - nincs válasz")
                    except KeyboardInterrupt:
                        print("\n[Felvétel megszakítva]")
                        continue

    except KeyboardInterrupt:
        print("\nKilépés...")
    finally:
        if session is not None:
            export_audit_log(session.audit_log, "voice")


async def run_tts_mode(language: str, voice: str) -> None:
    """Run TTS mode: text input → TTSProvider → audio output."""
    print(f"\n=== TTS mód ({language}, {voice}) ===")
    print("Írj be szöveget, vagy 'q' a kilépéshez.")

    config = TTSConfig(voice=voice, language=language, output_format="pcm")
    tts = TTSRegistry.create(config)

    try:
        with AudioPlayer() as player:
            while True:
                text = input("\nSzöveg> ").strip()
                if text.lower() == 'q':
                    print("Kilépés...")
                    break
                if not text:
                    continue

                try:
                    print("🔊 Lejátszás...")
                    async for chunk in tts.synthesize_stream(text, voice=voice):
                        audio_np = np.frombuffer(chunk, dtype=np.int16)
                        player.add_audio(audio_np)
                except Exception as e:
                    print(f"[Hiba] {e}")

    except KeyboardInterrupt:
        print("\nKilépés...")
    finally:
        print("[TTS mód használja globális audit naplózást - nincs session export]")


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description="Interactive CLI — openai_apis demo")
    parser.add_argument(
        "mode",
        choices=["transcription", "voice", "tts"],
        help="Operating mode: transcription, voice, or tts",
    )
    parser.add_argument("--language", "-l", default="hu", help="Language code (ISO 639-1, default: hu)")
    parser.add_argument("--voice", "-v", default="ash", help="Voice for TTS/voice mode (default: ash)")
    return parser.parse_args()


def main() -> None:
    """Main entry point for multi-mode CLI."""
    args = parse_args()
    try:
        if args.mode == "transcription":
            asyncio.run(run_transcription_mode(language=args.language))
        elif args.mode == "voice":
            asyncio.run(run_voice_mode(language=args.language, voice=args.voice))
        elif args.mode == "tts":
            asyncio.run(run_tts_mode(language=args.language, voice=args.voice))
    except KeyboardInterrupt:
        print("\nProgram vége.")


if __name__ == "__main__":
    main()
