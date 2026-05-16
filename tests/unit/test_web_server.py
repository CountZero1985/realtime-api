"""Unit tests for web server endpoints."""

import pytest
from unittest.mock import patch, MagicMock, AsyncMock
import numpy as np
import os


# Set test environment before imports
os.environ.setdefault("OPENAI_API_KEY", "test-key-for-testing")


@pytest.fixture
def test_client():
    """Create test client for FastAPI app."""
    from fastapi.testclient import TestClient
    from openai_apis.web.server import create_app

    app = create_app()
    return TestClient(app)


class TestHealthEndpoint:
    """Tests for /health endpoint."""

    def test_health_check(self, test_client):
        """Test health check returns healthy status."""
        response = test_client.get("/health")
        assert response.status_code == 200

        data = response.json()
        assert data["status"] == "healthy"
        assert "api_key_configured" in data

    def test_health_check_with_api_key(self, test_client):
        """Test health check shows API key configured."""
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
            response = test_client.get("/health")
            data = response.json()
            assert data["api_key_configured"] is True


class TestConfigEndpoint:
    """Tests for /api/config endpoint."""

    def test_get_config(self, test_client):
        """Test config endpoint returns available options."""
        response = test_client.get("/api/config")
        assert response.status_code == 200

        data = response.json()
        assert "voices" in data
        assert "tts_models" in data
        assert "stt_models" in data
        assert "languages" in data
        assert "defaults" in data

        # Check voices
        assert "ash" in data["voices"]
        assert "sage" in data["voices"]

        # Check defaults
        assert data["defaults"]["voice"] == "ash"
        assert data["defaults"]["language"] == "hu"


class TestSynthesisEndpoint:
    """Tests for /api/synthesize endpoint."""

    @patch("openai_apis.web.routes.synthesis.TTSAPI")
    def test_synthesize_text_base64(self, mock_tts_class, test_client):
        """Test TTS synthesis returns base64 audio."""
        # Setup mock
        mock_api = MagicMock()
        mock_api.synthesize = AsyncMock(return_value=np.zeros(24000, dtype=np.int16))
        mock_tts_class.return_value = mock_api

        response = test_client.post("/api/synthesize", json={
            "text": "Hello world",
            "voice": "ash",
            "speed": 1.0,
            "model": "gpt-4o-mini-tts",
            "output_format": "base64",
        })

        assert response.status_code == 200
        data = response.json()
        assert "audio" in data
        assert data["sample_rate"] == 24000
        assert data["format"] == "pcm16"

    @patch("openai_apis.web.routes.synthesis.TTSAPI")
    def test_synthesize_text_pcm(self, mock_tts_class, test_client):
        """Test TTS synthesis returns raw PCM."""
        # Setup mock
        mock_api = MagicMock()
        mock_api.synthesize = AsyncMock(return_value=np.zeros(24000, dtype=np.int16))
        mock_tts_class.return_value = mock_api

        response = test_client.post("/api/synthesize", json={
            "text": "Hello world",
            "voice": "ash",
            "speed": 1.0,
            "model": "gpt-4o-mini-tts",
            "output_format": "pcm",
        })

        assert response.status_code == 200
        assert response.headers["content-type"] == "audio/pcm"
        assert response.headers["x-sample-rate"] == "24000"

    def test_synthesize_empty_text(self, test_client):
        """Test TTS rejects empty text."""
        response = test_client.post("/api/synthesize", json={
            "text": "",
            "voice": "ash",
        })

        assert response.status_code == 422  # Validation error

    def test_synthesize_invalid_voice(self, test_client):
        """Test TTS rejects invalid voice."""
        response = test_client.post("/api/synthesize", json={
            "text": "Hello",
            "voice": "invalid_voice",
        })

        assert response.status_code == 422

    def test_synthesize_invalid_speed(self, test_client):
        """Test TTS rejects invalid speed."""
        response = test_client.post("/api/synthesize", json={
            "text": "Hello",
            "voice": "ash",
            "speed": 10.0,  # Max is 4.0
        })

        assert response.status_code == 422


class TestVoicesEndpoint:
    """Tests for /api/voices endpoint."""

    def test_get_voices(self, test_client):
        """Test get available voices."""
        response = test_client.get("/api/voices")
        assert response.status_code == 200

        data = response.json()
        assert "voices" in data
        assert "default" in data
        assert len(data["voices"]) == 5


class TestTranscriptionEndpoint:
    """Tests for /api/transcribe endpoint."""

    @patch("openai_apis.web.routes.transcription.TranscriptionAPI")
    def test_transcribe_audio(self, mock_api_class, test_client):
        """Test transcription of audio file."""
        # Setup mock
        mock_api = MagicMock()
        mock_api.transcribe_file = AsyncMock(return_value="Hello world transcription")
        mock_api_class.return_value = mock_api

        # Create test audio file content (minimal WAV header)
        wav_content = b"RIFF" + b"\x00" * 36 + b"data" + b"\x00" * 100

        response = test_client.post(
            "/api/transcribe",
            files={"file": ("test.wav", wav_content, "audio/wav")},
            data={"model": "gpt-4o-mini-transcribe", "language": "hu"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["text"] == "Hello world transcription"
        assert data["language"] == "hu"

    def test_transcribe_no_file(self, test_client):
        """Test transcription without file."""
        response = test_client.post("/api/transcribe")
        assert response.status_code == 422


class TestChatEndpoint:
    """Tests for /api/chat endpoint."""

    @patch("openai_apis.web.routes.chat._get_or_create_session")
    def test_chat_message(self, mock_get_session, test_client):
        """Test chat message."""
        # Setup mock
        mock_cli = MagicMock()
        mock_cli.query = AsyncMock(return_value="Hello! How can I help?")
        mock_get_session.return_value = mock_cli

        response = test_client.post("/api/chat", json={
            "message": "Hello",
        })

        assert response.status_code == 200
        data = response.json()
        assert data["response"] == "Hello! How can I help?"
        assert data["message_length"] == 5

    def test_chat_empty_message(self, test_client):
        """Test chat rejects empty message."""
        response = test_client.post("/api/chat", json={
            "message": "",
        })

        assert response.status_code == 422


class TestHistoryEndpoint:
    """Tests for /api/history endpoint."""

    @patch("openai_apis.web.routes.chat._get_or_create_session")
    def test_get_history(self, mock_get_session, test_client):
        """Test get conversation history."""
        # Setup mock
        mock_cli = MagicMock()
        mock_cli.get_history.return_value = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there!"},
        ]
        mock_get_session.return_value = mock_cli

        response = test_client.get("/api/history")

        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 2
        assert len(data["history"]) == 2

    @patch("openai_apis.web.routes.chat._chat_session", None)
    def test_clear_history(self, test_client):
        """Test clear conversation history."""
        response = test_client.delete("/api/history")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True


class TestStaticFiles:
    """Tests for static file serving."""

    def test_root_serves_frontend(self, test_client):
        """Test root path serves frontend HTML."""
        response = test_client.get("/")

        # Should either serve HTML or return message about missing frontend
        assert response.status_code == 200


class TestAPIDocumentation:
    """Tests for API documentation endpoints."""

    def test_openapi_schema(self, test_client):
        """Test OpenAPI schema is available."""
        response = test_client.get("/openapi.json")
        assert response.status_code == 200

        data = response.json()
        assert "openapi" in data
        assert "paths" in data

    def test_docs_endpoint(self, test_client):
        """Test Swagger docs endpoint."""
        response = test_client.get("/docs")
        assert response.status_code == 200
