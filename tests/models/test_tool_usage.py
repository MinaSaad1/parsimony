"""Tests for parsimony.models.tool_usage."""

from __future__ import annotations

from parsimony.models.tool_usage import parse_tool_name


class TestParseToolName:
    def test_native_tool(self) -> None:
        result = parse_tool_name("Read")
        assert result.name == "Read"
        assert result.is_mcp is False
        assert result.mcp_server is None
        assert result.mcp_tool is None

    def test_mcp_figma_tool(self) -> None:
        result = parse_tool_name("mcp__figma__get_design_context")
        assert result.is_mcp is True
        assert result.mcp_server == "figma"
        assert result.mcp_tool == "get_design_context"

    def test_mcp_context7_tool(self) -> None:
        result = parse_tool_name("mcp__context7__query-docs")
        assert result.is_mcp is True
        assert result.mcp_server == "context7"
        assert result.mcp_tool == "query-docs"

    def test_mcp_no_tool_part(self) -> None:
        result = parse_tool_name("mcp__standalone")
        assert result.is_mcp is False  # No double-underscore after server
        assert result.mcp_server is None

    def test_empty_string(self) -> None:
        result = parse_tool_name("")
        assert result.is_mcp is False
        assert result.name == ""
