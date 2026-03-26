"""Tests for parsimony.budget."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path
from textwrap import dedent
from unittest.mock import patch

from click.testing import CliRunner

from parsimony.budget import (
    BudgetConfig,
    TokenBudgetConfig,
    check_budget,
    check_token_budget,
    load_budget,
    load_token_budget,
)
from parsimony.cli import main
from parsimony.models.session import Session
from parsimony.parser.reader import read_events
from parsimony.parser.session_builder import build_session

FIXTURES = Path(__file__).parent / "fixtures"


def _make_session(fixture: str, session_id: str, project: str = "test") -> Session:
    events = list(read_events(FIXTURES / fixture))
    data = build_session(session_id, events)
    return Session.from_session_data(data, project, f"C:\\{project}")


class TestBudgetConfig:
    def test_default_not_configured(self) -> None:
        cfg = BudgetConfig()
        assert cfg.is_configured is False

    def test_daily_only(self) -> None:
        cfg = BudgetConfig(daily=Decimal("5.00"))
        assert cfg.is_configured is True

    def test_all_thresholds(self) -> None:
        cfg = BudgetConfig(
            daily=Decimal("5.00"),
            weekly=Decimal("25.00"),
            monthly=Decimal("80.00"),
        )
        assert cfg.is_configured is True

    def test_frozen(self) -> None:
        cfg = BudgetConfig()
        try:
            cfg.daily = Decimal("1")  # type: ignore[misc]
            raise AssertionError("Should not allow mutation")
        except AttributeError:
            pass


class TestCheckBudget:
    def test_under_budget(self) -> None:
        status = check_budget(Decimal("3.00"), Decimal("5.00"), "daily")
        assert status.over_budget is False
        assert status.percentage == 60.0
        assert status.period == "daily"

    def test_over_budget(self) -> None:
        status = check_budget(Decimal("6.00"), Decimal("5.00"), "daily")
        assert status.over_budget is True
        assert status.percentage == 120.0

    def test_exactly_at_limit(self) -> None:
        status = check_budget(Decimal("5.00"), Decimal("5.00"), "weekly")
        assert status.over_budget is False
        assert status.percentage == 100.0

    def test_zero_limit(self) -> None:
        status = check_budget(Decimal("1.00"), Decimal("0"), "daily")
        assert status.percentage == 0.0

    def test_zero_spend(self) -> None:
        status = check_budget(Decimal("0"), Decimal("5.00"), "daily")
        assert status.over_budget is False
        assert status.percentage == 0.0


class TestLoadBudget:
    def test_missing_file(self, tmp_path: Path) -> None:
        cfg = load_budget(tmp_path / "nonexistent.yaml")
        assert cfg.is_configured is False

    def test_valid_config(self, tmp_path: Path) -> None:
        config_file = tmp_path / "config.yaml"
        config_file.write_text(dedent("""\
            budget:
              daily: 5.00
              weekly: 25.00
              monthly: 80.00
        """))
        cfg = load_budget(config_file)
        assert cfg.daily == Decimal("5.0")
        assert cfg.weekly == Decimal("25.0")
        assert cfg.monthly == Decimal("80.0")

    def test_partial_config(self, tmp_path: Path) -> None:
        config_file = tmp_path / "config.yaml"
        config_file.write_text(dedent("""\
            budget:
              daily: 10.00
        """))
        cfg = load_budget(config_file)
        assert cfg.daily == Decimal("10.0")
        assert cfg.weekly is None
        assert cfg.monthly is None

    def test_no_budget_key(self, tmp_path: Path) -> None:
        config_file = tmp_path / "config.yaml"
        config_file.write_text("other_key: value\n")
        cfg = load_budget(config_file)
        assert cfg.is_configured is False

    def test_empty_file(self, tmp_path: Path) -> None:
        config_file = tmp_path / "config.yaml"
        config_file.write_text("")
        cfg = load_budget(config_file)
        assert cfg.is_configured is False

    def test_invalid_yaml(self, tmp_path: Path) -> None:
        config_file = tmp_path / "config.yaml"
        config_file.write_text(": : : invalid")
        cfg = load_budget(config_file)
        assert cfg.is_configured is False

    def test_invalid_decimal_value(self, tmp_path: Path) -> None:
        config_file = tmp_path / "config.yaml"
        config_file.write_text(dedent("""\
            budget:
              daily: "not a number"
              weekly: 25.00
        """))
        cfg = load_budget(config_file)
        assert cfg.daily is None
        assert cfg.weekly == Decimal("25.0")


class TestBudgetCLI:
    def test_budget_no_config(self) -> None:
        runner = CliRunner()
        with (
            patch("parsimony.cli.load_budget", return_value=BudgetConfig()),
            patch("parsimony.cli._load_all_sessions", return_value=[]),
        ):
            result = runner.invoke(main, ["budget"])
        assert result.exit_code == 0
        assert "No budget configured" in result.output

    def test_budget_with_config(self) -> None:
        sessions = [
            _make_session(
                "simple_session.jsonl", "aaaaaaaa-1111-2222-3333-444444444444",
            ),
        ]
        cfg = BudgetConfig(
            daily=Decimal("100.00"),
            weekly=Decimal("500.00"),
        )
        runner = CliRunner()
        with (
            patch("parsimony.cli.load_budget", return_value=cfg),
            patch("parsimony.cli._load_all_sessions", return_value=sessions),
        ):
            result = runner.invoke(main, ["budget"])
        assert result.exit_code == 0
        assert "daily" in result.output
        assert "weekly" in result.output


class TestTokenBudgetConfig:
    def test_default_not_configured(self) -> None:
        cfg = TokenBudgetConfig()
        assert cfg.is_configured is False

    def test_session_only(self) -> None:
        cfg = TokenBudgetConfig(session_limit=88_000)
        assert cfg.is_configured is True

    def test_weekly_only(self) -> None:
        cfg = TokenBudgetConfig(weekly_limit=45_000_000)
        assert cfg.is_configured is True

    def test_frozen(self) -> None:
        cfg = TokenBudgetConfig()
        try:
            cfg.session_limit = 100  # type: ignore[misc]
            raise AssertionError("Should not allow mutation")
        except AttributeError:
            pass


class TestTokenBudgetStatus:
    def test_under_limit(self) -> None:
        status = check_token_budget(30_000, 88_000, "session")
        assert status.over_limit is False
        assert 0 < status.percentage < 100

    def test_over_limit(self) -> None:
        status = check_token_budget(100_000, 88_000, "session")
        assert status.over_limit is True
        assert status.percentage > 100

    def test_zero_limit(self) -> None:
        status = check_token_budget(1000, 0, "session")
        assert status.percentage == 0.0

    def test_exact_limit(self) -> None:
        status = check_token_budget(88_000, 88_000, "session")
        assert status.over_limit is False  # used == limit is NOT over


class TestLoadTokenBudget:
    def test_no_file(self, tmp_path: Path) -> None:
        cfg = load_token_budget(config_path=tmp_path / "nonexistent.yaml")
        assert cfg.is_configured is False

    def test_config_file_session_limit(self, tmp_path: Path) -> None:
        config_file = tmp_path / "config.yaml"
        config_file.write_text(dedent("""\
            token_budget:
              session_limit: 500000
        """))
        cfg = load_token_budget(config_path=config_file)
        assert cfg.session_limit == 500_000

    def test_config_file_weekly_limit(self, tmp_path: Path) -> None:
        config_file = tmp_path / "config.yaml"
        config_file.write_text(dedent("""\
            token_budget:
              weekly_limit: 5000000
        """))
        cfg = load_token_budget(config_path=config_file)
        assert cfg.weekly_limit == 5_000_000

    def test_config_file_both_limits(self, tmp_path: Path) -> None:
        config_file = tmp_path / "config.yaml"
        config_file.write_text(dedent("""\
            token_budget:
              session_limit: 500000
              weekly_limit: 5000000
        """))
        cfg = load_token_budget(config_path=config_file)
        assert cfg.session_limit == 500_000
        assert cfg.weekly_limit == 5_000_000
