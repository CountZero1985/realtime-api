"""Agent configurations and tools for examples."""

from examples.agents.team import shodan_agent, assistant_agent, search_agent, assisstant_agent, tools_agent
from examples.agents.tools import websearch_tool, get_current_time, get_weather, display_text, display_text_terminal

__all__ = [
    "shodan_agent",
    "assistant_agent",
    "search_agent",
    "assisstant_agent",  # backward compat alias
    "tools_agent",  # backward compat alias
    "websearch_tool",
    "get_current_time",
    "get_weather",
    "display_text",
    "display_text_terminal",  # backward compat alias
]
