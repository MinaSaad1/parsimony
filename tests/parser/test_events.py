"""Tests for parsimony.parser.events."""

from __future__ import annotations

from parsimony.parser.events import (
    AssistantEvent,
    CustomTitleEvent,
    RawEvent,
    SubagentResult,
    TokenUsage,
    ToolUseRef,
    UserEvent,
)


class TestTokenUsage:
    def test_from_dict_full(self) -> None:
        data = {
            "input_tokens": 100,
            "output_tokens": 50,
            "cache_creation_input_tokens": 200,
            "cache_read_input_tokens": 300,
            "cache_creation": {
                "ephemeral_5m_input_tokens": 10,
                "ephemeral_1h_input_tokens": 190,
            },
            "service_tier": "standard",
        }
        usage = TokenUsage.from_dict(data)
        assert usage.input_tokens == 100
        assert usage.output_tokens == 50
        assert usage.cache_creation_input_tokens == 200
        assert usage.cache_read_input_tokens == 300
        assert usage.ephemeral_5m_input_tokens == 10
        assert usage.ephemeral_1h_input_tokens == 190
        assert usage.service_tier == "standard"

    def test_from_dict_empty(self) -> None:
        usage = TokenUsage.from_dict({})
        assert usage.input_tokens == 0
        assert usage.output_tokens == 0
        assert usage.total_tokens == 0

    def test_total_tokens(self) -> None:
        usage = TokenUsage(
            input_tokens=10,
            output_tokens=20,
            cache_creation_input_tokens=30,
            cache_read_input_tokens=40,
        )
        assert usage.total_tokens == 100

    def test_frozen(self) -> None:
        usage = TokenUsage.from_dict({})
        try:
            usage.input_tokens = 99  # type: ignore[misc]
            assert False, "Should have raised"
        except AttributeError:
            pass


class TestToolUseRef:
    def test_creation(self) -> None:
        ref = ToolUseRef(tool_id="toolu_001", tool_name="Read")
        assert ref.tool_id == "toolu_001"
        assert ref.tool_name == "Read"


class TestSubagentResult:
    def test_from_dict(self) -> None:
        data = {
            "agentId": "abc123",
            "status": "completed",
            "totalTokens": 39513,
            "totalToolUseCount": 30,
            "totalDurationMs": 55634,
            "usage": {
                "input_tokens": 7,
                "cache_creation_input_tokens": 1465,
                "cache_read_input_tokens": 34715,
                "output_tokens": 3326,
            },
        }
        result = SubagentResult.from_dict(data)
        assert result.agent_id == "abc123"
        assert result.status == "completed"
        assert result.total_tokens == 39513
        assert result.total_tool_use_count == 30
        assert result.total_duration_ms == 55634
        assert result.usage.input_tokens == 7
        assert result.usage.output_tokens == 3326

    def test_from_dict_missing_keys(self) -> None:
        result = SubagentResult.from_dict({})
        assert result.agent_id == ""
        assert result.total_tokens == 0
        assert result.usage.input_tokens == 0


class TestAssistantEvent:
    def test_from_dict_with_tool_use(self) -> None:
        raw = {
            "type": "assistant",
            "message": {
                "model": "claude-sonnet-4-6",
                "content": [
                    {"type": "thinking", "thinking": "..."},
                    {"type": "tool_use", "id": "toolu_001", "name": "Read", "input": {}},
                ],
                "usage": {"input_tokens": 100, "output_tokens": 50},
            },
            "requestId": "req_001",
            "timestamp": "2026-03-20T10:00:00.000Z",
            "uuid": "u1",
        }
        event = AssistantEvent.from_dict(raw)
        assert event.model == "claude-sonnet-4-6"
        assert event.request_id == "req_001"
        assert event.content_types == ("thinking", "tool_use")
        assert len(event.tool_uses) == 1
        assert event.tool_uses[0].tool_name == "Read"
        assert event.usage.input_tokens == 100

    def test_from_dict_empty_message(self) -> None:
        raw = {"type": "assistant", "timestamp": "2026-03-20T10:00:00.000Z", "uuid": "u1"}
        event = AssistantEvent.from_dict(raw)
        assert event.model == ""
        assert event.content_types == ()
        assert event.tool_uses == ()

    def test_frozen(self) -> None:
        raw = {
            "type": "assistant",
            "message": {"model": "claude-sonnet-4-6", "usage": {}},
            "requestId": "req_001",
            "timestamp": "t",
            "uuid": "u",
        }
        event = AssistantEvent.from_dict(raw)
        try:
            event.model = "different"  # type: ignore[misc]
            assert False, "Should have raised"
        except AttributeError:
            pass


class TestUserEvent:
    def test_from_dict_with_subagent(self) -> None:
        raw = {
            "type": "user",
            "sessionId": "sess1",
            "cwd": "c:\\Users\\pc",
            "version": "2.1.59",
            "gitBranch": "main",
            "timestamp": "2026-03-20T10:00:00.000Z",
            "uuid": "u1",
            "toolUseResult": {
                "agentId": "abc",
                "status": "completed",
                "totalTokens": 1000,
                "totalToolUseCount": 5,
                "totalDurationMs": 3000,
                "usage": {"input_tokens": 500, "output_tokens": 500},
            },
        }
        event = UserEvent.from_dict(raw)
        assert event.session_id == "sess1"
        assert event.cwd == "c:\\Users\\pc"
        assert event.subagent_result is not None
        assert event.subagent_result.agent_id == "abc"

    def test_from_dict_without_subagent(self) -> None:
        raw = {
            "type": "user",
            "sessionId": "sess1",
            "timestamp": "2026-03-20T10:00:00.000Z",
            "uuid": "u1",
        }
        event = UserEvent.from_dict(raw)
        assert event.subagent_result is None
        assert event.cwd is None


class TestCustomTitleEvent:
    def test_from_dict(self) -> None:
        raw = {
            "type": "custom-title",
            "sessionId": "sess1",
            "customTitle": "My Session",
        }
        event = CustomTitleEvent.from_dict(raw)
        assert event.session_id == "sess1"
        assert event.title == "My Session"


class TestRawEvent:
    def test_creation(self) -> None:
        event = RawEvent(
            event_type="queue-operation",
            timestamp="2026-03-20T10:00:00.000Z",
            session_id="sess1",
            raw={"type": "queue-operation", "operation": "enqueue"},
        )
        assert event.event_type == "queue-operation"
        assert event.raw["operation"] == "enqueue"
