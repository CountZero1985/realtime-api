"""Gmail MCP plugin stub."""
from openai_apis.mcp.base import MCPPlugin


class GmailPlugin(MCPPlugin):
    """Stub Gmail MCP plugin — raises NotImplementedError on execute."""

    @property
    def name(self) -> str:
        return "gmail"

    @property
    def description(self) -> str:
        return "Gmail operations (stub)"

    def get_tools(self) -> list[dict]:
        return [
            {
                "type": "function",
                "name": "send_email",
                "description": "Send an email via Gmail",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "to": {
                            "type": "string",
                            "description": "Recipient email address",
                        },
                        "subject": {
                            "type": "string",
                            "description": "Email subject line",
                        },
                        "body": {
                            "type": "string",
                            "description": "Email body text",
                        },
                    },
                    "required": ["to", "subject", "body"],
                },
            },
            {
                "type": "function",
                "name": "read_emails",
                "description": "Read recent emails from Gmail inbox",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "max_results": {
                            "type": "integer",
                            "description": "Maximum number of emails to return",
                        }
                    },
                    "required": [],
                },
            },
        ]

    async def execute_tool(self, name: str, arguments: dict) -> str:
        raise NotImplementedError(
            "Gmail MCP plugin not yet implemented"
        )
