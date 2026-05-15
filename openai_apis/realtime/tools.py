"""Tool/function calling registry for Realtime API sessions."""

import json
import asyncio
from typing import Callable, Any
from dataclasses import dataclass
from openai_apis._logging import get_logger

logger = get_logger(__name__)


@dataclass
class ToolDefinition:
    """A registered tool definition with its handler."""
    name: str
    description: str
    parameters: dict
    handler: Callable


class ToolRegistry:
    """Registry for tool/function definitions used with Realtime API sessions.

    Allows registering tools with JSON Schema parameters and handler functions,
    converting to API format, and executing handlers.

    Example:
        tools = ToolRegistry()
        tools.register(
            name="get_weather",
            description="Get current weather for a city",
            parameters={
                "type": "object",
                "properties": {
                    "city": {"type": "string", "description": "City name"}
                },
                "required": ["city"]
            },
            handler=get_weather_func
        )
        config = RealtimeConfig(tools=tools)
    """

    def __init__(self) -> None:
        """Initialize empty tool registry."""
        self._tools: dict[str, ToolDefinition] = {}

    def register(self, name: str, description: str,
                 parameters: dict, handler: Callable) -> None:
        """Register a tool with JSON Schema parameters and handler function.

        Args:
            name: Unique tool name.
            description: Human-readable description of what the tool does.
            parameters: JSON Schema object describing the tool's parameters.
            handler: Callable that executes the tool. Can be sync or async.
                     Receives keyword arguments matching the parameters schema.

        Raises:
            ValueError: If name is empty or already registered.
        """
        if not name:
            raise ValueError("Tool name cannot be empty")
        if name in self._tools:
            raise ValueError(f"Tool '{name}' is already registered")
        self._tools[name] = ToolDefinition(
            name=name,
            description=description,
            parameters=parameters,
            handler=handler,
        )

    def to_api_format(self) -> list[dict]:
        """Convert all tool definitions to OpenAI Realtime API format.

        Returns:
            List of tool definitions in the format expected by session.update.
            Each entry has {"type": "function", "name": ..., "description": ..., "parameters": ...}.
        """
        return [
            {
                "type": "function",
                "name": tool.name,
                "description": tool.description,
                "parameters": tool.parameters,
            }
            for tool in self._tools.values()
        ]

    async def execute(self, name: str, arguments: str) -> str:
        """Execute a registered tool handler.

        Parses JSON arguments, calls the handler (sync or async), and returns
        the result as a JSON string.

        Args:
            name: Name of the registered tool.
            arguments: JSON string of arguments to pass to the handler.

        Returns:
            JSON string of the handler's return value.

        Raises:
            KeyError: If the tool name is not registered.
            json.JSONDecodeError: If arguments is not valid JSON.
        """
        if name not in self._tools:
            available = ", ".join(sorted(self._tools.keys()))
            raise KeyError(f"Unknown tool: '{name}'. Available: {available}")

        tool = self._tools[name]
        args_dict = json.loads(arguments)

        handler = tool.handler
        if asyncio.iscoroutinefunction(handler):
            result = await handler(**args_dict)
        else:
            result = handler(**args_dict)

        return json.dumps(result)

    @property
    def tool_names(self) -> list[str]:
        """List all registered tool names."""
        return sorted(self._tools.keys())

    def __len__(self) -> int:
        """Return number of registered tools."""
        return len(self._tools)

    def __bool__(self) -> bool:
        """Return True if any tools are registered."""
        return len(self._tools) > 0
