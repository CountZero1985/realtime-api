"""Agent tools for example applications.

Tools are defined using the @function_tool decorator from the OpenAI Agents SDK.
Type annotations and docstrings are used to auto-generate JSON Schema definitions.
"""

from agents import function_tool, WebSearchTool
from datetime import datetime
from examples.utils.time_format import magyar_ido_szoveggel


# --- Hosted tools ---
websearch_tool = WebSearchTool(
    search_context_size="low",
    user_location={"type": "approximate", "country": "HU"},
)


# --- Function tools ---
@function_tool
def get_current_time() -> str:
    """Visszaadja az aktualis idot es datumot magyar nyelven.

    Returns:
        Az aktualis ido szovegesen, pl. "delutan harom ora huszonot perc"
    """
    now = datetime.now()
    time_str = magyar_ido_szoveggel(now.hour, now.minute)
    date_str = now.strftime("%Y. %m. %d.")
    return f"{date_str}, {time_str}"


@function_tool
def get_weather(city: str) -> str:
    """Visszaadja egy varos aktualis idojarasat.

    Args:
        city: A varos neve (pl. "Budapest", "Debrecen")

    Returns:
        Az idojaras szoveges leirasa.
    """
    # Stub implementacio — valos API integracio nelkul
    return f"{city}: 22°C, napos, enyhe szel"


@function_tool
def display_text(text: str) -> str:
    """Megjelenitett egy szoveget a terminal kepernyoen a felhasznalo szamara.

    Hasznald ezt az eszkozt, ha hosszabb szoveget, listat, tablazatot
    vagy formatozott informaciot kell megjelenitenid.

    Args:
        text: A megjelenitenedo szoveg (tamogatja a markdown formazast)

    Returns:
        Megerosites, hogy a szoveg megjelent.
    """
    print("\n\u250c\u2500\u2500\u2500 Megjelen\u00edtett tartalom \u2500\u2500\u2500\u2510")
    print(text)
    print("\u2514\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2518\n")
    return "A szoveg megjelent a felhasznalo kepernyojen."


# Backward compatibility alias
display_text_terminal = display_text
