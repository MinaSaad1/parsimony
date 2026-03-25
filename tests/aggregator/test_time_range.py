"""Tests for parsimony.aggregator.time_range."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from parsimony.aggregator.time_range import TimeRange, filter_sessions
from parsimony.models.session import Session
from parsimony.parser.reader import read_events
from parsimony.parser.session_builder import build_session

FIXTURES = Path(__file__).parent.parent / "fixtures"


def _make_session(fixture: str, session_id: str, project: str = "test") -> Session:
    events = list(read_events(FIXTURES / fixture))
    data = build_session(session_id, events)
    return Session.from_session_data(data, project, f"C:\\{project}")


class TestTimeRange:
    def test_today_has_label(self) -> None:
        tr = TimeRange.today()
        assert tr.label
        assert tr.start <= tr.end

    def test_yesterday(self) -> None:
        tr = TimeRange.yesterday()
        assert "Yesterday" in tr.label

    def test_this_week(self) -> None:
        tr = TimeRange.this_week()
        assert "Week of" in tr.label
        assert tr.start <= tr.end

    def test_last_week(self) -> None:
        tr = TimeRange.last_week()
        assert tr.start < TimeRange.this_week().start

    def test_this_month(self) -> None:
        tr = TimeRange.this_month()
        assert tr.start.day == 1
        assert tr.start <= tr.end

    def test_specific_month(self) -> None:
        tr = TimeRange.month(2026, 2)
        assert "February 2026" in tr.label
        assert tr.start.month == 2
        assert tr.end.month == 2

    def test_december_month(self) -> None:
        tr = TimeRange.month(2026, 12)
        assert tr.start.month == 12
        assert tr.end.month == 12
        assert tr.end.day == 31

    def test_last_n_days(self) -> None:
        tr = TimeRange.last_n_days(7)
        assert "Last 7 days" in tr.label

    def test_all_time(self) -> None:
        tr = TimeRange.all_time()
        assert tr.label == "All time"


class TestFilterSessions:
    def test_filters_by_time(self) -> None:
        session = _make_session(
            "simple_session.jsonl",
            "aaaaaaaa-1111-2222-3333-444444444444",
        )

        # Session timestamps are from 2026-03-20
        march_range = TimeRange.month(2026, 3)
        feb_range = TimeRange.month(2026, 2)

        assert len(filter_sessions([session], march_range)) == 1
        assert len(filter_sessions([session], feb_range)) == 0

    def test_all_time_includes_everything(self) -> None:
        session = _make_session(
            "simple_session.jsonl",
            "aaaaaaaa-1111-2222-3333-444444444444",
        )
        result = filter_sessions([session], TimeRange.all_time())
        assert len(result) == 1

    def test_empty_sessions(self) -> None:
        result = filter_sessions([], TimeRange.today())
        assert result == []

    def test_session_without_timestamp_excluded(self) -> None:
        data = build_session("empty", [])
        session = Session.from_session_data(data, "test", "test")
        result = filter_sessions([session], TimeRange.all_time())
        assert len(result) == 0
