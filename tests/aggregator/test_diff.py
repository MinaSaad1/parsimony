"""Tests for parsimony.aggregator.diff."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

from click.testing import CliRunner

from parsimony.aggregator.diff import DeltaValue, compute_diff
from parsimony.cli import main
from parsimony.models.cost import DEFAULT_PRICING
from parsimony.models.session import Session
from parsimony.parser.reader import read_events
from parsimony.parser.session_builder import build_session

FIXTURES = Path(__file__).parent.parent / "fixtures"


def _make_session(fixture: str, session_id: str, project: str = "test") -> Session:
    events = list(read_events(FIXTURES / fixture))
    data = build_session(session_id, events)
    return Session.from_session_data(data, project, f"C:\\{project}")


class TestDeltaValue:
    def test_positive_change(self) -> None:
        dv = DeltaValue(old=Decimal("10"), new=Decimal("15"))
        assert dv.change == Decimal("5")
        assert dv.change_pct == 50.0

    def test_negative_change(self) -> None:
        dv = DeltaValue(old=Decimal("10"), new=Decimal("5"))
        assert dv.change == Decimal("-5")
        assert dv.change_pct == -50.0

    def test_no_change(self) -> None:
        dv = DeltaValue(old=Decimal("10"), new=Decimal("10"))
        assert dv.change == Decimal("0")
        assert dv.change_pct == 0.0

    def test_from_zero(self) -> None:
        dv = DeltaValue(old=Decimal("0"), new=Decimal("5"))
        assert dv.change_pct == 100.0

    def test_both_zero(self) -> None:
        dv = DeltaValue(old=Decimal("0"), new=Decimal("0"))
        assert dv.change_pct == 0.0


class TestComputeDiff:
    def test_same_session(self) -> None:
        s = _make_session("simple_session.jsonl", "aaaa-1111-2222-3333-444444444444")
        diff = compute_diff(s, s, DEFAULT_PRICING)
        assert diff.total_cost.change == Decimal("0")
        assert diff.total_tokens.change == Decimal("0")
        assert diff.cache_efficiency.change == Decimal("0")

    def test_different_sessions(self) -> None:
        s1 = _make_session("simple_session.jsonl", "aaaa-1111-2222-3333-444444444444")
        s2 = _make_session(
            "multi_model_session.jsonl", "bbbb-1111-2222-3333-444444444444",
        )
        diff = compute_diff(s1, s2, DEFAULT_PRICING)

        assert diff.session_id_old == s1.session_id
        assert diff.session_id_new == s2.session_id
        # Multi-model session uses Opus, so should cost more
        assert diff.total_cost.new > diff.total_cost.old
        assert diff.total_cost.change > Decimal("0")

    def test_per_model_cost(self) -> None:
        s1 = _make_session("simple_session.jsonl", "aaaa-1111-2222-3333-444444444444")
        s2 = _make_session(
            "multi_model_session.jsonl", "bbbb-1111-2222-3333-444444444444",
        )
        diff = compute_diff(s1, s2, DEFAULT_PRICING)

        # s1 only uses Sonnet; s2 uses Opus, Sonnet, Haiku
        assert "claude-sonnet-4-6" in diff.per_model_cost
        assert "claude-opus-4-6" in diff.per_model_cost

        # Opus wasn't in s1, so old should be 0
        opus_delta = diff.per_model_cost["claude-opus-4-6"]
        assert opus_delta.old == Decimal("0")
        assert opus_delta.new > Decimal("0")

    def test_per_tool_count(self) -> None:
        s1 = _make_session("simple_session.jsonl", "aaaa-1111-2222-3333-444444444444")
        s2 = _make_session(
            "multi_model_session.jsonl", "bbbb-1111-2222-3333-444444444444",
        )
        diff = compute_diff(s1, s2, DEFAULT_PRICING)

        # simple_session has a Read tool call
        assert "Read" in diff.per_tool_count

    def test_token_deltas(self) -> None:
        s1 = _make_session("simple_session.jsonl", "aaaa-1111-2222-3333-444444444444")
        s2 = _make_session(
            "multi_model_session.jsonl", "bbbb-1111-2222-3333-444444444444",
        )
        diff = compute_diff(s1, s2, DEFAULT_PRICING)

        assert diff.input_tokens.old == Decimal(s1.total_input_tokens)
        assert diff.input_tokens.new == Decimal(s2.total_input_tokens)
        assert diff.output_tokens.old == Decimal(s1.total_output_tokens)
        assert diff.api_calls.old == Decimal(s1.total_api_calls)


class TestDiffCLI:
    def _sessions(self) -> list[Session]:
        return [
            _make_session(
                "simple_session.jsonl", "aaaaaaaa-1111-2222-3333-444444444444",
            ),
            _make_session(
                "multi_model_session.jsonl", "bbbbbbbb-1111-2222-3333-444444444444",
            ),
        ]

    def test_diff_command(self) -> None:
        runner = CliRunner()
        with patch("parsimony.cli._load_all_sessions", return_value=self._sessions()):
            result = runner.invoke(main, ["diff", "aaaaaaaa", "bbbbbbbb"])
        assert result.exit_code == 0
        assert "Comparison" in result.output

    def test_diff_json_export(self) -> None:
        runner = CliRunner()
        with patch("parsimony.cli._load_all_sessions", return_value=self._sessions()):
            result = runner.invoke(
                main, ["--export", "json", "diff", "aaaaaaaa", "bbbbbbbb"],
            )
        assert result.exit_code == 0
        assert "session1" in result.output
        assert "change_pct" in result.output

    def test_diff_not_found(self) -> None:
        runner = CliRunner()
        with patch("parsimony.cli._load_all_sessions", return_value=self._sessions()):
            result = runner.invoke(main, ["diff", "aaaaaaaa", "xxxxxxxx"])
        assert result.exit_code != 0

    def test_diff_same_session(self) -> None:
        runner = CliRunner()
        with patch("parsimony.cli._load_all_sessions", return_value=self._sessions()):
            result = runner.invoke(main, ["diff", "aaaaaaaa", "aaaaaaaa"])
        assert result.exit_code == 0
