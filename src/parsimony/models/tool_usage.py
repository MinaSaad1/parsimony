"""Tool usage parsing and aggregation utilities."""

from __future__ import annotations

from dataclasses import dataclass

_MCP_PREFIX = "mcp__"


@dataclass(frozen=True)
class ToolCall:
    """A parsed tool name with MCP server/tool decomposition."""

    name: str
    is_mcp: bool
    mcp_server: str | None
    mcp_tool: str | None


def parse_tool_name(name: str) -> ToolCall:
    """Parse a tool name, detecting MCP tools by their ``mcp__`` prefix.

    MCP tool names follow the pattern ``mcp__{server}__{tool}``, e.g.
    ``mcp__figma__get_design_context``.

    Args:
        name: Raw tool name from a JSONL tool_use block.

    Returns:
        A ToolCall with MCP fields populated if applicable.
    """
    if name.startswith(_MCP_PREFIX):
        remainder = name[len(_MCP_PREFIX):]
        parts = remainder.split("__", 1)
        if len(parts) == 2:
            return ToolCall(
                name=name,
                is_mcp=True,
                mcp_server=parts[0],
                mcp_tool=parts[1],
            )
    return ToolCall(name=name, is_mcp=False, mcp_server=None, mcp_tool=None)
