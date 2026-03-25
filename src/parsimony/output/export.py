"""JSON and CSV export for rollup data."""

from __future__ import annotations

import csv
import io
import json
from decimal import Decimal
from pathlib import Path
from typing import Any

from parsimony.aggregator.rollup import SessionRollup


class _DecimalEncoder(json.JSONEncoder):
    """JSON encoder that serializes Decimal as float strings."""

    def default(self, o: object) -> object:
        if isinstance(o, Decimal):
            return float(o)
        return super().default(o)


def _rollup_to_dict(rollup: SessionRollup) -> dict[str, Any]:
    """Convert a SessionRollup to a plain dict for serialization."""
    return {
        "session_count": rollup.session_count,
        "total_tokens": rollup.total_tokens,
        "total_cost": float(rollup.total_cost),
        "avg_cost_per_session": float(rollup.avg_cost_per_session),
        "cache_efficiency": rollup.cache_efficiency,
        "subagent_total_tokens": rollup.subagent_total_tokens,
        "subagent_total_cost": float(rollup.subagent_total_cost),
        "per_model": {
            model: {
                "input_tokens": mr.input_tokens,
                "output_tokens": mr.output_tokens,
                "cache_write_tokens": mr.cache_write_tokens,
                "cache_read_tokens": mr.cache_read_tokens,
                "total_tokens": mr.total_tokens,
                "cost": float(mr.cost),
                "call_count": mr.call_count,
            }
            for model, mr in rollup.per_model.items()
        },
        "per_tool": {
            name: {
                "call_count": tr.call_count,
                "is_mcp": tr.is_mcp,
                "mcp_server": tr.mcp_server,
            }
            for name, tr in rollup.per_tool.items()
        },
        "mcp_breakdown": rollup.mcp_breakdown,
    }


def export_json(rollup: SessionRollup, path: Path | None = None) -> str:
    """Export rollup data as JSON.

    Args:
        rollup: The rollup to export.
        path: Optional file path. If None, returns the JSON string.

    Returns:
        The JSON string.
    """
    data = _rollup_to_dict(rollup)
    output = json.dumps(data, indent=2, cls=_DecimalEncoder)
    if path:
        path.write_text(output, encoding="utf-8")
    return output


def export_csv(rollup: SessionRollup, path: Path | None = None) -> str:
    """Export per-model rollup data as CSV.

    Args:
        rollup: The rollup to export.
        path: Optional file path. If None, returns the CSV string.

    Returns:
        The CSV string.
    """
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow([
        "model",
        "input_tokens",
        "output_tokens",
        "cache_write_tokens",
        "cache_read_tokens",
        "total_tokens",
        "cost",
        "call_count",
    ])

    for model, mr in sorted(rollup.per_model.items()):
        writer.writerow([
            model,
            mr.input_tokens,
            mr.output_tokens,
            mr.cache_write_tokens,
            mr.cache_read_tokens,
            mr.total_tokens,
            float(mr.cost),
            mr.call_count,
        ])

    output = buf.getvalue()
    if path:
        path.write_text(output, encoding="utf-8")
    return output
