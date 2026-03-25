"""Tests for parsimony.output.formatters."""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from parsimony.output.formatters import (
    format_cost,
    format_duration,
    format_model_name,
    format_percentage,
    format_tokens,
)


class TestFormatTokens:
    def test_small_number(self) -> None:
        assert format_tokens(0) == "0"
        assert format_tokens(999) == "999"

    def test_thousands_separator(self) -> None:
        assert format_tokens(1_234) == "1,234"
        assert format_tokens(9_999) == "9,999"

    def test_k_suffix(self) -> None:
        assert format_tokens(10_000) == "10.0K"
        assert format_tokens(150_000) == "150.0K"

    def test_m_suffix(self) -> None:
        assert format_tokens(1_000_000) == "1.0M"
        assert format_tokens(2_500_000) == "2.5M"


class TestFormatCost:
    def test_zero(self) -> None:
        assert format_cost(Decimal("0")) == "$0.00"

    def test_small_cost(self) -> None:
        assert format_cost(Decimal("0.0042")) == "$0.0042"
        assert format_cost(Decimal("0.001")) == "$0.0010"

    def test_normal_cost(self) -> None:
        assert format_cost(Decimal("1.23")) == "$1.23"
        assert format_cost(Decimal("0.50")) == "$0.50"

    def test_large_cost(self) -> None:
        assert format_cost(Decimal("123.45")) == "$123.45"


class TestFormatDuration:
    def test_none(self) -> None:
        assert format_duration(None) == "-"

    def test_seconds_only(self) -> None:
        assert format_duration(timedelta(seconds=30)) == "30s"

    def test_minutes(self) -> None:
        assert format_duration(timedelta(minutes=5)) == "5m"
        assert format_duration(timedelta(minutes=5, seconds=30)) == "5m 30s"

    def test_hours(self) -> None:
        assert format_duration(timedelta(hours=1, minutes=30)) == "1h 30m"
        assert format_duration(timedelta(hours=2)) == "2h 0m"


class TestFormatPercentage:
    def test_normal(self) -> None:
        assert format_percentage(87.3) == "87.3%"
        assert format_percentage(0.0) == "0.0%"
        assert format_percentage(100.0) == "100.0%"


class TestFormatModelName:
    def test_known_models(self) -> None:
        assert format_model_name("claude-opus-4-6") == "Opus 4.6"
        assert format_model_name("claude-sonnet-4-6") == "Sonnet 4.6"
        assert format_model_name("claude-haiku-4-5-20251001") == "Haiku 4.5"

    def test_generic_claude_model(self) -> None:
        result = format_model_name("claude-new-model-1-0")
        assert "claude" not in result.lower() or result != "claude-new-model-1-0"

    def test_unknown_model(self) -> None:
        assert format_model_name("gpt-4") == "gpt-4"
