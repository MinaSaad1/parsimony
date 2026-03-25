"""Tests for parsimony.models.session."""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path

from parsimony.models.session import Session, _parse_timestamp
from parsimony.parser.reader import read_events
from parsimony.parser.session_builder import build_session

FIXTURES = Path(__file__).parent.parent / "fixtures"


class TestParseTimestamp:
    def test_utc_z_suffix(self) -> None:
        dt = _parse_timestamp("2026-03-20T10:00:00.000Z")
        assert dt is not None
        assert dt.year == 2026
        assert dt.month == 3
        assert dt.hour == 10

    def test_none_input(self) -> None:
        assert _parse_timestamp(None) is None

    def test_empty_string(self) -> None:
        assert _parse_timestamp("") is None

    def test_invalid_string(self) -> None:
        assert _parse_timestamp("not-a-date") is None


class TestSession:
    def test_from_session_data(self) -> None:
        events = list(read_events(FIXTURES / "simple_session.jsonl"))
        data = build_session("aaaaaaaa-1111-2222-3333-444444444444", events)
        session = Session.from_session_data(data, "myproject", "C:\\myproject")

        assert session.session_id == "aaaaaaaa-1111-2222-3333-444444444444"
        assert session.project_name == "myproject"
        assert session.project_path == "C:\\myproject"

    def test_duration(self) -> None:
        events = list(read_events(FIXTURES / "simple_session.jsonl"))
        data = build_session("aaaaaaaa-1111-2222-3333-444444444444", events)
        session = Session.from_session_data(data, "test", "test")

        assert session.duration is not None
        assert isinstance(session.duration, timedelta)
        assert session.duration.total_seconds() > 0

    def test_total_tokens(self) -> None:
        events = list(read_events(FIXTURES / "simple_session.jsonl"))
        data = build_session("aaaaaaaa-1111-2222-3333-444444444444", events)
        session = Session.from_session_data(data, "test", "test")

        assert session.total_tokens > 0
        assert session.total_input_tokens > 0
        assert session.total_output_tokens > 0

    def test_multi_model_models_used(self) -> None:
        events = list(read_events(FIXTURES / "multi_model_session.jsonl"))
        data = build_session("bbbbbbbb-1111-2222-3333-444444444444", events)
        session = Session.from_session_data(data, "test", "test")

        assert len(session.models_used) == 3

    def test_subagent_total_tokens(self) -> None:
        events = list(read_events(FIXTURES / "subagent_session.jsonl"))
        data = build_session("cccccccc-1111-2222-3333-444444444444", events)
        session = Session.from_session_data(data, "test", "test")

        assert session.subagent_total_tokens == 42000

    def test_empty_session(self) -> None:
        data = build_session("empty", [])
        session = Session.from_session_data(data, "test", "test")

        assert session.duration is None
        assert session.total_tokens == 0
        assert session.total_api_calls == 0
