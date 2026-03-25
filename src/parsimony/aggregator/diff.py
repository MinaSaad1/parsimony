"""Side-by-side comparison of two sessions."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from parsimony.models.cost import ModelPricing, calculate_session_cost
from parsimony.models.session import Session


@dataclass(frozen=True)
class DeltaValue:
    """A single metric comparison between two sessions."""

    old: Decimal
    new: Decimal

    @property
    def change(self) -> Decimal:
        return self.new - self.old

    @property
    def change_pct(self) -> float:
        if self.old == 0:
            return 100.0 if self.new > 0 else 0.0
        return float(self.change / self.old * 100)


@dataclass(frozen=True)
class SessionDiff:
    """Comparison result between two sessions."""

    session_id_old: str
    session_id_new: str
    total_cost: DeltaValue
    total_tokens: DeltaValue
    input_tokens: DeltaValue
    output_tokens: DeltaValue
    cache_write_tokens: DeltaValue
    cache_read_tokens: DeltaValue
    cache_efficiency: DeltaValue
    api_calls: DeltaValue
    per_model_cost: dict[str, DeltaValue]
    per_tool_count: dict[str, DeltaValue]


def _cache_efficiency(session: Session) -> Decimal:
    """Compute cache efficiency as a Decimal percentage."""
    total_in = session.total_input_tokens
    total_cw = session.total_cache_write_tokens
    total_cr = session.total_cache_read_tokens
    denom = total_in + total_cw + total_cr
    if denom == 0:
        return Decimal("0")
    return Decimal(total_cr) / Decimal(denom) * 100


def _tool_counts(session: Session) -> dict[str, int]:
    """Count tool calls across all segments."""
    counts: dict[str, int] = {}
    for seg in session.segments:
        for call in seg.calls:
            for ref in call.tool_uses:
                counts[ref.tool_name] = counts.get(ref.tool_name, 0) + 1
    return counts


def compute_diff(
    s1: Session,
    s2: Session,
    pricing: dict[str, ModelPricing] | None = None,
) -> SessionDiff:
    """Compare two sessions and produce a diff of all key metrics.

    Args:
        s1: The "old" (baseline) session.
        s2: The "new" session to compare against.
        pricing: Pricing table for cost calculation.

    Returns:
        A SessionDiff with delta values for every metric.
    """
    cost1 = calculate_session_cost(s1, pricing)
    cost2 = calculate_session_cost(s2, pricing)

    # Per-model cost deltas
    all_models = set(cost1.per_model_costs) | set(cost2.per_model_costs)
    per_model: dict[str, DeltaValue] = {}
    for model in all_models:
        old_cost = cost1.per_model_costs.get(model)
        new_cost = cost2.per_model_costs.get(model)
        per_model[model] = DeltaValue(
            old=old_cost.total if old_cost else Decimal("0"),
            new=new_cost.total if new_cost else Decimal("0"),
        )

    # Per-tool count deltas
    tools1 = _tool_counts(s1)
    tools2 = _tool_counts(s2)
    all_tools = set(tools1) | set(tools2)
    per_tool: dict[str, DeltaValue] = {}
    for tool in all_tools:
        per_tool[tool] = DeltaValue(
            old=Decimal(tools1.get(tool, 0)),
            new=Decimal(tools2.get(tool, 0)),
        )

    return SessionDiff(
        session_id_old=s1.session_id,
        session_id_new=s2.session_id,
        total_cost=DeltaValue(old=cost1.total, new=cost2.total),
        total_tokens=DeltaValue(
            old=Decimal(s1.total_tokens), new=Decimal(s2.total_tokens),
        ),
        input_tokens=DeltaValue(
            old=Decimal(s1.total_input_tokens), new=Decimal(s2.total_input_tokens),
        ),
        output_tokens=DeltaValue(
            old=Decimal(s1.total_output_tokens), new=Decimal(s2.total_output_tokens),
        ),
        cache_write_tokens=DeltaValue(
            old=Decimal(s1.total_cache_write_tokens),
            new=Decimal(s2.total_cache_write_tokens),
        ),
        cache_read_tokens=DeltaValue(
            old=Decimal(s1.total_cache_read_tokens),
            new=Decimal(s2.total_cache_read_tokens),
        ),
        cache_efficiency=DeltaValue(
            old=_cache_efficiency(s1), new=_cache_efficiency(s2),
        ),
        api_calls=DeltaValue(
            old=Decimal(s1.total_api_calls), new=Decimal(s2.total_api_calls),
        ),
        per_model_cost=per_model,
        per_tool_count=per_tool,
    )
