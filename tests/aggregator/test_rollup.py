"""Tests for parsimony.aggregator.rollup."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

from parsimony.aggregator.rollup import compute_rollup
from parsimony.models.session import Session
from parsimony.parser.reader import read_events
from parsimony.parser.session_builder import build_session

FIXTURES = Path(__file__).parent.parent / "fixtures"


def _make_session(fixture: str, session_id: str, project: str = "test") -> Session:
    events = list(read_events(FIXTURES / fixture))
    data = build_session(session_id, events)
    return Session.from_session_data(data, project, f"C:\\{project}")


class TestComputeRollup:
    def test_single_session(self) -> None:
        session = _make_session(
            "simple_session.jsonl", "aaaaaaaa-1111-2222-3333-444444444444"
        )
        rollup = compute_rollup([session])

        assert rollup.session_count == 1
        assert rollup.total_tokens > 0
        assert rollup.total_cost > Decimal("0")
        assert "claude-sonnet-4-6" in rollup.per_model

    def test_multi_model_breakdown(self) -> None:
        session = _make_session(
            "multi_model_session.jsonl", "bbbbbbbb-1111-2222-3333-444444444444"
        )
        rollup = compute_rollup([session])

        assert len(rollup.per_model) == 3
        assert rollup.per_model["claude-opus-4-6"].cost > rollup.per_model["claude-haiku-4-5-20251001"].cost

    def test_tool_breakdown(self) -> None:
        session = _make_session(
            "simple_session.jsonl", "aaaaaaaa-1111-2222-3333-444444444444"
        )
        rollup = compute_rollup([session])
        assert "Read" in rollup.per_tool

    def test_mcp_breakdown(self) -> None:
        session = _make_session(
            "mcp_session.jsonl", "dddddddd-1111-2222-3333-444444444444"
        )
        rollup = compute_rollup([session])
        assert "figma" in rollup.mcp_breakdown
        assert "context7" in rollup.mcp_breakdown

    def test_subagent_costs(self) -> None:
        session = _make_session(
            "subagent_session.jsonl", "cccccccc-1111-2222-3333-444444444444"
        )
        rollup = compute_rollup([session])
        assert rollup.subagent_total_tokens == 42000
        assert rollup.subagent_total_cost > Decimal("0")

    def test_cache_efficiency(self) -> None:
        session = _make_session(
            "simple_session.jsonl", "aaaaaaaa-1111-2222-3333-444444444444"
        )
        rollup = compute_rollup([session])
        assert 0 <= rollup.cache_efficiency <= 100

    def test_most_expensive_session(self) -> None:
        s1 = _make_session("simple_session.jsonl", "s1", "cheap")
        s2 = _make_session("multi_model_session.jsonl", "s2", "expensive")
        rollup = compute_rollup([s1, s2])

        assert rollup.most_expensive_session is not None
        assert rollup.most_expensive_cost > Decimal("0")

    def test_avg_cost_per_session(self) -> None:
        s1 = _make_session("simple_session.jsonl", "s1")
        s2 = _make_session("multi_model_session.jsonl", "s2")
        rollup = compute_rollup([s1, s2])

        assert rollup.avg_cost_per_session > Decimal("0")
        assert rollup.avg_cost_per_session == rollup.total_cost / 2

    def test_empty_sessions(self) -> None:
        rollup = compute_rollup([])
        assert rollup.session_count == 0
        assert rollup.total_tokens == 0
        assert rollup.total_cost == Decimal("0")
        assert rollup.cache_efficiency == 0.0
        assert rollup.most_expensive_session is None

    def test_multiple_sessions_accumulate(self) -> None:
        s1 = _make_session("simple_session.jsonl", "s1")
        s2 = _make_session("simple_session.jsonl", "s2")
        single = compute_rollup([s1])
        double = compute_rollup([s1, s2])

        assert double.total_tokens == single.total_tokens * 2
        assert double.session_count == 2


class TestRollupTokenFields:
    def test_token_breakdown(self) -> None:
        session = _make_session("simple_session.jsonl", "s1")
        rollup = compute_rollup([session])
        assert rollup.total_input_tokens >= 0
        assert rollup.total_output_tokens >= 0
        assert rollup.total_cache_write_tokens >= 0
        assert rollup.total_cache_read_tokens >= 0
        total = (
            rollup.total_input_tokens
            + rollup.total_output_tokens
            + rollup.total_cache_write_tokens
            + rollup.total_cache_read_tokens
        )
        assert total == rollup.total_tokens

    def test_avg_tokens_per_session(self) -> None:
        s1 = _make_session("simple_session.jsonl", "s1")
        s2 = _make_session("multi_model_session.jsonl", "s2")
        rollup = compute_rollup([s1, s2])
        assert rollup.avg_tokens_per_session == rollup.total_tokens // 2

    def test_highest_token_session(self) -> None:
        s1 = _make_session("simple_session.jsonl", "s1")
        s2 = _make_session("multi_model_session.jsonl", "s2")
        rollup = compute_rollup([s1, s2])
        assert rollup.highest_token_session is not None
        assert rollup.highest_token_count > 0

    def test_empty_rollup_token_fields(self) -> None:
        rollup = compute_rollup([])
        assert rollup.total_input_tokens == 0
        assert rollup.total_output_tokens == 0
        assert rollup.avg_tokens_per_session == 0
        assert rollup.highest_token_session is None
        assert rollup.highest_token_count == 0
