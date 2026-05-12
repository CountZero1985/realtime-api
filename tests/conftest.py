"""Shared pytest fixtures for all tests."""

import pytest
from unittest.mock import AsyncMock, MagicMock
try:
    from agents import Agent
except ImportError:
    Agent = None

@pytest.fixture
def mock_openai_client():
    """Mock OpenAI client for testing."""
    client = MagicMock()
    return client

@pytest.fixture
def mock_agent():
    """Mock agent for testing."""
    if Agent is None:
        pytest.skip("openai-agents not installed")
    agent = MagicMock(spec=Agent)
    agent.name = "test_agent"
    return agent
