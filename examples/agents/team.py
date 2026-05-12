"""Agent team configuration for examples.

This module defines the agent team used in example applications:
- assisstant_agent: Main Hungarian-language assistant with time and display tools
- tools_agent: Specialized agent for web search queries

The agents are configured to work together, with the main assistant delegating
web search tasks to the tools agent.
"""

from agents import Agent
from examples.agents.prompts.voice_assistant import assisstant_prompt
from examples.agents.tools import display_text_terminal, get_current_time, websearch_tool

#
# a megnyitott linkeket valahól chacelni kellene egy state-ben, ha további user interakcióhoz.
tools_agent = Agent( # lehet hogy structured outputba kell terelni a dolgot? információ és igazolólink és külön feldolgozni őket
    name="ToolsAgent",
    # handoff_description="Egy ügynök, aki internetes keresést végez, ha a felhasználó olyan kérdést tesz fel, amihez webes információ kell.",
    instructions=
    """
Ha a felhasználó olyan kérdést tesz fel, amelyhez internetes keresés szükséges, használd a websearch eszközt, és add át
a választ röviden összefoglalva. Csak szöveges választ adj, ne adj meg forrásmegjelölést. Mindig magyarul válaszolj!
válaszod egy tts modelbe van csatornázva, ezért soha ne add meg közvetlenül a forrásokat,
a forrásokat szöveges leírásként add meg például így:  azt írja a Portfólió: ... ; vagy a Magyar Nemzet szerint: ... ; adunamenti.com honlap értesülései szerint: ... ;)
    """,
    model="gpt-4o-mini",
    tools=[websearch_tool, display_text_terminal],
)
# fő ügynök
assisstant_agent = Agent(
    model="gpt-4o-mini",
    name="AssistantAgent",
    instructions=assisstant_prompt,
    # mcp_servers=[file_container],
    # handoffs=[],
    tools=[display_text_terminal, get_current_time, tools_agent.as_tool(
        tool_name="ToolsAgent",
        tool_description="Egy ügynök, aki internetes keresést végez."
    )],
)
