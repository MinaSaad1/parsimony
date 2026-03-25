"""Frozen dataclasses representing every event type in Claude Code JSONL session files.

Each dataclass maps directly to one top-level JSONL record shape. The
``from_dict`` classmethods handle missing or malformed keys gracefully so
that a single bad record never aborts a full session parse.

Union type ``Event`` covers all concrete event types plus the ``RawEvent``
fallback for unknown or future record types.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

# ---------------------------------------------------------------------------
# Token accounting
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class TokenUsage:
    """Token counts drawn from a single usage block in the API response."""

    input_tokens: int = 0
    output_tokens: int = 0
    cache_creation_input_tokens: int = 0
    cache_read_input_tokens: int = 0
    ephemeral_5m_input_tokens: int = 0
    ephemeral_1h_input_tokens: int = 0
    service_tier: str = "standard"

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TokenUsage:
        """Build a ``TokenUsage`` from a raw usage dict.

        Args:
            data: Raw usage mapping from a JSONL record. Missing keys default
                to zero or the field-level default.

        Returns:
            A fully populated, immutable ``TokenUsage`` instance.
        """
        cache_creation: dict[str, Any] = data.get("cache_creation") or {}
        return cls(
            input_tokens=data.get("input_tokens", 0),
            output_tokens=data.get("output_tokens", 0),
            cache_creation_input_tokens=data.get("cache_creation_input_tokens", 0),
            cache_read_input_tokens=data.get("cache_read_input_tokens", 0),
            ephemeral_5m_input_tokens=cache_creation.get(
                "ephemeral_5m_input_tokens", 0
            ),
            ephemeral_1h_input_tokens=cache_creation.get(
                "ephemeral_1h_input_tokens", 0
            ),
            service_tier=data.get("service_tier", "standard"),
        )

    @property
    def total_tokens(self) -> int:
        """Sum of input, output, cache-creation, and cache-read tokens."""
        return (
            self.input_tokens
            + self.output_tokens
            + self.cache_creation_input_tokens
            + self.cache_read_input_tokens
        )


# ---------------------------------------------------------------------------
# Tool-use reference (lightweight; extracted from assistant content blocks)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ToolUseRef:
    """Minimal reference to a single tool-use block inside an assistant turn."""

    tool_id: str
    tool_name: str


# ---------------------------------------------------------------------------
# Subagent result (nested inside user tool_result entries)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SubagentResult:
    """Outcome metadata attached to a completed subagent tool-use result."""

    agent_id: str
    status: str
    total_tokens: int
    total_tool_use_count: int
    total_duration_ms: int
    usage: TokenUsage

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SubagentResult:
        """Build a ``SubagentResult`` from a raw ``toolUseResult`` dict.

        Args:
            data: The ``toolUseResult`` mapping from a user JSONL record.

        Returns:
            A fully populated, immutable ``SubagentResult`` instance.
        """
        return cls(
            agent_id=data.get("agentId", ""),
            status=data.get("status", ""),
            total_tokens=data.get("totalTokens", 0),
            total_tool_use_count=data.get("totalToolUseCount", 0),
            total_duration_ms=data.get("totalDurationMs", 0),
            usage=TokenUsage.from_dict(data.get("usage") or {}),
        )


# ---------------------------------------------------------------------------
# Concrete event types
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class AssistantEvent:
    """A single assistant turn parsed from a JSONL ``type: assistant`` record."""

    model: str
    request_id: str
    content_types: tuple[str, ...]
    tool_uses: tuple[ToolUseRef, ...]
    usage: TokenUsage
    timestamp: str
    uuid: str

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> AssistantEvent:
        """Build an ``AssistantEvent`` from a top-level JSONL record dict.

        Args:
            raw: The full deserialized JSONL record with ``type == "assistant"``.

        Returns:
            A fully populated, immutable ``AssistantEvent`` instance.
        """
        message: dict[str, Any] = raw.get("message") or {}
        content: list[dict[str, Any]] = message.get("content") or []

        content_types: tuple[str, ...] = tuple(
            block.get("type", "") for block in content if block.get("type")
        )
        tool_uses: tuple[ToolUseRef, ...] = tuple(
            ToolUseRef(
                tool_id=block.get("id", ""),
                tool_name=block.get("name", ""),
            )
            for block in content
            if block.get("type") == "tool_use"
        )

        return cls(
            model=message.get("model", ""),
            request_id=raw.get("requestId", ""),
            content_types=content_types,
            tool_uses=tool_uses,
            usage=TokenUsage.from_dict(message.get("usage") or {}),
            timestamp=raw.get("timestamp", ""),
            uuid=raw.get("uuid", ""),
        )


@dataclass(frozen=True)
class UserEvent:
    """A single user turn parsed from a JSONL ``type: user`` record."""

    session_id: str
    cwd: str | None
    version: str | None
    git_branch: str | None
    timestamp: str
    uuid: str
    subagent_result: SubagentResult | None

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> UserEvent:
        """Build a ``UserEvent`` from a top-level JSONL record dict.

        Args:
            raw: The full deserialized JSONL record with ``type == "user"``.

        Returns:
            A fully populated, immutable ``UserEvent`` instance.
        """
        tool_use_result: dict[str, Any] | None = raw.get("toolUseResult")
        subagent: SubagentResult | None = (
            SubagentResult.from_dict(tool_use_result)
            if tool_use_result
            else None
        )
        return cls(
            session_id=raw.get("sessionId", ""),
            cwd=raw.get("cwd"),
            version=raw.get("version"),
            git_branch=raw.get("gitBranch"),
            timestamp=raw.get("timestamp", ""),
            uuid=raw.get("uuid", ""),
            subagent_result=subagent,
        )


@dataclass(frozen=True)
class CustomTitleEvent:
    """A session title record parsed from a JSONL ``type: custom-title`` entry."""

    session_id: str
    title: str

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> CustomTitleEvent:
        """Build a ``CustomTitleEvent`` from a top-level JSONL record dict.

        Args:
            raw: The full deserialized JSONL record with ``type == "custom-title"``.

        Returns:
            A fully populated, immutable ``CustomTitleEvent`` instance.
        """
        return cls(
            session_id=raw.get("sessionId", ""),
            title=raw.get("customTitle", ""),
        )


@dataclass(frozen=True)
class RawEvent:
    """Fallback container for any JSONL record whose ``type`` is not recognized.

    The ``raw`` field holds the original deserialized dict. The dataclass
    itself is frozen; the dict value is intentionally kept mutable so no
    deep-copy overhead is incurred during parsing of large sessions.
    """

    event_type: str
    timestamp: str | None
    session_id: str | None
    raw: dict[str, Any]


# ---------------------------------------------------------------------------
# Union type for all event variants
# ---------------------------------------------------------------------------

Event = AssistantEvent | UserEvent | CustomTitleEvent | RawEvent
