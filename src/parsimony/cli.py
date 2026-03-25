"""CLI entry point for Parsimony."""

from __future__ import annotations

import logging
import sys

import click
from rich.console import Console

from parsimony.aggregator.grouper import group_by_day
from parsimony.aggregator.rollup import SessionRollup, compute_rollup
from parsimony.aggregator.time_range import TimeRange, filter_sessions
from parsimony.config import load_pricing
from parsimony.models.cost import ModelPricing, calculate_session_cost
from parsimony.models.session import Session
from parsimony.output.charts import render_cache_gauge, render_cost_trend, render_model_distribution
from parsimony.output.export import export_csv, export_json
from parsimony.output.formatters import format_model_name
from parsimony.output.tables import (
    render_comparison,
    render_mcp_breakdown,
    render_model_breakdown,
    render_session_detail,
    render_session_list,
    render_summary,
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
) -> None:
    """Filter sessions, compute rollup, and render output."""
    filtered = filter_sessions(sessions, time_range)

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

    console.print(render_summary(rollup, label=time_range.label))
    console.print(render_model_breakdown(rollup))
    console.print(render_tool_breakdown(rollup))

    if rollup.mcp_breakdown:
        console.print(render_mcp_breakdown(rollup))

    # Daily cost trend
    daily = group_by_day(filtered)
    if len(daily) > 1:
        daily_costs = []
        for day in sorted(daily):
            day_rollup = compute_rollup(daily[day], pricing)
            daily_costs.append((day.strftime("%b %d"), day_rollup.total_cost))
        console.print(render_cost_trend(daily_costs))

    console.print(render_cache_gauge(rollup.cache_efficiency))

    # Session list
    session_costs = [
        (s, calculate_session_cost(s, pricing)) for s in filtered
    ]
    console.print(render_session_list(session_costs))


# ---------------------------------------------------------------------------
# CLI group + commands
# ---------------------------------------------------------------------------


@click.group(invoke_without_command=True)
@click.option("--project", "-p", default=None, help="Filter by project name (substring match).")
@click.option("--export", "export_format", type=click.Choice(["json", "csv"]), default=None,
              help="Export report as JSON or CSV.")
@click.option("--no-cache", is_flag=True, help="Disable session cache.")
@click.option("--verbose", "-v", is_flag=True, help="Enable verbose logging.")
@click.pass_context
def main(
    ctx: click.Context,
    project: str | None,
    export_format: str | None,
    no_cache: bool,
    verbose: bool,
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

    if ctx.invoked_subcommand is None:
        # Default: show today's report
        sessions = _load_all_sessions(project, use_cache=not no_cache)
        _render_report(sessions, TimeRange.today(), ctx.obj["pricing"], export_format)


@main.command()
@click.pass_context
def today(ctx: click.Context) -> None:
    """Show today's usage report."""
    sessions = _load_all_sessions(ctx.obj["project"], ctx.obj["use_cache"])
    _render_report(sessions, TimeRange.today(), ctx.obj["pricing"], ctx.obj["export_format"])


@main.command()
@click.pass_context
def yesterday(ctx: click.Context) -> None:
    """Show yesterday's usage report."""
    sessions = _load_all_sessions(ctx.obj["project"], ctx.obj["use_cache"])
    _render_report(sessions, TimeRange.yesterday(), ctx.obj["pricing"], ctx.obj["export_format"])


@main.command()
@click.option("--last", is_flag=True, help="Show last week instead of current.")
@click.pass_context
def week(ctx: click.Context, last: bool) -> None:
    """Show weekly usage report."""
    time_range = TimeRange.last_week() if last else TimeRange.this_week()
    sessions = _load_all_sessions(ctx.obj["project"], ctx.obj["use_cache"])
    _render_report(sessions, time_range, ctx.obj["pricing"], ctx.obj["export_format"])


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
    _render_report(sessions, time_range, ctx.obj["pricing"], ctx.obj["export_format"])


@main.command()
@click.argument("session_id")
@click.pass_context
def session(ctx: click.Context, session_id: str) -> None:
    """Show detailed breakdown for a specific session.

    Accepts a full UUID or a prefix (minimum 8 characters).
    """
    sessions = _load_all_sessions(ctx.obj["project"], ctx.obj["use_cache"])
    pricing = ctx.obj["pricing"]

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
            "total_cost": float(cost.total),
            "models": list(target.models_used),
            "total_api_calls": target.total_api_calls,
            "total_tokens": target.total_tokens,
        }
        click.echo(json.dumps(data, indent=2))
        return

    console.print(render_session_detail(target, cost))


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
    sessions = _load_all_sessions(ctx.obj["project"], ctx.obj["use_cache"])
    filtered = filter_sessions(sessions, time_range)

    if not filtered:
        console.print(f"[dim]No sessions found for {time_range.label}[/dim]")
        return

    if dimension == "sessions":
        session_costs = [(s, calculate_session_cost(s, pricing)) for s in filtered]
        console.print(render_session_list(session_costs, limit=limit))

    elif dimension == "models":
        rollup = compute_rollup(filtered, pricing)
        console.print(render_model_breakdown(rollup))
        model_costs = {
            format_model_name(m): mr.cost for m, mr in rollup.per_model.items()
        }
        console.print(render_model_distribution(model_costs))

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
        table.add_column("Cost", justify="right", style="green")

        project_costs = []
        for proj_name, proj_sessions in groups.items():
            rollup = compute_rollup(proj_sessions, pricing)
            project_costs.append((proj_name, len(proj_sessions), rollup.total_cost))

        from parsimony.output.formatters import format_cost
        for name, count, cost in sorted(project_costs, key=lambda x: x[2], reverse=True)[:limit]:
            table.add_row(name, str(count), format_cost(cost))
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
            {"label": label, "sessions": r.session_count, "total_cost": float(r.total_cost)}
            for label, r in labeled_rollups
        ]
        click.echo(json.dumps(data, indent=2))
        return

    console.print(render_comparison(labeled_rollups))
