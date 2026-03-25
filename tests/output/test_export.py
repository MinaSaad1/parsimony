"""Tests for parsimony.output.export."""

from __future__ import annotations

import csv
import io
import json
from pathlib import Path

from parsimony.aggregator.rollup import compute_rollup
from parsimony.models.session import Session
from parsimony.output.export import export_csv, export_json
from parsimony.parser.reader import read_events
from parsimony.parser.session_builder import build_session

FIXTURES = Path(__file__).parent.parent / "fixtures"


def _make_session(fixture: str, session_id: str, project: str = "test") -> Session:
    events = list(read_events(FIXTURES / fixture))
    data = build_session(session_id, events)
    return Session.from_session_data(data, project, f"C:\\{project}")


class TestExportJson:
    def test_valid_json(self) -> None:
        session = _make_session("simple_session.jsonl", "s1")
        rollup = compute_rollup([session])
        result = export_json(rollup)
        data = json.loads(result)
        assert data["session_count"] == 1
        assert data["total_cost"] > 0

    def test_has_per_model(self) -> None:
        session = _make_session("multi_model_session.jsonl", "s1")
        rollup = compute_rollup([session])
        data = json.loads(export_json(rollup))
        assert len(data["per_model"]) == 3

    def test_write_to_file(self, tmp_path: Path) -> None:
        session = _make_session("simple_session.jsonl", "s1")
        rollup = compute_rollup([session])
        out_file = tmp_path / "report.json"
        export_json(rollup, path=out_file)
        assert out_file.exists()
        data = json.loads(out_file.read_text())
        assert data["session_count"] == 1


class TestExportCsv:
    def test_valid_csv(self) -> None:
        session = _make_session("simple_session.jsonl", "s1")
        rollup = compute_rollup([session])
        result = export_csv(rollup)
        reader = csv.reader(io.StringIO(result))
        rows = list(reader)
        assert rows[0][0] == "model"
        assert len(rows) >= 2  # header + at least one model

    def test_multi_model_rows(self) -> None:
        session = _make_session("multi_model_session.jsonl", "s1")
        rollup = compute_rollup([session])
        result = export_csv(rollup)
        reader = csv.reader(io.StringIO(result))
        rows = list(reader)
        assert len(rows) == 4  # header + 3 models

    def test_write_to_file(self, tmp_path: Path) -> None:
        session = _make_session("simple_session.jsonl", "s1")
        rollup = compute_rollup([session])
        out_file = tmp_path / "report.csv"
        export_csv(rollup, path=out_file)
        assert out_file.exists()
