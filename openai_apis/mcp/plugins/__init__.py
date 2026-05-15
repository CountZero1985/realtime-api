"""MCP plugin stub implementations."""
from openai_apis.mcp.plugins.filesystem import FileSystemPlugin
from openai_apis.mcp.plugins.gmail import GmailPlugin

__all__ = ["FileSystemPlugin", "GmailPlugin"]
