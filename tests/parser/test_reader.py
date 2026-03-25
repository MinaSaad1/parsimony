"""Tests for parsimony.parser.reader."""

from __future__ import annotations

from pathlib import Path

from parsimony.parser.events import AssistantEvent, RawEvent, UserEvent
from parsimony.parser.reader import parse_event, read_events

FIXTURES = Path(__file__).parent.parent / "fixtures"


class TestReadEvents:
    def test_simple_session(self) -> None:
        events = list(read_events(FIXTURES / "simple_session.jsonl"))
        # 7 lines: 2 queue-ops, 1 user, 2 assistant (streaming), 1 user (tool_result), 1 assistant
        assert len(events) == 7
        types = [type(e).__name__ for e in events]
        assert "AssistantEvent" in types
        assert "UserEvent" in types
        assert "RawEvent" in types  # queue-operation lines

    def test_malformed_lines_skipped(self) -> None:
        events = list(read_events(FIXTURES / "malformed_session.jsonl"))
        # 6 lines total: 1 user, 2 malformed (skipped), 1 assistant, 1 blank (skipped), 1 user
        assert len(events) == 3

    def test_empty_lines_skipped(self) -> None:
        events = list(read_events(FIXTURES / "malformed_session.jsonl"))
        # blank line should be skipped, not cause errors
        for event in events:
            assert event is not None


class TestParseEvent:
    def test_assistant_type(self) -> None:
        raw = {
            "type": "assistant",
            "message": {"model": "claude-sonnet-4-6", "content": [], "usage": {}},
            "requestId": "req_001",
            "timestamp": "2026-03-20T10:00:00.000Z",
            "uuid": "u1",
        }
        event = parse_event(raw)
        assert isinstance(event, AssistantEvent)

    def test_user_type(self) -> None:
        raw = {
            "type": "user",
            "sessionId": "sess1",
            "timestamp": "2026-03-20T10:00:00.000Z",
            "uuid": "u1",
        }
        event = parse_event(raw)
        assert isinstance(event, UserEvent)

    def test_unknown_type(self) -> None:
        raw = {"type": "queue-operation", "operation": "enqueue"}
        event = parse_event(raw)
        assert isinstance(event, RawEvent)
        assert event.event_type == "queue-operation"

    def test_missing_type(self) -> None:
        raw = {"no_type_key": True}
        event = parse_event(raw)
        assert isinstance(event, RawEvent)
        assert event.event_type == "unknown"
