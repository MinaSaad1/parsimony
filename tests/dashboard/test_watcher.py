"""Tests for the filesystem watcher module."""

from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from parsimony.dashboard.watcher import _jsonl_filter, watch_sessions


class TestJsonlFilter:
    """Tests for the _jsonl_filter helper."""

    def test_accepts_jsonl(self) -> None:
        assert _jsonl_filter(None, "/some/path/session.jsonl") is True

    def test_rejects_json(self) -> None:
        assert _jsonl_filter(None, "/some/path/session.json") is False

    def test_rejects_txt(self) -> None:
        assert _jsonl_filter(None, "/some/path/notes.txt") is False

    def test_rejects_no_extension(self) -> None:
        assert _jsonl_filter(None, "/some/path/file") is False


class TestWatchSessions:
    """Tests for the watch_sessions async function."""

    @pytest.mark.asyncio
    async def test_stop_event_stops_watcher(self) -> None:
        stop_event = asyncio.Event()
        callback = AsyncMock()
        stop_event.set()

        async def empty_awatch(*args, **kwargs):  # type: ignore[no-untyped-def]
            return
            yield  # make it an async generator  # noqa: RET504

        with patch("watchfiles.awatch", new=empty_awatch):
            await watch_sessions(Path("/fake"), callback, stop_event)

        callback.assert_not_called()

    @pytest.mark.asyncio
    async def test_callback_invoked_on_jsonl_changes(self) -> None:
        callback = AsyncMock()
        stop_event = asyncio.Event()

        changes = [
            (1, "/projects/abc/session.jsonl"),
            (1, "/projects/abc/other.txt"),
        ]

        async def fake_awatch(*args, **kwargs):  # type: ignore[no-untyped-def]
            yield changes

        with patch("watchfiles.awatch", new=fake_awatch):
            await watch_sessions(Path("/fake"), callback, stop_event)

        callback.assert_called_once()
        called_paths = callback.call_args[0][0]
        assert len(called_paths) == 1
        assert Path("/projects/abc/session.jsonl") in called_paths

    @pytest.mark.asyncio
    async def test_callback_error_does_not_crash(self) -> None:
        callback = AsyncMock(side_effect=RuntimeError("boom"))
        stop_event = asyncio.Event()

        changes = [(1, "/a/b.jsonl")]

        async def fake_awatch(*args, **kwargs):  # type: ignore[no-untyped-def]
            yield changes

        with patch("watchfiles.awatch", new=fake_awatch):
            # Should not raise
            await watch_sessions(Path("/fake"), callback, stop_event)

    @pytest.mark.asyncio
    async def test_non_jsonl_changes_skipped(self) -> None:
        callback = AsyncMock()
        stop_event = asyncio.Event()

        changes = [(1, "/a/b.txt"), (1, "/a/c.json")]

        async def fake_awatch(*args, **kwargs):  # type: ignore[no-untyped-def]
            yield changes

        with patch("watchfiles.awatch", new=fake_awatch):
            await watch_sessions(Path("/fake"), callback, stop_event)

        callback.assert_not_called()
