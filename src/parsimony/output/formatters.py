"""Human-friendly formatting for tokens, costs, durations, and model names."""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal


def format_tokens(n: int) -> str:
    """Format a token count with thousands separators or M/K suffix."""
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 10_000:
        return f"{n / 1_000:.1f}K"
    return f"{n:,}"


def format_cost(d: Decimal) -> str:
    """Format a USD cost value."""
    if d == 0:
        return "$0.00"
    if d < Decimal("0.01"):
        return f"${d:.4f}"
    return f"${d:.2f}"


def format_duration(td: timedelta | None) -> str:
    """Format a timedelta as a human-readable string."""
    if td is None:
        return "-"
    total_seconds = int(td.total_seconds())
    if total_seconds < 60:
        return f"{total_seconds}s"
    minutes = total_seconds // 60
    seconds = total_seconds % 60
    if minutes < 60:
        return f"{minutes}m {seconds}s" if seconds else f"{minutes}m"
    hours = minutes // 60
    remaining_minutes = minutes % 60
    return f"{hours}h {remaining_minutes}m"


def format_percentage(f: float) -> str:
    """Format a percentage value."""
    return f"{f:.1f}%"


_MODEL_SHORT_NAMES: dict[str, str] = {
    "claude-opus-4-6": "Opus 4.6",
    "claude-sonnet-4-6": "Sonnet 4.6",
    "claude-haiku-4-5-20251001": "Haiku 4.5",
    "claude-haiku-4-5": "Haiku 4.5",
}


def format_model_name(name: str) -> str:
    """Shorten a model identifier to a human-friendly name."""
    if name in _MODEL_SHORT_NAMES:
        return _MODEL_SHORT_NAMES[name]
    # Generic fallback: strip "claude-" prefix, replace dashes
    if name.startswith("claude-"):
        return name[len("claude-"):].replace("-", " ").title()
    return name
