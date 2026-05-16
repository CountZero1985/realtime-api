"""Text chat REST endpoint for agent interaction."""

from typing import Optional, List, Dict, Any
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from examples.cli_app import CLI, CLIConfig
from examples.agents.team import assisstant_agent
from openai_apis._logging import get_logger

router = APIRouter(prefix="/api", tags=["chat"])
logger = get_logger(__name__)

# Session storage (in-memory, single session for simplicity)
_chat_session: Optional[CLI] = None


class ChatRequest(BaseModel):
    """Request model for chat endpoint."""
    message: str = Field(..., min_length=1, max_length=4096, description="User message")
    system_prompt: Optional[str] = Field(
        None, description="Optional system prompt to customize agent behavior"
    )
    stream: bool = Field(False, description="Whether to stream response (not implemented yet)")


class ChatResponse(BaseModel):
    """Response model for chat endpoint."""
    response: str
    message_length: int
    response_length: int


class HistoryItem(BaseModel):
    """Single history item."""
    role: str
    content: str


class HistoryResponse(BaseModel):
    """Response model for history endpoint."""
    history: List[HistoryItem]
    count: int


def _get_or_create_session() -> CLI:
    """Get existing chat session or create new one."""
    global _chat_session
    if _chat_session is None:
        config = CLIConfig(
            enable_streaming=False,  # Disable terminal streaming for web
        )
        _chat_session = CLI(agent=assisstant_agent, config=config)
        logger.info("Created new chat session")
    return _chat_session


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    """
    Send a message to the AI agent and get a response.

    Uses the assistant agent with conversation history.
    History is maintained across requests until cleared.
    """
    logger.info(f"Chat request: message_len={len(request.message)}")

    try:
        session = _get_or_create_session()

        # Query the agent (non-streaming for now)
        response = await session.query(
            message=request.message,
            add_to_history=True,
            stream=False,
        )

        logger.info(f"Chat response: {len(response)} chars")

        return ChatResponse(
            response=response,
            message_length=len(request.message),
            response_length=len(response),
        )

    except Exception as e:
        logger.error(f"Chat failed: {e}")
        raise HTTPException(status_code=500, detail=f"Chat failed: {str(e)}")


@router.get("/history", response_model=HistoryResponse)
async def get_history() -> HistoryResponse:
    """Get the current conversation history."""
    session = _get_or_create_session()
    history = session.get_history()

    return HistoryResponse(
        history=[HistoryItem(role=h["role"], content=h["content"]) for h in history],
        count=len(history),
    )


@router.delete("/history")
async def clear_history():
    """Clear the conversation history."""
    global _chat_session

    if _chat_session is not None:
        _chat_session.clear_history()
        logger.info("Chat history cleared")

    return {"message": "History cleared", "success": True}


@router.post("/reset")
async def reset_session():
    """Reset the entire chat session (clear history and state)."""
    global _chat_session

    if _chat_session is not None:
        _chat_session.clear_history()
        _chat_session.clear_state()
        _chat_session = None
        logger.info("Chat session reset")

    return {"message": "Session reset", "success": True}
