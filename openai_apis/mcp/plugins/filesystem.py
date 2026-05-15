"""FileSystem MCP plugin stub."""
from openai_apis.mcp.base import MCPPlugin


class FileSystemPlugin(MCPPlugin):
    """Stub FileSystem MCP plugin — raises NotImplementedError on execute."""

    @property
    def name(self) -> str:
        return "filesystem"

    @property
    def description(self) -> str:
        return "File system operations (stub)"

    def get_tools(self) -> list[dict]:
        return [
            {
                "type": "function",
                "name": "read_file",
                "description": "Read contents of a file",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "Path to the file to read",
                        }
                    },
                    "required": ["path"],
                },
            },
            {
                "type": "function",
                "name": "write_file",
                "description": "Write contents to a file",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "Path to the file to write",
                        },
                        "content": {
                            "type": "string",
                            "description": "Content to write to the file",
                        },
                    },
                    "required": ["path", "content"],
                },
            },
        ]

    async def execute_tool(self, name: str, arguments: dict) -> str:
        raise NotImplementedError(
            "FileSystem MCP plugin not yet implemented"
        )
