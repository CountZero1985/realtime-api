"""MCP (Model Context Protocol) plugin system.

Provides an abstract plugin interface and manager for registering,
discovering, and dispatching MCP tool calls.
"""
from openai_apis.mcp.base import MCPPlugin
from openai_apis.mcp.manager import MCPPluginManager
from openai_apis.mcp.plugins import FileSystemPlugin, GmailPlugin

__all__ = [
    "MCPPlugin",
    "MCPPluginManager",
    "FileSystemPlugin",
    "GmailPlugin",
]
