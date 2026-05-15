"""Abstract base class for MCP plugins."""
from abc import ABC, abstractmethod


class MCPPlugin(ABC):
    """Abstract base class for Model Context Protocol plugins.

    Subclasses define a plugin name, description, tool definitions
    (JSON Schema format), and tool execution logic.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique plugin name (e.g., 'filesystem', 'gmail')."""
        ...

    @property
    @abstractmethod
    def description(self) -> str:
        """Human-readable description of the plugin."""
        ...

    @abstractmethod
    def get_tools(self) -> list[dict]:
        """Return tool definitions in OpenAI function-calling JSON Schema format.

        Each dict should have:
            {"type": "function", "name": "...", "description": "...", "parameters": {...}}

        Returns:
            List of tool definition dicts.
        """
        ...

    @abstractmethod
    async def execute_tool(self, name: str, arguments: dict) -> str:
        """Execute a named tool with the given arguments.

        Args:
            name: The tool name to execute.
            arguments: Dict of arguments matching the tool's parameters schema.

        Returns:
            String result of the tool execution.
        """
        ...
