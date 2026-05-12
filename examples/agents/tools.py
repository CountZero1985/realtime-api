"""Agent tools for example applications.

This module provides tools that can be used by agents:
- websearch_tool: Web search with low context size for quick results
- get_current_time: Returns current time formatted in Hungarian
- display_text_terminal: Displays text to the terminal for user visibility

All tools are designed to work with Hungarian language agents.
"""

from agents import WebSearchTool
from agents import function_tool
from examples.utils.time_format import magyar_ido_szoveggel
from datetime import datetime

# hagyományos toolok
websearch_tool = WebSearchTool(search_context_size="low")

@function_tool
def get_current_time() -> str:
    """
    Visszaadja a jelenlegi időt magyar nyelven.
    """
    # Az aktuális idő lekérdezése
    aktualis_ido = datetime.now()
    return magyar_ido_szoveggel(aktualis_ido.hour, aktualis_ido.minute)

@function_tool
def display_text_terminal(text: str) -> str:
    """
    Megjelenítő eszköz, Megjelenít egy tetszőleges szöveget a terminálon a felhasználónak.
    """
    print("\n\n--- Képernyőn megjelenített információ ---")
    print(text)
    print("---\n")
    return "Kész!"
