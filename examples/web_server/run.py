#!/usr/bin/env python3
"""Entry point for the web server example.

Usage:
    python examples/web_server/run.py
    python examples/web_server/run.py --host 0.0.0.0 --port 8080
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import argparse
import uvicorn
from examples.web_server.app import create_app


def main():
    parser = argparse.ArgumentParser(description="OpenAI APIs Web Server Example")
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind to")
    parser.add_argument("--port", type=int, default=8000, help="Port to listen on")
    parser.add_argument("--reload", action="store_true", help="Enable auto-reload")
    args = parser.parse_args()

    app = create_app()
    uvicorn.run(app, host=args.host, port=args.port, reload=args.reload)


if __name__ == "__main__":
    main()
