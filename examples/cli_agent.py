#!/usr/bin/env python3
"""CLI Agent Example - Text-based interactive agent.

This example demonstrates how to use the CLI interface for text-based
interactions with an AI assistant in Hungarian.
"""

from openai_apis.cli.interface import CLI
from openai_apis.agents.team import assisstant_agent
from dotenv import load_dotenv

load_dotenv()

def main():
    """Run CLI agent in interactive mode."""
    print("Asszisztens indítása (szöveges CLI mód)")

    cli = CLI(agent=assisstant_agent)
    cli.run_sync()

if __name__ == "__main__":
    main()
