# ADR-007: MCP Plugin System

## Status
Accepted

## Context
The realtime voice API supports tool/function calling via `ToolRegistry`. To integrate external services (file system, email, etc.) we needed a plugin architecture that:

- Defines a standard interface for tool providers
- Supports registration and discovery of available tools
- Dispatches tool calls to the correct plugin
- Bridges into the existing `ToolRegistry` for realtime sessions
- Allows stub implementations for future integrations without breaking the interface

We adopted the Model Context Protocol (MCP) pattern, which standardizes how AI models interact with external tools and data sources.

## Decision
Implement `openai_apis/mcp/` module with abstract plugin base and manager:

```python
class MCPPlugin(ABC):
    @property
    @abstractmethod
    def name(self) -> str: ...

    @property
    @abstractmethod
    def description(self) -> str: ...

    @abstractmethod
    def get_tools(self) -> list[dict]: ...  # OpenAI function-calling JSON Schema

    @abstractmethod
    async def execute_tool(self, name: str, arguments: dict) -> str: ...


class MCPPluginManager:
    def register(self, plugin: MCPPlugin) -> None: ...
    def get_all_tools(self) -> list[dict]: ...
    async def execute(self, tool_name: str, arguments: dict) -> str: ...
    def populate_tool_registry(self, registry: ToolRegistry) -> None: ...
```

Key design choices:
- **Abstract base class** (`MCPPlugin`) ensures consistent plugin interface
- **Manager pattern** (`MCPPluginManager`) handles registration, aggregation, and dispatch
- **Tool name uniqueness** enforced across all registered plugins
- **`populate_tool_registry()`** bridges MCP tools into Realtime API's ToolRegistry
- **Stub implementations** (FileSystemPlugin, GmailPlugin) demonstrate the pattern without requiring external service configuration
- **JSON Schema tool definitions** match OpenAI's function-calling format for compatibility

## Consequences

**Easier:**
- Adding new external integrations (implement `MCPPlugin`, register with manager)
- Combining multiple tool sources in a single realtime session
- Testing tool dispatch in isolation (mock plugins)
- Discovering available tools at runtime (`get_all_tools()`)

**More difficult:**
- Tool name collisions between plugins (must be globally unique)
- Async-only execution (all `execute_tool` methods are async)
- Stub plugins may confuse users expecting working implementations
- No built-in authentication/authorization for plugin access
