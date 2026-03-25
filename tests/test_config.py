"""Tests for parsimony.config."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

from parsimony.config import load_pricing


class TestLoadPricing:
    def test_loads_bundled_pricing(self) -> None:
        pricing = load_pricing()
        assert "claude-sonnet-4-6" in pricing
        assert "claude-opus-4-6" in pricing
        assert "claude-haiku-4-5-20251001" in pricing

    def test_sonnet_rates(self) -> None:
        pricing = load_pricing()
        sonnet = pricing["claude-sonnet-4-6"]
        assert sonnet.input_per_million == Decimal("3.00")
        assert sonnet.output_per_million == Decimal("15.00")

    def test_explicit_path(self, tmp_path: Path) -> None:
        yaml_content = """
models:
  test-model:
    input_per_million: 1.00
    output_per_million: 2.00
    cache_write_per_million: 0.50
    cache_read_per_million: 0.10
"""
        pricing_file = tmp_path / "pricing.yaml"
        pricing_file.write_text(yaml_content)

        pricing = load_pricing(pricing_file)
        assert "test-model" in pricing
        assert pricing["test-model"].input_per_million == Decimal("1.00")

    def test_missing_file_uses_defaults(self, tmp_path: Path) -> None:
        missing = tmp_path / "nonexistent.yaml"
        pricing = load_pricing(missing)
        # Should fall back to bundled or defaults
        assert len(pricing) > 0

    def test_empty_yaml_uses_defaults(self, tmp_path: Path) -> None:
        empty_file = tmp_path / "empty.yaml"
        empty_file.write_text("")
        pricing = load_pricing(empty_file)
        assert len(pricing) > 0
