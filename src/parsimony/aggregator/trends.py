"""Cost trend analysis with moving averages and direction detection."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

from parsimony.aggregator.grouper import group_by_day
from parsimony.aggregator.rollup import compute_rollup
from parsimony.models.cost import ModelPricing
from parsimony.models.session import Session


@dataclass(frozen=True)
class DailyTrend:
    """Aggregated metrics for a single day."""

    day: date
    cost: Decimal
    tokens: int
    sessions: int
    cache_efficiency: float


def compute_trends(
    sessions: list[Session],
    days: int = 30,
    pricing: dict[str, ModelPricing] | None = None,
) -> list[DailyTrend]:
    """Compute per-day cost, token, and session metrics.

    Returns one ``DailyTrend`` per day in the range, including days with
    zero activity so the timeline has no gaps.

    Args:
        sessions: All sessions (will be grouped by day internally).
        days: Number of days to include (counting back from today).
        pricing: Pricing table for cost calculation.

    Returns:
        A chronologically sorted list of DailyTrend entries.
    """
    from parsimony.aggregator.time_range import _local_now

    today = _local_now().date()
    start = today - timedelta(days=days - 1)

    by_day = group_by_day(sessions)

    trends: list[DailyTrend] = []
    for offset in range(days):
        d = start + timedelta(days=offset)
        day_sessions = by_day.get(d, [])

        if day_sessions:
            rollup = compute_rollup(day_sessions, pricing)
            trends.append(DailyTrend(
                day=d,
                cost=rollup.total_cost,
                tokens=rollup.total_tokens,
                sessions=rollup.session_count,
                cache_efficiency=rollup.cache_efficiency,
            ))
        else:
            trends.append(DailyTrend(
                day=d,
                cost=Decimal("0"),
                tokens=0,
                sessions=0,
                cache_efficiency=0.0,
            ))

    return trends


def moving_average(
    trends: list[DailyTrend],
    window: int = 7,
) -> list[Decimal]:
    """Compute a simple moving average of daily costs.

    For the first ``window - 1`` entries where there aren't enough
    preceding days, the average uses all available days up to that point.

    Args:
        trends: Chronologically sorted daily trends.
        window: Number of days in the moving average window.

    Returns:
        A list of Decimal averages, same length as *trends*.
    """
    result: list[Decimal] = []
    for i in range(len(trends)):
        start = max(0, i - window + 1)
        window_slice = trends[start:i + 1]
        total = sum((t.cost for t in window_slice), Decimal("0"))
        result.append(total / len(window_slice))
    return result


def moving_average_tokens(
    trends: list[DailyTrend],
    window: int = 7,
) -> list[int]:
    result: list[int] = []
    for i in range(len(trends)):
        start = max(0, i - window + 1)
        window_slice = trends[start:i + 1]
        total = sum(t.tokens for t in window_slice)
        result.append(total // len(window_slice))
    return result


def trend_direction_tokens(trends: list[DailyTrend], window: int = 7) -> str:
    if len(trends) < window * 2:
        return "stable"

    recent = trends[-window:]
    previous = trends[-window * 2:-window]

    recent_avg = sum(t.tokens for t in recent) / len(recent)
    prev_avg = sum(t.tokens for t in previous) / len(previous)

    if prev_avg == 0:
        return "rising" if recent_avg > 0 else "stable"

    change_pct = (recent_avg - prev_avg) / prev_avg * 100

    if change_pct > 10:
        return "rising"
    if change_pct < -10:
        return "falling"
    return "stable"


def trend_direction(trends: list[DailyTrend], window: int = 7) -> str:
    """Determine whether costs are rising, falling, or stable.

    Compares the moving average of the last ``window`` days to the
    preceding ``window`` days. A change of more than 10% in either
    direction is considered significant.

    Args:
        trends: Chronologically sorted daily trends.
        window: Window size for comparison.

    Returns:
        One of ``"rising"``, ``"falling"``, or ``"stable"``.
    """
    if len(trends) < window * 2:
        # Not enough data for a meaningful comparison
        recent = trends[-min(len(trends), window):]
        if not recent:
            return "stable"
        avg = sum((t.cost for t in recent), Decimal("0")) / len(recent)
        return "stable" if avg == 0 else "stable"

    recent = trends[-window:]
    previous = trends[-window * 2:-window]

    recent_avg = sum((t.cost for t in recent), Decimal("0")) / len(recent)
    prev_avg = sum((t.cost for t in previous), Decimal("0")) / len(previous)

    if prev_avg == 0:
        return "rising" if recent_avg > 0 else "stable"

    change_pct = float((recent_avg - prev_avg) / prev_avg * 100)

    if change_pct > 10:
        return "rising"
    if change_pct < -10:
        return "falling"
    return "stable"
