"""Filesystem watcher for JSONL session files.

Uses ``watchfiles`` (Rust-based) to efficiently detect changes in
``~/.claude/projects/`` and trigger dashboard refreshes.
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger("parsimony.dashboard.watcher")

# Minimum interval between refresh callbacks (seconds)
_DEBOUNCE_SECONDS = 2.0


async def watch_sessions(
    base_path: Path,
    callback: Any,
    stop_event: asyncio.Event | None = None,
) -> None:
    """Watch for JSONL file changes and invoke *callback* on each batch.

    Changes are debounced so the callback fires at most once every
    ``_DEBOUNCE_SECONDS``.

    Args:
        base_path: Root directory to watch (e.g. ``~/.claude/projects``).
        callback: An async callable invoked with a set of changed paths.
        stop_event: Optional event to signal the watcher to stop.
    """
    from watchfiles import awatch

    if stop_event is None:
        stop_event = asyncio.Event()

    try:
        async for changes in awatch(
            base_path,
            debounce=int(_DEBOUNCE_SECONDS * 1000),
            step=500,
            stop_event=stop_event,
            watch_filter=_jsonl_filter,
        ):
            jsonl_paths = {Path(path) for _, path in changes if path.endswith(".jsonl")}
            if jsonl_paths:
                logger.debug("Detected %d JSONL changes", len(jsonl_paths))
                try:
                    await callback(jsonl_paths)
                except Exception:
                    logger.debug("Refresh callback failed", exc_info=True)
    except Exception:
        logger.debug("Watcher stopped", exc_info=True)


def _jsonl_filter(change: Any, path: str) -> bool:
    """Only watch .jsonl files."""
    return path.endswith(".jsonl")
