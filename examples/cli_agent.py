#!/usr/bin/env python3
"""CLI Agent Example - Text-based interactive agent.

This example demonstrates how to use the CLI interface for text-based
interactions with an AI assistant in Hungarian.
"""

import sys
from pathlib import Path

# Add project root to path for examples imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from examples.cli_app import CLI
from examples.agents.team import assisstant_agent
from dotenv import load_dotenv

load_dotenv()

def main():
    """Run CLI agent in interactive mode."""
    print("Asszisztens indítása (szöveges CLI mód)")

    cli = CLI(agent=assisstant_agent)
    cli.run_sync()

if __name__ == "__main__":
    main()
