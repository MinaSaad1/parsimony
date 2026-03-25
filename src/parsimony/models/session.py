"""Domain models for parsed sessions with computed properties.

Wraps the parser output (SessionData, ModelSegment, APICall) with richer
domain logic including cost association and duration computation.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from parsimony.parser.events import SubagentResult
from parsimony.parser.session_builder import (
    ModelSegment,
    SessionData,
)


def _parse_timestamp(ts: str | None) -> datetime | None:
    """Parse an ISO 8601 UTC timestamp string into a datetime."""
    if not ts:
        return None
    try:
        # Handle both 'Z' suffix and '+00:00'
        cleaned = ts.replace("Z", "+00:00")
        return datetime.fromisoformat(cleaned)
    except (ValueError, TypeError):
        return None


@dataclass(frozen=True)
class Session:
    """Enriched session model with parsed timestamps and project context."""

    session_id: str
    project_name: str
    project_path: str
    title: str | None
    segments: tuple[ModelSegment, ...]
    subagent_results: tuple[SubagentResult, ...]
    start_time: datetime | None
    end_time: datetime | None
    cwd: str | None
    version: str | None
    git_branch: str | None

    @classmethod
    def from_session_data(
        cls,
        data: SessionData,
        project_name: str,
        project_path: str,
    ) -> Session:
        """Build a Session from parser output plus project context."""
        return cls(
            session_id=data.session_id,
            project_name=project_name,
            project_path=project_path,
            title=data.title,
            segments=data.segments,
            subagent_results=data.subagent_results,
            start_time=_parse_timestamp(data.start_time),
            end_time=_parse_timestamp(data.end_time),
            cwd=data.cwd,
            version=data.version,
            git_branch=data.git_branch,
        )

    @property
    def duration(self) -> timedelta | None:
        if self.start_time and self.end_time:
            return self.end_time - self.start_time
        return None

    @property
    def total_api_calls(self) -> int:
        return sum(seg.call_count for seg in self.segments)

    @property
    def models_used(self) -> frozenset[str]:
        return frozenset(seg.model for seg in self.segments)

    @property
    def total_input_tokens(self) -> int:
        return sum(seg.total_input_tokens for seg in self.segments)

    @property
    def total_output_tokens(self) -> int:
        return sum(seg.total_output_tokens for seg in self.segments)

    @property
    def total_cache_write_tokens(self) -> int:
        return sum(seg.total_cache_write_tokens for seg in self.segments)

    @property
    def total_cache_read_tokens(self) -> int:
        return sum(seg.total_cache_read_tokens for seg in self.segments)

    @property
    def total_tokens(self) -> int:
        return (
            self.total_input_tokens
            + self.total_output_tokens
            + self.total_cache_write_tokens
            + self.total_cache_read_tokens
        )

    @property
    def subagent_total_tokens(self) -> int:
        return sum(s.total_tokens for s in self.subagent_results)
