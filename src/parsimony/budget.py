"""Budget tracking and alerting for token spend."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger("parsimony.budget")


@dataclass(frozen=True)
class BudgetConfig:
    """Immutable cost thresholds (all optional, in USD)."""

    daily: Decimal | None = None
    weekly: Decimal | None = None
    monthly: Decimal | None = None

    @property
    def is_configured(self) -> bool:
        return self.daily is not None or self.weekly is not None or self.monthly is not None


@dataclass(frozen=True)
class BudgetStatus:
    """Result of checking spend against a budget threshold."""

    period: str
    spent: Decimal
    limit: Decimal
    over_budget: bool
    percentage: float


def check_budget(
    spent: Decimal,
    limit: Decimal,
    period: str,
) -> BudgetStatus:
    """Compare actual spend against a single budget threshold.

    Args:
        spent: Total cost for the period.
        limit: Budget threshold.
        period: Label for the period (e.g. "daily", "weekly", "monthly").

    Returns:
        A BudgetStatus indicating whether the budget is exceeded.
    """
    pct = float(spent / limit * 100) if limit > 0 else 0.0
    return BudgetStatus(
        period=period,
        spent=spent,
        limit=limit,
        over_budget=spent > limit,
        percentage=pct,
    )


def load_budget(path: Path | None = None) -> BudgetConfig:
    """Load budget configuration from ``~/.parsimony/config.yaml``.

    The file should contain a top-level ``budget`` key:

    .. code-block:: yaml

        budget:
          daily: 5.00
          weekly: 25.00
          monthly: 80.00

    Args:
        path: Explicit path to config file.  Defaults to
            ``~/.parsimony/config.yaml``.

    Returns:
        A BudgetConfig (all-None if file is missing or has no budget key).
    """
    if path is None:
        path = Path("~/.parsimony/config.yaml").expanduser()

    if not path.is_file():
        return BudgetConfig()

    try:
        with path.open(encoding="utf-8") as f:
            data: dict[str, Any] = yaml.safe_load(f) or {}
    except Exception:
        logger.warning("Failed to parse config file: %s", path)
        return BudgetConfig()

    budget_data = data.get("budget")
    if not isinstance(budget_data, dict):
        return BudgetConfig()

    return BudgetConfig(
        daily=_to_decimal(budget_data.get("daily")),
        weekly=_to_decimal(budget_data.get("weekly")),
        monthly=_to_decimal(budget_data.get("monthly")),
    )


def _to_decimal(value: Any) -> Decimal | None:
    """Convert a YAML value to Decimal, returning None on failure."""
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except Exception:
        return None


@dataclass(frozen=True)
class TokenBudgetConfig:
    session_limit: int | None = None
    weekly_limit: int | None = None

    @property
    def is_configured(self) -> bool:
        return self.session_limit is not None or self.weekly_limit is not None


@dataclass(frozen=True)
class TokenBudgetStatus:
    scope: str
    used: int
    limit: int

    @property
    def over_limit(self) -> bool:
        return self.used > self.limit

    @property
    def percentage(self) -> float:
        return (self.used / self.limit * 100) if self.limit > 0 else 0.0


def check_token_budget(used: int, limit: int, scope: str) -> TokenBudgetStatus:
    return TokenBudgetStatus(scope=scope, used=used, limit=limit)


def load_token_budget(
    config_path: Path | None = None,
) -> TokenBudgetConfig:
    if config_path is None:
        config_path = Path("~/.parsimony/config.yaml").expanduser()

    if not config_path.is_file():
        return TokenBudgetConfig()

    try:
        with config_path.open(encoding="utf-8") as f:
            data: dict[str, Any] = yaml.safe_load(f) or {}
    except Exception:
        logger.warning("Failed to parse config file: %s", config_path)
        return TokenBudgetConfig()

    tb = data.get("token_budget")
    if not isinstance(tb, dict):
        return TokenBudgetConfig()

    session_limit = _to_int(tb.get("session_limit"))
    weekly_limit = _to_int(tb.get("weekly_limit"))

    return TokenBudgetConfig(session_limit=session_limit, weekly_limit=weekly_limit)


def _to_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except Exception:
        return None
