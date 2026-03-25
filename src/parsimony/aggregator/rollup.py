"""Aggregation and rollup of session metrics."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from parsimony.models.cost import (
    DEFAULT_PRICING,
    ModelPricing,
    calculate_session_cost,
)
from parsimony.models.session import Session
from parsimony.models.tool_usage import parse_tool_name


@dataclass(frozen=True)
class ModelRollup:
    """Aggregated metrics for a single model."""

    model: str
    input_tokens: int
    output_tokens: int
    cache_write_tokens: int
    cache_read_tokens: int
    cost: Decimal
    call_count: int

    @property
    def total_tokens(self) -> int:
        return (
            self.input_tokens
            + self.output_tokens
            + self.cache_write_tokens
            + self.cache_read_tokens
        )


@dataclass(frozen=True)
class ToolRollup:
    """Aggregated metrics for a single tool."""

    name: str
    call_count: int
    is_mcp: bool
    mcp_server: str | None


@dataclass(frozen=True)
class SessionRollup:
    """Complete rollup of metrics across a collection of sessions."""

    session_count: int
    total_tokens: int
    total_cost: Decimal
    per_model: dict[str, ModelRollup]
    per_tool: dict[str, ToolRollup]
    mcp_breakdown: dict[str, dict[str, int]]
    cache_efficiency: float
    avg_cost_per_session: Decimal
    most_expensive_session: Session | None
    most_expensive_cost: Decimal
    subagent_total_tokens: int
    subagent_total_cost: Decimal


def compute_rollup(
    sessions: list[Session],
    pricing: dict[str, ModelPricing] | None = None,
) -> SessionRollup:
    """Compute a full rollup from a list of sessions.

    Args:
        sessions: The sessions to aggregate.
        pricing: Model pricing table. Defaults to DEFAULT_PRICING.

    Returns:
        A SessionRollup with all metrics computed.
    """
    if pricing is None:
        pricing = DEFAULT_PRICING

    # Per-model aggregation
    model_input: dict[str, int] = {}
    model_output: dict[str, int] = {}
    model_cache_write: dict[str, int] = {}
    model_cache_read: dict[str, int] = {}
    model_calls: dict[str, int] = {}
    model_cost: dict[str, Decimal] = {}

    # Tool aggregation
    tool_counts: dict[str, int] = {}

    # MCP breakdown
    mcp_breakdown: dict[str, dict[str, int]] = {}

    # Session costs for finding most expensive
    session_costs: list[tuple[Session, Decimal]] = []

    # Subagent totals
    subagent_tokens = 0
    subagent_cost_total = Decimal("0")

    for session in sessions:
        cost = calculate_session_cost(session, pricing)
        session_costs.append((session, cost.total))
        subagent_cost_total += cost.subagent_cost

        for segment in session.segments:
            model = segment.model
            model_input[model] = model_input.get(model, 0) + segment.total_input_tokens
            model_output[model] = model_output.get(model, 0) + segment.total_output_tokens
            model_cache_write[model] = (
                model_cache_write.get(model, 0) + segment.total_cache_write_tokens
            )
            model_cache_read[model] = (
                model_cache_read.get(model, 0) + segment.total_cache_read_tokens
            )
            model_calls[model] = model_calls.get(model, 0) + segment.call_count

            for call in segment.calls:
                for tool_ref in call.tool_uses:
                    tool_counts[tool_ref.tool_name] = (
                        tool_counts.get(tool_ref.tool_name, 0) + 1
                    )
                    parsed = parse_tool_name(tool_ref.tool_name)
                    if parsed.is_mcp and parsed.mcp_server and parsed.mcp_tool:
                        if parsed.mcp_server not in mcp_breakdown:
                            mcp_breakdown[parsed.mcp_server] = {}
                        server_tools = mcp_breakdown[parsed.mcp_server]
                        server_tools[parsed.mcp_tool] = (
                            server_tools.get(parsed.mcp_tool, 0) + 1
                        )

        for sub in session.subagent_results:
            subagent_tokens += sub.total_tokens

    # Build per-model cost from session costs
    for session in sessions:
        sc = calculate_session_cost(session, pricing)
        for model_name, cb in sc.per_model_costs.items():
            model_cost[model_name] = model_cost.get(model_name, Decimal("0")) + cb.total

    # Build ModelRollup dict
    all_models = set(model_input) | set(model_cost)
    per_model: dict[str, ModelRollup] = {}
    for model in all_models:
        per_model[model] = ModelRollup(
            model=model,
            input_tokens=model_input.get(model, 0),
            output_tokens=model_output.get(model, 0),
            cache_write_tokens=model_cache_write.get(model, 0),
            cache_read_tokens=model_cache_read.get(model, 0),
            cost=model_cost.get(model, Decimal("0")),
            call_count=model_calls.get(model, 0),
        )

    # Build ToolRollup dict
    per_tool: dict[str, ToolRollup] = {}
    for name, count in tool_counts.items():
        parsed = parse_tool_name(name)
        per_tool[name] = ToolRollup(
            name=name,
            call_count=count,
            is_mcp=parsed.is_mcp,
            mcp_server=parsed.mcp_server,
        )

    # Totals
    total_tokens = sum(mr.total_tokens for mr in per_model.values())
    total_cost = sum((mr.cost for mr in per_model.values()), Decimal("0")) + subagent_cost_total

    # Cache efficiency
    total_cache_read = sum(model_cache_read.values())
    total_input = sum(model_input.values())
    total_cache_write = sum(model_cache_write.values())
    denominator = total_input + total_cache_read + total_cache_write
    cache_efficiency = (total_cache_read / denominator * 100) if denominator > 0 else 0.0

    # Most expensive session
    most_expensive: Session | None = None
    most_expensive_cost_val = Decimal("0")
    for session, cost_val in session_costs:
        if cost_val > most_expensive_cost_val:
            most_expensive = session
            most_expensive_cost_val = cost_val

    # Avg cost
    avg_cost = total_cost / len(sessions) if sessions else Decimal("0")

    return SessionRollup(
        session_count=len(sessions),
        total_tokens=total_tokens,
        total_cost=total_cost,
        per_model=per_model,
        per_tool=per_tool,
        mcp_breakdown=mcp_breakdown,
        cache_efficiency=cache_efficiency,
        avg_cost_per_session=avg_cost,
        most_expensive_session=most_expensive,
        most_expensive_cost=most_expensive_cost_val,
        subagent_total_tokens=subagent_tokens,
        subagent_total_cost=subagent_cost_total,
    )
