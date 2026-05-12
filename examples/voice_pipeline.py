#!/usr/bin/env python3
"""
Voice Pipeline Example - Agent Framework API and Streaming Workflow

This module provides a clean API for voice-based agent interactions using
OpenAI Agents SDK's VoicePipeline with custom streaming workflows.

Features:
- Voice input → STT → Agent processing → TTS → Voice output
- Custom state management support
- Streaming responses with event callbacks
- Push-to-talk and continuous recording modes
- Full integration with existing agent team

Example usage:
    from examples.voice_pipeline import AgentFrameworkAPI
    from examples.agents.team import assisstant_agent

    api = AgentFrameworkAPI(agent=assisstant_agent)
    await api.run_interactive()
"""

import asyncio
import time
import numpy as np
from typing import Any, Optional, Dict, Callable, AsyncIterator
from dataclasses import dataclass, asdict
from collections.abc import AsyncIterator as AsyncIteratorType

from agents import Agent, Runner
from agents.voice import VoicePipeline, VoicePipelineConfig, STTModelSettings, TTSModelSettings, AudioInput
from agents.voice.workflow import VoiceWorkflowBase, VoiceWorkflowHelper, SingleAgentWorkflowCallbacks

from openai.types.responses import (
    Response,
    ResponseComputerToolCall,
    ResponseFileSearchToolCall,
    ResponseFunctionToolCall,
    ResponseFunctionWebSearch,
    ResponseInputItemParam,
    ResponseOutputItem,
    ResponseOutputMessage,
    ResponseOutputRefusal,
    ResponseOutputText,
    ResponseStreamEvent,
)

from openai_apis._logging import get_logger, set_correlation_id, log_audit_event, log_performance
from examples.utils.audio_io import record_audio, AudioPlayer


# === StreamingVoiceWorkflow (from old voice/workflow.py) ===

class StreamingVoiceWorkflow(VoiceWorkflowBase):
    """A simple voice workflow that runs a single agent. Each transcription and result is added to
    the input history.
    For more complex workflows (e.g. multiple Runner calls, custom message history, custom logic,
    custom configs), subclass `VoiceWorkflowBase` and implement your own logic.
    """

    def __init__(self, agent: Agent[Any], callbacks: SingleAgentWorkflowCallbacks | None = None):
        """Create a new single agent voice workflow.

        Args:
            agent: The agent to run.
            callbacks: Optional callbacks to call during the workflow.
        """
        TResponseInputItem = ResponseInputItemParam  # """A type alias for the ResponseInputItemParam type from the OpenAI SDK."""

        self._input_history: list[TResponseInputItem] = []
        self._current_agent = agent
        self._callbacks = callbacks

    @property
    def input_history(self):
        """A beszélgetés input history-ja (user és assistant üzenetek)."""
        return self._input_history

    async def run(self, transcription: str) -> AsyncIteratorType[str]: # itt kell implementálni a while ciklust
        if self._callbacks:
            self._callbacks.on_run(self, transcription)

        # Add the transcription to the input history (OpenAI SDK format)
        self._input_history.append({
                "role": "user",
                "content": transcription,
            })

        # Run the agent
        result = Runner.run_streamed(self._current_agent, self._input_history)

        # Stream the text from the result and collect the full response
        full_response = ""
        async for chunk in VoiceWorkflowHelper.stream_text_from(result):
            print(f"[MODELL VÁLASZ]: {chunk}")
            full_response += chunk
            yield chunk

        # Add the assistant's response to the input history (OpenAI SDK format)
        self._input_history.append({
            "role": "assistant",
            "content": full_response,
        })

        # Update the current agent if needed
        self._current_agent = result.last_agent


# === VoiceConfig and AgentFrameworkAPI (from old voice/agent_framework.py) ===

@dataclass
class VoiceConfig:
    """Configuration for voice pipeline settings."""

    # STT Configuration
    stt_model: str = "gpt-4o-mini-transcribe"
    stt_language: str = "hu"  # Hungarian by default

    # TTS Configuration
    tts_model: str = "gpt-4o-mini-tts"
    tts_voice: str = "ash"  # ash, sage, alloy, echo, shimmer
    tts_speed: float = 4.0  # 0.25 - 4.0

    # Audio settings
    sample_rate: int = 24000
    silence_padding_ms: int = 1000  # 1 second silence after response


class TranscriptionCallback(SingleAgentWorkflowCallbacks):
    """Callback handler for transcription events."""

    def __init__(self, on_transcription: Optional[Callable[[str], None]] = None):
        """Initialize with optional transcription callback."""
        self._on_transcription = on_transcription

    def on_run(self, workflow, transcription: str):
        """Called when transcription is available."""
        if self._on_transcription:
            self._on_transcription(transcription)


class AgentFrameworkAPI:
    """
    Voice-based agent interaction API using VoicePipeline.

    This class manages the complete voice interaction pipeline:
    audio recording → transcription → agent processing → TTS → audio playback

    Attributes:
        agent: The agent to interact with.
        config: Voice pipeline configuration.
        state: Optional state dictionary for agent context.
        workflow: StreamingVoiceWorkflow instance.
        pipeline: VoicePipeline instance.
    """

    def __init__(
        self,
        agent: Agent[Any],
        config: Optional[VoiceConfig] = None,
        state: Optional[Dict[str, Any]] = None,
        on_transcription: Optional[Callable[[str], None]] = None,
        on_response_start: Optional[Callable[[], None]] = None,
        on_response_complete: Optional[Callable[[str], None]] = None,
        on_error: Optional[Callable[[Exception], None]] = None,
    ):
        """
        Initialize the Agent Framework API.

        Args:
            agent: The agent to interact with.
            config: Voice configuration settings.
            state: Optional state dictionary for agent context.
            on_transcription: Callback when user speech is transcribed.
            on_response_start: Callback when agent starts responding.
            on_response_complete: Callback when agent response is complete.
            on_error: Callback for error handling.
        """
        self.agent = agent
        self.config = config or VoiceConfig()
        self.state = state or {}

        # Callbacks
        self._on_transcription = on_transcription
        self._on_response_start = on_response_start
        self._on_response_complete = on_response_complete
        self._on_error = on_error

        # Initialize workflow with transcription callback
        transcription_cb = TranscriptionCallback(on_transcription=self._handle_transcription)
        self.workflow = StreamingVoiceWorkflow(
            agent=agent,
            callbacks=transcription_cb
        )

        # Initialize voice pipeline
        self.pipeline = self._create_pipeline()

        # Internal state
        self._running = False

        # Logging
        self.logger = get_logger(__name__)
        self.logger.info(
            f"AgentFrameworkAPI initialized for agent: {agent.name}",
            extra={"extra_data": {
                "agent_name": agent.name,
                "config": asdict(self.config)
            }}
        )

        log_audit_event(
            event_type="voice_init",
            action="agent_framework_initialized",
            details={"agent_name": agent.name, "language": self.config.stt_language}
        )

    def _create_pipeline(self) -> VoicePipeline:
        """Create and configure the voice pipeline."""
        return VoicePipeline(
            stt_model=self.config.stt_model,
            tts_model=self.config.tts_model,
            config=VoicePipelineConfig(
                stt_settings=STTModelSettings(language=self.config.stt_language),
                tts_settings=TTSModelSettings(
                    voice=self.config.tts_voice,
                    speed=self.config.tts_speed
                )
            ),
            workflow=self.workflow
        )

    def _handle_transcription(self, transcription: str):
        """Internal transcription handler."""
        print(f"[TRANSZKRIPCIÓ] {transcription}")

        self.logger.info(
            f"Transcription received: {transcription[:100]}...",
            extra={"extra_data": {"transcript_length": len(transcription)}}
        )

        log_audit_event(
            event_type="voice_transcription",
            action="transcription_received",
            details={
                "transcript_length": len(transcription),
                "language": self.config.stt_language
            }
        )

        if self._on_transcription:
            self._on_transcription(transcription)

    async def process_audio(
        self,
        audio_data: np.ndarray,
        add_silence: bool = True
    ) -> Optional[str]:
        """
        Process a single audio input through the pipeline.

        Args:
            audio_data: Audio data as numpy array (24kHz, mono, int16).
            add_silence: Whether to add silence padding after response.

        Returns:
            The transcribed user input, or None if unavailable.

        Raises:
            Exception: If pipeline processing fails.
        """
        corr_id = set_correlation_id()
        start_time = time.time()

        audio_length = len(audio_data)
        audio_duration = audio_length / self.config.sample_rate

        self.logger.info(
            f"Processing audio: {audio_duration:.2f}s",
            extra={"extra_data": {
                "audio_length": audio_length,
                "audio_duration_seconds": audio_duration,
                "sample_rate": self.config.sample_rate
            }}
        )

        log_audit_event(
            event_type="voice_audio",
            action="audio_processing_started",
            details={
                "audio_length": audio_length,
                "audio_duration_seconds": audio_duration,
                "sample_rate": self.config.sample_rate
            }
        )

        try:
            if self._on_response_start:
                self._on_response_start()

            # Create audio input
            audio_input = AudioInput(buffer=audio_data)

            # Run through pipeline
            result = await self.pipeline.run(audio_input)

            # Process results and play audio
            full_transcript = None
            full_response = ""

            with AudioPlayer() as player:
                async for event in result.stream():
                    if event.type == "voice_stream_event_audio":
                        player.add_audio(event.data)
                    elif event.type == "voice_stream_event_lifecycle":
                        # Lifecycle events (optional logging)
                        pass
                    elif event.type == "voice_stream_event_transcript":
                        full_transcript = event.data
                        full_response = event.data

                # Add silence padding
                if add_silence:
                    silence_samples = int(
                        self.config.sample_rate * self.config.silence_padding_ms / 1000
                    )
                    player.add_audio(np.zeros((silence_samples, 1), dtype=np.int16))

            if self._on_response_complete and full_response:
                self._on_response_complete(full_response)

            # Log success
            duration_ms = (time.time() - start_time) * 1000

            self.logger.info(
                f"Audio processing completed successfully",
                extra={"extra_data": {
                    "transcript_length": len(full_transcript) if full_transcript else 0,
                    "duration_ms": duration_ms
                }}
            )

            log_audit_event(
                event_type="voice_audio",
                action="audio_processing_completed",
                details={
                    "audio_length": audio_length,
                    "transcript_length": len(full_transcript) if full_transcript else 0,
                    "duration_ms": duration_ms
                },
                status="success"
            )

            log_performance(
                operation="process_audio",
                duration_ms=duration_ms,
                details={
                    "audio_duration_seconds": audio_duration,
                    "processing_speed": audio_duration / (duration_ms / 1000) if duration_ms > 0 else 0
                }
            )

            return full_transcript

        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000

            self.logger.error(
                f"Audio processing failed: {str(e)}",
                extra={"extra_data": {"error": str(e), "duration_ms": duration_ms}},
                exc_info=True
            )

            log_audit_event(
                event_type="voice_audio",
                action="audio_processing_failed",
                details={"error": str(e), "duration_ms": duration_ms},
                status="error"
            )

            if self._on_error:
                self._on_error(e)
            raise

    async def run_single_interaction(self) -> Optional[str]:
        """
        Run a single voice interaction: record → process → respond.

        Returns:
            The transcribed user input, or None if unavailable.
        """
        print("[INFO] Press Enter to start recording, then Enter again to stop...")
        audio_data = record_audio()
        return await self.process_audio(audio_data)

    async def run_interactive(self):
        """
        Run an interactive voice session with command menu.

        This provides a loop where users can:
        - Record and process voice input
        - View conversation history
        - Exit the session
        """
        session_id = set_correlation_id()
        session_start = time.time()

        print("Asszisztens indítása (hangalapú mód)")
        self._running = True

        self.logger.info(
            "Interactive voice session started",
            extra={"extra_data": {"session_id": session_id}}
        )

        log_audit_event(
            event_type="voice_session",
            action="voice_session_started",
            session_id=session_id,
            details={"config": asdict(self.config)}
        )

        interaction_count = 0

        try:
            while self._running:
                print(
                    "\n---\n"
                    "Instrukciók:\n"
                    "  <Enter> - felvétel indítása/leállítása\n"
                    "  h - input history kiírása\n"
                    "  q - kilépés\n"
                    "  (hangutasítással: 'kilépés' vagy 'exit' is kilép)\n"
                    "---"
                )

                user_input = input("Válassz műveletet (<Enter>/h/q): ").strip().lower()

                if user_input == "q":
                    print("Kilépés...")
                    break

                elif user_input == "h":
                    self._display_history()
                    continue

                else:
                    # Record and process voice input
                    await self.run_single_interaction()
                    interaction_count += 1

                    # Check for voice exit command
                    if self._should_exit_from_voice():
                        print("[LOG] Hangutasításos kilépés észlelve.")

                        log_audit_event(
                            event_type="voice_exit",
                            action="voice_exit_detected",
                            session_id=session_id,
                            details={"trigger": "voice_command"}
                        )
                        break

        finally:
            session_duration_ms = (time.time() - session_start) * 1000
            self._running = False

            self.logger.info(
                "Interactive voice session ended",
                extra={"extra_data": {
                    "session_id": session_id,
                    "interaction_count": interaction_count,
                    "duration_ms": session_duration_ms
                }}
            )

            log_audit_event(
                event_type="voice_session",
                action="voice_session_ended",
                session_id=session_id,
                details={
                    "total_interactions": interaction_count,
                    "duration_ms": session_duration_ms
                }
            )

            print("---\nA program véget ért.")

    def run_interactive_sync(self):
        """Run interactive session synchronously."""
        asyncio.run(self.run_interactive())

    def _display_history(self):
        """Display conversation history."""
        print("\n--- Input history ---")
        for i, msg in enumerate(self.workflow.input_history):
            print(f"{i+1}. [{msg['role']}] {msg['content']}")
        print("---\n")

    def _should_exit_from_voice(self) -> bool:
        """Check if last user message contained exit command."""
        if len(self.workflow.input_history) >= 2:
            last_user = self.workflow.input_history[-2]["content"]
            return any(x in last_user.lower() for x in ["kilépés", "exit"])
        return False

    def get_history(self) -> list:
        """Get the conversation history."""
        return self.workflow.input_history.copy()

    def clear_history(self):
        """Clear the conversation history."""
        self.workflow._input_history.clear()

    def set_state(self, key: str, value: Any):
        """Set a state value for agent context."""
        self.state[key] = value

    def get_state(self, key: str, default: Any = None) -> Any:
        """Get a state value."""
        return self.state.get(key, default)

    def stop(self):
        """Stop the interactive session."""
        self._running = False


# Convenience function
def start_voice_agent(
    agent: Agent[Any],
    config: Optional[VoiceConfig] = None,
    state: Optional[Dict[str, Any]] = None
):
    """
    Start an interactive voice agent session.

    Args:
        agent: The agent to interact with.
        config: Optional voice configuration.
        state: Optional state dictionary.

    Example:
        >>> from examples.agents.team import assisstant_agent
        >>> from examples.voice_pipeline import start_voice_agent
        >>> start_voice_agent(assisstant_agent)
    """
    api = AgentFrameworkAPI(agent=agent, config=config, state=state)
    api.run_interactive_sync()


if __name__ == "__main__":
    print("Voice Pipeline Example Module")
    print("\nExample:")
    print("  from examples.voice_pipeline import AgentFrameworkAPI")
    print("  from examples.agents.team import assisstant_agent")
    print("  api = AgentFrameworkAPI(agent=assisstant_agent)")
    print("  api.run_interactive_sync()")
