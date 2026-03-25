"""Tests for parsimony.parser.session_builder."""

from __future__ import annotations

from pathlib import Path

from parsimony.parser.reader import read_events
from parsimony.parser.session_builder import build_session

FIXTURES = Path(__file__).parent.parent / "fixtures"


class TestBuildSessionSimple:
    def test_simple_session(self) -> None:
        events = list(read_events(FIXTURES / "simple_session.jsonl"))
        session = build_session("aaaaaaaa-1111-2222-3333-444444444444", events)

        assert session.session_id == "aaaaaaaa-1111-2222-3333-444444444444"
        assert session.cwd == "c:\\Users\\pc\\Desktop\\myproject"
        assert session.version == "2.1.59"
        assert session.git_branch == "main"
        assert session.start_time is not None
        assert session.end_time is not None

    def test_request_id_dedup(self) -> None:
        """Two assistant entries with same requestId should produce one API call."""
        events = list(read_events(FIXTURES / "simple_session.jsonl"))
        session = build_session("aaaaaaaa-1111-2222-3333-444444444444", events)

        # req_001 has 2 chunks (thinking + tool_use), req_002 has 1 chunk
        assert session.total_api_calls == 2

    def test_streaming_takes_last_usage(self) -> None:
        """Final streaming chunk carries cumulative usage."""
        events = list(read_events(FIXTURES / "simple_session.jsonl"))
        session = build_session("aaaaaaaa-1111-2222-3333-444444444444", events)

        # req_001's final chunk has output_tokens=50 (not 10 from first chunk)
        first_call = session.segments[0].calls[0]
        assert first_call.usage.output_tokens == 50

    def test_tool_uses_merged_across_chunks(self) -> None:
        events = list(read_events(FIXTURES / "simple_session.jsonl"))
        session = build_session("aaaaaaaa-1111-2222-3333-444444444444", events)

        # req_001 should have the Read tool from the second chunk
        first_call = session.segments[0].calls[0]
        tool_names = [t.tool_name for t in first_call.tool_uses]
        assert "Read" in tool_names

    def test_single_model_segment(self) -> None:
        events = list(read_events(FIXTURES / "simple_session.jsonl"))
        session = build_session("aaaaaaaa-1111-2222-3333-444444444444", events)

        assert len(session.segments) == 1
        assert session.segments[0].model == "claude-sonnet-4-6"
        assert session.models_used == frozenset({"claude-sonnet-4-6"})


class TestBuildSessionMultiModel:
    def test_model_segments(self) -> None:
        events = list(read_events(FIXTURES / "multi_model_session.jsonl"))
        session = build_session("bbbbbbbb-1111-2222-3333-444444444444", events)

        assert len(session.segments) == 3
        assert session.segments[0].model == "claude-sonnet-4-6"
        assert session.segments[1].model == "claude-opus-4-6"
        assert session.segments[2].model == "claude-haiku-4-5-20251001"

    def test_models_used(self) -> None:
        events = list(read_events(FIXTURES / "multi_model_session.jsonl"))
        session = build_session("bbbbbbbb-1111-2222-3333-444444444444", events)

        assert session.models_used == frozenset({
            "claude-sonnet-4-6",
            "claude-opus-4-6",
            "claude-haiku-4-5-20251001",
        })

    def test_segment_call_counts(self) -> None:
        events = list(read_events(FIXTURES / "multi_model_session.jsonl"))
        session = build_session("bbbbbbbb-1111-2222-3333-444444444444", events)

        assert session.segments[0].call_count == 1  # sonnet: 1 call
        assert session.segments[1].call_count == 2  # opus: 2 calls
        assert session.segments[2].call_count == 1  # haiku: 1 call

    def test_opus_segment_tokens(self) -> None:
        events = list(read_events(FIXTURES / "multi_model_session.jsonl"))
        session = build_session("bbbbbbbb-1111-2222-3333-444444444444", events)

        opus_seg = session.segments[1]
        assert opus_seg.total_input_tokens == 700  # 300 + 400
        assert opus_seg.total_output_tokens == 250  # 150 + 100


class TestBuildSessionSubagent:
    def test_subagent_results(self) -> None:
        events = list(read_events(FIXTURES / "subagent_session.jsonl"))
        session = build_session("cccccccc-1111-2222-3333-444444444444", events)

        assert len(session.subagent_results) == 1
        sub = session.subagent_results[0]
        assert sub.agent_id == "agent-abc123"
        assert sub.total_tokens == 42000
        assert sub.total_tool_use_count == 25
        assert sub.total_duration_ms == 58000
        assert sub.usage.output_tokens == 5000


class TestBuildSessionMCP:
    def test_mcp_tool_names_extracted(self) -> None:
        events = list(read_events(FIXTURES / "mcp_session.jsonl"))
        session = build_session("dddddddd-1111-2222-3333-444444444444", events)

        all_tool_names: list[str] = []
        for seg in session.segments:
            for call in seg.calls:
                all_tool_names.extend(t.tool_name for t in call.tool_uses)

        assert "mcp__figma__get_design_context" in all_tool_names
        assert "mcp__figma__get_screenshot" in all_tool_names
        assert "mcp__context7__query-docs" in all_tool_names


class TestBuildSessionMalformed:
    def test_malformed_skipped_gracefully(self) -> None:
        events = list(read_events(FIXTURES / "malformed_session.jsonl"))
        session = build_session("eeeeeeee-1111-2222-3333-444444444444", events)

        # Should still build a valid session from the surviving events
        assert session.session_id == "eeeeeeee-1111-2222-3333-444444444444"
        assert session.total_api_calls == 1  # Only one valid assistant event


class TestBuildSessionEmpty:
    def test_empty_events(self) -> None:
        session = build_session("empty-session", [])
        assert session.segments == ()
        assert session.subagent_results == ()
        assert session.start_time is None
        assert session.end_time is None
        assert session.total_api_calls == 0
