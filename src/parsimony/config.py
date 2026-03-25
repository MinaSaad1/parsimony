"""Configuration and path helpers for Parsimony.

Handles loading pricing tables from YAML files with fallback to bundled
defaults, and provides cross-platform path resolution.
"""

from __future__ import annotations

import logging
from decimal import Decimal
from pathlib import Path
from typing import Any

import yaml

from parsimony.models.cost import DEFAULT_PRICING, ModelPricing

logger = logging.getLogger("parsimony.config")


def get_claude_dir() -> Path:
    """Return the path to ``~/.claude``."""
    return Path("~/.claude").expanduser()


def get_parsimony_dir() -> Path:
    """Return the path to ``~/.parsimony``, creating it if needed."""
    path = Path("~/.parsimony").expanduser()
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_cache_path() -> Path:
    """Return the path to the SQLite cache database."""
    return get_parsimony_dir() / "cache.db"


def _bundled_pricing_path() -> Path:
    """Return the path to the bundled pricing.yaml shipped with the package."""
    return Path(__file__).parent.parent.parent / "pricing.yaml"


def load_pricing(path: Path | None = None) -> dict[str, ModelPricing]:
    """Load model pricing from a YAML file.

    Checks these locations in order:
    1. Explicit ``path`` argument (if provided)
    2. ``~/.parsimony/pricing.yaml`` (user override)
    3. Bundled ``pricing.yaml`` in the package

    Falls back to hardcoded defaults if no YAML file is found or parsing fails.

    Args:
        path: Optional explicit path to a pricing YAML file.

    Returns:
        A mapping of model name to ModelPricing.
    """
    candidates = []
    if path:
        candidates.append(path)
    candidates.append(get_parsimony_dir() / "pricing.yaml")
    candidates.append(_bundled_pricing_path())

    for candidate in candidates:
        if candidate.is_file():
            try:
                return _parse_pricing_yaml(candidate)
            except Exception:
                logger.warning("Failed to parse pricing file: %s", candidate)
                continue

    logger.info("No pricing file found, using built-in defaults")
    return dict(DEFAULT_PRICING)


def _parse_pricing_yaml(path: Path) -> dict[str, ModelPricing]:
    """Parse a pricing YAML file into a ModelPricing mapping."""
    with path.open(encoding="utf-8") as f:
        data: dict[str, Any] = yaml.safe_load(f) or {}

    models_data: dict[str, Any] = data.get("models", {})
    result: dict[str, ModelPricing] = {}

    for model_name, rates in models_data.items():
        if not isinstance(rates, dict):
            continue
        result[model_name] = ModelPricing(
            input_per_million=Decimal(str(rates.get("input_per_million", "0"))),
            output_per_million=Decimal(str(rates.get("output_per_million", "0"))),
            cache_write_per_million=Decimal(str(rates.get("cache_write_per_million", "0"))),
            cache_read_per_million=Decimal(str(rates.get("cache_read_per_million", "0"))),
        )

    if not result:
        logger.warning("Pricing file %s had no valid models, using defaults", path)
        return dict(DEFAULT_PRICING)

    return result
