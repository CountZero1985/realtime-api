"""Shared pytest fixtures for all tests."""

import pytest
import os
from unittest.mock import AsyncMock, MagicMock, patch
try:
    from agents import Agent
except ImportError:
    Agent = None


@pytest.fixture(autouse=True)
def mock_api_key(monkeypatch):
    """Automatically set OPENAI_API_KEY for all tests."""
    monkeypatch.setenv("OPENAI_API_KEY", "test-key-12345")

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
