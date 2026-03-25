"""Cost calculation engine using Decimal precision.

Computes token costs per model using configurable pricing tables. All
monetary values use ``decimal.Decimal`` to avoid floating-point rounding
errors in financial calculations.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from decimal import Decimal

from parsimony.parser.events import TokenUsage

logger = logging.getLogger("parsimony.models.cost")

_MILLION = Decimal("1000000")


@dataclass(frozen=True)
class ModelPricing:
    """Per-model token pricing rates (USD per million tokens)."""

    input_per_million: Decimal
    output_per_million: Decimal
    cache_write_per_million: Decimal
    cache_read_per_million: Decimal


@dataclass(frozen=True)
class CostBreakdown:
    """Itemized cost for a single usage block."""

    input_cost: Decimal
    output_cost: Decimal
    cache_write_cost: Decimal
    cache_read_cost: Decimal

    @property
    def total(self) -> Decimal:
        return (
            self.input_cost
            + self.output_cost
            + self.cache_write_cost
            + self.cache_read_cost
        )


@dataclass(frozen=True)
class SessionCost:
    """Aggregated cost for an entire session, broken down by model."""

    per_model_costs: dict[str, CostBreakdown]
    subagent_cost: Decimal

    @property
    def total(self) -> Decimal:
        model_total = sum(
            (cb.total for cb in self.per_model_costs.values()),
            Decimal("0"),
        )
        return model_total + self.subagent_cost


# ---------------------------------------------------------------------------
# Default pricing (can be overridden via pricing.yaml)
# ---------------------------------------------------------------------------

DEFAULT_PRICING: dict[str, ModelPricing] = {
    "claude-opus-4-6": ModelPricing(
        input_per_million=Decimal("5.00"),
        output_per_million=Decimal("25.00"),
        cache_write_per_million=Decimal("6.25"),
        cache_read_per_million=Decimal("0.50"),
    ),
    "claude-sonnet-4-6": ModelPricing(
        input_per_million=Decimal("3.00"),
        output_per_million=Decimal("15.00"),
        cache_write_per_million=Decimal("3.75"),
        cache_read_per_million=Decimal("0.30"),
    ),
    "claude-haiku-4-5-20251001": ModelPricing(
        input_per_million=Decimal("1.00"),
        output_per_million=Decimal("5.00"),
        cache_write_per_million=Decimal("1.25"),
        cache_read_per_million=Decimal("0.10"),
    ),
}

# Fallback for unknown models (uses Sonnet pricing as safe default)
_FALLBACK_MODEL = "claude-sonnet-4-6"


def _get_pricing(model: str, pricing_table: dict[str, ModelPricing]) -> ModelPricing:
    """Look up pricing for a model, falling back to Sonnet with a warning."""
    if model in pricing_table:
        return pricing_table[model]
    logger.warning(
        "Unknown model '%s', using fallback pricing (%s)",
        model,
        _FALLBACK_MODEL,
    )
    return pricing_table.get(_FALLBACK_MODEL, DEFAULT_PRICING[_FALLBACK_MODEL])


def calculate_cost(usage: TokenUsage, pricing: ModelPricing) -> CostBreakdown:
    """Calculate the cost breakdown for a single usage block.

    Args:
        usage: Token counts from an API call.
        pricing: Per-million-token rates for the model used.

    Returns:
        An itemized CostBreakdown with Decimal precision.
    """
    return CostBreakdown(
        input_cost=Decimal(usage.input_tokens) * pricing.input_per_million / _MILLION,
        output_cost=Decimal(usage.output_tokens) * pricing.output_per_million / _MILLION,
        cache_write_cost=(
            Decimal(usage.cache_creation_input_tokens)
            * pricing.cache_write_per_million
            / _MILLION
        ),
        cache_read_cost=(
            Decimal(usage.cache_read_input_tokens)
            * pricing.cache_read_per_million
            / _MILLION
        ),
    )


def calculate_session_cost(
    session: object,
    pricing_table: dict[str, ModelPricing] | None = None,
) -> SessionCost:
    """Calculate the total cost of a session across all model segments.

    Args:
        session: A Session or SessionData object with ``segments`` and
            ``subagent_results`` attributes.
        pricing_table: Model-to-pricing mapping. Defaults to DEFAULT_PRICING.

    Returns:
        A SessionCost with per-model breakdowns and subagent costs.
    """
    if pricing_table is None:
        pricing_table = DEFAULT_PRICING

    per_model: dict[str, CostBreakdown] = {}

    for segment in session.segments:  # type: ignore[attr-defined]
        pricing = _get_pricing(segment.model, pricing_table)
        segment_costs: list[CostBreakdown] = []
        for call in segment.calls:
            segment_costs.append(calculate_cost(call.usage, pricing))

        # Merge costs for same model across multiple segments
        merged = CostBreakdown(
            input_cost=sum((c.input_cost for c in segment_costs), Decimal("0")),
            output_cost=sum((c.output_cost for c in segment_costs), Decimal("0")),
            cache_write_cost=sum(
                (c.cache_write_cost for c in segment_costs), Decimal("0")
            ),
            cache_read_cost=sum(
                (c.cache_read_cost for c in segment_costs), Decimal("0")
            ),
        )

        if segment.model in per_model:
            existing = per_model[segment.model]
            per_model[segment.model] = CostBreakdown(
                input_cost=existing.input_cost + merged.input_cost,
                output_cost=existing.output_cost + merged.output_cost,
                cache_write_cost=existing.cache_write_cost + merged.cache_write_cost,
                cache_read_cost=existing.cache_read_cost + merged.cache_read_cost,
            )
        else:
            per_model[segment.model] = merged

    # Calculate subagent costs (use Sonnet pricing as approximation)
    subagent_total = Decimal("0")
    for sub in session.subagent_results:  # type: ignore[attr-defined]
        sub_pricing = _get_pricing(_FALLBACK_MODEL, pricing_table)
        sub_cost = calculate_cost(sub.usage, sub_pricing)
        subagent_total += sub_cost.total

    return SessionCost(per_model_costs=per_model, subagent_cost=subagent_total)
