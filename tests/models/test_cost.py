"""Tests for parsimony.models.cost."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

from parsimony.models.cost import (
    DEFAULT_PRICING,
    CostBreakdown,
    ModelPricing,
    calculate_cost,
    calculate_session_cost,
)
from parsimony.parser.events import TokenUsage
from parsimony.parser.reader import read_events
from parsimony.parser.session_builder import build_session

FIXTURES = Path(__file__).parent.parent / "fixtures"


class TestCostBreakdown:
    def test_total(self) -> None:
        cb = CostBreakdown(
            input_cost=Decimal("1.00"),
            output_cost=Decimal("2.00"),
            cache_write_cost=Decimal("0.50"),
            cache_read_cost=Decimal("0.25"),
        )
        assert cb.total == Decimal("3.75")


class TestCalculateCost:
    def test_sonnet_pricing(self) -> None:
        usage = TokenUsage(
            input_tokens=1_000_000,
            output_tokens=1_000_000,
            cache_creation_input_tokens=1_000_000,
            cache_read_input_tokens=1_000_000,
        )
        pricing = DEFAULT_PRICING["claude-sonnet-4-6"]
        cost = calculate_cost(usage, pricing)

        assert cost.input_cost == Decimal("3.00")
        assert cost.output_cost == Decimal("15.00")
        assert cost.cache_write_cost == Decimal("3.75")
        assert cost.cache_read_cost == Decimal("0.30")
        assert cost.total == Decimal("22.05")

    def test_zero_tokens(self) -> None:
        usage = TokenUsage()
        pricing = DEFAULT_PRICING["claude-sonnet-4-6"]
        cost = calculate_cost(usage, pricing)

        assert cost.total == Decimal("0")

    def test_opus_more_expensive(self) -> None:
        usage = TokenUsage(input_tokens=1000, output_tokens=1000)
        sonnet_cost = calculate_cost(usage, DEFAULT_PRICING["claude-sonnet-4-6"])
        opus_cost = calculate_cost(usage, DEFAULT_PRICING["claude-opus-4-6"])

        assert opus_cost.total > sonnet_cost.total

    def test_decimal_precision(self) -> None:
        """Ensure small token counts don't lose precision."""
        usage = TokenUsage(input_tokens=1, output_tokens=1)
        pricing = DEFAULT_PRICING["claude-sonnet-4-6"]
        cost = calculate_cost(usage, pricing)

        # input: 1/1M * 3.00 = 0.000003
        # output: 1/1M * 15.00 = 0.000015
        assert cost.input_cost == Decimal("1") * Decimal("3.00") / Decimal("1000000")
        assert cost.total > Decimal("0")


class TestCalculateSessionCost:
    def test_simple_session(self) -> None:
        events = list(read_events(FIXTURES / "simple_session.jsonl"))
        data = build_session("test", events)
        cost = calculate_session_cost(data)

        assert cost.total > Decimal("0")
        assert "claude-sonnet-4-6" in cost.per_model_costs

    def test_multi_model_session(self) -> None:
        events = list(read_events(FIXTURES / "multi_model_session.jsonl"))
        data = build_session("test", events)
        cost = calculate_session_cost(data)

        assert "claude-sonnet-4-6" in cost.per_model_costs
        assert "claude-opus-4-6" in cost.per_model_costs
        assert "claude-haiku-4-5-20251001" in cost.per_model_costs
        assert cost.total > Decimal("0")

    def test_subagent_cost_included(self) -> None:
        events = list(read_events(FIXTURES / "subagent_session.jsonl"))
        data = build_session("test", events)
        cost = calculate_session_cost(data)

        assert cost.subagent_cost > Decimal("0")
        assert cost.total > cost.subagent_cost  # session also has direct costs

    def test_empty_session(self) -> None:
        data = build_session("empty", [])
        cost = calculate_session_cost(data)

        assert cost.total == Decimal("0")
        assert cost.subagent_cost == Decimal("0")
