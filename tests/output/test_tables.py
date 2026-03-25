"""Tests for parsimony.output.tables."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from parsimony.aggregator.rollup import compute_rollup
from parsimony.models.cost import calculate_session_cost
from parsimony.models.session import Session
from parsimony.output.display_config import DisplayConfig
from parsimony.output.tables import (
    render_comparison,
    render_mcp_breakdown,
    render_model_breakdown,
    render_session_detail,
    render_session_list,
    render_summary,
    render_tool_breakdown,
)
from parsimony.parser.reader import read_events
from parsimony.parser.session_builder import build_session

FIXTURES = Path(__file__).parent.parent / "fixtures"


def _make_session(fixture: str, session_id: str, project: str = "test") -> Session:
    events = list(read_events(FIXTURES / fixture))
    data = build_session(session_id, events)
    return Session.from_session_data(data, project, f"C:\\{project}")


def _render_to_string(renderable: object) -> str:
    """Render a Rich object to a plain string for assertion."""
    c = Console(file=None, force_terminal=True, width=120)
    with c.capture() as capture:
        c.print(renderable)
    return capture.get()


class TestRenderSummary:
    def test_returns_panel(self) -> None:
        session = _make_session("simple_session.jsonl", "s1")
        rollup = compute_rollup([session])
        result = render_summary(rollup)
        assert isinstance(result, Panel)

    def test_includes_cost_when_show_cost(self) -> None:
        session = _make_session("simple_session.jsonl", "s1")
        rollup = compute_rollup([session])
        config = DisplayConfig(show_cost=True)
        text = _render_to_string(render_summary(rollup, config=config))
        assert "$" in text

    def test_hides_cost_by_default(self) -> None:
        session = _make_session("simple_session.jsonl", "s1")
        rollup = compute_rollup([session])
        text = _render_to_string(render_summary(rollup))
        assert "$" not in text

    def test_label_in_title(self) -> None:
        session = _make_session("simple_session.jsonl", "s1")
        rollup = compute_rollup([session])
        text = _render_to_string(render_summary(rollup, label="March 2026"))
        assert "March 2026" in text


class TestRenderModelBreakdown:
    def test_returns_table(self) -> None:
        session = _make_session("multi_model_session.jsonl", "s1")
        rollup = compute_rollup([session])
        result = render_model_breakdown(rollup)
        assert isinstance(result, Table)

    def test_multi_model_rows(self) -> None:
        session = _make_session("multi_model_session.jsonl", "s1")
        rollup = compute_rollup([session])
        text = _render_to_string(render_model_breakdown(rollup))
        assert "Opus" in text
        assert "Sonnet" in text


class TestRenderToolBreakdown:
    def test_returns_table(self) -> None:
        session = _make_session("simple_session.jsonl", "s1")
        rollup = compute_rollup([session])
        result = render_tool_breakdown(rollup)
        assert isinstance(result, Table)


class TestRenderMCPBreakdown:
    def test_mcp_servers_shown(self) -> None:
        session = _make_session("mcp_session.jsonl", "s1")
        rollup = compute_rollup([session])
        text = _render_to_string(render_mcp_breakdown(rollup))
        assert "figma" in text
        assert "context7" in text


class TestRenderSessionList:
    def test_returns_table(self) -> None:
        session = _make_session("simple_session.jsonl", "s1")
        cost = calculate_session_cost(session)
        result = render_session_list([(session, cost)])
        assert isinstance(result, Table)


class TestRenderSessionDetail:
    def test_renders_without_error(self) -> None:
        session = _make_session("simple_session.jsonl", "s1")
        cost = calculate_session_cost(session)
        result = render_session_detail(session, cost)
        text = _render_to_string(result)
        assert "s1" in text or "Session" in text


class TestRenderComparison:
    def test_comparison_table(self) -> None:
        s1 = _make_session("simple_session.jsonl", "s1")
        s2 = _make_session("multi_model_session.jsonl", "s2")
        r1 = compute_rollup([s1])
        r2 = compute_rollup([s2])
        result = render_comparison([("Period A", r1), ("Period B", r2)])
        assert isinstance(result, Table)
        text = _render_to_string(result)
        assert "Period A" in text
        assert "Period B" in text
