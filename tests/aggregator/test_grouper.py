"""Tests for parsimony.aggregator.grouper."""

from __future__ import annotations

from pathlib import Path

from parsimony.aggregator.grouper import (
    group_by_day,
    group_by_mcp_server,
    group_by_model,
    group_by_project,
    group_by_tool,
)
from parsimony.models.session import Session
from parsimony.parser.reader import read_events
from parsimony.parser.session_builder import build_session

FIXTURES = Path(__file__).parent.parent / "fixtures"


def _make_session(fixture: str, session_id: str, project: str = "test") -> Session:
    events = list(read_events(FIXTURES / fixture))
    data = build_session(session_id, events)
    return Session.from_session_data(data, project, f"C:\\{project}")


class TestGroupByProject:
    def test_groups_correctly(self) -> None:
        s1 = _make_session("simple_session.jsonl", "s1", "ProjectA")
        s2 = _make_session("multi_model_session.jsonl", "s2", "ProjectB")
        s3 = _make_session("subagent_session.jsonl", "s3", "ProjectA")

        groups = group_by_project([s1, s2, s3])
        assert len(groups["ProjectA"]) == 2
        assert len(groups["ProjectB"]) == 1


class TestGroupByModel:
    def test_multi_model_session(self) -> None:
        session = _make_session(
            "multi_model_session.jsonl", "bbbbbbbb-1111-2222-3333-444444444444"
        )
        groups = group_by_model([session])

        assert "claude-sonnet-4-6" in groups
        assert "claude-opus-4-6" in groups
        assert "claude-haiku-4-5-20251001" in groups
        assert len(groups["claude-opus-4-6"]) == 2  # 2 opus calls


class TestGroupByTool:
    def test_tool_counts(self) -> None:
        session = _make_session(
            "simple_session.jsonl", "aaaaaaaa-1111-2222-3333-444444444444"
        )
        tools = group_by_tool([session])
        assert "Read" in tools
        assert tools["Read"].call_count >= 1

    def test_mcp_tools_flagged(self) -> None:
        session = _make_session(
            "mcp_session.jsonl", "dddddddd-1111-2222-3333-444444444444"
        )
        tools = group_by_tool([session])

        mcp_tools = {k: v for k, v in tools.items() if v.is_mcp}
        assert len(mcp_tools) >= 2


class TestGroupByMCPServer:
    def test_mcp_breakdown(self) -> None:
        session = _make_session(
            "mcp_session.jsonl", "dddddddd-1111-2222-3333-444444444444"
        )
        breakdown = group_by_mcp_server([session])

        assert "figma" in breakdown
        assert "context7" in breakdown
        assert "get_design_context" in breakdown["figma"]
        assert "get_screenshot" in breakdown["figma"]
        assert "query-docs" in breakdown["context7"]


class TestGroupByDay:
    def test_groups_by_date(self) -> None:
        s1 = _make_session("simple_session.jsonl", "s1")
        s2 = _make_session("multi_model_session.jsonl", "s2")

        days = group_by_day([s1, s2])
        # Both fixtures use 2026-03-20 timestamps
        assert len(days) >= 1
