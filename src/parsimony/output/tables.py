"""Rich table renderers for terminal output."""

from __future__ import annotations

from rich.console import Group
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from parsimony.aggregator.rollup import SessionRollup
from parsimony.budget import BudgetStatus, TokenBudgetStatus
from parsimony.models.cost import SessionCost
from parsimony.models.session import Session
from parsimony.output.display_config import DisplayConfig
from parsimony.output.formatters import (
    format_cost,
    format_duration,
    format_model_name,
    format_percentage,
    format_tokens,
)

_DEFAULT_CONFIG = DisplayConfig()


def render_summary(
    rollup: SessionRollup,
    label: str = "",
    config: DisplayConfig = _DEFAULT_CONFIG,
) -> Panel:
    """Render a top-level summary panel."""
    title = f"Parsimony | {label}" if label else "Parsimony"
    text = Text()
    text.append("  Total Tokens: ", style="dim")
    text.append(format_tokens(rollup.total_tokens), style="bold cyan")
    text.append("  (", style="dim")
    text.append(f"In: {format_tokens(rollup.total_input_tokens)}", style="dim")
    text.append(f"  Out: {format_tokens(rollup.total_output_tokens)}", style="dim")
    text.append(
        f"  Cache: {format_tokens(rollup.total_cache_read_tokens)}", style="dim"
    )
    text.append(")", style="dim")

    text.append("\n  Sessions: ", style="dim")
    text.append(str(rollup.session_count), style="bold cyan")
    text.append("    API Calls: ", style="dim")
    total_calls = sum(mr.call_count for mr in rollup.per_model.values())
    text.append(str(total_calls), style="bold cyan")

    if config.show_cost:
        text.append("    Cost: ", style="dim")
        text.append(format_cost(rollup.total_cost), style="bold green")

    return Panel(text, title=title, border_style="bright_blue")


def render_model_breakdown(
    rollup: SessionRollup,
    config: DisplayConfig = _DEFAULT_CONFIG,
) -> Table:
    """Render per-model token breakdown."""
    table = Table(title="By Model", show_header=True, header_style="bold magenta")
    table.add_column("Model", style="cyan", min_width=18)
    table.add_column("Tokens", justify="right", style="bold cyan")
    table.add_column("Share", justify="right")
    if config.show_cost:
        table.add_column("Cost", justify="right", style="green")

    total = rollup.total_tokens if rollup.total_tokens > 0 else 1
    sorted_models = sorted(
        rollup.per_model.values(), key=lambda m: m.total_tokens, reverse=True
    )

    for mr in sorted_models:
        share = mr.total_tokens / total * 100 if rollup.total_tokens > 0 else 0
        row = [
            format_model_name(mr.model),
            format_tokens(mr.total_tokens),
            format_percentage(share),
        ]
        if config.show_cost:
            row.append(format_cost(mr.cost))
        table.add_row(*row)

    return table


def render_tool_breakdown(rollup: SessionRollup, limit: int = 15) -> Table:
    """Render tool usage breakdown."""
    table = Table(title="By Tool", show_header=True, header_style="bold magenta")
    table.add_column("Tool", style="cyan", min_width=20)
    table.add_column("Calls", justify="right")
    table.add_column("Type", justify="right")

    sorted_tools = sorted(
        rollup.per_tool.values(), key=lambda t: t.call_count, reverse=True
    )

    for tr in sorted_tools[:limit]:
        tool_type = f"MCP: {tr.mcp_server}" if tr.is_mcp else "Built-in"
        table.add_row(tr.name, str(tr.call_count), tool_type)

    return table


def render_mcp_breakdown(rollup: SessionRollup) -> Table:
    """Render MCP server breakdown."""
    table = Table(title="MCP Servers", show_header=True, header_style="bold magenta")
    table.add_column("Server", style="cyan")
    table.add_column("Tool", style="white")
    table.add_column("Calls", justify="right")

    for server, tools in sorted(rollup.mcp_breakdown.items()):
        for tool_name, count in sorted(tools.items(), key=lambda x: -x[1]):
            table.add_row(server, tool_name, str(count))

    return table


def render_session_list(
    sessions_with_costs: list[tuple[Session, SessionCost]],
    limit: int = 10,
    config: DisplayConfig = _DEFAULT_CONFIG,
) -> Table:
    """Render a list of sessions sorted by token usage."""
    table = Table(title="Sessions", show_header=True, header_style="bold magenta")
    table.add_column("Time", style="dim", min_width=8)
    table.add_column("Duration", justify="right")
    table.add_column("Project", style="cyan", min_width=18)
    table.add_column("Model(s)", min_width=10)
    table.add_column("Tokens", justify="right", style="bold cyan")
    if config.show_cost:
        table.add_column("Cost", justify="right", style="green")

    sorted_sessions = sorted(
        sessions_with_costs,
        key=lambda sc: sc[0].total_tokens,
        reverse=True,
    )

    for session, cost in sorted_sessions[:limit]:
        time_str = (
            session.start_time.astimezone().strftime("%H:%M")
            if session.start_time
            else "-"
        )
        models = session.models_used
        if len(models) == 1:
            model_str = format_model_name(next(iter(models)))
        elif len(models) > 1:
            model_str = "mixed"
        else:
            model_str = "-"

        row = [
            time_str,
            format_duration(session.duration),
            session.project_name,
            model_str,
            format_tokens(session.total_tokens),
        ]
        if config.show_cost:
            row.append(format_cost(cost.total))
        table.add_row(*row)

    return table


def render_session_detail(
    session: Session,
    session_cost: SessionCost,
    config: DisplayConfig = _DEFAULT_CONFIG,
) -> Group:
    """Render a full drill-down for a single session."""
    parts: list[Table | Panel | Text] = []

    # Header
    header = Text()
    header.append(f"Session: {session.session_id[:8]}", style="bold cyan")
    header.append(f" | Project: {session.project_name}", style="dim")
    if session.start_time and session.end_time:
        start_str = session.start_time.astimezone().strftime("%Y-%m-%d %H:%M")
        header.append(f" | {start_str}", style="dim")
        header.append(f" ({format_duration(session.duration)})", style="dim")
    parts.append(Panel(header, border_style="bright_blue"))

    # Token summary (primary)
    token_text = Text()
    token_text.append(
        f"  Total Tokens: {format_tokens(session.total_tokens)}", style="bold cyan"
    )
    token_text.append(
        f"  |  API Calls: {session.total_api_calls}  |  Models: ", style="dim"
    )
    model_parts = []
    for seg in session.segments:
        model_parts.append(f"{format_model_name(seg.model)}({seg.call_count})")
    token_text.append(", ".join(model_parts), style="cyan")

    if config.show_cost:
        token_text.append(f"\n  Cost: {format_cost(session_cost.total)}", style="green")
    parts.append(token_text)

    # Model segments table
    seg_table = Table(
        title="Model Segments", show_header=True, header_style="bold magenta"
    )
    seg_table.add_column("Time", style="dim")
    seg_table.add_column("Model", style="cyan")
    seg_table.add_column("Calls", justify="right")
    seg_table.add_column("Input", justify="right")
    seg_table.add_column("Output", justify="right")
    seg_table.add_column("Cache W", justify="right")
    seg_table.add_column("Cache R", justify="right")

    for seg in session.segments:
        first_ts = seg.calls[0].timestamp if seg.calls else "-"
        if isinstance(first_ts, str) and first_ts != "-":
            try:
                from datetime import datetime

                dt = datetime.fromisoformat(first_ts.replace("Z", "+00:00"))
                first_ts = dt.astimezone().strftime("%H:%M")
            except (ValueError, TypeError):
                pass

        seg_table.add_row(
            str(first_ts),
            format_model_name(seg.model),
            str(seg.call_count),
            format_tokens(seg.total_input_tokens),
            format_tokens(seg.total_output_tokens),
            format_tokens(seg.total_cache_write_tokens),
            format_tokens(seg.total_cache_read_tokens),
        )
    parts.append(seg_table)

    # Tool breakdown for this session
    tool_counts: dict[str, int] = {}
    for seg in session.segments:
        for call in seg.calls:
            for tool_ref in call.tool_uses:
                tool_counts[tool_ref.tool_name] = (
                    tool_counts.get(tool_ref.tool_name, 0) + 1
                )

    if tool_counts:
        tool_table = Table(
            title="Tool Breakdown", show_header=True, header_style="bold magenta"
        )
        tool_table.add_column("Tool", style="cyan")
        tool_table.add_column("Calls", justify="right")
        for name, count in sorted(tool_counts.items(), key=lambda x: -x[1]):
            tool_table.add_row(name, str(count))
        parts.append(tool_table)

    # Subagents
    if session.subagent_results:
        sub_table = Table(
            title="Subagents", show_header=True, header_style="bold magenta"
        )
        sub_table.add_column("Agent", style="cyan")
        sub_table.add_column("Tokens", justify="right")
        sub_table.add_column("Tools", justify="right")
        sub_table.add_column("Duration", justify="right")
        for sub in session.subagent_results:
            from datetime import timedelta

            sub_table.add_row(
                sub.agent_id[:12],
                format_tokens(sub.total_tokens),
                str(sub.total_tool_use_count),
                format_duration(timedelta(milliseconds=sub.total_duration_ms)),
            )
        parts.append(sub_table)

    # Cache efficiency
    total_in = session.total_input_tokens
    total_cw = session.total_cache_write_tokens
    total_cr = session.total_cache_read_tokens
    denom = total_in + total_cw + total_cr
    efficiency = (total_cr / denom * 100) if denom > 0 else 0.0
    cache_text = Text()
    cache_text.append(
        f"  Cache Efficiency: {format_percentage(efficiency)} reads"
        f" | {format_percentage(100 - efficiency)} writes",
        style="dim",
    )
    parts.append(cache_text)

    return Group(*parts)


def render_budget_warning(statuses: list[BudgetStatus]) -> Panel | None:
    """Render a budget warning panel for any periods that are near or over limit.

    Returns ``None`` if no statuses warrant a warning (all under 70%).
    """
    lines: list[Text] = []
    for s in statuses:
        if s.over_budget:
            line = Text()
            line.append("  OVER BUDGET ", style="bold red")
            line.append(f"({s.period}): ", style="red")
            line.append(f"{format_cost(s.spent)}", style="bold red")
            line.append(f" / {format_cost(s.limit)}", style="dim")
            line.append(f"  ({format_percentage(s.percentage)})", style="red")
            lines.append(line)
        elif s.percentage >= 90:
            line = Text()
            line.append("  WARNING ", style="bold yellow")
            line.append(f"({s.period}): ", style="yellow")
            line.append(f"{format_cost(s.spent)}", style="bold yellow")
            line.append(f" / {format_cost(s.limit)}", style="dim")
            line.append(f"  ({format_percentage(s.percentage)})", style="yellow")
            lines.append(line)
        elif s.percentage >= 70:
            line = Text()
            line.append("  NOTICE ", style="bold blue")
            line.append(f"({s.period}): ", style="blue")
            line.append(f"{format_cost(s.spent)}", style="bold blue")
            line.append(f" / {format_cost(s.limit)}", style="dim")
            line.append(f"  ({format_percentage(s.percentage)})", style="blue")
            lines.append(line)

    if not lines:
        return None

    combined = Text("\n").join(lines)
    border = "red" if any(s.over_budget for s in statuses) else "yellow"
    return Panel(combined, title="Budget", border_style=border)


def _build_progress_bar(percentage: float, width: int = 16) -> str:
    filled = int(percentage / 100 * width)
    filled = min(filled, width)
    return "=" * filled + "." * (width - filled)


def render_token_budget_warning(statuses: list[TokenBudgetStatus]) -> Panel | None:
    if not statuses:
        return None

    lines: list[Text] = []
    for s in statuses:
        if s.percentage >= 90:
            color = "red"
        elif s.percentage >= 70:
            color = "yellow"
        else:
            color = "green"

        bar = _build_progress_bar(s.percentage)
        line = Text()
        line.append(f"  {s.scope.capitalize()}: ", style="dim")
        line.append(format_tokens(s.used), style=f"bold {color}")
        line.append(f" / {format_tokens(s.limit)}", style="dim")
        line.append(f" [{bar}] ", style=color)
        line.append(format_percentage(s.percentage), style=f"bold {color}")
        lines.append(line)

    combined = Text("\n").join(lines)
    border = "red" if any(s.over_limit for s in statuses) else "yellow"
    return Panel(combined, title="Token Budget", border_style=border)


def render_comparison(
    labeled_rollups: list[tuple[str, SessionRollup]],
    config: DisplayConfig = _DEFAULT_CONFIG,
) -> Table:
    """Render a side-by-side comparison of multiple time periods."""
    table = Table(title="Comparison", show_header=True, header_style="bold magenta")
    table.add_column("Metric", style="cyan")

    for label, _ in labeled_rollups:
        table.add_column(label, justify="right")

    # Rows: tokens first
    table.add_row(
        "Sessions",
        *[str(r.session_count) for _, r in labeled_rollups],
    )
    table.add_row(
        "Total Tokens",
        *[format_tokens(r.total_tokens) for _, r in labeled_rollups],
    )
    table.add_row(
        "Avg Tokens/Session",
        *[format_tokens(r.avg_tokens_per_session) for _, r in labeled_rollups],
    )
    if config.show_cost:
        table.add_row(
            "Total Cost",
            *[format_cost(r.total_cost) for _, r in labeled_rollups],
        )
        table.add_row(
            "Avg Cost/Session",
            *[format_cost(r.avg_cost_per_session) for _, r in labeled_rollups],
        )
    table.add_row(
        "Cache Efficiency",
        *[format_percentage(r.cache_efficiency) for _, r in labeled_rollups],
    )

    return table
