"""Streaming JSONL reader for Claude Code session files.

Reads session files line by line to avoid loading large files into memory.
Files may contain millions of events, so all I/O is generator-based.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from parsimony.parser.events import (
    AssistantEvent,
    CustomTitleEvent,
    Event,
    RawEvent,
    UserEvent,
)

logger = logging.getLogger("parsimony.parser.reader")


def read_events(path: Path) -> Iterator[Event]:
    """Read and parse all events from a JSONL session file.

    Reads the file line by line, skipping blank lines and lines that
    cannot be decoded as JSON. Malformed lines are logged as warnings
    and never raise exceptions to the caller.

    Args:
        path: Absolute path to the JSONL session file.

    Yields:
        Parsed Event instances in the order they appear in the file.
    """
    with path.open(encoding="utf-8") as fh:
        for line_number, raw_line in enumerate(fh, start=1):
            line = raw_line.strip()
            if not line:
                continue

            try:
                raw_dict: dict[str, Any] = json.loads(line)
            except json.JSONDecodeError:
                logger.warning(
                    "Skipping malformed JSON at line %d in %s",
                    line_number,
                    path,
                )
                continue

            yield parse_event(raw_dict)


def parse_event(raw: dict[str, Any]) -> Event:
    """Dispatch a raw dictionary to the appropriate typed Event class.

    Args:
        raw: A single decoded JSON object from a session file line.

    Returns:
        A typed Event subclass when the type is recognised, or a
        RawEvent wrapping the original dictionary for unknown types.
    """
    event_type = raw.get("type")

    if event_type == "assistant":
        return AssistantEvent.from_dict(raw)
    if event_type == "user":
        return UserEvent.from_dict(raw)
    if event_type == "custom-title":
        return CustomTitleEvent.from_dict(raw)

    return RawEvent(
        event_type=event_type if isinstance(event_type, str) else "unknown",
        timestamp=raw.get("timestamp"),
        session_id=raw.get("sessionId"),
        raw=raw,
    )
