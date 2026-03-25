"""Tests for parsimony.cache.store."""

from __future__ import annotations

import time
from pathlib import Path

from parsimony.cache.store import CacheStore
from parsimony.models.session import Session
from parsimony.parser.reader import read_events
from parsimony.parser.session_builder import build_session

FIXTURES = Path(__file__).parent.parent / "fixtures"


def _make_session(fixture: str, session_id: str, project: str = "test") -> Session:
    events = list(read_events(FIXTURES / fixture))
    data = build_session(session_id, events)
    return Session.from_session_data(data, project, f"C:\\{project}")


class TestCacheStore:
    def test_miss_returns_none(self, tmp_path: Path) -> None:
        store = CacheStore(tmp_path / "cache.db")
        result = store.get("nonexistent.jsonl", 100, 12345.0)
        assert result is None
        store.close()

    def test_hit_after_put(self, tmp_path: Path) -> None:
        store = CacheStore(tmp_path / "cache.db")
        session = _make_session("simple_session.jsonl", "s1")
        store.put("test.jsonl", 1000, 12345.0, session)
        result = store.get("test.jsonl", 1000, 12345.0)
        assert result is not None
        assert result.session_id == "s1"
        assert result.total_tokens == session.total_tokens
        store.close()

    def test_miss_on_size_change(self, tmp_path: Path) -> None:
        store = CacheStore(tmp_path / "cache.db")
        session = _make_session("simple_session.jsonl", "s1")
        store.put("test.jsonl", 1000, 12345.0, session)
        result = store.get("test.jsonl", 2000, 12345.0)
        assert result is None
        store.close()

    def test_miss_on_mtime_change(self, tmp_path: Path) -> None:
        store = CacheStore(tmp_path / "cache.db")
        session = _make_session("simple_session.jsonl", "s1")
        store.put("test.jsonl", 1000, 12345.0, session)
        result = store.get("test.jsonl", 1000, 99999.0)
        assert result is None
        store.close()

    def test_invalidate(self, tmp_path: Path) -> None:
        store = CacheStore(tmp_path / "cache.db")
        session = _make_session("simple_session.jsonl", "s1")
        store.put("test.jsonl", 1000, 12345.0, session)
        store.invalidate("test.jsonl")
        result = store.get("test.jsonl", 1000, 12345.0)
        assert result is None
        store.close()

    def test_prune_old_entries(self, tmp_path: Path) -> None:
        store = CacheStore(tmp_path / "cache.db")
        session = _make_session("simple_session.jsonl", "s1")
        store.put("old.jsonl", 1000, 12345.0, session)
        # Manually backdate the cached_at timestamp
        store._conn.execute(
            "UPDATE session_cache SET cached_at = ? WHERE file_path = ?",
            (time.time() - 86400 * 60, "old.jsonl"),
        )
        store._conn.commit()
        store.put("new.jsonl", 1000, 12345.0, session)
        removed = store.prune(max_age_days=30)
        assert removed == 1
        assert store.get("old.jsonl", 1000, 12345.0) is None
        assert store.get("new.jsonl", 1000, 12345.0) is not None
        store.close()

    def test_multi_model_session_roundtrip(self, tmp_path: Path) -> None:
        store = CacheStore(tmp_path / "cache.db")
        session = _make_session("multi_model_session.jsonl", "mm1")
        store.put("multi.jsonl", 5000, 99999.0, session)
        result = store.get("multi.jsonl", 5000, 99999.0)
        assert result is not None
        assert result.models_used == session.models_used
        assert len(result.segments) == len(session.segments)
        store.close()

    def test_subagent_session_roundtrip(self, tmp_path: Path) -> None:
        store = CacheStore(tmp_path / "cache.db")
        session = _make_session("subagent_session.jsonl", "sub1")
        store.put("sub.jsonl", 3000, 11111.0, session)
        result = store.get("sub.jsonl", 3000, 11111.0)
        assert result is not None
        assert len(result.subagent_results) == len(session.subagent_results)
        assert result.subagent_total_tokens == session.subagent_total_tokens
        store.close()

    def test_overwrite_existing(self, tmp_path: Path) -> None:
        store = CacheStore(tmp_path / "cache.db")
        s1 = _make_session("simple_session.jsonl", "s1")
        s2 = _make_session("multi_model_session.jsonl", "s2")
        store.put("test.jsonl", 1000, 12345.0, s1)
        store.put("test.jsonl", 2000, 99999.0, s2)
        result = store.get("test.jsonl", 2000, 99999.0)
        assert result is not None
        assert result.session_id == "s2"
        store.close()
