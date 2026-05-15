"""Unit tests for ToolRegistry."""
import pytest
import json
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from openai_apis.realtime.tools import ToolRegistry, ToolDefinition


def mock_websockets_connect(mock_ws):
    """Create async mock for websockets.connect that returns mock_ws."""
    async def _connect(*args, **kwargs):
        return mock_ws
    return _connect


# --- ToolRegistry Registration Tests ---

class TestToolRegistryRegister:
    """Test register() method."""

    def test_register_sync_handler(self):
        registry = ToolRegistry()
        registry.register("test", "A test tool", {"type": "object", "properties": {}}, lambda: None)
        assert "test" in registry.tool_names

    def test_register_async_handler(self):
        registry = ToolRegistry()
        async def handler(): pass
        registry.register("test", "A test tool", {"type": "object", "properties": {}}, handler)
        assert "test" in registry.tool_names

    def test_register_multiple_tools(self):
        registry = ToolRegistry()
        registry.register("tool_a", "Tool A", {"type": "object", "properties": {}}, lambda: None)
        registry.register("tool_b", "Tool B", {"type": "object", "properties": {}}, lambda: None)
        assert len(registry) == 2
        assert "tool_a" in registry.tool_names
        assert "tool_b" in registry.tool_names

    def test_register_empty_name_raises(self):
        registry = ToolRegistry()
        with pytest.raises(ValueError, match="cannot be empty"):
            registry.register("", "desc", {}, lambda: None)

    def test_register_duplicate_name_raises(self):
        registry = ToolRegistry()
        registry.register("test", "desc", {}, lambda: None)
        with pytest.raises(ValueError, match="already registered"):
            registry.register("test", "desc2", {}, lambda: None)


# --- ToolRegistry API Format Tests ---

class TestToolRegistryToApiFormat:
    """Test to_api_format() method."""

    def test_empty_registry(self):
        registry = ToolRegistry()
        assert registry.to_api_format() == []

    def test_single_tool_format(self):
        registry = ToolRegistry()
        params = {
            "type": "object",
            "properties": {"city": {"type": "string"}},
            "required": ["city"],
        }
        registry.register("get_weather", "Get weather", params, lambda city: None)
        result = registry.to_api_format()
        assert len(result) == 1
        assert result[0]["type"] == "function"
        assert result[0]["name"] == "get_weather"
        assert result[0]["description"] == "Get weather"
        assert result[0]["parameters"] == params

    def test_multiple_tools_format(self):
        registry = ToolRegistry()
        registry.register("tool_a", "Tool A", {"type": "object", "properties": {}}, lambda: None)
        registry.register("tool_b", "Tool B", {"type": "object", "properties": {}}, lambda: None)
        result = registry.to_api_format()
        assert len(result) == 2
        names = {t["name"] for t in result}
        assert names == {"tool_a", "tool_b"}


# --- ToolRegistry Execute Tests ---

class TestToolRegistryExecute:
    """Test execute() method."""

    @pytest.mark.asyncio
    async def test_execute_sync_handler(self):
        registry = ToolRegistry()
        def get_weather(city: str) -> dict:
            return {"city": city, "temp": 22}
        registry.register("get_weather", "Get weather",
                         {"type": "object", "properties": {"city": {"type": "string"}}},
                         get_weather)
        result = await registry.execute("get_weather", '{"city": "Budapest"}')
        parsed = json.loads(result)
        assert parsed == {"city": "Budapest", "temp": 22}

    @pytest.mark.asyncio
    async def test_execute_async_handler(self):
        registry = ToolRegistry()
        async def get_weather(city: str) -> dict:
            return {"city": city, "temp": 22}
        registry.register("get_weather", "Get weather",
                         {"type": "object", "properties": {"city": {"type": "string"}}},
                         get_weather)
        result = await registry.execute("get_weather", '{"city": "Budapest"}')
        parsed = json.loads(result)
        assert parsed == {"city": "Budapest", "temp": 22}

    @pytest.mark.asyncio
    async def test_execute_unknown_tool_raises(self):
        registry = ToolRegistry()
        with pytest.raises(KeyError, match="Unknown tool"):
            await registry.execute("nonexistent", "{}")

    @pytest.mark.asyncio
    async def test_execute_invalid_json_raises(self):
        registry = ToolRegistry()
        registry.register("test", "desc", {}, lambda: None)
        with pytest.raises(json.JSONDecodeError):
            await registry.execute("test", "not-json")

    @pytest.mark.asyncio
    async def test_execute_result_is_json_string(self):
        registry = ToolRegistry()
        registry.register("test", "desc", {}, lambda: {"ok": True})
        result = await registry.execute("test", "{}")
        assert isinstance(result, str)
        assert json.loads(result) == {"ok": True}


# --- ToolRegistry Properties Tests ---

class TestToolRegistryProperties:
    """Test tool_names, len, bool."""

    def test_tool_names_sorted(self):
        registry = ToolRegistry()
        registry.register("zebra", "z", {}, lambda: None)
        registry.register("alpha", "a", {}, lambda: None)
        assert registry.tool_names == ["alpha", "zebra"]

    def test_len_empty(self):
        assert len(ToolRegistry()) == 0

    def test_len_with_tools(self):
        registry = ToolRegistry()
        registry.register("a", "a", {}, lambda: None)
        assert len(registry) == 1

    def test_bool_empty(self):
        assert not ToolRegistry()

    def test_bool_with_tools(self):
        registry = ToolRegistry()
        registry.register("a", "a", {}, lambda: None)
        assert registry


# --- RealtimeConfig Integration Tests ---

class TestToolRegistryConfigIntegration:
    """Test ToolRegistry integration with RealtimeConfig."""

    def test_config_accepts_tool_registry(self):
        from openai_apis.realtime.config import RealtimeConfig
        registry = ToolRegistry()
        registry.register("test", "desc", {"type": "object", "properties": {}}, lambda: None)
        config = RealtimeConfig(tools=registry)
        assert config.tools is registry

    def test_config_to_session_update_converts_registry(self):
        from openai_apis.realtime.config import RealtimeConfig
        registry = ToolRegistry()
        registry.register("get_weather", "Get weather",
                         {"type": "object", "properties": {"city": {"type": "string"}}},
                         lambda city: None)
        config = RealtimeConfig(tools=registry)
        result = config.to_session_update()
        assert "tools" in result["session"]
        assert len(result["session"]["tools"]) == 1
        assert result["session"]["tools"][0]["name"] == "get_weather"
        assert result["session"]["tools"][0]["type"] == "function"

    def test_config_still_accepts_raw_list(self):
        from openai_apis.realtime.config import RealtimeConfig
        tools = [{"type": "function", "name": "test"}]
        config = RealtimeConfig(tools=tools)
        result = config.to_session_update()
        assert result["session"]["tools"] == tools

    def test_config_empty_registry_omits_tools(self):
        from openai_apis.realtime.config import RealtimeConfig
        registry = ToolRegistry()
        config = RealtimeConfig(tools=registry)
        result = config.to_session_update()
        assert "tools" not in result["session"]


# --- RealtimeSession Tool Execution Integration Tests ---

class TestToolRegistrySessionIntegration:
    """Test ToolRegistry auto-execution in RealtimeSession."""

    # Uses MockWebSocket pattern from test_realtime_session.py

    @pytest.mark.asyncio
    async def test_session_auto_executes_tool(self):
        """When ToolRegistry is provided, tool calls are auto-executed."""
        from openai_apis.realtime import RealtimeSession, RealtimeConfig

        # Set up registry
        registry = ToolRegistry()
        def get_weather(city: str) -> dict:
            return {"city": city, "temp": 22}
        registry.register("get_weather", "Get weather",
                         {"type": "object", "properties": {"city": {"type": "string"}}},
                         get_weather)

        # Mock WebSocket messages
        messages = [
            json.dumps({"type": "session.created", "session": {"id": "s1"}}),
            json.dumps({"type": "session.updated", "session": {"id": "s1"}}),
            json.dumps({
                "type": "response.function_call_arguments.done",
                "call_id": "call_1",
                "name": "get_weather",
                "arguments": '{"city": "Budapest"}',
            }),
        ]

        # Mock WebSocket
        class MockWS:
            def __init__(self):
                self.msgs = list(messages)
                self.sent = []
                self.idx = 0
            async def send(self, m): self.sent.append(m)
            async def recv(self):
                if self.idx < len(self.msgs):
                    m = self.msgs[self.idx]; self.idx += 1; return m
                await asyncio.sleep(1000)
            async def close(self): pass
            def __aiter__(self): return self
            async def __anext__(self):
                if self.idx < len(self.msgs):
                    m = self.msgs[self.idx]; self.idx += 1; return m
                raise StopAsyncIteration

        mock_ws = MockWS()

        config = RealtimeConfig(tools=registry)
        with patch("openai_apis.realtime.session.websockets.connect",
                   side_effect=mock_websockets_connect(mock_ws)):
            async with RealtimeSession(config=config) as session:
                await asyncio.sleep(0.2)  # Let receive loop + tool execution process

        # Verify: conversation.item.create (tool result) + response.create were sent
        parsed_messages = [json.loads(m) for m in mock_ws.sent]
        sent_types = [m["type"] for m in parsed_messages]
        assert "conversation.item.create" in sent_types
        assert "response.create" in sent_types

        # Verify tool result content
        tool_result_msg = next(
            m for m in parsed_messages
            if m["type"] == "conversation.item.create"
        )
        assert tool_result_msg["item"]["call_id"] == "call_1"
        output = json.loads(tool_result_msg["item"]["output"])
        assert output == {"city": "Budapest", "temp": 22}

    @pytest.mark.asyncio
    async def test_session_audit_logs_tool_execution(self):
        """Audit log records tool execution events."""
        from openai_apis.realtime import RealtimeSession, RealtimeConfig

        registry = ToolRegistry()
        registry.register("test", "desc", {}, lambda: {"ok": True})

        messages = [
            json.dumps({"type": "session.created", "session": {"id": "s1"}}),
            json.dumps({"type": "session.updated", "session": {"id": "s1"}}),
            json.dumps({
                "type": "response.function_call_arguments.done",
                "call_id": "call_1",
                "name": "test",
                "arguments": "{}",
            }),
        ]

        class MockWS:
            def __init__(self):
                self.msgs = list(messages)
                self.sent = []
                self.idx = 0
            async def send(self, m): self.sent.append(m)
            async def recv(self):
                if self.idx < len(self.msgs):
                    m = self.msgs[self.idx]; self.idx += 1; return m
                await asyncio.sleep(1000)
            async def close(self): pass
            def __aiter__(self): return self
            async def __anext__(self):
                if self.idx < len(self.msgs):
                    m = self.msgs[self.idx]; self.idx += 1; return m
                raise StopAsyncIteration

        mock_ws = MockWS()
        config = RealtimeConfig(tools=registry)
        with patch("openai_apis.realtime.session.websockets.connect",
                   side_effect=mock_websockets_connect(mock_ws)):
            async with RealtimeSession(config=config) as session:
                await asyncio.sleep(0.2)
                events = session.audit_log.events

        event_types = [e.event_type for e in events]
        assert "tool.execution.started" in event_types
        assert "tool.execution.completed" in event_types
