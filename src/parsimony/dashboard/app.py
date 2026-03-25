"""Main Textual application for the Parsimony live dashboard."""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.widgets import Footer, Header, Static

from parsimony.aggregator.rollup import compute_rollup
from parsimony.aggregator.time_range import TimeRange, filter_sessions
from parsimony.aggregator.trends import compute_trends, trend_direction
from parsimony.budget import TokenBudgetConfig, load_token_budget
from parsimony.config import load_pricing
from parsimony.dashboard.widgets import (
    CacheGauge,
    ModelBreakdown,
    SessionLog,
    SessionPeakGauge,
    ToolList,
    UsageGauge,
    UsageHeader,
)
from parsimony.models.cost import ModelPricing, calculate_session_cost
from parsimony.models.session import Session
from parsimony.output.display_config import DisplayConfig

logger = logging.getLogger("parsimony.dashboard.app")

_PERIOD_CYCLE = ("today", "week", "month")


def _load_sessions_for_dashboard(
    project_filter: str | None = None,
) -> list[Session]:
    """Load all sessions without cache for live data."""
    from parsimony.parser.reader import read_events
    from parsimony.parser.scanner import get_claude_base_path, scan_projects, scan_sessions
    from parsimony.parser.session_builder import build_session

    base = get_claude_base_path() / "projects"
    sessions: list[Session] = []

    for project in scan_projects(base):
        if project_filter and project_filter.lower() not in project.decoded_path.lower():
            continue
        for sf in scan_sessions(project.directory):
            try:
                events = list(read_events(sf.file_path))
                data = build_session(sf.session_id, events)
                session = Session.from_session_data(
                    data, project.encoded_name, project.decoded_path,
                )
                sessions.append(session)
            except Exception:
                logger.debug("Failed to parse session %s", sf.session_id, exc_info=True)

    return sessions


class ParsimonyDashboard(App[None]):
    """Live terminal dashboard for Claude Code usage monitoring."""

    TITLE = "Parsimony Dashboard"

    CSS = """
    #usage-header {
        height: 3;
        background: $surface;
        border-bottom: solid $primary;
        padding: 1;
    }
    #main-area {
        height: 1fr;
    }
    #left-panel {
        width: 1fr;
    }
    #right-panel {
        width: 1fr;
    }
    #model-breakdown {
        height: auto;
        max-height: 12;
        padding: 1;
        border: solid $primary;
    }
    #tool-list {
        height: auto;
        max-height: 12;
        padding: 1;
        border: solid $primary;
    }
    #cache-gauge {
        height: 3;
        padding: 1;
        border: solid $primary;
    }
    #session-log {
        height: 1fr;
        border: solid $primary;
    }
    #status-bar {
        height: 1;
        background: $surface;
        padding: 0 1;
    }
    #usage-gauge {
        height: 3;
        padding: 1;
        border: solid $primary;
    }
    #session-peak-gauge {
        height: 3;
        padding: 1;
        border: solid $primary;
    }
    """

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("r", "force_refresh", "Refresh"),
        Binding("t", "toggle_period", "Period"),
    ]

    def __init__(
        self,
        project_filter: str | None = None,
        pricing: dict[str, ModelPricing] | None = None,
        config: DisplayConfig | None = None,
        token_budget: TokenBudgetConfig | None = None,
    ) -> None:
        super().__init__()
        self._project_filter = project_filter
        self._pricing = pricing or load_pricing()
        self._config = config or DisplayConfig()
        self._token_budget = token_budget or load_token_budget()
        self._period_index = 0
        self._stop_event = asyncio.Event()
        self._watcher_task: asyncio.Task[None] | None = None

    def compose(self) -> ComposeResult:
        yield Header()
        yield UsageHeader(id="usage-header")
        if self._token_budget.weekly_limit is not None:
            yield UsageGauge(id="usage-gauge")
        if self._token_budget.session_limit is not None:
            yield SessionPeakGauge(id="session-peak-gauge")
        with Horizontal(id="main-area"):
            with Vertical(id="left-panel"):
                yield ModelBreakdown(id="model-breakdown")
                yield ToolList(id="tool-list")
                yield CacheGauge(id="cache-gauge")
            with Vertical(id="right-panel"):
                yield SessionLog(id="session-log")
        yield Static("Watching for changes...", id="status-bar")
        yield Footer()

    def on_mount(self) -> None:
        self._refresh_data()
        self._start_watcher()

    def _start_watcher(self) -> None:
        from parsimony.dashboard.watcher import watch_sessions
        from parsimony.parser.scanner import get_claude_base_path

        base = get_claude_base_path() / "projects"
        if base.is_dir():
            self._watcher_task = asyncio.create_task(
                watch_sessions(base, self._on_file_change, self._stop_event),
            )

    async def _on_file_change(self, changed_paths: set[Path]) -> None:
        logger.debug("File change detected: %d paths", len(changed_paths))
        self._refresh_data()

    def _get_time_range(self) -> TimeRange:
        period = _PERIOD_CYCLE[self._period_index]
        if period == "today":
            return TimeRange.today()
        if period == "week":
            return TimeRange.this_week()
        return TimeRange.this_month()

    def _refresh_data(self) -> None:
        try:
            sessions = _load_sessions_for_dashboard(self._project_filter)
            time_range = self._get_time_range()
            filtered = filter_sessions(sessions, time_range)

            if not filtered:
                self.query_one("#usage-header", UsageHeader).update(
                    f"  No sessions found for {time_range.label}"
                )
                return

            rollup = compute_rollup(filtered, self._pricing)

            # Trend direction
            trends = compute_trends(filtered, days=7, pricing=self._pricing)
            direction = trend_direction(trends, window=3)

            # Update widgets
            self.query_one("#usage-header", UsageHeader).update_data(
                rollup, direction, self._config,
            )
            self.query_one("#model-breakdown", ModelBreakdown).update_data(
                rollup, self._config,
            )
            self.query_one("#tool-list", ToolList).update_data(rollup)
            self.query_one("#cache-gauge", CacheGauge).update_data(
                rollup.cache_efficiency,
            )

            # Session log
            session_costs = [
                (s, calculate_session_cost(s, self._pricing)) for s in filtered
            ]
            self.query_one("#session-log", SessionLog).update_data(session_costs)

            # Token budget gauges
            if self._token_budget.weekly_limit is not None:
                weekly_filtered = filter_sessions(sessions, TimeRange.this_week())
                weekly_rollup = compute_rollup(weekly_filtered, self._pricing)
                self.query_one("#usage-gauge", UsageGauge).update_data(
                    weekly_rollup.total_tokens, self._token_budget.weekly_limit,
                )
            if self._token_budget.session_limit is not None:
                peak = max((s.total_tokens for s in filtered), default=0)
                self.query_one("#session-peak-gauge", SessionPeakGauge).update_data(
                    peak, self._token_budget.session_limit,
                )

            # Status bar
            period = _PERIOD_CYCLE[self._period_index]
            status = (
                f"  Period: {period}  |  "
                f"Sessions: {len(filtered)}  |  "
                f"Watching {len(sessions)} total sessions"
            )
            self.query_one("#status-bar", Static).update(status)
        except Exception:
            logger.debug("Refresh failed", exc_info=True)

    def action_force_refresh(self) -> None:
        self._refresh_data()

    def action_toggle_period(self) -> None:
        self._period_index = (self._period_index + 1) % len(_PERIOD_CYCLE)
        self._refresh_data()

    async def action_quit(self) -> None:
        self._stop_event.set()
        if self._watcher_task:
            self._watcher_task.cancel()
        self.exit()
