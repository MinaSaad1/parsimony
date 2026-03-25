"""Tests for parsimony.output.charts."""

from __future__ import annotations

from decimal import Decimal

from rich.panel import Panel

from parsimony.output.charts import (
    render_cache_gauge,
    render_cost_trend,
    render_model_distribution,
)


class TestRenderCostTrend:
    def test_empty_data(self) -> None:
        result = render_cost_trend([])
        assert isinstance(result, Panel)

    def test_with_data(self) -> None:
        data = [
            ("Mar 18", Decimal("1.50")),
            ("Mar 19", Decimal("3.00")),
            ("Mar 20", Decimal("0.75")),
        ]
        result = render_cost_trend(data)
        assert isinstance(result, Panel)

    def test_all_zero_costs(self) -> None:
        data = [("Mar 18", Decimal("0")), ("Mar 19", Decimal("0"))]
        result = render_cost_trend(data)
        assert isinstance(result, Panel)


class TestRenderModelDistribution:
    def test_empty_data(self) -> None:
        result = render_model_distribution({})
        assert isinstance(result, Panel)

    def test_with_models(self) -> None:
        costs = {
            "Sonnet 4.6": Decimal("5.00"),
            "Opus 4.6": Decimal("15.00"),
            "Haiku 4.5": Decimal("0.50"),
        }
        result = render_model_distribution(costs)
        assert isinstance(result, Panel)


class TestRenderCacheGauge:
    def test_zero_efficiency(self) -> None:
        result = render_cache_gauge(0.0)
        assert isinstance(result, Panel)

    def test_full_efficiency(self) -> None:
        result = render_cache_gauge(100.0)
        assert isinstance(result, Panel)

    def test_partial_efficiency(self) -> None:
        result = render_cache_gauge(67.5)
        assert isinstance(result, Panel)
