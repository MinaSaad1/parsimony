"""Grouping utilities for sessions by various dimensions."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date

from parsimony.models.session import Session
from parsimony.models.tool_usage import parse_tool_name
from parsimony.parser.session_builder import APICall


@dataclass(frozen=True)
class ToolAggregation:
    """Aggregated stats for a single tool across sessions."""

    name: str
    call_count: int
    is_mcp: bool
    mcp_server: str | None


def group_by_project(sessions: list[Session]) -> dict[str, list[Session]]:
    """Group sessions by project name."""
    result: dict[str, list[Session]] = defaultdict(list)
    for session in sessions:
        result[session.project_name].append(session)
    return dict(result)


def group_by_model(sessions: list[Session]) -> dict[str, list[APICall]]:
    """Flatten all API calls and group by model name."""
    result: dict[str, list[APICall]] = defaultdict(list)
    for session in sessions:
        for segment in session.segments:
            result[segment.model].extend(segment.calls)
    return dict(result)


def group_by_tool(sessions: list[Session]) -> dict[str, ToolAggregation]:
    """Count tool usage across all sessions."""
    counts: dict[str, int] = defaultdict(int)
    for session in sessions:
        for segment in session.segments:
            for call in segment.calls:
                for tool_ref in call.tool_uses:
                    counts[tool_ref.tool_name] += 1

    result: dict[str, ToolAggregation] = {}
    for name, count in counts.items():
        parsed = parse_tool_name(name)
        result[name] = ToolAggregation(
            name=name,
            call_count=count,
            is_mcp=parsed.is_mcp,
            mcp_server=parsed.mcp_server,
        )
    return result


def group_by_mcp_server(sessions: list[Session]) -> dict[str, dict[str, int]]:
    """Group MCP tool calls by server, then by tool name."""
    result: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for session in sessions:
        for segment in session.segments:
            for call in segment.calls:
                for tool_ref in call.tool_uses:
                    parsed = parse_tool_name(tool_ref.tool_name)
                    if parsed.is_mcp and parsed.mcp_server and parsed.mcp_tool:
                        result[parsed.mcp_server][parsed.mcp_tool] += 1
    return {k: dict(v) for k, v in result.items()}


def group_by_day(sessions: list[Session]) -> dict[date, list[Session]]:
    """Group sessions by the date of their start_time (local timezone)."""
    result: dict[date, list[Session]] = defaultdict(list)
    for session in sessions:
        if session.start_time is not None:
            local_time = session.start_time.astimezone()
            result[local_time.date()].append(session)
    return dict(result)
