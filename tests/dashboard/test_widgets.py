"""Tests for the dashboard widgets module."""

from __future__ import annotations

from parsimony.dashboard.widgets import _bar


class TestBar:
    """Tests for the _bar helper function."""

    def test_zero_value(self) -> None:
        assert _bar(0, 100) == ""

    def test_zero_max(self) -> None:
        assert _bar(50, 0) == ""

    def test_full_bar(self) -> None:
        result = _bar(100, 100, width=10)
        assert "█" in result
        assert len(result.replace("█", "")) <= 1  # at most one partial char

    def test_half_bar(self) -> None:
        result = _bar(50, 100, width=10)
        # Should have roughly 5 full blocks
        full_count = result.count("█")
        assert 4 <= full_count <= 6

    def test_negative_value(self) -> None:
        assert _bar(-10, 100) == ""

    def test_value_exceeds_max(self) -> None:
        result = _bar(200, 100, width=10)
        # Capped at 1.0 ratio
        assert "█" in result
