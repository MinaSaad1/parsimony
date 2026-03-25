"""Simple Rich-based chart renderers for terminal output."""

from __future__ import annotations

from decimal import Decimal

from rich.panel import Panel
from rich.text import Text

from parsimony.output.formatters import format_cost, format_percentage

_BAR_CHARS = " ▏▎▍▌▋▊▉█"


def _bar(value: float, max_value: float, width: int = 20) -> str:
    """Render a horizontal bar of given width using Unicode block characters."""
    if max_value <= 0 or value <= 0:
        return ""
    ratio = min(value / max_value, 1.0)
    full_blocks = int(ratio * width)
    remainder = (ratio * width) - full_blocks
    partial_index = int(remainder * (len(_BAR_CHARS) - 1))
    bar = "█" * full_blocks
    if full_blocks < width:
        bar += _BAR_CHARS[partial_index]
    return bar


def render_cost_trend(daily_costs: list[tuple[str, Decimal]]) -> Panel:
    """Render a daily cost trend as horizontal bars.

    Args:
        daily_costs: List of (date_label, cost) tuples, ordered chronologically.

    Returns:
        A Rich Panel containing the bar chart.
    """
    text = Text()
    if not daily_costs:
        text.append("  No data", style="dim")
        return Panel(text, title="Daily Cost Trend", border_style="bright_blue")

    max_cost = float(max(c for _, c in daily_costs)) if daily_costs else 1.0
    if max_cost <= 0:
        max_cost = 1.0

    for i, (label, cost) in enumerate(daily_costs):
        bar = _bar(float(cost), max_cost, width=30)
        text.append(f"  {label:>10}  ", style="dim")
        text.append(bar, style="green")
        text.append(f"  {format_cost(cost)}", style="bold green")
        if i < len(daily_costs) - 1:
            text.append("\n")

    return Panel(text, title="Daily Cost Trend", border_style="bright_blue")


def render_model_distribution(model_costs: dict[str, Decimal]) -> Panel:
    """Render model cost distribution as horizontal bars.

    Args:
        model_costs: Mapping of model display name to total cost.

    Returns:
        A Rich Panel containing the distribution chart.
    """
    text = Text()
    if not model_costs:
        text.append("  No data", style="dim")
        return Panel(text, title="Model Distribution", border_style="bright_blue")

    total = float(sum(model_costs.values()))
    max_cost = float(max(model_costs.values())) if model_costs else 1.0
    if max_cost <= 0:
        max_cost = 1.0

    sorted_models = sorted(model_costs.items(), key=lambda x: x[1], reverse=True)
    for i, (name, cost) in enumerate(sorted_models):
        share = float(cost) / total * 100 if total > 0 else 0
        bar = _bar(float(cost), max_cost, width=25)
        text.append(f"  {name:<16}  ", style="cyan")
        text.append(bar, style="green")
        text.append(f"  {format_cost(cost)}", style="bold green")
        text.append(f"  ({format_percentage(share)})", style="dim")
        if i < len(sorted_models) - 1:
            text.append("\n")

    return Panel(text, title="Model Distribution", border_style="bright_blue")


def render_cache_gauge(efficiency: float) -> Panel:
    """Render a cache efficiency gauge.

    Args:
        efficiency: Cache read efficiency as a percentage (0-100).

    Returns:
        A Rich Panel containing the gauge visualization.
    """
    text = Text()
    width = 40
    filled = int(efficiency / 100 * width)
    empty = width - filled

    text.append("  Cache Hit Rate: ", style="dim")
    text.append("█" * filled, style="green")
    text.append("░" * empty, style="dim")
    text.append(f"  {format_percentage(efficiency)}", style="bold green")

    return Panel(text, title="Cache Efficiency", border_style="bright_blue")
