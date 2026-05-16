# Testing

## Overview

This project uses **pytest** with `pytest-asyncio` (auto mode) and `pytest-cov`. All async tests run without explicit `@pytest.mark.asyncio` decorators.

## Directory Layout

```
tests/
├── conftest.py                          # Shared fixtures (mock_api_key, mock_openai_client, mock_agent)
├── unit/                                # Fast, isolated tests (mocked dependencies)
│   ├── test_config.py                   # BaseConfig, AudioFormat, VADConfig validation
│   ├── test_base_session.py             # BaseSession lifecycle, state machine
│   ├── test_audit_log.py                # SessionAuditLog, AuditEvent
│   ├── test_transcription.py            # TranscriptionAPI (stateless)
│   ├── test_transcription_session.py    # TranscriptionSession (WebSocket)
│   ├── test_transcription_config.py     # TranscriptionConfig validation
│   ├── test_tts_base.py                 # BaseTTSProvider abstract class
│   ├── test_tts_config.py              # TTSConfig validation
│   ├── test_tts_openai_provider.py     # OpenAITTSProvider
│   ├── test_tts_registry.py            # TTSRegistry factory
│   ├── test_realtime_session.py        # RealtimeSession WebSocket
│   ├── test_realtime_config.py         # RealtimeConfig validation
│   ├── test_realtime_events.py         # Event dataclasses
│   ├── test_realtime_tools.py          # ToolRegistry
│   ├── test_mcp_base.py               # MCPPlugin abstract class
│   ├── test_mcp_manager.py            # MCPPluginManager
│   ├── test_mcp_plugins.py            # FileSystemPlugin, GmailPlugin
│   ├── test_synthesis.py              # TTS synthesis tests
│   ├── test_agent_framework.py        # Agent framework utilities
│   ├── test_cli_interface.py          # CLI interface classes
│   └── test_web_server.py             # Web server unit tests
├── integration/                         # E2E flows with mock WebSocket backends
│   ├── conftest.py                     # MockWebSocket, ErrorMockWebSocket, sample_audio
│   ├── test_e2e_flows.py              # 7 test classes, 23 tests covering all modules
│   ├── test_integration.py            # Additional integration scenarios
│   └── test_public_api.py             # Public API surface validation
├── api/                                 # API schema tests
│   └── test_web_server_schema.py       # Web server OpenAPI schema validation
└── test_web_server.py                   # Web server endpoint tests
```

## Key Fixtures

### Root `conftest.py`

| Fixture | Scope | Description |
|---------|-------|-------------|
| `mock_api_key` | function (autouse) | Sets `OPENAI_API_KEY=test-key-12345` for all tests |
| `mock_openai_client` | function | `MagicMock` of OpenAI client |
| `mock_agent` | function | `MagicMock(spec=Agent)` with `name="test_agent"` (skips if openai-agents not installed) |

### Integration `conftest.py`

| Fixture / Helper | Description |
|------------------|-------------|
| `MockWebSocket` | Async mock WebSocket with `send()`, `recv()`, `close()`, async iteration |
| `ErrorMockWebSocket` | Raises `ConnectionClosed` after consuming messages |
| `make_handshake_messages(session_id)` | Returns session.created + session.updated JSON messages |
| `mock_websockets_connect(mock_ws)` | Async callable for patching `websockets.connect` |
| `sample_audio` | 1-second 24kHz PCM16 numpy array (zeros) |
| `temp_audit_dir` | Temporary directory for audit log export |

## pytest Configuration

From `pyproject.toml`:

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = ["test_*.py"]
python_classes = ["Test*"]
python_functions = ["test_*"]
asyncio_mode = "auto"
addopts = "--strict-markers --cov=openai_apis --cov-report=term-missing"

[tool.coverage.run]
source = ["openai_apis"]
omit = ["*/tests/*", "*/examples/*"]
```

Key points:
- `asyncio_mode = "auto"` — no need for `@pytest.mark.asyncio` on async tests
- Coverage is automatic via `addopts` (covers `openai_apis` package)
- Strict markers — unregistered markers will fail

## Running Tests

```bash
# All tests (with automatic coverage)
pytest tests/ -v

# Unit tests only (fast)
pytest tests/unit/ -v

# Integration tests (E2E flows)
pytest tests/integration/ -v

# Specific test file
pytest tests/unit/test_tts_registry.py -v

# Specific test class/function
pytest tests/integration/test_e2e_flows.py::TestTranscriptionE2E -v

# With HTML coverage report
pytest tests/ --cov-report=html

# Stop at first failure
pytest tests/ -x
```

## Test Patterns

### Async tests (no decorator needed)

```python
async def test_session_lifecycle():
    """asyncio_mode=auto handles this automatically."""
    async with TranscriptionSession() as session:
        assert session.state == SessionState.CONNECTED
```

### Mocking WebSocket connections

```python
from unittest.mock import patch, AsyncMock

async def test_realtime_connect():
    mock_ws = MockWebSocket(messages=make_handshake_messages())
    with patch("websockets.connect", mock_websockets_connect(mock_ws)):
        async with RealtimeSession(config) as session:
            assert session.state == SessionState.CONNECTED
```

### Config validation tests

```python
def test_invalid_speed_raises():
    with pytest.raises(ValueError, match="speed"):
        TTSConfig(speed=5.0)  # Max is 4.0
```

## Dependencies

Testing dependencies (installed via `[dev]` extra):
- `pytest>=7.0.0`
- `pytest-asyncio>=0.21.0`
- `pytest-cov>=4.0.0`
- `httpx` (for FastAPI TestClient)
- `schemathesis>=3.19.0` (for API schema testing)

Install: `uv sync --extra dev` or `pip install -e ".[dev]"`
