"""Tests for parsimony.output.gauges."""

from __future__ import annotations

from rich.panel import Panel
from rich.text import Text

from parsimony.budget import TokenBudgetConfig
from parsimony.output.gauges import render_usage_gauge, render_usage_summary


class TestRenderUsageGauge:
    def test_returns_text(self) -> None:
        result = render_usage_gauge(30_000, 88_000, "Session")
        assert isinstance(result, Text)

    def test_zero_usage(self) -> None:
        result = render_usage_gauge(0, 88_000, "Session")
        assert isinstance(result, Text)

    def test_over_limit(self) -> None:
        result = render_usage_gauge(100_000, 88_000, "Session")
        assert isinstance(result, Text)

    def test_zero_limit(self) -> None:
        result = render_usage_gauge(1000, 0, "Session")
        assert isinstance(result, Text)


class TestRenderUsageSummary:
    def test_weekly_only(self) -> None:
        cfg = TokenBudgetConfig(weekly_limit=45_000_000)
        result = render_usage_summary(cfg, 30_000_000, 0)
        assert isinstance(result, Panel)

    def test_session_only(self) -> None:
        cfg = TokenBudgetConfig(session_limit=88_000)
        result = render_usage_summary(cfg, 0, 50_000)
        assert isinstance(result, Panel)

    def test_both_limits(self) -> None:
        cfg = TokenBudgetConfig(session_limit=88_000, weekly_limit=45_000_000)
        result = render_usage_summary(cfg, 30_000_000, 50_000)
        assert isinstance(result, Panel)
