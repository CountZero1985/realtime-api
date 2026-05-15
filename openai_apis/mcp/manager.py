"""MCP plugin manager for registration, discovery, and dispatch."""
from openai_apis._logging import get_logger
from openai_apis.mcp.base import MCPPlugin

logger = get_logger(__name__)


class MCPPluginManager:
    """Manages MCP plugin registration, tool aggregation, and dispatch.

    Example:
        manager = MCPPluginManager()
        manager.register(FileSystemPlugin())
        manager.register(GmailPlugin())

        tools = manager.get_all_tools()
        result = await manager.execute("read_file", {"path": "/tmp/x"})
    """

    def __init__(self) -> None:
        self._plugins: dict[str, MCPPlugin] = {}
        self._tool_to_plugin: dict[str, str] = {}

    def register(self, plugin: MCPPlugin) -> None:
        """Register an MCP plugin.

        Raises:
            TypeError: If plugin is not an MCPPlugin instance.
            ValueError: If plugin name or any tool name is already registered.
        """
        if not isinstance(plugin, MCPPlugin):
            raise TypeError(
                f"Expected MCPPlugin instance, got {type(plugin).__name__}"
            )
        if plugin.name in self._plugins:
            raise ValueError(f"Plugin '{plugin.name}' is already registered")

        for tool_def in plugin.get_tools():
            tool_name = tool_def["name"]
            if tool_name in self._tool_to_plugin:
                raise ValueError(
                    f"Tool '{tool_name}' already registered by "
                    f"plugin '{self._tool_to_plugin[tool_name]}'"
                )

        # Only mutate state after all validations pass
        self._plugins[plugin.name] = plugin
        for tool_def in plugin.get_tools():
            self._tool_to_plugin[tool_def["name"]] = plugin.name

    def get_all_tools(self) -> list[dict]:
        """Aggregate tool definitions from all registered plugins.

        Returns:
            List of tool definition dicts in OpenAI function-calling format.
        """
        tools: list[dict] = []
        for plugin in self._plugins.values():
            tools.extend(plugin.get_tools())
        return tools

    async def execute(self, tool_name: str, arguments: dict) -> str:
        """Dispatch tool execution to the appropriate plugin.

        Raises:
            KeyError: If tool_name is not registered.
        """
        if tool_name not in self._tool_to_plugin:
            available = ", ".join(sorted(self._tool_to_plugin.keys()))
            raise KeyError(
                f"Unknown MCP tool: '{tool_name}'. Available: {available}"
            )
        plugin_name = self._tool_to_plugin[tool_name]
        plugin = self._plugins[plugin_name]
        return await plugin.execute_tool(tool_name, arguments)

    def populate_tool_registry(self, registry: "ToolRegistry") -> None:
        """Register all MCP plugin tools into a ToolRegistry.

        Bridges MCP plugins into the Realtime API's ToolRegistry so
        MCP tools appear as regular tools.

        Note: ToolRegistry.execute() passes **kwargs to the handler and
        wraps the return value with json.dumps(). The handler here returns
        the string from execute_tool(), so ToolRegistry will produce a
        JSON-quoted string result.
        """
        for tool_def in self.get_all_tools():
            tool_name = tool_def["name"]
            plugin_name = self._tool_to_plugin[tool_name]
            plugin = self._plugins[plugin_name]

            async def _handler(_plugin=plugin, _tool_name=tool_name, **kwargs):
                return await _plugin.execute_tool(_tool_name, kwargs)

            registry.register(
                name=tool_name,
                description=tool_def.get("description", ""),
                parameters=tool_def.get("parameters", {}),
                handler=_handler,
            )

    @property
    def plugin_names(self) -> list[str]:
        return sorted(self._plugins.keys())

    def __len__(self) -> int:
        return len(self._plugins)

    def __bool__(self) -> bool:
        return len(self._plugins) > 0
