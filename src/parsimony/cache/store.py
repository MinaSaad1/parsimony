"""SQLite-backed cache for parsed session data.

Avoids re-parsing unchanged JSONL files by storing serialized Session
objects keyed by file path, size, and modification time.
"""

from __future__ import annotations

import json
import logging
import sqlite3
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from parsimony.models.session import Session
from parsimony.parser.events import SubagentResult, TokenUsage, ToolUseRef
from parsimony.parser.session_builder import APICall, ModelSegment

logger = logging.getLogger("parsimony.cache")

_SCHEMA = """\
CREATE TABLE IF NOT EXISTS session_cache (
    file_path TEXT PRIMARY KEY,
    file_size INTEGER NOT NULL,
    modified_time REAL NOT NULL,
    session_json TEXT NOT NULL,
    cached_at REAL NOT NULL
);
"""


class CacheStore:
    """SQLite cache for parsed Session objects."""

    def __init__(self, path: Path) -> None:
        self._path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(path))
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute(_SCHEMA)
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()

    def get(
        self, file_path: str, file_size: int, modified_time: float
    ) -> Session | None:
        """Return a cached Session if the file hasn't changed, else None."""
        row = self._conn.execute(
            "SELECT file_size, modified_time, session_json FROM session_cache "
            "WHERE file_path = ?",
            (file_path,),
        ).fetchone()

        if row is None:
            return None

        cached_size, cached_mtime, session_json = row
        if cached_size != file_size or abs(cached_mtime - modified_time) > 0.01:
            return None

        try:
            return _deserialize_session(json.loads(session_json))
        except Exception:
            logger.debug("Cache deserialization failed for %s", file_path, exc_info=True)
            self.invalidate(file_path)
            return None

    def put(
        self,
        file_path: str,
        file_size: int,
        modified_time: float,
        session: Session,
    ) -> None:
        """Store a parsed Session in the cache."""
        session_json = json.dumps(_serialize_session(session))
        self._conn.execute(
            "INSERT OR REPLACE INTO session_cache "
            "(file_path, file_size, modified_time, session_json, cached_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (file_path, file_size, modified_time, session_json, time.time()),
        )
        self._conn.commit()

    def invalidate(self, file_path: str) -> None:
        """Remove a cache entry."""
        self._conn.execute(
            "DELETE FROM session_cache WHERE file_path = ?", (file_path,)
        )
        self._conn.commit()

    def prune(self, max_age_days: int = 30) -> int:
        """Remove entries older than max_age_days. Returns count removed."""
        cutoff = time.time() - (max_age_days * 86400)
        cursor = self._conn.execute(
            "DELETE FROM session_cache WHERE cached_at < ?", (cutoff,)
        )
        self._conn.commit()
        return cursor.rowcount


# ---------------------------------------------------------------------------
# Serialization helpers
# ---------------------------------------------------------------------------


def _serialize_session(session: Session) -> dict[str, Any]:
    """Convert a Session to a JSON-serializable dict."""
    return {
        "session_id": session.session_id,
        "project_name": session.project_name,
        "project_path": session.project_path,
        "title": session.title,
        "segments": [_serialize_segment(s) for s in session.segments],
        "subagent_results": [_serialize_subagent(s) for s in session.subagent_results],
        "start_time": session.start_time.isoformat() if session.start_time else None,
        "end_time": session.end_time.isoformat() if session.end_time else None,
        "cwd": session.cwd,
        "version": session.version,
        "git_branch": session.git_branch,
    }


def _serialize_segment(seg: ModelSegment) -> dict[str, Any]:
    return {
        "model": seg.model,
        "calls": [_serialize_call(c) for c in seg.calls],
    }


def _serialize_call(call: APICall) -> dict[str, Any]:
    return {
        "request_id": call.request_id,
        "model": call.model,
        "usage": _serialize_usage(call.usage),
        "tool_uses": [{"tool_id": t.tool_id, "tool_name": t.tool_name} for t in call.tool_uses],
        "content_types": list(call.content_types),
        "timestamp": call.timestamp,
    }


def _serialize_usage(u: TokenUsage) -> dict[str, Any]:
    return {
        "input_tokens": u.input_tokens,
        "output_tokens": u.output_tokens,
        "cache_creation_input_tokens": u.cache_creation_input_tokens,
        "cache_read_input_tokens": u.cache_read_input_tokens,
    }


def _serialize_subagent(s: SubagentResult) -> dict[str, Any]:
    return {
        "agent_id": s.agent_id,
        "status": s.status,
        "total_tokens": s.total_tokens,
        "total_tool_use_count": s.total_tool_use_count,
        "total_duration_ms": s.total_duration_ms,
        "usage": _serialize_usage(s.usage),
    }


def _deserialize_session(d: dict[str, Any]) -> Session:
    """Reconstruct a Session from a serialized dict."""
    start_time = _parse_dt(d.get("start_time"))
    end_time = _parse_dt(d.get("end_time"))

    return Session(
        session_id=d["session_id"],
        project_name=d["project_name"],
        project_path=d["project_path"],
        title=d.get("title"),
        segments=tuple(_deserialize_segment(s) for s in d.get("segments", [])),
        subagent_results=tuple(
            _deserialize_subagent(s) for s in d.get("subagent_results", [])
        ),
        start_time=start_time,
        end_time=end_time,
        cwd=d.get("cwd"),
        version=d.get("version"),
        git_branch=d.get("git_branch"),
    )


def _deserialize_segment(d: dict[str, Any]) -> ModelSegment:
    return ModelSegment(
        model=d["model"],
        calls=tuple(_deserialize_call(c) for c in d.get("calls", [])),
    )


def _deserialize_call(d: dict[str, Any]) -> APICall:
    return APICall(
        request_id=d["request_id"],
        model=d["model"],
        usage=_deserialize_usage(d["usage"]),
        tool_uses=tuple(
            ToolUseRef(tool_id=t["tool_id"], tool_name=t["tool_name"])
            for t in d.get("tool_uses", [])
        ),
        content_types=tuple(d.get("content_types", [])),
        timestamp=d.get("timestamp", ""),
    )


def _deserialize_usage(d: dict[str, Any]) -> TokenUsage:
    return TokenUsage(
        input_tokens=d.get("input_tokens", 0),
        output_tokens=d.get("output_tokens", 0),
        cache_creation_input_tokens=d.get("cache_creation_input_tokens", 0),
        cache_read_input_tokens=d.get("cache_read_input_tokens", 0),
    )


def _deserialize_subagent(d: dict[str, Any]) -> SubagentResult:
    return SubagentResult(
        agent_id=d["agent_id"],
        status=d.get("status", "completed"),
        total_tokens=d.get("total_tokens", 0),
        total_tool_use_count=d.get("total_tool_use_count", 0),
        total_duration_ms=d.get("total_duration_ms", 0),
        usage=_deserialize_usage(d.get("usage", {})),
    )


def _parse_dt(val: str | None) -> datetime | None:
    if not val:
        return None
    try:
        return datetime.fromisoformat(val)
    except (ValueError, TypeError):
        return None
