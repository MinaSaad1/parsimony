"""Display configuration for controlling output presentation."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DisplayConfig:
    """Controls what metrics are shown in output.

    By default, only token usage is displayed. Cost columns appear
    only when ``show_cost`` is True (via the ``--show-cost`` CLI flag).
    """

    show_cost: bool = False
