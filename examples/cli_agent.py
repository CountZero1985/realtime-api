#!/usr/bin/env python3
"""CLI Agent Example - Text-based interactive agent with Shodan persona."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import argparse
from examples.cli_app import CLI
from examples.agents.team import shodan_agent, assistant_agent
from dotenv import load_dotenv

load_dotenv()

def main():
    """Run CLI agent in interactive mode."""
    parser = argparse.ArgumentParser(description="Text-based CLI agent")
    parser.add_argument(
        "--persona", choices=["shodan", "generic"], default="shodan",
        help="Agent persona (default: shodan)"
    )
    args = parser.parse_args()

    agent = shodan_agent if args.persona == "shodan" else assistant_agent
    print(f"Asszisztens inditasa: {agent.name} (szoveges mod)")

    cli = CLI(agent=agent)
    cli.run_sync()

if __name__ == "__main__":
    main()
