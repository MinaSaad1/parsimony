"""Build structured session data from a stream of parsed JSONL events.

Groups raw events into a hierarchy of API calls, model segments, and
subagent results.  The central algorithm deduplicates streaming assistant
chunks by ``requestId`` and detects model switches within a session.
"""

from __future__ import annotations

from dataclasses import dataclass

from parsimony.parser.events import (
    AssistantEvent,
    CustomTitleEvent,
    Event,
    SubagentResult,
    TokenUsage,
    ToolUseRef,
    UserEvent,
)

# ---------------------------------------------------------------------------
# Intermediate representations (output of session building)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class APICall:
    """A single deduplicated API call (one ``requestId``)."""

    request_id: str
    model: str
    usage: TokenUsage
    tool_uses: tuple[ToolUseRef, ...]
    content_types: tuple[str, ...]
    timestamp: str


@dataclass(frozen=True)
class ModelSegment:
    """A contiguous run of API calls using the same model."""

    model: str
    calls: tuple[APICall, ...]

    @property
    def total_input_tokens(self) -> int:
        return sum(c.usage.input_tokens for c in self.calls)

    @property
    def total_output_tokens(self) -> int:
        return sum(c.usage.output_tokens for c in self.calls)

    @property
    def total_cache_write_tokens(self) -> int:
        return sum(c.usage.cache_creation_input_tokens for c in self.calls)

    @property
    def total_cache_read_tokens(self) -> int:
        return sum(c.usage.cache_read_input_tokens for c in self.calls)

    @property
    def call_count(self) -> int:
        return len(self.calls)


@dataclass(frozen=True)
class SessionData:
    """Fully parsed session data extracted from a single JSONL file."""

    session_id: str
    title: str | None
    segments: tuple[ModelSegment, ...]
    subagent_results: tuple[SubagentResult, ...]
    start_time: str | None
    end_time: str | None
    cwd: str | None
    version: str | None
    git_branch: str | None

    @property
    def total_api_calls(self) -> int:
        return sum(seg.call_count for seg in self.segments)

    @property
    def models_used(self) -> frozenset[str]:
        return frozenset(seg.model for seg in self.segments)


# ---------------------------------------------------------------------------
# Builder logic
# ---------------------------------------------------------------------------

_SYNTHETIC_MODEL = "<synthetic>"


def _deduplicate_api_calls(events: list[AssistantEvent]) -> list[APICall]:
    """Group assistant events by requestId and take the last chunk's usage.

    Multiple streaming chunks share the same ``requestId``. The final chunk
    carries the cumulative usage, so we always take the *last* entry per
    request.  Content types and tool uses are merged across all chunks.
    """
    by_request: dict[str, list[AssistantEvent]] = {}
    for event in events:
        if not event.request_id:
            continue
        by_request.setdefault(event.request_id, []).append(event)

    calls: list[APICall] = []
    for request_id, chunks in by_request.items():
        final = chunks[-1]

        # Skip synthetic model entries (not billed)
        if final.model == _SYNTHETIC_MODEL:
            continue

        merged_types: list[str] = []
        merged_tools: list[ToolUseRef] = []
        for chunk in chunks:
            merged_types.extend(chunk.content_types)
            merged_tools.extend(chunk.tool_uses)

        calls.append(
            APICall(
                request_id=request_id,
                model=final.model,
                usage=final.usage,
                tool_uses=tuple(merged_tools),
                content_types=tuple(dict.fromkeys(merged_types)),
                timestamp=chunks[0].timestamp,
            )
        )

    calls.sort(key=lambda c: c.timestamp)
    return calls


def _build_model_segments(calls: list[APICall]) -> list[ModelSegment]:
    """Split a sorted list of API calls into contiguous model segments."""
    if not calls:
        return []

    segments: list[ModelSegment] = []
    current_model = calls[0].model
    segment_calls: list[APICall] = []

    for call in calls:
        if call.model != current_model:
            segments.append(
                ModelSegment(model=current_model, calls=tuple(segment_calls))
            )
            current_model = call.model
            segment_calls = []
        segment_calls.append(call)

    if segment_calls:
        segments.append(
            ModelSegment(model=current_model, calls=tuple(segment_calls))
        )

    return segments


def build_session(session_id: str, events: list[Event]) -> SessionData:
    """Transform a flat list of events into a structured ``SessionData``.

    Args:
        session_id: The UUID identifying this session.
        events: All events from a single session file, in order.

    Returns:
        A fully populated, immutable ``SessionData`` instance.
    """
    assistant_events: list[AssistantEvent] = []
    subagent_results: list[SubagentResult] = []
    title: str | None = None
    cwd: str | None = None
    version: str | None = None
    git_branch: str | None = None
    timestamps: list[str] = []

    for event in events:
        if isinstance(event, AssistantEvent):
            assistant_events.append(event)
            if event.timestamp:
                timestamps.append(event.timestamp)

        elif isinstance(event, UserEvent):
            if event.subagent_result is not None:
                subagent_results.append(event.subagent_result)
            if cwd is None and event.cwd:
                cwd = event.cwd
            if version is None and event.version:
                version = event.version
            if git_branch is None and event.git_branch:
                git_branch = event.git_branch
            if event.timestamp:
                timestamps.append(event.timestamp)

        elif isinstance(event, CustomTitleEvent):
            title = event.title

    api_calls = _deduplicate_api_calls(assistant_events)
    segments = _build_model_segments(api_calls)

    timestamps.sort()
    start_time = timestamps[0] if timestamps else None
    end_time = timestamps[-1] if timestamps else None

    return SessionData(
        session_id=session_id,
        title=title,
        segments=tuple(segments),
        subagent_results=tuple(subagent_results),
        start_time=start_time,
        end_time=end_time,
        cwd=cwd,
        version=version,
        git_branch=git_branch,
    )
