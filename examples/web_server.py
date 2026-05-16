#!/usr/bin/env python3
"""
Web Server Example - Run the OpenAI Voice Agent web frontend.

This script starts a FastAPI web server that provides:
- Real-time voice conversation via WebSocket
- Speech-to-text transcription
- Text-to-speech synthesis
- Text chat with AI agent

Usage:
    python examples/web_server.py
    python examples/web_server.py --port 8080
    python examples/web_server.py --host 0.0.0.0 --port 8000 --reload

Then open http://localhost:8000 in your browser.
"""

import argparse
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv


def main():
    """Run the web server."""
    load_dotenv()

    parser = argparse.ArgumentParser(
        description="Run the OpenAI Voice Agent web server",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Host to bind to (use 0.0.0.0 for all interfaces)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Port to listen on",
    )
    parser.add_argument(
        "--reload",
        action="store_true",
        help="Enable auto-reload for development",
    )
    parser.add_argument(
        "--log-level",
        default="info",
        choices=["debug", "info", "warning", "error"],
        help="Logging level",
    )

    args = parser.parse_args()

    # Check for API key
    if not os.environ.get("OPENAI_API_KEY"):
        print("Warning: OPENAI_API_KEY environment variable not set.")
        print("Set it in your .env file or environment before using the API features.")
        print()

    print(f"Starting web server on http://{args.host}:{args.port}")
    print("Press Ctrl+C to stop")
    print()

    # Import and run server
    from openai_apis.web.server import run_server

    try:
        run_server(
            host=args.host,
            port=args.port,
            reload=args.reload,
            log_level=args.log_level,
        )
    except KeyboardInterrupt:
        print("\nServer stopped.")


if __name__ == "__main__":
    main()
