"""Rich table renderer for session diffs."""

from __future__ import annotations

from rich.console import Group
from rich.table import Table
from rich.text import Text

from parsimony.aggregator.diff import DeltaValue, SessionDiff
from parsimony.output.formatters import (
    format_cost,
    format_model_name,
    format_percentage,
    format_tokens,
)


def _arrow(delta: DeltaValue) -> Text:
    """Return a styled arrow showing direction and magnitude of change."""
    if delta.change > 0:
        return Text(f"+{delta.change_pct:.1f}%", style="red")
    if delta.change < 0:
        return Text(f"{delta.change_pct:.1f}%", style="green")
    return Text("0.0%", style="dim")


def _cost_arrow(delta: DeltaValue) -> Text:
    """Arrow for cost deltas (increase = red, decrease = green)."""
    sign = "+" if delta.change > 0 else ""
    if delta.change > 0:
        return Text(f"{sign}{format_cost(delta.change)} ({delta.change_pct:+.1f}%)", style="red")
    if delta.change < 0:
        return Text(f"{format_cost(delta.change)} ({delta.change_pct:+.1f}%)", style="green")
    return Text("--", style="dim")


def render_diff(diff: SessionDiff) -> Group:
    """Render a full side-by-side comparison of two sessions."""
    parts: list[Table | Text] = []

    # Header
    header = Text()
    header.append(f"  {diff.session_id_old[:8]}", style="cyan")
    header.append("  vs  ", style="dim")
    header.append(f"{diff.session_id_new[:8]}", style="cyan")
    parts.append(header)

    # Main metrics table
    table = Table(
        title="Session Comparison",
        show_header=True,
        header_style="bold magenta",
    )
    table.add_column("Metric", style="cyan", min_width=18)
    table.add_column(diff.session_id_old[:8], justify="right")
    table.add_column(diff.session_id_new[:8], justify="right")
    table.add_column("Change", justify="right")

    table.add_row(
        "Total Cost",
        format_cost(diff.total_cost.old),
        format_cost(diff.total_cost.new),
        _cost_arrow(diff.total_cost),
    )
    table.add_row(
        "Total Tokens",
        format_tokens(int(diff.total_tokens.old)),
        format_tokens(int(diff.total_tokens.new)),
        _arrow(diff.total_tokens),
    )
    table.add_row(
        "Input Tokens",
        format_tokens(int(diff.input_tokens.old)),
        format_tokens(int(diff.input_tokens.new)),
        _arrow(diff.input_tokens),
    )
    table.add_row(
        "Output Tokens",
        format_tokens(int(diff.output_tokens.old)),
        format_tokens(int(diff.output_tokens.new)),
        _arrow(diff.output_tokens),
    )
    table.add_row(
        "Cache Write",
        format_tokens(int(diff.cache_write_tokens.old)),
        format_tokens(int(diff.cache_write_tokens.new)),
        _arrow(diff.cache_write_tokens),
    )
    table.add_row(
        "Cache Read",
        format_tokens(int(diff.cache_read_tokens.old)),
        format_tokens(int(diff.cache_read_tokens.new)),
        _arrow(diff.cache_read_tokens),
    )
    table.add_row(
        "Cache Efficiency",
        format_percentage(float(diff.cache_efficiency.old)),
        format_percentage(float(diff.cache_efficiency.new)),
        _arrow(diff.cache_efficiency),
    )
    table.add_row(
        "API Calls",
        str(int(diff.api_calls.old)),
        str(int(diff.api_calls.new)),
        _arrow(diff.api_calls),
    )
    parts.append(table)

    # Per-model cost table (only if there are models)
    if diff.per_model_cost:
        model_table = Table(
            title="By Model",
            show_header=True,
            header_style="bold magenta",
        )
        model_table.add_column("Model", style="cyan", min_width=14)
        model_table.add_column(diff.session_id_old[:8], justify="right")
        model_table.add_column(diff.session_id_new[:8], justify="right")
        model_table.add_column("Change", justify="right")

        for model in sorted(
            diff.per_model_cost, key=lambda m: diff.per_model_cost[m].new, reverse=True,
        ):
            dv = diff.per_model_cost[model]
            model_table.add_row(
                format_model_name(model),
                format_cost(dv.old),
                format_cost(dv.new),
                _cost_arrow(dv),
            )
        parts.append(model_table)

    # Per-tool count table (top 10 by total)
    if diff.per_tool_count:
        tool_table = Table(
            title="By Tool",
            show_header=True,
            header_style="bold magenta",
        )
        tool_table.add_column("Tool", style="cyan", min_width=14)
        tool_table.add_column(diff.session_id_old[:8], justify="right")
        tool_table.add_column(diff.session_id_new[:8], justify="right")
        tool_table.add_column("Change", justify="right")

        sorted_tools = sorted(
            diff.per_tool_count.items(),
            key=lambda kv: max(kv[1].old, kv[1].new),
            reverse=True,
        )
        for tool_name, dv in sorted_tools[:10]:
            tool_table.add_row(
                tool_name,
                str(int(dv.old)),
                str(int(dv.new)),
                _arrow(dv),
            )
        parts.append(tool_table)

    return Group(*parts)
