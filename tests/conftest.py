"""Shared pytest fixtures for all tests."""

import pytest
from unittest.mock import AsyncMock, MagicMock
from agents import Agent

@pytest.fixture
def mock_openai_client():
    """Mock OpenAI client for testing."""
    client = MagicMock()
    return client

@pytest.fixture
def mock_agent():
    """Mock agent for testing."""
    agent = MagicMock(spec=Agent)
    agent.name = "test_agent"
    return agent
