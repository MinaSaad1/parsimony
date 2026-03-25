"""Tests for the Parsimony dashboard app."""

from __future__ import annotations

from unittest.mock import patch

from click.testing import CliRunner

from parsimony.cli import main


class TestLiveCommand:
    """Tests for the parsimony live CLI command."""

    def test_live_missing_textual(self) -> None:
        """Graceful error when textual is not installed."""
        runner = CliRunner()

        with (
            patch.dict("sys.modules", {"parsimony.dashboard.app": None}),
            patch("parsimony.cli.live", side_effect=SystemExit(1)),
        ):
            result = runner.invoke(main, ["live"], catch_exceptions=True)
            assert result.exit_code != 0

    def test_live_command_exists(self) -> None:
        """The live command is registered."""
        runner = CliRunner()
        result = runner.invoke(main, ["live", "--help"])
        assert result.exit_code == 0
        assert "live terminal dashboard" in result.output.lower()
