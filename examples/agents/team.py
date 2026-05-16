"""Agent team configuration.

Two agent configurations are provided:
- shodan_agent: Named persona ("Shodan") with display + web search capabilities
- assistant_agent: Generic Hungarian voice assistant (lightweight, no persona)

Both use the same tools but different prompts and interaction styles.
"""

from agents import Agent, ModelSettings
from examples.agents.tools import (
    websearch_tool,
    get_current_time,
    get_weather,
    display_text,
)
from examples.agents.prompts import shodan_prompt, generic_assistant_prompt


# --- Web search specialist (delegated tool-agent) ---
search_agent = Agent(
    name="SearchAgent",
    instructions=(
        "Internetes keresest vegzel. A keresesi eredmenyeket roviden, magyarul "
        "foglald ossze. Forrasokat szovegesen jelold (pl. 'a Telex szerint...'). "
        "Ne adj meg URL-eket kozvetlenul."
    ),
    model="gpt-4o-mini",
    tools=[websearch_tool],
)

# --- Shodan persona agent ---
shodan_agent = Agent(
    name="Shodan",
    instructions=shodan_prompt,
    model="gpt-4o-mini",
    model_settings=ModelSettings(temperature=0.7),
    tools=[
        get_current_time,
        get_weather,
        display_text,
        search_agent.as_tool(
            tool_name="web_search",
            tool_description="Internetes keresest vegez es magyarul osszefoglalja az eredmenyt.",
        ),
    ],
)

# --- Generic assistant agent (no persona) ---
assistant_agent = Agent(
    name="Assistant",
    instructions=generic_assistant_prompt,
    model="gpt-4o-mini",
    model_settings=ModelSettings(temperature=0.7),
    tools=[
        get_current_time,
        get_weather,
        display_text,
        search_agent.as_tool(
            tool_name="web_search",
            tool_description="Internetes keresest vegez es magyarul osszefoglalja az eredmenyt.",
        ),
    ],
)

# Backward compatibility aliases
assisstant_agent = assistant_agent
tools_agent = search_agent
