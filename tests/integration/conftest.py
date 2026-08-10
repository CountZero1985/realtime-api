"""Shared fixtures for integration tests."""
import pytest
import asyncio
import json
import tempfile
import numpy as np
from pathlib import Path


class MockWebSocket:
    """Mock WebSocket for integration testing.

    Reuses proven pattern from tests/unit/test_realtime_session.py.
    """

    def __init__(self, messages=None):
        self.messages = messages or []
        self.sent_messages = []
        self.closed = False
        self.message_index = 0

    async def send(self, message):
        self.sent_messages.append(message)

    async def recv(self):
        if self.message_index < len(self.messages):
            msg = self.messages[self.message_index]
            self.message_index += 1
            return msg
        await asyncio.sleep(1000)

    async def close(self):
        self.closed = True

    def __aiter__(self):
        return self

    async def __anext__(self):
        if self.message_index < len(self.messages):
            msg = self.messages[self.message_index]
            self.message_index += 1
            return msg
        raise StopAsyncIteration


def make_handshake_messages(session_id="sess_test"):
    """Create session.created + session.updated handshake messages."""
    return [
        json.dumps({"type": "session.created", "session": {"id": session_id}}),
        json.dumps({"type": "session.updated", "session": {"id": session_id}}),
    ]


def mock_websockets_connect(mock_ws):
    """Create async callable that returns mock_ws (for use as side_effect)."""
    async def _connect(*args, **kwargs):
        return mock_ws
    return _connect


@pytest.fixture
def sample_audio():
    """Create sample PCM16 audio data (1 second at 24kHz)."""
    return np.zeros(24000, dtype=np.int16)


class ErrorMockWebSocket(MockWebSocket):
    """MockWebSocket that raises ConnectionClosed after consuming messages."""

    def __init__(self, messages=None):
        super().__init__(messages)
        self.should_raise = False

    async def __anext__(self):
        if self.should_raise or self.message_index >= len(self.messages):
            import websockets
            raise websockets.ConnectionClosed(None, None)
        msg = self.messages[self.message_index]
        self.message_index += 1
        return msg


@pytest.fixture
def temp_audit_dir():
    """Create a temporary directory for audit log export."""
    with tempfile.TemporaryDirectory() as d:
        yield Path(d)


# `mock_transcription_rest` lives in tests/conftest.py so the unit suite can
# use it too — both suites hit the same GA REST handshake.
