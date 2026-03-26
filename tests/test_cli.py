"""Tests for parsimony.cli."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from click.testing import CliRunner

from parsimony.cli import main
from parsimony.models.session import Session
from parsimony.parser.reader import read_events
from parsimony.parser.session_builder import build_session

FIXTURES = Path(__file__).parent / "fixtures"


def _make_session(fixture: str, session_id: str, project: str = "test") -> Session:
    events = list(read_events(FIXTURES / fixture))
    data = build_session(session_id, events)
    return Session.from_session_data(data, project, f"C:\\{project}")


def _mock_sessions() -> list[Session]:
    return [
        _make_session("simple_session.jsonl", "aaaaaaaa-1111-2222-3333-444444444444"),
        _make_session("multi_model_session.jsonl", "bbbbbbbb-1111-2222-3333-444444444444"),
    ]


class TestCLIBasic:
    def test_help(self) -> None:
        runner = CliRunner()
        result = runner.invoke(main, ["--help"])
        assert result.exit_code == 0
        assert "Parsimony" in result.output

    def test_default_command(self) -> None:
        runner = CliRunner()
        with patch("parsimony.cli._load_all_sessions", return_value=_mock_sessions()):
            result = runner.invoke(main, [])
        assert result.exit_code == 0

    def test_today_command(self) -> None:
        runner = CliRunner()
        with patch("parsimony.cli._load_all_sessions", return_value=_mock_sessions()):
            result = runner.invoke(main, ["today"])
        assert result.exit_code == 0

    def test_yesterday_command(self) -> None:
        runner = CliRunner()
        with patch("parsimony.cli._load_all_sessions", return_value=_mock_sessions()):
            result = runner.invoke(main, ["yesterday"])
        assert result.exit_code == 0

    def test_week_command(self) -> None:
        runner = CliRunner()
        with patch("parsimony.cli._load_all_sessions", return_value=_mock_sessions()):
            result = runner.invoke(main, ["week"])
        assert result.exit_code == 0

    def test_month_command(self) -> None:
        runner = CliRunner()
        with patch("parsimony.cli._load_all_sessions", return_value=_mock_sessions()):
            result = runner.invoke(main, ["month", "2026-03"])
        assert result.exit_code == 0

    def test_month_invalid_format(self) -> None:
        runner = CliRunner()
        with patch("parsimony.cli._load_all_sessions", return_value=_mock_sessions()):
            result = runner.invoke(main, ["month", "invalid"])
        assert result.exit_code != 0


class TestCLISession:
    def test_session_detail(self) -> None:
        runner = CliRunner()
        with patch("parsimony.cli._load_all_sessions", return_value=_mock_sessions()):
            result = runner.invoke(main, ["session", "aaaaaaaa"])
        assert result.exit_code == 0

    def test_session_not_found(self) -> None:
        runner = CliRunner()
        with patch("parsimony.cli._load_all_sessions", return_value=_mock_sessions()):
            result = runner.invoke(main, ["session", "zzzzzzzz"])
        assert result.exit_code != 0

    def test_session_json_export(self) -> None:
        runner = CliRunner()
        with patch("parsimony.cli._load_all_sessions", return_value=_mock_sessions()):
            result = runner.invoke(main, ["--export", "json", "session", "aaaaaaaa"])
        assert result.exit_code == 0
        assert "session_id" in result.output


class TestCLITop:
    def test_top_sessions(self) -> None:
        runner = CliRunner()
        with patch("parsimony.cli._load_all_sessions", return_value=_mock_sessions()):
            result = runner.invoke(main, ["top", "sessions", "--period", "all"])
        assert result.exit_code == 0

    def test_top_models(self) -> None:
        runner = CliRunner()
        with patch("parsimony.cli._load_all_sessions", return_value=_mock_sessions()):
            result = runner.invoke(main, ["top", "models", "--period", "all"])
        assert result.exit_code == 0

    def test_top_tools(self) -> None:
        runner = CliRunner()
        with patch("parsimony.cli._load_all_sessions", return_value=_mock_sessions()):
            result = runner.invoke(main, ["top", "tools", "--period", "all"])
        assert result.exit_code == 0

    def test_top_projects(self) -> None:
        runner = CliRunner()
        with patch("parsimony.cli._load_all_sessions", return_value=_mock_sessions()):
            result = runner.invoke(main, ["top", "projects", "--period", "all"])
        assert result.exit_code == 0


class TestCLICompare:
    def test_compare_weeks(self) -> None:
        runner = CliRunner()
        with patch("parsimony.cli._load_all_sessions", return_value=_mock_sessions()):
            result = runner.invoke(main, ["compare", "--period", "week", "--last", "2"])
        assert result.exit_code == 0

    def test_compare_json_export(self) -> None:
        runner = CliRunner()
        with patch("parsimony.cli._load_all_sessions", return_value=_mock_sessions()):
            result = runner.invoke(main, ["--export", "json", "compare", "--period", "week", "--last", "2"])
        assert result.exit_code == 0


class TestCLIShowCost:
    def test_show_cost_flag(self) -> None:
        runner = CliRunner()
        with patch("parsimony.cli._load_all_sessions", return_value=_mock_sessions()):
            result = runner.invoke(main, ["--show-cost", "today"])
        assert result.exit_code == 0

    def test_show_cost_with_week(self) -> None:
        runner = CliRunner()
        with patch("parsimony.cli._load_all_sessions", return_value=_mock_sessions()):
            result = runner.invoke(main, ["--show-cost", "week"])
        assert result.exit_code == 0


class TestCLITokenFilters:
    def test_min_tokens(self) -> None:
        runner = CliRunner()
        with patch("parsimony.cli._load_all_sessions", return_value=_mock_sessions()):
            result = runner.invoke(main, ["--min-tokens", "1", "today"])
        assert result.exit_code == 0

    def test_max_tokens(self) -> None:
        runner = CliRunner()
        with patch("parsimony.cli._load_all_sessions", return_value=_mock_sessions()):
            result = runner.invoke(main, ["--max-tokens", "999999999", "today"])
        assert result.exit_code == 0


class TestCLIExport:
    def test_json_export(self) -> None:
        runner = CliRunner()
        with patch("parsimony.cli._load_all_sessions", return_value=_mock_sessions()):
            result = runner.invoke(main, ["--export", "json", "month", "2026-03"])
        assert result.exit_code == 0
        import json
        data = json.loads(result.output)
        assert "total_cost" in data

    def test_csv_export(self) -> None:
        runner = CliRunner()
        with patch("parsimony.cli._load_all_sessions", return_value=_mock_sessions()):
            result = runner.invoke(main, ["--export", "csv", "month", "2026-03"])
        assert result.exit_code == 0
        assert "model" in result.output
