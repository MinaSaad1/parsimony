"""Usage gauge renderers for token budget visualization."""

from __future__ import annotations

from rich.panel import Panel
from rich.text import Text

from parsimony.budget import TokenBudgetConfig
from parsimony.output.formatters import format_tokens

_BAR_WIDTH = 30


def _gauge_style(percentage: float) -> str:
    if percentage >= 90:
        return "bold red"
    if percentage >= 70:
        return "bold yellow"
    return "bold green"


def render_usage_gauge(used: int, limit: int, label: str) -> Text:
    percentage = (used / limit * 100) if limit > 0 else 0.0
    filled = int(percentage / 100 * _BAR_WIDTH)
    filled = min(filled, _BAR_WIDTH)
    empty = _BAR_WIDTH - filled
    bar = "█" * filled + "░" * empty
    style = _gauge_style(percentage)
    text = Text()
    text.append(f"  {label}: ", style="dim")
    text.append(bar, style=style)
    text.append(f"  {format_tokens(used)} / {format_tokens(limit)}", style=style)
    text.append(f"  ({percentage:.1f}%)", style="dim")
    return text


def render_usage_summary(
    token_budget: TokenBudgetConfig,
    weekly_tokens: int,
    peak_session_tokens: int,
) -> Panel:
    lines: list[Text] = []
    if token_budget.weekly_limit is not None:
        lines.append(render_usage_gauge(weekly_tokens, token_budget.weekly_limit, "Weekly"))
    if token_budget.session_limit is not None:
        lines.append(
            render_usage_gauge(peak_session_tokens, token_budget.session_limit, "Session Peak")
        )

    combined = Text()
    for i, line in enumerate(lines):
        combined.append_text(line)
        if i < len(lines) - 1:
            combined.append("\n")

    return Panel(combined, title="Usage Limits", border_style="bright_blue")
