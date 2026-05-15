"""Tests for the FastAPI web server example."""

import pytest
import base64
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient
import numpy as np

from examples.web_server.app import create_app


@pytest.fixture
def test_app():
    """Create a test FastAPI application."""
    return create_app()


@pytest.fixture
def client(test_app):
    """Create a test client."""
    return TestClient(test_app)


class TestHealthEndpoint:
    """Tests for GET /api/health endpoint."""

    def test_health_check_with_api_key(self, client):
        """Test health check returns healthy status with API key configured."""
        response = client.get("/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "api_key_configured" in data
        assert data["api_key_configured"] is True  # Set by mock_api_key fixture

    def test_health_check_cors_headers(self, client):
        """Test CORS headers are present on health endpoint."""
        response = client.get(
            "/api/health",
            headers={"Origin": "http://localhost:3000"}
        )
        assert response.status_code == 200
        assert "access-control-allow-origin" in response.headers


class TestConfigEndpoint:
    """Tests for GET /api/config endpoint."""

    def test_config_structure(self, client):
        """Test config endpoint returns expected structure."""
        response = client.get("/api/config")
        assert response.status_code == 200
        data = response.json()

        # Check all three sections exist
        assert "tts" in data
        assert "transcription" in data
        assert "realtime" in data

        # Check TTS config structure
        assert "voices" in data["tts"]
        assert "models" in data["tts"]
        assert "output_formats" in data["tts"]
        assert "defaults" in data["tts"]
        assert isinstance(data["tts"]["voices"], list)
        assert len(data["tts"]["voices"]) > 0

        # Check transcription config structure
        assert "models" in data["transcription"]
        assert "defaults" in data["transcription"]

        # Check realtime config structure
        assert "voices" in data["realtime"]
        assert "models" in data["realtime"]
        assert "defaults" in data["realtime"]

    def test_config_defaults(self, client):
        """Test config endpoint returns correct default values."""
        response = client.get("/api/config")
        data = response.json()

        assert data["tts"]["defaults"]["voice"] == "ash"
        assert data["tts"]["defaults"]["model"] == "gpt-4o-mini-tts"
        assert data["tts"]["defaults"]["speed"] == 1.0

        assert data["transcription"]["defaults"]["model"] == "gpt-realtime-whisper"
        assert data["transcription"]["defaults"]["language"] == "hu"

        assert data["realtime"]["defaults"]["voice"] == "ash"
        assert data["realtime"]["defaults"]["model"] == "gpt-realtime-mini"
        assert data["realtime"]["defaults"]["language"] == "hu"


class TestTTSEndpoint:
    """Tests for POST /api/tts endpoint."""

    @patch("examples.web_server.routes.tts.TTSRegistry")
    def test_tts_base64_format(self, mock_registry, client):
        """Test TTS endpoint with base64 output format."""
        # Mock TTS provider
        mock_provider = AsyncMock()
        mock_audio = np.array([0, 100, -100, 0], dtype=np.int16)
        mock_provider.synthesize.return_value = mock_audio
        mock_registry.create.return_value = mock_provider

        # Request
        response = client.post("/api/tts", json={
            "text": "Hello world",
            "voice": "ash",
            "speed": 1.0,
            "model": "gpt-4o-mini-tts",
            "output_format": "base64"
        })

        assert response.status_code == 200
        data = response.json()

        # Check response structure
        assert "audio" in data
        assert "sample_rate" in data
        assert "channels" in data
        assert "format" in data
        assert "text_length" in data
        assert "audio_duration_seconds" in data

        # Verify base64 audio can be decoded
        audio_bytes = base64.b64decode(data["audio"])
        assert len(audio_bytes) == mock_audio.nbytes

        # Verify metadata
        assert data["sample_rate"] == 24000
        assert data["channels"] == 1
        assert data["format"] == "pcm16"
        assert data["text_length"] == 11

    @patch("examples.web_server.routes.tts.TTSRegistry")
    def test_tts_pcm_format(self, mock_registry, client):
        """Test TTS endpoint with PCM binary output format."""
        # Mock TTS provider
        mock_provider = AsyncMock()
        mock_audio = np.array([0, 100, -100, 0], dtype=np.int16)
        mock_provider.synthesize.return_value = mock_audio
        mock_registry.create.return_value = mock_provider

        # Request
        response = client.post("/api/tts", json={
            "text": "Test",
            "output_format": "pcm"
        })

        assert response.status_code == 200
        assert response.headers["content-type"] == "audio/pcm"
        assert "x-sample-rate" in response.headers
        assert "x-channels" in response.headers
        assert "x-format" in response.headers
        assert "x-duration-seconds" in response.headers

        # Verify binary audio
        assert len(response.content) == mock_audio.nbytes

    @patch("examples.web_server.routes.tts.TTSRegistry")
    def test_tts_with_instructions(self, mock_registry, client):
        """Test TTS endpoint with voice steering instructions."""
        mock_provider = AsyncMock()
        mock_audio = np.array([0], dtype=np.int16)
        mock_provider.synthesize.return_value = mock_audio
        mock_registry.create.return_value = mock_provider

        response = client.post("/api/tts", json={
            "text": "Speak slowly",
            "instructions": "Speak in a calm, slow manner"
        })

        assert response.status_code == 200
        mock_provider.synthesize.assert_called_once()
        call_kwargs = mock_provider.synthesize.call_args.kwargs
        assert call_kwargs["instructions"] == "Speak in a calm, slow manner"

    def test_tts_validation_empty_text(self, client):
        """Test TTS endpoint rejects empty text."""
        response = client.post("/api/tts", json={
            "text": "",
            "voice": "ash"
        })
        assert response.status_code == 422  # Validation error

    def test_tts_validation_speed_out_of_range(self, client):
        """Test TTS endpoint rejects speed outside valid range."""
        response = client.post("/api/tts", json={
            "text": "Test",
            "speed": 5.0  # Max is 4.0
        })
        assert response.status_code == 422  # Validation error

    @patch("examples.web_server.routes.tts.TTSRegistry")
    def test_tts_synthesis_error(self, mock_registry, client):
        """Test TTS endpoint handles synthesis errors."""
        mock_provider = AsyncMock()
        mock_provider.synthesize.side_effect = ValueError("Invalid voice")
        mock_registry.create.return_value = mock_provider

        response = client.post("/api/tts", json={
            "text": "Test"
        })

        assert response.status_code == 400
        assert "Invalid voice" in response.json()["detail"]


class TestAppCreation:
    """Tests for app factory."""

    def test_create_app_default_cors(self):
        """Test app creation with default CORS origins."""
        app = create_app()
        assert app.title == "OpenAI APIs Web Server Example"
        assert app.version == "1.0.0"

    def test_create_app_custom_cors(self):
        """Test app creation with custom CORS origins."""
        custom_origins = ["https://example.com"]
        app = create_app(cors_origins=custom_origins)
        assert app is not None


# Note: WebSocket endpoint tests would require additional setup with
# WebSocket test client and mocking the session classes. For now, we
# test the HTTP endpoints which cover the basic integration.
