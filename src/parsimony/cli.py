"""CLI entry point for Parsimony."""

from __future__ import annotations

import logging
import sys
from decimal import Decimal

import click
from rich.console import Console

from parsimony.aggregator.filters import SessionFilter, apply_filters
from parsimony.aggregator.grouper import group_by_day
from parsimony.aggregator.rollup import SessionRollup, compute_rollup
from parsimony.aggregator.time_range import TimeRange, filter_sessions
from parsimony.budget import (
    BudgetStatus,
    TokenBudgetStatus,
    check_budget,
    check_token_budget,
    load_budget,
    load_token_budget,
)
from parsimony.config import load_pricing
from parsimony.models.cost import ModelPricing, calculate_session_cost
from parsimony.models.session import Session
from parsimony.output.charts import (
    render_cache_gauge,
    render_cost_trend,
    render_model_distribution,
    render_model_token_distribution,
    render_token_trend,
)
from parsimony.output.display_config import DisplayConfig
from parsimony.output.export import export_csv, export_json
from parsimony.output.formatters import format_model_name, format_tokens
from parsimony.output.gauges import render_usage_summary
from parsimony.output.tables import (
    render_budget_warning,
    render_comparison,
    render_mcp_breakdown,
    render_model_breakdown,
    render_session_detail,
    render_session_list,
    render_summary,
    render_token_budget_warning,
    render_tool_breakdown,
)
from parsimony.parser.reader import read_events
from parsimony.parser.scanner import scan_projects, scan_sessions
from parsimony.parser.session_builder import build_session

console = Console()
logger = logging.getLogger("parsimony.cli")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _load_all_sessions(
    project_filter: str | None = None,
    use_cache: bool = True,
) -> list[Session]:
    """Scan ~/.claude/projects and build Session objects."""
    from parsimony.cache.store import CacheStore
    from parsimony.config import get_cache_path
    from parsimony.parser.scanner import get_claude_base_path

    base = get_claude_base_path() / "projects"
    sessions: list[Session] = []
    cache: CacheStore | None = None

    if use_cache:
        try:
            cache = CacheStore(get_cache_path())
        except Exception:
            logger.debug("Failed to open cache", exc_info=True)

    for project in scan_projects(base):
        if project_filter and project_filter.lower() not in project.decoded_path.lower():
            continue
        for sf in scan_sessions(project.directory):
            try:
                file_key = str(sf.file_path)
                if cache:
                    cached = cache.get(file_key, sf.file_size, sf.modified_time)
                    if cached:
                        sessions.append(cached)
                        continue

                events = list(read_events(sf.file_path))
                data = build_session(sf.session_id, events)
                session = Session.from_session_data(
                    data, project.encoded_name, project.decoded_path
                )
                sessions.append(session)

                if cache:
                    cache.put(file_key, sf.file_size, sf.modified_time, session)
            except Exception:
                logger.debug("Failed to parse session %s", sf.session_id, exc_info=True)

    if cache:
        cache.close()

    return sessions


def _render_report(
    sessions: list[Session],
    time_range: TimeRange,
    pricing: dict[str, ModelPricing],
    export_format: str | None = None,
    session_filter: SessionFilter | None = None,
    config: DisplayConfig | None = None,
) -> None:
    """Filter sessions, compute rollup, and render output."""
    if config is None:
        config = DisplayConfig()

    filtered = filter_sessions(sessions, time_range)

    if session_filter and not session_filter.is_empty:
        filtered = apply_filters(filtered, session_filter, pricing)

    if not filtered:
        console.print(f"[dim]No sessions found for {time_range.label}[/dim]")
        return

    rollup = compute_rollup(filtered, pricing)

    if export_format == "json":
        click.echo(export_json(rollup))
        return
    if export_format == "csv":
        click.echo(export_csv(rollup))
        return

    # Budget warnings (cost-based, only when show_cost)
    if config.show_cost:
        budget_cfg = load_budget()
        if budget_cfg.is_configured:
            statuses: list[BudgetStatus] = []
            if budget_cfg.daily is not None and "today" in time_range.label.lower():
                statuses.append(check_budget(rollup.total_cost, budget_cfg.daily, "daily"))
            if budget_cfg.weekly is not None and "week" in time_range.label.lower():
                statuses.append(check_budget(rollup.total_cost, budget_cfg.weekly, "weekly"))
            if budget_cfg.monthly is not None and "month" in time_range.label.lower():
                statuses.append(
                    check_budget(rollup.total_cost, budget_cfg.monthly, "monthly"),
                )
            warning = render_budget_warning(statuses) if statuses else None
            if warning:
                console.print(warning)

    # Token budget warnings and gauges
    token_cfg = load_token_budget()
    if token_cfg.is_configured:
        token_statuses: list[TokenBudgetStatus] = []
        weekly_tokens = 0
        peak = 0
        if token_cfg.weekly_limit is not None and "week" in time_range.label.lower():
            weekly_tokens = rollup.total_tokens
            token_statuses.append(
                check_token_budget(rollup.total_tokens, token_cfg.weekly_limit, "weekly")
            )
        if token_cfg.session_limit is not None:
            peak = max((s.total_tokens for s in filtered), default=0)
            token_statuses.append(
                check_token_budget(peak, token_cfg.session_limit, "session peak")
            )
        token_warning = render_token_budget_warning(token_statuses)
        if token_warning:
            console.print(token_warning)
        console.print(render_usage_summary(token_cfg, weekly_tokens, peak))

    console.print(render_summary(rollup, label=time_range.label, config=config))
    console.print(render_model_breakdown(rollup, config=config))
    console.print(render_tool_breakdown(rollup))

    if rollup.mcp_breakdown:
        console.print(render_mcp_breakdown(rollup))

    # Daily trend
    daily = group_by_day(filtered)
    if len(daily) > 1:
        if config.show_cost:
            daily_costs = []
            for day in sorted(daily):
                day_rollup = compute_rollup(daily[day], pricing)
                daily_costs.append((day.strftime("%b %d"), day_rollup.total_cost))
            console.print(render_cost_trend(daily_costs))
        else:
            daily_tokens = []
            for day in sorted(daily):
                day_rollup = compute_rollup(daily[day], pricing)
                daily_tokens.append((day.strftime("%b %d"), day_rollup.total_tokens))
            console.print(render_token_trend(daily_tokens))

    console.print(render_cache_gauge(rollup.cache_efficiency))

    # Session list
    session_costs = [
        (s, calculate_session_cost(s, pricing)) for s in filtered
    ]
    console.print(render_session_list(session_costs, config=config))


# ---------------------------------------------------------------------------
# CLI group + commands
# ---------------------------------------------------------------------------


def _build_session_filter(ctx: click.Context) -> SessionFilter:
    """Build a SessionFilter from CLI context options."""
    models = ctx.obj.get("filter_models")
    tools = ctx.obj.get("filter_tools")
    min_cost = ctx.obj.get("filter_min_cost")
    max_cost = ctx.obj.get("filter_max_cost")
    min_tokens = ctx.obj.get("filter_min_tokens")
    max_tokens = ctx.obj.get("filter_max_tokens")
    return SessionFilter(
        models=frozenset(models) if models else None,
        tools=frozenset(tools) if tools else None,
        min_tokens=min_tokens,
        max_tokens=max_tokens,
        min_cost=Decimal(str(min_cost)) if min_cost is not None else None,
        max_cost=Decimal(str(max_cost)) if max_cost is not None else None,
    )


@click.group(invoke_without_command=True)
@click.option("--project", "-p", default=None, help="Filter by project name (substring match).")
@click.option("--export", "export_format", type=click.Choice(["json", "csv"]), default=None,
              help="Export report as JSON or CSV.")
@click.option("--no-cache", is_flag=True, help="Disable session cache.")
@click.option("--verbose", "-v", is_flag=True, help="Enable verbose logging.")
@click.option("--show-cost", is_flag=True,
              help="Show cost columns alongside token usage.")
@click.option("--model", "filter_models", multiple=True,
              help="Filter by model (e.g. sonnet, opus, haiku). Repeatable.")
@click.option("--tool", "filter_tools", multiple=True,
              help="Filter by tool name (e.g. Read, Write). Repeatable.")
@click.option("--min-cost", "filter_min_cost", type=float, default=None,
              help="Minimum session cost threshold (USD).")
@click.option("--max-cost", "filter_max_cost", type=float, default=None,
              help="Maximum session cost threshold (USD).")
@click.option("--min-tokens", "filter_min_tokens", type=int, default=None,
              help="Minimum session token threshold.")
@click.option("--max-tokens", "filter_max_tokens", type=int, default=None,
              help="Maximum session token threshold.")
@click.pass_context
def main(
    ctx: click.Context,
    project: str | None,
    export_format: str | None,
    no_cache: bool,
    verbose: bool,
    show_cost: bool,
    filter_models: tuple[str, ...],
    filter_tools: tuple[str, ...],
    filter_min_cost: float | None,
    filter_max_cost: float | None,
    filter_min_tokens: int | None,
    filter_max_tokens: int | None,
) -> None:
    """Parsimony: Know where every token goes."""
    if verbose:
        logging.basicConfig(level=logging.DEBUG, format="%(name)s: %(message)s")
    else:
        logging.basicConfig(level=logging.WARNING)

    ctx.ensure_object(dict)
    ctx.obj["project"] = project
    ctx.obj["export_format"] = export_format
    ctx.obj["use_cache"] = not no_cache
    ctx.obj["pricing"] = load_pricing()
    ctx.obj["show_cost"] = show_cost
    ctx.obj["config"] = DisplayConfig(show_cost=show_cost)
    ctx.obj["filter_models"] = filter_models if filter_models else None
    ctx.obj["filter_tools"] = filter_tools if filter_tools else None
    ctx.obj["filter_min_cost"] = filter_min_cost
    ctx.obj["filter_max_cost"] = filter_max_cost
    ctx.obj["filter_min_tokens"] = filter_min_tokens
    ctx.obj["filter_max_tokens"] = filter_max_tokens

    if ctx.invoked_subcommand is None:
        # Default: show today's report
        sessions = _load_all_sessions(project, use_cache=not no_cache)
        sf = _build_session_filter(ctx)
        _render_report(
            sessions, TimeRange.today(), ctx.obj["pricing"],
            export_format, sf, ctx.obj["config"],
        )


@main.command()
@click.pass_context
def today(ctx: click.Context) -> None:
    """Show today's usage report."""
    sessions = _load_all_sessions(ctx.obj["project"], ctx.obj["use_cache"])
    sf = _build_session_filter(ctx)
    _render_report(
        sessions, TimeRange.today(), ctx.obj["pricing"],
        ctx.obj["export_format"], sf, ctx.obj["config"],
    )


@main.command()
@click.pass_context
def yesterday(ctx: click.Context) -> None:
    """Show yesterday's usage report."""
    sessions = _load_all_sessions(ctx.obj["project"], ctx.obj["use_cache"])
    sf = _build_session_filter(ctx)
    _render_report(
        sessions, TimeRange.yesterday(), ctx.obj["pricing"],
        ctx.obj["export_format"], sf, ctx.obj["config"],
    )


@main.command()
@click.option("--last", is_flag=True, help="Show last week instead of current.")
@click.pass_context
def week(ctx: click.Context, last: bool) -> None:
    """Show weekly usage report."""
    time_range = TimeRange.last_week() if last else TimeRange.this_week()
    sessions = _load_all_sessions(ctx.obj["project"], ctx.obj["use_cache"])
    sf = _build_session_filter(ctx)
    _render_report(
        sessions, time_range, ctx.obj["pricing"],
        ctx.obj["export_format"], sf, ctx.obj["config"],
    )


@main.command()
@click.argument("year_month", required=False, default=None)
@click.pass_context
def month(ctx: click.Context, year_month: str | None) -> None:
    """Show monthly usage report.

    Optionally pass YYYY-MM for a specific month (e.g. 2026-03).
    """
    if year_month:
        try:
            parts = year_month.split("-")
            year = int(parts[0])
            mon = int(parts[1])
            time_range = TimeRange.month(year, mon)
        except (ValueError, IndexError):
            click.echo(f"Invalid month format: {year_month}. Use YYYY-MM.", err=True)
            sys.exit(1)
    else:
        time_range = TimeRange.this_month()

    sessions = _load_all_sessions(ctx.obj["project"], ctx.obj["use_cache"])
    sf = _build_session_filter(ctx)
    _render_report(
        sessions, time_range, ctx.obj["pricing"],
        ctx.obj["export_format"], sf, ctx.obj["config"],
    )


@main.command()
@click.pass_context
def budget(ctx: click.Context) -> None:
    """Show current budget status across daily, weekly, and monthly periods."""
    from parsimony.output.formatters import format_cost as _fmt_cost
    from parsimony.output.formatters import format_percentage as _fmt_pct

    budget_cfg = load_budget()
    token_cfg = load_token_budget()
    any_configured = budget_cfg.is_configured or token_cfg.is_configured

    if not any_configured:
        console.print("[dim]No budget configured.[/dim]")
        console.print("[dim]Add a budget section to ~/.parsimony/config.yaml:[/dim]")
        console.print("[cyan]  budget:\n    daily: 5.00\n    weekly: 25.00\n    monthly: 80.00[/]")
        console.print(
            "[dim]  token_budget:\n    session_limit: 500000\n    weekly_limit: 5000000[/]",
        )
        return

    pricing = ctx.obj["pricing"]
    sessions = _load_all_sessions(ctx.obj["project"], ctx.obj["use_cache"])

    if budget_cfg.is_configured:
        checks: list[tuple[str, Decimal | None, TimeRange]] = [
            ("daily", budget_cfg.daily, TimeRange.today()),
            ("weekly", budget_cfg.weekly, TimeRange.this_week()),
            ("monthly", budget_cfg.monthly, TimeRange.this_month()),
        ]

        statuses: list[BudgetStatus] = []
        for period, limit, tr in checks:
            if limit is None:
                continue
            filtered = filter_sessions(sessions, tr)
            rollup = compute_rollup(filtered, pricing)
            statuses.append(check_budget(rollup.total_cost, limit, period))

        for s in statuses:
            if s.over_budget:
                style = "bold red"
                icon = "OVER"
            elif s.percentage >= 90:
                style = "bold yellow"
                icon = "WARN"
            elif s.percentage >= 70:
                style = "bold blue"
                icon = "NOTE"
            else:
                style = "bold green"
                icon = "  OK"
            console.print(
                f"  [{style}]{icon}[/]  {s.period:<8} "
                f"{_fmt_cost(s.spent)} / {_fmt_cost(s.limit)}  "
                f"({_fmt_pct(s.percentage)})",
            )

    if token_cfg.is_configured:
        token_statuses: list[TokenBudgetStatus] = []
        weekly_tokens = 0
        peak = 0
        if token_cfg.weekly_limit is not None:
            weekly_filtered = filter_sessions(sessions, TimeRange.this_week())
            weekly_rollup = compute_rollup(weekly_filtered, pricing)
            weekly_tokens = weekly_rollup.total_tokens
            token_statuses.append(
                check_token_budget(weekly_tokens, token_cfg.weekly_limit, "weekly")
            )
        if token_cfg.session_limit is not None:
            today_filtered = filter_sessions(sessions, TimeRange.today())
            peak = max((s.total_tokens for s in today_filtered), default=0)
            token_statuses.append(
                check_token_budget(peak, token_cfg.session_limit, "session peak")
            )
        token_warning = render_token_budget_warning(token_statuses)
        if token_warning:
            console.print(token_warning)
        console.print(render_usage_summary(token_cfg, weekly_tokens, peak))


@main.command()
@click.option("--days", "-d", default=30, help="Number of days to analyze (default 30).")
@click.pass_context
def trend(ctx: click.Context, days: int) -> None:
    """Show usage trends over time with moving averages."""
    from parsimony.aggregator.trends import (
        compute_trends,
        moving_average,
        trend_direction,
    )
    from parsimony.output.charts import render_trend_chart, render_trend_summary

    pricing = ctx.obj["pricing"]
    config: DisplayConfig = ctx.obj["config"]
    sessions = _load_all_sessions(ctx.obj["project"], ctx.obj["use_cache"])
    time_range = TimeRange.last_n_days(days)
    filtered = filter_sessions(sessions, time_range)

    sf = _build_session_filter(ctx)
    if not sf.is_empty:
        filtered = apply_filters(filtered, sf, pricing)

    trends = compute_trends(filtered, days=days, pricing=pricing)
    ma = moving_average(trends, window=7)
    direction = trend_direction(trends, window=7)

    if ctx.obj["export_format"] == "json":
        import json
        data = [
            {
                "date": t.day.isoformat(),
                "cost": float(t.cost),
                "tokens": t.tokens,
                "sessions": t.sessions,
                "cache_efficiency": t.cache_efficiency,
                "moving_avg": float(ma[i]),
            }
            for i, t in enumerate(trends)
        ]
        click.echo(json.dumps(data, indent=2))
        return

    metric = "cost" if config.show_cost else "tokens"
    if metric == "tokens":
        # Compute token moving averages
        from parsimony.aggregator.trends import moving_average_tokens
        token_ma = moving_average_tokens(trends, window=7)
        from parsimony.aggregator.trends import trend_direction_tokens
        direction = trend_direction_tokens(trends, window=7)
        console.print(render_trend_summary(trends, direction, metric=metric))
        console.print(render_trend_chart(trends, token_ma, metric=metric))
    else:
        console.print(render_trend_summary(trends, direction, metric=metric))
        console.print(render_trend_chart(trends, ma, metric=metric))


@main.command(name="diff")
@click.argument("session1")
@click.argument("session2")
@click.pass_context
def diff_cmd(ctx: click.Context, session1: str, session2: str) -> None:
    """Compare two sessions side-by-side.

    Accepts full UUIDs or prefixes (minimum 8 characters).
    """
    from parsimony.aggregator.diff import compute_diff
    from parsimony.output.diff_table import render_diff

    sessions = _load_all_sessions(ctx.obj["project"], ctx.obj["use_cache"])
    pricing = ctx.obj["pricing"]
    config: DisplayConfig = ctx.obj["config"]

    def _find(prefix: str) -> Session:
        matches = [s for s in sessions if s.session_id.startswith(prefix)]
        if not matches:
            click.echo(f"No session found matching '{prefix}'.", err=True)
            sys.exit(1)
        if len(matches) > 1:
            click.echo(f"Multiple sessions match '{prefix}':", err=True)
            for m in matches[:10]:
                click.echo(f"  {m.session_id}  ({m.project_name})", err=True)
            sys.exit(1)
        return matches[0]

    s1 = _find(session1)
    s2 = _find(session2)
    result = compute_diff(s1, s2, pricing)

    if ctx.obj["export_format"] == "json":
        import json
        data = {
            "session1": result.session_id_old,
            "session2": result.session_id_new,
            "total_cost": {
                "old": float(result.total_cost.old),
                "new": float(result.total_cost.new),
                "change": float(result.total_cost.change),
                "change_pct": result.total_cost.change_pct,
            },
            "total_tokens": {
                "old": int(result.total_tokens.old),
                "new": int(result.total_tokens.new),
                "change": int(result.total_tokens.change),
                "change_pct": result.total_tokens.change_pct,
            },
        }
        click.echo(json.dumps(data, indent=2))
        return

    console.print(render_diff(result, config=config))


@main.command()
@click.option("--project", "-p", "live_project", default=None,
              help="Filter by project name.")
@click.pass_context
def live(ctx: click.Context, live_project: str | None) -> None:
    """Launch the live terminal dashboard.

    Requires the 'dashboard' extras: pip install parsimony-cli[dashboard]
    """
    try:
        from parsimony.dashboard.app import ParsimonyDashboard
    except ImportError:
        click.echo(
            "Dashboard dependencies not installed.\n"
            "Install with: pip install parsimony-cli[dashboard]",
            err=True,
        )
        sys.exit(1)

    project = live_project or ctx.obj.get("project")
    config: DisplayConfig = ctx.obj["config"]
    app = ParsimonyDashboard(
        project_filter=project, pricing=ctx.obj["pricing"], config=config,
    )
    app.run()


@main.command()
@click.argument("session_id")
@click.pass_context
def session(ctx: click.Context, session_id: str) -> None:
    """Show detailed breakdown for a specific session.

    Accepts a full UUID or a prefix (minimum 8 characters).
    """
    sessions = _load_all_sessions(ctx.obj["project"], ctx.obj["use_cache"])
    pricing = ctx.obj["pricing"]
    config: DisplayConfig = ctx.obj["config"]

    matches = [s for s in sessions if s.session_id.startswith(session_id)]
    if not matches:
        click.echo(f"No session found matching '{session_id}'.", err=True)
        sys.exit(1)
    if len(matches) > 1:
        click.echo(f"Multiple sessions match '{session_id}':", err=True)
        for m in matches[:10]:
            click.echo(f"  {m.session_id}  ({m.project_name})", err=True)
        sys.exit(1)

    target = matches[0]
    cost = calculate_session_cost(target, pricing)

    if ctx.obj["export_format"] == "json":
        import json
        data = {
            "session_id": target.session_id,
            "project": target.project_name,
            "total_tokens": target.total_tokens,
            "total_cost": float(cost.total),
            "models": list(target.models_used),
            "total_api_calls": target.total_api_calls,
        }
        click.echo(json.dumps(data, indent=2))
        return

    console.print(render_session_detail(target, cost, config=config))


@main.command()
@click.argument("dimension", type=click.Choice(["sessions", "projects", "models", "tools"]))
@click.option("--period", type=click.Choice(["day", "week", "month", "all"]), default="week",
              help="Time period to analyze.")
@click.option("--limit", "-n", default=10, help="Number of results to show.")
@click.pass_context
def top(ctx: click.Context, dimension: str, period: str, limit: int) -> None:
    """Show top items by a given dimension."""
    time_ranges = {
        "day": TimeRange.today,
        "week": TimeRange.this_week,
        "month": TimeRange.this_month,
        "all": TimeRange.all_time,
    }
    time_range = time_ranges[period]()
    pricing = ctx.obj["pricing"]
    config: DisplayConfig = ctx.obj["config"]
    sessions = _load_all_sessions(ctx.obj["project"], ctx.obj["use_cache"])
    filtered = filter_sessions(sessions, time_range)

    sf = _build_session_filter(ctx)
    if not sf.is_empty:
        filtered = apply_filters(filtered, sf, pricing)

    if not filtered:
        console.print(f"[dim]No sessions found for {time_range.label}[/dim]")
        return

    if dimension == "sessions":
        session_costs = [(s, calculate_session_cost(s, pricing)) for s in filtered]
        console.print(render_session_list(session_costs, limit=limit, config=config))

    elif dimension == "models":
        rollup = compute_rollup(filtered, pricing)
        console.print(render_model_breakdown(rollup, config=config))
        if config.show_cost:
            model_costs = {
                format_model_name(m): mr.cost for m, mr in rollup.per_model.items()
            }
            console.print(render_model_distribution(model_costs))
        else:
            model_tokens = {
                format_model_name(m): mr.total_tokens
                for m, mr in rollup.per_model.items()
            }
            console.print(render_model_token_distribution(model_tokens))

    elif dimension == "tools":
        rollup = compute_rollup(filtered, pricing)
        console.print(render_tool_breakdown(rollup, limit=limit))
        if rollup.mcp_breakdown:
            console.print(render_mcp_breakdown(rollup))

    elif dimension == "projects":
        from rich.table import Table

        from parsimony.aggregator.grouper import group_by_project

        groups = group_by_project(filtered)
        table = Table(title=f"Top Projects ({time_range.label})",
                      show_header=True, header_style="bold magenta")
        table.add_column("Project", style="cyan")
        table.add_column("Sessions", justify="right")
        table.add_column("Tokens", justify="right", style="bold cyan")
        if config.show_cost:
            table.add_column("Cost", justify="right", style="green")

        project_data = []
        for proj_name, proj_sessions in groups.items():
            rollup = compute_rollup(proj_sessions, pricing)
            project_data.append(
                (proj_name, len(proj_sessions), rollup.total_tokens, rollup.total_cost)
            )

        from parsimony.output.formatters import format_cost
        for name, count, tokens, cost in sorted(
            project_data, key=lambda x: x[2], reverse=True
        )[:limit]:
            row = [name, str(count), format_tokens(tokens)]
            if config.show_cost:
                row.append(format_cost(cost))
            table.add_row(*row)
        console.print(table)


@main.command()
@click.option("--last", "-n", default=4, help="Number of periods to compare.")
@click.option("--period", type=click.Choice(["day", "week", "month"]), default="week",
              help="Period granularity.")
@click.pass_context
def compare(ctx: click.Context, last: int, period: str) -> None:
    """Compare usage across multiple time periods side-by-side."""
    from datetime import timedelta

    pricing = ctx.obj["pricing"]
    config: DisplayConfig = ctx.obj["config"]
    sessions = _load_all_sessions(ctx.obj["project"], ctx.obj["use_cache"])

    labeled_rollups: list[tuple[str, SessionRollup]] = []

    if period == "day":
        for i in range(last - 1, -1, -1):
            tr = TimeRange.last_n_days(1)
            if i > 0:
                from parsimony.aggregator.time_range import _end_of_day, _local_now, _start_of_day
                d = _local_now().date() - timedelta(days=i)
                tr = TimeRange(
                    start=_start_of_day(d),
                    end=_end_of_day(d),
                    label=d.strftime("%b %d"),
                )
            filtered = filter_sessions(sessions, tr)
            labeled_rollups.append((tr.label, compute_rollup(filtered, pricing)))

    elif period == "week":
        for i in range(last - 1, -1, -1):
            from parsimony.aggregator.time_range import _end_of_day, _local_now, _start_of_day
            now = _local_now()
            monday = now.date() - timedelta(days=now.weekday()) - timedelta(weeks=i)
            sunday = monday + timedelta(days=6)
            tr = TimeRange(
                start=_start_of_day(monday),
                end=_end_of_day(sunday),
                label=f"Wk {monday.strftime('%m/%d')}",
            )
            filtered = filter_sessions(sessions, tr)
            labeled_rollups.append((tr.label, compute_rollup(filtered, pricing)))

    elif period == "month":
        from parsimony.aggregator.time_range import _local_now
        now = _local_now()
        for i in range(last - 1, -1, -1):
            m = now.month - i
            y = now.year
            while m <= 0:
                m += 12
                y -= 1
            tr = TimeRange.month(y, m)
            filtered = filter_sessions(sessions, tr)
            labeled_rollups.append((tr.label, compute_rollup(filtered, pricing)))

    if ctx.obj["export_format"] == "json":
        import json
        data = [
            {
                "label": label,
                "sessions": r.session_count,
                "total_tokens": r.total_tokens,
                "total_cost": float(r.total_cost),
            }
            for label, r in labeled_rollups
        ]
        click.echo(json.dumps(data, indent=2))
        return

    console.print(render_comparison(labeled_rollups, config=config))
