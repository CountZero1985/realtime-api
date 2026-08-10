"""Shared pytest fixtures for all tests."""

import pytest
import os
from unittest.mock import AsyncMock, MagicMock, patch
try:
    from agents import Agent
except ImportError:
    Agent = None


# Token handed back by the mocked REST handshake. Not a real credential.
FAKE_CLIENT_SECRET = "ek_test_transcription_secret"


@pytest.fixture(autouse=True)
def mock_api_key(monkeypatch):
    """Automatically set OPENAI_API_KEY for all tests."""
    monkeypatch.setenv("OPENAI_API_KEY", "test-key-12345")


@pytest.fixture
def mock_transcription_rest():
    """Stub the REST leg of TranscriptionSession's GA connect handshake.

    Under the GA API, ``TranscriptionSession._connect()`` first does a REST
    ``POST /realtime/transcription_sessions`` to mint an ephemeral token, and
    only then opens the WebSocket. Tests that patch ``websockets.connect``
    alone therefore still reach out to api.openai.com and fail on the real 404
    that endpoint currently returns — a test suite should never depend on the
    network.

    Any test that connects a TranscriptionSession needs this in addition to
    its WebSocket patch. Yields the mock so a test can assert on the model it
    was called with.
    """
    with patch(
        "openai_apis.transcription.ws_session.TranscriptionSession"
        "._create_transcription_session",
        new_callable=AsyncMock,
        return_value=FAKE_CLIENT_SECRET,
    ) as mock:
        yield mock

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
