"""Textual widgets for the Parsimony live dashboard."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.widgets import DataTable, Static

from parsimony.aggregator.rollup import SessionRollup
from parsimony.models.cost import SessionCost
from parsimony.models.session import Session
from parsimony.output.formatters import (
    format_cost,
    format_duration,
    format_model_name,
    format_percentage,
    format_tokens,
)

_BAR_CHARS = " ▏▎▍▌▋▊▉█"


def _bar(value: float, max_value: float, width: int = 15) -> str:
    """Render a horizontal bar using Unicode block characters."""
    if max_value <= 0 or value <= 0:
        return ""
    ratio = min(value / max_value, 1.0)
    full = int(ratio * width)
    remainder = (ratio * width) - full
    partial = int(remainder * (len(_BAR_CHARS) - 1))
    bar = "█" * full
    if full < width:
        bar += _BAR_CHARS[partial]
    return bar


class CostHeader(Static):
    """Top-level cost summary bar."""

    def update_data(self, rollup: SessionRollup, direction: str = "stable") -> None:
        arrows = {"rising": "↑", "falling": "↓", "stable": "→"}
        arrow = arrows.get(direction, "→")
        self.update(
            f"  Total: {format_cost(rollup.total_cost)}  "
            f"Sessions: {rollup.session_count}  "
            f"Trend: {arrow} {direction}  "
            f"Cache: {format_percentage(rollup.cache_efficiency)}"
        )


class ModelBreakdown(Static):
    """Per-model cost breakdown with horizontal bars."""

    def update_data(self, rollup: SessionRollup) -> None:
        if not rollup.per_model:
            self.update("  No model data")
            return

        max_cost = float(max(mr.cost for mr in rollup.per_model.values()))
        if max_cost <= 0:
            max_cost = 1.0

        lines: list[str] = []
        sorted_models = sorted(
            rollup.per_model.values(), key=lambda m: m.cost, reverse=True,
        )
        for mr in sorted_models:
            bar = _bar(float(mr.cost), max_cost)
            name = format_model_name(mr.model)
            lines.append(
                f"  {name:<14} {bar}  {format_cost(mr.cost)}  "
                f"({format_tokens(mr.total_tokens)})"
            )
        self.update("\n".join(lines))


class ToolList(Static):
    """Top tools by call count."""

    def update_data(self, rollup: SessionRollup, limit: int = 8) -> None:
        if not rollup.per_tool:
            self.update("  No tool data")
            return

        sorted_tools = sorted(
            rollup.per_tool.values(), key=lambda t: t.call_count, reverse=True,
        )
        lines: list[str] = []
        for tr in sorted_tools[:limit]:
            tag = f"MCP:{tr.mcp_server}" if tr.is_mcp else "built-in"
            lines.append(f"  {tr.name:<22} {tr.call_count:>5}  ({tag})")
        self.update("\n".join(lines))


class CacheGauge(Static):
    """Cache efficiency progress bar."""

    def update_data(self, efficiency: float) -> None:
        width = 30
        filled = int(efficiency / 100 * width)
        empty = width - filled
        bar = "█" * filled + "░" * empty
        self.update(f"  Hit Rate: {bar}  {format_percentage(efficiency)}")


class SessionLog(DataTable):
    """Scrollable session list sorted by cost."""

    _initialized: bool = False

    def compose(self) -> ComposeResult:
        yield from super().compose()

    def on_mount(self) -> None:
        self.add_columns("Time", "Duration", "Project", "Model", "Cost")
        self._initialized = True

    def update_data(
        self,
        sessions_with_costs: list[tuple[Session, SessionCost]],
        limit: int = 15,
    ) -> None:
        if not self._initialized:
            return
        self.clear()
        sorted_sessions = sorted(
            sessions_with_costs, key=lambda sc: sc[1].total, reverse=True,
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
            self.add_row(
                time_str,
                format_duration(session.duration),
                session.project_name[:20],
                model_str,
                format_cost(cost.total),
            )
