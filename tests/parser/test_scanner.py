"""Tests for parsimony.parser.scanner."""

from __future__ import annotations

import os
from pathlib import Path

from parsimony.parser.scanner import (
    decode_project_path,
    get_claude_base_path,
    scan_projects,
    scan_sessions,
    scan_subagents,
)


class TestGetClaudeBasePath:
    def test_returns_path(self) -> None:
        path = get_claude_base_path()
        assert isinstance(path, Path)
        assert path.name == ".claude"


class TestDecodeProjectPath:
    def test_windows_style(self) -> None:
        result = decode_project_path("e--Coding-Projects-Acumen")
        sep = os.sep
        drive = "E"
        if os.name == "nt":
            assert result == f"{drive}:{sep}Coding{sep}Projects{sep}Acumen"
        else:
            assert result == f"{drive}{sep}Coding{sep}Projects{sep}Acumen"

    def test_simple_path(self) -> None:
        result = decode_project_path("C--Users-pc")
        sep = os.sep
        if os.name == "nt":
            assert result == f"C:{sep}Users{sep}pc"
        else:
            assert result == f"C{sep}Users{sep}pc"

    def test_no_double_dash(self) -> None:
        result = decode_project_path("some-random-name")
        assert result == "some-random-name"

    def test_drive_letter_uppercased(self) -> None:
        result = decode_project_path("c--Users-pc")
        assert result.startswith("C")


class TestScanProjects:
    def test_discovers_project_dirs(self, tmp_path: Path) -> None:
        proj1 = tmp_path / "e--Project-One"
        proj2 = tmp_path / "C--Users-pc"
        proj1.mkdir()
        proj2.mkdir()
        # Add a file that should be skipped
        (tmp_path / "not-a-dir.txt").write_text("skip me")

        projects = list(scan_projects(tmp_path))
        names = {p.encoded_name for p in projects}
        assert "e--Project-One" in names
        assert "C--Users-pc" in names
        assert len(projects) == 2

    def test_missing_directory(self, tmp_path: Path) -> None:
        missing = tmp_path / "nonexistent"
        projects = list(scan_projects(missing))
        assert projects == []


class TestScanSessions:
    def test_discovers_session_files(self, tmp_path: Path) -> None:
        # Valid session file (UUID name)
        session_file = tmp_path / "aaaaaaaa-1111-2222-3333-444444444444.jsonl"
        session_file.write_text('{"type":"test"}')

        # Invalid filename (not a UUID)
        bad_file = tmp_path / "not-a-uuid.jsonl"
        bad_file.write_text('{"type":"test"}')

        # Subdirectory should be skipped
        (tmp_path / "subdir").mkdir()

        sessions = list(scan_sessions(tmp_path))
        assert len(sessions) == 1
        assert sessions[0].session_id == "aaaaaaaa-1111-2222-3333-444444444444"
        assert sessions[0].file_size > 0

    def test_missing_directory(self, tmp_path: Path) -> None:
        missing = tmp_path / "nonexistent"
        sessions = list(scan_sessions(missing))
        assert sessions == []


class TestScanSubagents:
    def test_discovers_subagent_files(self, tmp_path: Path) -> None:
        session_id = "aaaaaaaa-1111-2222-3333-444444444444"
        subagents_dir = tmp_path / session_id / "subagents"
        subagents_dir.mkdir(parents=True)

        agent_file = subagents_dir / "agent-abc123def.jsonl"
        agent_file.write_text('{"type":"test"}')

        agent_file2 = subagents_dir / "agent-xyz789.jsonl"
        agent_file2.write_text('{"type":"test"}')

        subagents = list(scan_subagents(tmp_path, session_id))
        assert len(subagents) == 2
        ids = {s.agent_id for s in subagents}
        assert "abc123def" in ids
        assert "xyz789" in ids
        for s in subagents:
            assert s.parent_session_id == session_id

    def test_missing_subagents_dir(self, tmp_path: Path) -> None:
        subagents = list(scan_subagents(tmp_path, "nonexistent"))
        assert subagents == []
