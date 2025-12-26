import asyncio
from agents.voice.workflow import VoiceWorkflowBase, VoiceWorkflowHelper, SingleAgentWorkflowCallbacks
from agents import Runner, Agent
#from agents.mcp import MCPServer, MCPServerSse
from typing import Any
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
from collections.abc import AsyncIterator

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

    async def run(self, transcription: str) -> AsyncIterator[str]: # itt kell implementálni a while ciklust
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
