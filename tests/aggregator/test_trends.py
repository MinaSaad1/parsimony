"""Tests for parsimony.aggregator.trends."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

from click.testing import CliRunner

from parsimony.aggregator.trends import (
    DailyTrend,
    compute_trends,
    moving_average,
    trend_direction,
)
from parsimony.cli import main
from parsimony.models.session import Session
from parsimony.parser.reader import read_events
from parsimony.parser.session_builder import build_session

FIXTURES = Path(__file__).parent.parent / "fixtures"


def _make_session(fixture: str, session_id: str, project: str = "test") -> Session:
    events = list(read_events(FIXTURES / fixture))
    data = build_session(session_id, events)
    return Session.from_session_data(data, project, f"C:\\{project}")


def _make_trends(costs: list[float], start: date | None = None) -> list[DailyTrend]:
    """Build a list of DailyTrend from cost values."""
    if start is None:
        start = date(2026, 3, 1)
    return [
        DailyTrend(
            day=start + timedelta(days=i),
            cost=Decimal(str(c)),
            tokens=1000,
            sessions=1 if c > 0 else 0,
            cache_efficiency=50.0,
        )
        for i, c in enumerate(costs)
    ]


class TestComputeTrends:
    def test_empty_sessions(self) -> None:
        trends = compute_trends([], days=7)
        assert len(trends) == 7
        assert all(t.cost == Decimal("0") for t in trends)
        assert all(t.sessions == 0 for t in trends)

    def test_fills_gaps(self) -> None:
        # Even with sessions only on some days, all days should be present
        sessions = [
            _make_session(
                "simple_session.jsonl", "aaaa-1111-2222-3333-444444444444",
            ),
        ]
        trends = compute_trends(sessions, days=7)
        assert len(trends) == 7

    def test_chronological_order(self) -> None:
        trends = compute_trends([], days=10)
        for i in range(1, len(trends)):
            assert trends[i].day > trends[i - 1].day


class TestMovingAverage:
    def test_constant_values(self) -> None:
        trends = _make_trends([5.0] * 10)
        ma = moving_average(trends, window=3)
        assert len(ma) == 10
        # After the window fills, all averages should be 5.0
        for avg in ma[2:]:
            assert avg == Decimal("5")

    def test_increasing_values(self) -> None:
        trends = _make_trends([1.0, 2.0, 3.0, 4.0, 5.0])
        ma = moving_average(trends, window=3)
        assert len(ma) == 5
        # Last MA: avg of 3, 4, 5 = 4
        assert ma[4] == Decimal("4")

    def test_window_larger_than_data(self) -> None:
        trends = _make_trends([1.0, 2.0, 3.0])
        ma = moving_average(trends, window=10)
        assert len(ma) == 3
        # Each uses all available data up to that point
        assert ma[0] == Decimal("1")
        assert ma[1] == Decimal("1.5")
        assert ma[2] == Decimal("2")

    def test_single_entry(self) -> None:
        trends = _make_trends([7.0])
        ma = moving_average(trends, window=7)
        assert ma == [Decimal("7")]

    def test_empty(self) -> None:
        ma = moving_average([], window=7)
        assert ma == []

    def test_all_zeros(self) -> None:
        trends = _make_trends([0.0] * 5)
        ma = moving_average(trends, window=3)
        assert all(avg == Decimal("0") for avg in ma)


class TestTrendDirection:
    def test_rising(self) -> None:
        # First 7 days low, next 7 days high
        costs = [1.0] * 7 + [5.0] * 7
        trends = _make_trends(costs)
        assert trend_direction(trends, window=7) == "rising"

    def test_falling(self) -> None:
        costs = [5.0] * 7 + [1.0] * 7
        trends = _make_trends(costs)
        assert trend_direction(trends, window=7) == "falling"

    def test_stable(self) -> None:
        costs = [5.0] * 14
        trends = _make_trends(costs)
        assert trend_direction(trends, window=7) == "stable"

    def test_insufficient_data(self) -> None:
        trends = _make_trends([1.0, 2.0, 3.0])
        assert trend_direction(trends, window=7) == "stable"

    def test_empty(self) -> None:
        assert trend_direction([], window=7) == "stable"

    def test_from_zero_to_spending(self) -> None:
        costs = [0.0] * 7 + [5.0] * 7
        trends = _make_trends(costs)
        assert trend_direction(trends, window=7) == "rising"


class TestTrendCLI:
    def test_trend_command(self) -> None:
        sessions = [
            _make_session(
                "simple_session.jsonl", "aaaa-1111-2222-3333-444444444444",
            ),
        ]
        runner = CliRunner()
        with patch("parsimony.cli._load_all_sessions", return_value=sessions):
            result = runner.invoke(main, ["trend", "--days", "7"])
        assert result.exit_code == 0
        assert "Trend" in result.output

    def test_trend_json_export(self) -> None:
        sessions = [
            _make_session(
                "simple_session.jsonl", "aaaa-1111-2222-3333-444444444444",
            ),
        ]
        runner = CliRunner()
        with patch("parsimony.cli._load_all_sessions", return_value=sessions):
            result = runner.invoke(main, ["--export", "json", "trend", "--days", "7"])
        assert result.exit_code == 0
        assert "moving_avg" in result.output
        assert "date" in result.output

    def test_trend_empty(self) -> None:
        runner = CliRunner()
        with patch("parsimony.cli._load_all_sessions", return_value=[]):
            result = runner.invoke(main, ["trend", "--days", "3"])
        assert result.exit_code == 0
