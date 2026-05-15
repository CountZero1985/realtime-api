"""Unit tests for MCP plugin stubs (FileSystem, Gmail)."""
import pytest
from openai_apis.mcp.base import MCPPlugin
from openai_apis.mcp.plugins.filesystem import FileSystemPlugin
from openai_apis.mcp.plugins.gmail import GmailPlugin


class TestFileSystemPlugin:

    def test_name(self):
        assert FileSystemPlugin().name == "filesystem"

    def test_description(self):
        assert FileSystemPlugin().description == "File system operations (stub)"

    def test_is_mcp_plugin(self):
        assert isinstance(FileSystemPlugin(), MCPPlugin)

    def test_get_tools_returns_list(self):
        tools = FileSystemPlugin().get_tools()
        assert isinstance(tools, list)
        assert len(tools) == 2

    def test_get_tools_has_read_file(self):
        tools = FileSystemPlugin().get_tools()
        names = [t["name"] for t in tools]
        assert "read_file" in names

    def test_get_tools_has_write_file(self):
        tools = FileSystemPlugin().get_tools()
        names = [t["name"] for t in tools]
        assert "write_file" in names

    def test_tools_have_required_keys(self):
        for tool in FileSystemPlugin().get_tools():
            assert "type" in tool
            assert "name" in tool
            assert "description" in tool
            assert "parameters" in tool
            assert tool["type"] == "function"

    @pytest.mark.asyncio
    async def test_execute_tool_raises_not_implemented(self):
        plugin = FileSystemPlugin()
        with pytest.raises(NotImplementedError, match="FileSystem MCP plugin not yet implemented"):
            await plugin.execute_tool("read_file", {"path": "/tmp/x"})


class TestGmailPlugin:

    def test_name(self):
        assert GmailPlugin().name == "gmail"

    def test_description(self):
        assert GmailPlugin().description == "Gmail operations (stub)"

    def test_is_mcp_plugin(self):
        assert isinstance(GmailPlugin(), MCPPlugin)

    def test_get_tools_returns_list(self):
        tools = GmailPlugin().get_tools()
        assert isinstance(tools, list)
        assert len(tools) == 2

    def test_get_tools_has_send_email(self):
        tools = GmailPlugin().get_tools()
        names = [t["name"] for t in tools]
        assert "send_email" in names

    def test_get_tools_has_read_emails(self):
        tools = GmailPlugin().get_tools()
        names = [t["name"] for t in tools]
        assert "read_emails" in names

    def test_tools_have_required_keys(self):
        for tool in GmailPlugin().get_tools():
            assert "type" in tool
            assert "name" in tool
            assert "description" in tool
            assert "parameters" in tool
            assert tool["type"] == "function"

    @pytest.mark.asyncio
    async def test_execute_tool_raises_not_implemented(self):
        plugin = GmailPlugin()
        with pytest.raises(NotImplementedError, match="Gmail MCP plugin not yet implemented"):
            await plugin.execute_tool("send_email", {"to": "a@b.c", "subject": "hi", "body": "hello"})
