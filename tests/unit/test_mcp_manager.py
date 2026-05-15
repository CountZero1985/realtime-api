"""Unit tests for MCPPluginManager."""
import pytest
import json
from openai_apis.mcp.base import MCPPlugin
from openai_apis.mcp.manager import MCPPluginManager
from openai_apis.realtime.tools import ToolRegistry


class DummyPlugin(MCPPlugin):
    """Concrete plugin for manager tests."""

    @property
    def name(self) -> str:
        return "dummy"

    @property
    def description(self) -> str:
        return "Dummy plugin"

    def get_tools(self) -> list[dict]:
        return [
            {
                "type": "function",
                "name": "dummy_action",
                "description": "A dummy action",
                "parameters": {
                    "type": "object",
                    "properties": {"x": {"type": "string"}},
                    "required": ["x"],
                },
            },
        ]

    async def execute_tool(self, name: str, arguments: dict) -> str:
        return f"executed {name} with {arguments}"


class TestMCPPluginManagerRegister:

    def test_register_plugin(self):
        manager = MCPPluginManager()
        manager.register(DummyPlugin())
        assert "dummy" in manager.plugin_names

    def test_register_duplicate_raises(self):
        manager = MCPPluginManager()
        manager.register(DummyPlugin())
        with pytest.raises(ValueError, match="already registered"):
            manager.register(DummyPlugin())

    def test_register_non_plugin_raises(self):
        manager = MCPPluginManager()
        with pytest.raises(TypeError, match="Expected MCPPlugin"):
            manager.register("not a plugin")

    def test_register_duplicate_tool_name_raises(self):
        class Plugin2(MCPPlugin):
            @property
            def name(self): return "other"
            @property
            def description(self): return ""
            def get_tools(self):
                return [{"type": "function", "name": "dummy_action", "description": "", "parameters": {}}]
            async def execute_tool(self, name, arguments): return ""

        manager = MCPPluginManager()
        manager.register(DummyPlugin())
        with pytest.raises(ValueError, match="Tool 'dummy_action' already registered"):
            manager.register(Plugin2())


class TestMCPPluginManagerGetAllTools:

    def test_empty_manager_returns_empty(self):
        manager = MCPPluginManager()
        assert manager.get_all_tools() == []

    def test_returns_tools_from_registered_plugin(self):
        manager = MCPPluginManager()
        manager.register(DummyPlugin())
        tools = manager.get_all_tools()
        assert len(tools) == 1
        assert tools[0]["name"] == "dummy_action"
        assert tools[0]["type"] == "function"

    def test_aggregates_tools_from_multiple_plugins(self):
        class Plugin2(MCPPlugin):
            @property
            def name(self): return "p2"
            @property
            def description(self): return ""
            def get_tools(self):
                return [{"type": "function", "name": "p2_tool", "description": "P2 tool", "parameters": {}}]
            async def execute_tool(self, name, arguments): return ""

        manager = MCPPluginManager()
        manager.register(DummyPlugin())
        manager.register(Plugin2())
        tools = manager.get_all_tools()
        names = [t["name"] for t in tools]
        assert "dummy_action" in names
        assert "p2_tool" in names


class TestMCPPluginManagerExecute:

    @pytest.mark.asyncio
    async def test_execute_dispatches_to_correct_plugin(self):
        manager = MCPPluginManager()
        manager.register(DummyPlugin())
        result = await manager.execute("dummy_action", {"x": "hello"})
        assert "dummy_action" in result
        assert "hello" in result

    @pytest.mark.asyncio
    async def test_execute_unknown_tool_raises(self):
        manager = MCPPluginManager()
        with pytest.raises(KeyError, match="Unknown MCP tool"):
            await manager.execute("nonexistent", {})


class TestMCPPluginManagerProperties:

    def test_plugin_names_sorted(self):
        class PluginA(MCPPlugin):
            @property
            def name(self): return "aaa"
            @property
            def description(self): return ""
            def get_tools(self): return [{"type": "function", "name": "a_tool", "description": "", "parameters": {}}]
            async def execute_tool(self, name, arguments): return ""

        class PluginZ(MCPPlugin):
            @property
            def name(self): return "zzz"
            @property
            def description(self): return ""
            def get_tools(self): return [{"type": "function", "name": "z_tool", "description": "", "parameters": {}}]
            async def execute_tool(self, name, arguments): return ""

        manager = MCPPluginManager()
        manager.register(PluginZ())
        manager.register(PluginA())
        assert manager.plugin_names == ["aaa", "zzz"]

    def test_len(self):
        manager = MCPPluginManager()
        assert len(manager) == 0
        manager.register(DummyPlugin())
        assert len(manager) == 1

    def test_bool(self):
        manager = MCPPluginManager()
        assert not manager
        manager.register(DummyPlugin())
        assert manager


class TestMCPPluginManagerToolRegistryIntegration:
    """Test populate_tool_registry bridges MCP tools to ToolRegistry."""

    def test_populate_adds_tools(self):
        manager = MCPPluginManager()
        manager.register(DummyPlugin())
        registry = ToolRegistry()
        manager.populate_tool_registry(registry)
        assert "dummy_action" in registry.tool_names

    def test_populate_api_format_matches(self):
        manager = MCPPluginManager()
        manager.register(DummyPlugin())
        registry = ToolRegistry()
        manager.populate_tool_registry(registry)
        api_tools = registry.to_api_format()
        assert len(api_tools) == 1
        assert api_tools[0]["name"] == "dummy_action"
        assert api_tools[0]["type"] == "function"

    @pytest.mark.asyncio
    async def test_populate_handler_executes(self):
        manager = MCPPluginManager()
        manager.register(DummyPlugin())
        registry = ToolRegistry()
        manager.populate_tool_registry(registry)
        result = await registry.execute("dummy_action", json.dumps({"x": "test"}))
        parsed = json.loads(result)
        assert "dummy_action" in parsed
        assert "test" in parsed

    @pytest.mark.asyncio
    async def test_populate_stub_raises_not_implemented(self):
        from openai_apis.mcp.plugins.filesystem import FileSystemPlugin
        manager = MCPPluginManager()
        manager.register(FileSystemPlugin())
        registry = ToolRegistry()
        manager.populate_tool_registry(registry)
        with pytest.raises(NotImplementedError):
            await registry.execute("read_file", json.dumps({"path": "/tmp/x"}))
