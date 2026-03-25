"""Session filtering by model, tool, and cost thresholds."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from parsimony.models.cost import ModelPricing, calculate_session_cost
from parsimony.models.session import Session


@dataclass(frozen=True)
class SessionFilter:
    """Immutable filter criteria for narrowing session results.

    All fields are optional.  When ``None``, that dimension is not filtered.
    """

    models: frozenset[str] | None = None
    tools: frozenset[str] | None = None
    min_cost: Decimal | None = None
    max_cost: Decimal | None = None

    @property
    def is_empty(self) -> bool:
        return (
            self.models is None
            and self.tools is None
            and self.min_cost is None
            and self.max_cost is None
        )


def _normalize_model_name(name: str) -> str:
    """Map short aliases to full model identifiers.

    Accepts inputs like ``"sonnet"``, ``"opus"``, ``"haiku"`` and returns the
    canonical model id so users don't have to type the full string.
    """
    lower = name.lower().strip()
    aliases: dict[str, str] = {
        "opus": "claude-opus-4-6",
        "sonnet": "claude-sonnet-4-6",
        "haiku": "claude-haiku-4-5-20251001",
    }
    return aliases.get(lower, name)


def _session_uses_tool(session: Session, tool_names: frozenset[str]) -> bool:
    """Return True if the session contains at least one call to any of the named tools."""
    lower_names = frozenset(t.lower() for t in tool_names)
    for segment in session.segments:
        for call in segment.calls:
            for tool_ref in call.tool_uses:
                if tool_ref.tool_name.lower() in lower_names:
                    return True
    return False


def apply_filters(
    sessions: list[Session],
    filt: SessionFilter,
    pricing: dict[str, ModelPricing] | None = None,
) -> list[Session]:
    """Return only sessions that match all criteria in *filt*.

    Filters are applied in cheapest-first order: model and tool checks
    (pure attribute lookups) run before cost checks (which require
    ``calculate_session_cost``).

    Args:
        sessions: Sessions to filter.
        filt: Filter criteria.
        pricing: Pricing table required when ``min_cost`` or ``max_cost``
            is set.  Ignored otherwise.

    Returns:
        A new list containing only matching sessions.
    """
    if filt.is_empty:
        return sessions

    normalized_models: frozenset[str] | None = None
    if filt.models is not None:
        normalized_models = frozenset(
            _normalize_model_name(m) for m in filt.models
        )

    result: list[Session] = []
    for session in sessions:
        # Model filter: session must use at least one of the requested models
        if normalized_models is not None and not session.models_used & normalized_models:
            continue

        # Tool filter: session must contain at least one matching tool call
        if filt.tools is not None and not _session_uses_tool(session, filt.tools):
            continue

        # Cost filters require pricing
        if filt.min_cost is not None or filt.max_cost is not None:
            cost = calculate_session_cost(session, pricing)
            if filt.min_cost is not None and cost.total < filt.min_cost:
                continue
            if filt.max_cost is not None and cost.total > filt.max_cost:
                continue

        result.append(session)

    return result
