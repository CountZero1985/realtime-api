# ADR-006: Web Module with FastAPI

## Status
Accepted

## Context
The core `openai_apis` package provides Python SDK-style access to transcription, TTS, and realtime APIs. However, many use cases require HTTP/WebSocket access from web frontends, mobile apps, or other services. We needed a web layer that:

- Exposes the core modules over REST and WebSocket protocols
- Provides a ready-to-use web UI for testing and demos
- Is part of the package (not just an example) so it can be imported and extended
- Uses a modern, async-native Python web framework

We considered Flask, Django, and FastAPI. FastAPI was chosen for its native async support, automatic OpenAPI documentation, WebSocket support, and Pydantic integration.

## Decision
Add `openai_apis/web/` module with FastAPI-based server:

```python
from openai_apis.web import create_app, run_server

# Factory pattern for app creation
app = create_app(title="My App", cors_origins=["http://localhost:3000"])

# Or run directly
run_server(host="0.0.0.0", port=8000, reload=True)
```

Key design choices:
- **Factory function** `create_app()` for configurable app creation
- **Route modules** in `web/routes/` — one per domain (transcription, synthesis, chat, realtime)
- **CORS middleware** pre-configured for localhost development
- **Static file serving** for built-in web UI (`web/static/`)
- **System endpoints** — `/health` and `/api/config` for monitoring and frontend configuration
- **Uvicorn** as the ASGI server
- **Separate from examples** — `openai_apis/web/` is importable library code; `examples/web_server/` demonstrates usage

## Consequences

**Easier:**
- Deploying the voice system as a web service
- Building web frontends that consume the APIs
- Interactive API documentation via `/docs` (Swagger UI)
- Testing endpoints with standard HTTP tools (curl, Postman)

**More difficult:**
- Additional dependency (FastAPI, uvicorn, starlette)
- Must keep web routes in sync with underlying Python API changes
- WebSocket route requires different patterns than REST routes
- CORS configuration needed for production deployments
