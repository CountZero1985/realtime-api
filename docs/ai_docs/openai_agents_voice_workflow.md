# OpenAI Agents SDK - Voice Workflow Documentation

**SDK Version:** openai-agents (Python)
**Last Updated:** 2025-12-25

## Overview

The OpenAI Agents SDK provides a lightweight, powerful framework for building multi-agent workflows and voice agents. The `VoiceWorkflow` system integrates speech-to-text (STT), agent processing, and text-to-speech (TTS) into a unified pipeline.

**Key Components:**
- `VoiceWorkflowBase` - Abstract base class for voice workflows
- `SingleAgentVoiceWorkflow` - Concrete implementation for simple single-agent workflows
- `VoiceWorkflowHelper` - Utility class for extracting text from streaming results
- `VoicePipeline` - Complete voice pipeline with STT and TTS
- `Runner` - Agent execution engine with streaming support

---

## VoiceWorkflowBase

### Overview

`VoiceWorkflowBase` is the abstract base class that defines the interface for voice workflows. A voice workflow processes transcriptions (from STT) and yields text that will be converted to speech (via TTS).

### Class Definition

```python
from agents.voice.workflow import VoiceWorkflowBase
from collections.abc import AsyncIterator

class VoiceWorkflowBase:
    """Base class for a voice workflow.

    A workflow is any code that receives a transcription and yields text
    that will be turned into speech by a text-to-speech model.
    """

    async def run(self, transcription: str) -> AsyncIterator[str]:
        """Process a transcription and yield text to be spoken.

        Args:
            transcription: The user's speech converted to text by STT.

        Yields:
            Text chunks to be converted to speech by TTS.
        """
        raise NotImplementedError

    async def on_start(self) -> AsyncIterator[str]:
        """Called before receiving user input.

        Optional method for delivering greetings or initial messages via TTS.
        Defaults to no action.

        Yields:
            Text chunks to be spoken before user interaction.
        """
        return
        yield  # Make this an async generator
```

### Key Methods

#### `run(transcription: str) -> AsyncIterator[str]`
**Purpose:** Core method that processes user transcription and yields assistant response text.

**Parameters:**
- `transcription` - User's speech as text (from STT model)

**Returns:**
- Async iterator yielding text chunks for TTS

**Implementation Requirements:**
- Must be implemented by subclasses
- Should yield text incrementally for streaming
- Typically calls `Runner.run_streamed()` internally
- Must handle conversation state/history

#### `on_start() -> AsyncIterator[str]`
**Purpose:** Optional initialization method called before first user input.

**Use Cases:**
- Welcome greetings
- Initial instructions
- System status announcements

**Example:**
```python
async def on_start(self) -> AsyncIterator[str]:
    yield "Helló! Miben segíthetek?"
```

---

## SingleAgentVoiceWorkflow

### Overview

`SingleAgentVoiceWorkflow` is a concrete implementation for simple workflows with a single starting agent and no custom logic. It automatically manages input history and agent state.

### Class Definition

```python
from agents.voice.workflow import SingleAgentVoiceWorkflow, SingleAgentWorkflowCallbacks
from agents import Agent

class SingleAgentVoiceWorkflow(VoiceWorkflowBase):
    """A simple voice workflow that runs a single agent.

    Each transcription and result is added to the input history.
    For more complex workflows, subclass VoiceWorkflowBase.
    """

    def __init__(
        self,
        agent: Agent,
        callbacks: SingleAgentWorkflowCallbacks | None = None
    ):
        """Create a new single agent voice workflow.

        Args:
            agent: The agent to run.
            callbacks: Optional callbacks to call during the workflow.
        """
        self._input_history: list[ResponseInputItemParam] = []
        self._current_agent = agent
        self._callbacks = callbacks
```

### Constructor Parameters

#### `agent: Agent`
The Agent instance to execute for each transcription.

**Example:**
```python
from agents import Agent

assistant = Agent(
    name="voice_assistant",
    instructions="You are a helpful Hungarian voice assistant.",
    model="gpt-4o-mini"
)

workflow = SingleAgentVoiceWorkflow(agent=assistant)
```

#### `callbacks: SingleAgentWorkflowCallbacks | None`
Optional callbacks for workflow events.

**Callback Interface:**
```python
class SingleAgentWorkflowCallbacks:
    def on_run(self, workflow: VoiceWorkflowBase, transcription: str) -> None:
        """Called when the workflow processes a transcription.

        Args:
            workflow: The workflow instance.
            transcription: The user's transcription being processed.
        """
        pass
```

### Automatic Behavior

1. **Input History Management:**
   - Automatically appends user transcriptions to history
   - Automatically appends assistant responses to history
   - Format: OpenAI SDK `ResponseInputItemParam` format

2. **Agent State Updates:**
   - Automatically updates `_current_agent` to `result.last_agent`
   - Enables agent handoffs within workflow

3. **Streaming:**
   - Streams text from agent response using `VoiceWorkflowHelper.stream_text_from()`
   - Yields text chunks incrementally for TTS

### Example Usage

```python
from agents import Agent
from agents.voice.workflow import SingleAgentVoiceWorkflow
from agents.voice import VoicePipeline

# Create agent
assistant = Agent(
    name="assistant",
    instructions="You are a helpful Hungarian assistant.",
    model="gpt-4o-mini"
)

# Create workflow
workflow = SingleAgentVoiceWorkflow(agent=assistant)

# Use in voice pipeline
pipeline = VoicePipeline(workflow=workflow)

# Run pipeline
await pipeline.run()
```

---

## Custom VoiceWorkflow Implementation

For complex scenarios, subclass `VoiceWorkflowBase` directly.

### Example: Custom State Management

```python
from agents.voice.workflow import VoiceWorkflowBase, VoiceWorkflowHelper
from agents import Runner, Agent
from collections.abc import AsyncIterator
from typing import Any

class CustomVoiceWorkflow(VoiceWorkflowBase):
    """Voice workflow with custom state management."""

    def __init__(self, agent: Agent, state_manager: Any):
        self._agent = agent
        self._state_manager = state_manager
        self._input_history = []

    async def run(self, transcription: str) -> AsyncIterator[str]:
        # Add transcription to history
        self._input_history.append({
            "role": "user",
            "content": transcription
        })

        # Get context from state manager
        context = self._state_manager.get_context()

        # Optionally modify input based on state
        enriched_input = self._enrich_with_context(
            self._input_history,
            context
        )

        # Run agent with enriched input
        result = Runner.run_streamed(self._agent, enriched_input)

        # Stream and collect response
        full_response = ""
        async for chunk in VoiceWorkflowHelper.stream_text_from(result):
            full_response += chunk
            yield chunk

        # Update history and state
        self._input_history.append({
            "role": "assistant",
            "content": full_response
        })
        self._state_manager.update(full_response)

        # Update agent if handoff occurred
        self._agent = result.last_agent

    def _enrich_with_context(self, history, context):
        # Custom logic to add context to input
        return history
```

---

## VoiceWorkflowHelper

### Overview

Utility class for extracting text from agent streaming results.

### Class Methods

#### `stream_text_from(result: RunResultStreaming) -> AsyncIterator[str]`

**Purpose:** Extracts and yields text content from a streaming agent result.

**Parameters:**
- `result` - `RunResultStreaming` object from `Runner.run_streamed()`

**Returns:**
- Async iterator yielding text chunks

**Implementation:**
Filters events for `"response.output_text.delta"` type and yields the delta text content.

**Example:**
```python
from agents import Runner
from agents.voice.workflow import VoiceWorkflowHelper

result = Runner.run_streamed(agent, input_history)

async for text_chunk in VoiceWorkflowHelper.stream_text_from(result):
    print(text_chunk, end='', flush=True)
    yield text_chunk  # Forward to TTS
```

**Event Filtering:**
The helper specifically looks for:
```python
event.type == "response.output_text.delta"
event.delta  # The text content
```

---

## VoicePipeline

### Overview

`VoicePipeline` is the complete voice agent system that integrates STT, workflow, and TTS.

### Architecture

```
User Speech
    ↓
STT (Speech-to-Text)
    ↓
Transcription
    ↓
VoiceWorkflow.run(transcription)
    ↓
Text Response (streamed)
    ↓
TTS (Text-to-Speech)
    ↓
Audio Output
```

### Configuration

```python
from agents.voice import VoicePipeline, STTModelSettings, TTSModelSettings
from agents.voice.workflow import SingleAgentVoiceWorkflow

# STT Configuration
stt_settings = STTModelSettings(
    model="gpt-4o-mini-transcribe",  # Transcription model
    language="hu"  # Hungarian language
)

# TTS Configuration
tts_settings = TTSModelSettings(
    model="gpt-4o-mini-tts",  # TTS model
    voice="ash",  # Voice: ash, sage, alloy, echo, shimmer
    speed=4.0  # Speech speed (0.25 - 4.0)
)

# Create pipeline
pipeline = VoicePipeline(
    workflow=workflow,
    stt_settings=stt_settings,
    tts_settings=tts_settings
)
```

### STT Models

#### `gpt-4o-mini-transcribe`
- Fast, cost-effective transcription
- Supports 90+ languages
- Low latency

#### `gpt-4o-transcribe`
- Higher accuracy
- Same language support
- Higher cost

### TTS Models & Voices

#### Models
- `gpt-4o-mini-tts` - Fast, cost-effective
- `gpt-4o-tts` - Higher quality

#### Voices
- `ash` - Neutral, clear
- `sage` - Warm, calm
- `alloy` - Balanced, professional
- `echo` - Smooth, mature
- `shimmer` - Bright, energetic

#### Speed
- Range: 0.25 - 4.0
- Default: 1.0
- Recommendation: 1.0-1.5 for natural speech, 2.0-4.0 for fast playback

---

## Runner and Agent Execution

### Runner.run_streamed()

**Purpose:** Execute an agent with streaming results.

**Signature:**
```python
from agents import Runner

result = Runner.run_streamed(
    agent: Agent,
    input: list[ResponseInputItemParam]
) -> RunResultStreaming
```

**Parameters:**
- `agent` - The Agent instance to run
- `input` - List of conversation messages in OpenAI format

**Returns:**
- `RunResultStreaming` object with async iteration support

**Input Format:**
```python
input_history = [
    {
        "role": "user",
        "content": "What is the weather?"
    },
    {
        "role": "assistant",
        "content": "I'll check the weather for you."
    },
    {
        "role": "user",
        "content": "What's the temperature?"
    }
]
```

### Event Stream

`RunResultStreaming` emits various events:

**Event Types:**
- `response.output_text.delta` - Text content chunks
- `response.done` - Response complete
- Tool call events
- Error events

**Iteration Example:**
```python
result = Runner.run_streamed(agent, input_history)

async for event in result:
    if event.type == "response.output_text.delta":
        text_chunk = event.delta
        print(text_chunk, end='')
```

**Using VoiceWorkflowHelper:**
```python
result = Runner.run_streamed(agent, input_history)

async for text in VoiceWorkflowHelper.stream_text_from(result):
    yield text  # Simplified - helper filters for you
```

---

## Complete Implementation Example

### Project Implementation (streaming_voice_workflow.py)

```python
import asyncio
from agents.voice.workflow import (
    VoiceWorkflowBase,
    VoiceWorkflowHelper,
    SingleAgentWorkflowCallbacks
)
from agents import Runner, Agent
from typing import Any
from openai.types.responses import ResponseInputItemParam
from collections.abc import AsyncIterator

class StreamingVoiceWorkflow(VoiceWorkflowBase):
    """Custom voice workflow with full control over state and history."""

    def __init__(
        self,
        agent: Agent[Any],
        callbacks: SingleAgentWorkflowCallbacks | None = None
    ):
        self._input_history: list[ResponseInputItemParam] = []
        self._current_agent = agent
        self._callbacks = callbacks

    @property
    def input_history(self):
        """Access conversation history."""
        return self._input_history

    async def run(self, transcription: str) -> AsyncIterator[str]:
        # Optional callback
        if self._callbacks:
            self._callbacks.on_run(self, transcription)

        # Add user transcription to history
        self._input_history.append({
            "role": "user",
            "content": transcription,
        })

        # Run agent with full history
        result = Runner.run_streamed(
            self._current_agent,
            self._input_history
        )

        # Stream text and collect full response
        full_response = ""
        async for chunk in VoiceWorkflowHelper.stream_text_from(result):
            print(f"[Assistant]: {chunk}", end='', flush=True)
            full_response += chunk
            yield chunk  # Forward to TTS

        # Add assistant response to history
        self._input_history.append({
            "role": "assistant",
            "content": full_response,
        })

        # Update agent if handoff occurred
        self._current_agent = result.last_agent
```

### Main Application (main.py)

```python
import asyncio
from agents import Agent
from agents.voice import VoicePipeline, STTModelSettings, TTSModelSettings
from streaming_voice_workflow import StreamingVoiceWorkflow
from agent_team import assistant_agent

async def main():
    # Create custom workflow
    workflow = StreamingVoiceWorkflow(agent=assistant_agent)

    # Configure STT (Hungarian)
    stt_settings = STTModelSettings(
        model="gpt-4o-mini-transcribe",
        language="hu"
    )

    # Configure TTS (Hungarian-friendly voice)
    tts_settings = TTSModelSettings(
        model="gpt-4o-mini-tts",
        voice="ash",
        speed=4.0
    )

    # Create voice pipeline
    pipeline = VoicePipeline(
        workflow=workflow,
        stt_settings=stt_settings,
        tts_settings=tts_settings
    )

    # Run voice agent
    print("Voice agent started. Speak to interact...")
    await pipeline.run()

if __name__ == "__main__":
    asyncio.run(main())
```

---

## Agent Configuration

### Basic Agent

```python
from agents import Agent

agent = Agent(
    name="assistant",
    instructions="You are a helpful Hungarian assistant.",
    model="gpt-4o-mini"
)
```

### Agent with Tools

```python
from agents import Agent, function_tool

@function_tool
def get_weather(location: str) -> str:
    """Get weather for a location."""
    return f"Weather in {location}: Sunny, 22°C"

agent = Agent(
    name="assistant",
    instructions="You are a helpful assistant. Use tools when needed.",
    model="gpt-4o-mini",
    tools=[get_weather]
)
```

### Agent Team with Handoff

```python
from agents import Agent

# Tools agent for searches
tools_agent = Agent(
    name="tools_agent",
    instructions="You search the web and provide information.",
    model="gpt-4o-mini",
    tools=[websearch_tool]
)

# Main assistant with sub-agent delegation
assistant_agent = Agent(
    name="assistant",
    instructions="""You are the main assistant.
    When you need to search for information, transfer to tools_agent.""",
    model="gpt-4o-mini",
    agents=[tools_agent.as_tool()]  # Sub-agent as tool
)
```

**Agent Handoff:**
- Use `agents=[sub_agent.as_tool()]` to enable handoff
- Runner automatically handles delegation
- `result.last_agent` contains the final agent after handoffs

---

## Best Practices

### State Management

**1. Conversation History:**
```python
# Keep history manageable
if len(self._input_history) > 20:
    # Keep system message + recent 10 messages
    self._input_history = self._input_history[-10:]
```

**2. Custom State:**
```python
class StatefulWorkflow(VoiceWorkflowBase):
    def __init__(self, agent, state_manager):
        self._agent = agent
        self._state = state_manager

    async def run(self, transcription: str):
        # Use state to enrich context
        context = self._state.get_relevant_context()
        # ...
```

### Streaming Performance

**1. Immediate Yielding:**
```python
async for chunk in VoiceWorkflowHelper.stream_text_from(result):
    yield chunk  # Yield immediately for low latency
```

**2. Buffering (if needed):**
```python
buffer = ""
async for chunk in VoiceWorkflowHelper.stream_text_from(result):
    buffer += chunk
    if len(buffer) >= 50 or chunk.endswith(('.', '!', '?')):
        yield buffer
        buffer = ""
```

### Error Handling

```python
async def run(self, transcription: str):
    try:
        result = Runner.run_streamed(self._agent, self._input_history)
        async for chunk in VoiceWorkflowHelper.stream_text_from(result):
            yield chunk
    except Exception as e:
        print(f"Error in workflow: {e}")
        yield "Sajnálom, hiba történt."  # Fallback message
```

### Language Consistency

For non-English assistants:
```python
# Ensure instructions match language
agent = Agent(
    name="assistant",
    instructions="Te egy magyar nyelvű asszisztens vagy.",  # Hungarian
    model="gpt-4o-mini"
)

# Match STT language
stt_settings = STTModelSettings(
    language="hu"  # Hungarian
)

# TTS will automatically match content language
```

---

## Testing Voice Workflows

### Unit Test Example

```python
import pytest
from streaming_voice_workflow import StreamingVoiceWorkflow
from agents import Agent

@pytest.mark.asyncio
async def test_workflow_response():
    agent = Agent(
        name="test_agent",
        instructions="Always respond with 'Hello!'",
        model="gpt-4o-mini"
    )

    workflow = StreamingVoiceWorkflow(agent=agent)

    response_chunks = []
    async for chunk in workflow.run("Hi there"):
        response_chunks.append(chunk)

    full_response = ''.join(response_chunks)
    assert "Hello" in full_response
```

---

## References

- **Official SDK Documentation:** [OpenAI Agents SDK](https://openai.github.io/openai-agents-python/)
- **Voice Workflow Reference:** [VoiceWorkflow API](https://openai.github.io/openai-agents-python/ref/voice/workflow/)
- **Quickstart Guide:** [Voice Agents Quickstart](https://openai.github.io/openai-agents-python/voice/quickstart/)
- **Cookbook Example:** [Building Voice Assistants](https://cookbook.openai.com/examples/agents_sdk/app_assistant_voice_agents)
- **GitHub Repository:** [openai-agents-python](https://github.com/openai/openai-agents-python)
- **Agents SDK Guide:** [OpenAI Agents SDK](https://platform.openai.com/docs/guides/agents-sdk)

---

**Document Version:** 1.0
**Last Updated:** 2025-12-25
**SDK:** openai-agents (Python)
