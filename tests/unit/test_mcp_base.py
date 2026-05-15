"""Unit tests for MCPPlugin abstract base class."""
import pytest
from openai_apis.mcp.base import MCPPlugin


class ConcreteMCPPlugin(MCPPlugin):
    """Minimal concrete implementation for testing the ABC."""

    @property
    def name(self) -> str:
        return "test_plugin"

    @property
    def description(self) -> str:
        return "Test plugin"

    def get_tools(self) -> list[dict]:
        return [{"type": "function", "name": "test_tool", "description": "A test tool", "parameters": {}}]

    async def execute_tool(self, name: str, arguments: dict) -> str:
        return "ok"


class TestMCPPluginContract:
    """Test that MCPPlugin cannot be instantiated without all abstract methods."""

    def test_cannot_instantiate_abc_directly(self):
        with pytest.raises(TypeError):
            MCPPlugin()

    def test_missing_name_raises(self):
        class Incomplete(MCPPlugin):
            @property
            def description(self): return ""
            def get_tools(self): return []
            async def execute_tool(self, name, arguments): return ""
        with pytest.raises(TypeError):
            Incomplete()

    def test_missing_description_raises(self):
        class Incomplete(MCPPlugin):
            @property
            def name(self): return "x"
            def get_tools(self): return []
            async def execute_tool(self, name, arguments): return ""
        with pytest.raises(TypeError):
            Incomplete()

    def test_missing_get_tools_raises(self):
        class Incomplete(MCPPlugin):
            @property
            def name(self): return "x"
            @property
            def description(self): return ""
            async def execute_tool(self, name, arguments): return ""
        with pytest.raises(TypeError):
            Incomplete()

    def test_missing_execute_tool_raises(self):
        class Incomplete(MCPPlugin):
            @property
            def name(self): return "x"
            @property
            def description(self): return ""
            def get_tools(self): return []
        with pytest.raises(TypeError):
            Incomplete()

    def test_concrete_implementation_instantiates(self):
        plugin = ConcreteMCPPlugin()
        assert plugin.name == "test_plugin"
        assert plugin.description == "Test plugin"
        assert isinstance(plugin.get_tools(), list)
