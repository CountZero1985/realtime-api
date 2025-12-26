from agents import WebSearchTool
#from agents.mcp import MCPServer, MCPServerSse
from agents import Tool
from agents import function_tool
from openai_apis.utils.time_format import magyar_ido_szoveggel
from datetime import datetime
import requests

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

