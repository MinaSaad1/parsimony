"""Tests for parsimony.aggregator.filters."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

from parsimony.aggregator.filters import (
    SessionFilter,
    _normalize_model_name,
    apply_filters,
)
from parsimony.models.cost import DEFAULT_PRICING
from parsimony.models.session import Session
from parsimony.parser.reader import read_events
from parsimony.parser.session_builder import build_session

FIXTURES = Path(__file__).parent.parent / "fixtures"


def _make_session(fixture: str, session_id: str, project: str = "test") -> Session:
    events = list(read_events(FIXTURES / fixture))
    data = build_session(session_id, events)
    return Session.from_session_data(data, project, f"C:\\{project}")


def _sessions() -> list[Session]:
    return [
        _make_session("simple_session.jsonl", "aaaaaaaa-1111-2222-3333-444444444444"),
        _make_session("multi_model_session.jsonl", "bbbbbbbb-1111-2222-3333-444444444444"),
    ]


class TestSessionFilter:
    def test_is_empty_default(self) -> None:
        filt = SessionFilter()
        assert filt.is_empty is True

    def test_is_empty_with_models(self) -> None:
        filt = SessionFilter(models=frozenset(["claude-sonnet-4-6"]))
        assert filt.is_empty is False

    def test_is_empty_with_tools(self) -> None:
        filt = SessionFilter(tools=frozenset(["Read"]))
        assert filt.is_empty is False

    def test_is_empty_with_cost(self) -> None:
        filt = SessionFilter(min_cost=Decimal("1.00"))
        assert filt.is_empty is False

    def test_frozen(self) -> None:
        filt = SessionFilter()
        try:
            filt.models = frozenset()  # type: ignore[misc]
            raise AssertionError("Should not allow mutation")
        except AttributeError:
            pass


class TestNormalizeModelName:
    def test_alias_sonnet(self) -> None:
        assert _normalize_model_name("sonnet") == "claude-sonnet-4-6"

    def test_alias_opus(self) -> None:
        assert _normalize_model_name("opus") == "claude-opus-4-6"

    def test_alias_haiku(self) -> None:
        assert _normalize_model_name("haiku") == "claude-haiku-4-5-20251001"

    def test_case_insensitive(self) -> None:
        assert _normalize_model_name("SONNET") == "claude-sonnet-4-6"
        assert _normalize_model_name("Opus") == "claude-opus-4-6"

    def test_full_name_passthrough(self) -> None:
        assert _normalize_model_name("claude-sonnet-4-6") == "claude-sonnet-4-6"

    def test_unknown_passthrough(self) -> None:
        assert _normalize_model_name("some-future-model") == "some-future-model"


class TestApplyFilters:
    def test_empty_filter_returns_all(self) -> None:
        sessions = _sessions()
        result = apply_filters(sessions, SessionFilter())
        assert len(result) == len(sessions)

    def test_filter_by_model_full_name(self) -> None:
        sessions = _sessions()
        filt = SessionFilter(models=frozenset(["claude-opus-4-6"]))
        result = apply_filters(sessions, filt)
        # Only multi_model_session uses Opus
        assert len(result) == 1
        assert "claude-opus-4-6" in result[0].models_used

    def test_filter_by_model_alias(self) -> None:
        sessions = _sessions()
        filt = SessionFilter(models=frozenset(["opus"]))
        result = apply_filters(sessions, filt)
        assert len(result) == 1
        assert "claude-opus-4-6" in result[0].models_used

    def test_filter_by_model_sonnet_matches_both(self) -> None:
        sessions = _sessions()
        filt = SessionFilter(models=frozenset(["sonnet"]))
        result = apply_filters(sessions, filt)
        # Both sessions use Sonnet
        assert len(result) == 2

    def test_filter_by_tool(self) -> None:
        sessions = _sessions()
        filt = SessionFilter(tools=frozenset(["Read"]))
        result = apply_filters(sessions, filt)
        # simple_session has a Read tool call
        assert len(result) >= 1

    def test_filter_by_tool_case_insensitive(self) -> None:
        sessions = _sessions()
        filt = SessionFilter(tools=frozenset(["read"]))
        result = apply_filters(sessions, filt)
        filt_upper = SessionFilter(tools=frozenset(["READ"]))
        result_upper = apply_filters(sessions, filt_upper)
        assert len(result) == len(result_upper)

    def test_filter_by_nonexistent_tool(self) -> None:
        sessions = _sessions()
        filt = SessionFilter(tools=frozenset(["NonExistentTool"]))
        result = apply_filters(sessions, filt)
        assert len(result) == 0

    def test_filter_by_min_cost(self) -> None:
        sessions = _sessions()
        # Use a very high min_cost to exclude all
        filt = SessionFilter(min_cost=Decimal("999999"))
        result = apply_filters(sessions, filt, pricing=DEFAULT_PRICING)
        assert len(result) == 0

    def test_filter_by_max_cost(self) -> None:
        sessions = _sessions()
        # Use a very high max_cost to include all
        filt = SessionFilter(max_cost=Decimal("999999"))
        result = apply_filters(sessions, filt, pricing=DEFAULT_PRICING)
        assert len(result) == len(sessions)

    def test_filter_by_max_cost_excludes_expensive(self) -> None:
        sessions = _sessions()
        # Use a very low max_cost to exclude all
        filt = SessionFilter(max_cost=Decimal("0"))
        result = apply_filters(sessions, filt, pricing=DEFAULT_PRICING)
        assert len(result) == 0

    def test_combined_model_and_tool(self) -> None:
        sessions = _sessions()
        filt = SessionFilter(
            models=frozenset(["sonnet"]),
            tools=frozenset(["Read"]),
        )
        result = apply_filters(sessions, filt)
        for s in result:
            assert "claude-sonnet-4-6" in s.models_used

    def test_combined_model_and_cost(self) -> None:
        sessions = _sessions()
        filt = SessionFilter(
            models=frozenset(["opus"]),
            min_cost=Decimal("0"),
        )
        result = apply_filters(sessions, filt, pricing=DEFAULT_PRICING)
        assert len(result) == 1
        assert "claude-opus-4-6" in result[0].models_used

    def test_empty_session_list(self) -> None:
        filt = SessionFilter(models=frozenset(["sonnet"]))
        result = apply_filters([], filt)
        assert result == []


class TestTokenFilters:
    def test_is_empty_with_min_tokens(self) -> None:
        filt = SessionFilter(min_tokens=1000)
        assert filt.is_empty is False

    def test_is_empty_with_max_tokens(self) -> None:
        filt = SessionFilter(max_tokens=100000)
        assert filt.is_empty is False

    def test_filter_by_min_tokens(self) -> None:
        sessions = _sessions()
        filt = SessionFilter(min_tokens=999_999_999)
        result = apply_filters(sessions, filt)
        assert len(result) == 0

    def test_filter_by_max_tokens(self) -> None:
        sessions = _sessions()
        filt = SessionFilter(max_tokens=999_999_999)
        result = apply_filters(sessions, filt)
        assert len(result) == len(sessions)

    def test_filter_by_max_tokens_excludes(self) -> None:
        sessions = _sessions()
        filt = SessionFilter(max_tokens=0)
        result = apply_filters(sessions, filt)
        assert len(result) == 0
