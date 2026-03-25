"""Filesystem scanner that discovers Claude Code session files.

Claude Code stores sessions at:
  ~/.claude/projects/{encoded-project-path}/{session-id}.jsonl
  ~/.claude/projects/{encoded-project-path}/{session-id}/subagents/agent-{id}.jsonl

Encoded project paths use a deterministic scheme:
  E:\\Coding Projects\\Acumen  ->  e--Coding-Projects-Acumen
  C:\\Users\\pc               ->  C--Users-pc

The first ``--`` separates the drive letter from the rest of the path.
Every ``-`` in the remainder represents an OS path separator.  Spaces in
folder names are also encoded as ``-``, so perfect reconstruction of the
original path is not possible; the encoded name is the canonical key.
"""

from __future__ import annotations

import os
import uuid
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ProjectInfo:
    """Metadata for a single Claude Code project directory."""

    encoded_name: str
    decoded_path: str
    directory: Path


@dataclass(frozen=True)
class SessionFileInfo:
    """Metadata for a top-level session JSONL file."""

    session_id: str
    file_path: Path
    file_size: int
    modified_time: float


@dataclass(frozen=True)
class SubagentFileInfo:
    """Metadata for a subagent JSONL file nested inside a session directory."""

    agent_id: str
    file_path: Path
    parent_session_id: str


# ---------------------------------------------------------------------------
# Path helpers
# ---------------------------------------------------------------------------


def get_claude_base_path() -> Path:
    """Return the path to the ``~/.claude`` directory.

    Expands the user home directory and works on both Windows and Unix.

    Returns:
        Absolute Path pointing to ``~/.claude``.
    """
    return Path("~/.claude").expanduser()


def decode_project_path(encoded: str) -> str:
    """Convert an encoded project directory name back to a human-readable path.

    The encoding scheme:
    - The drive letter precedes ``--``, which replaces ``<drive>:\\``.
    - Each ``-`` in the remainder replaces an OS path separator.
    - Spaces and hyphens in the original path are both encoded as ``-``,
      so the decoded path uses the OS separator in place of every ``-``.

    Args:
        encoded: Encoded directory name, e.g. ``e--Coding-Projects-Acumen``.

    Returns:
        A human-readable path string, e.g. ``E:\\Coding Projects\\Acumen``
        on Windows or ``E/Coding Projects/Acumen`` on Unix.
    """
    if "--" not in encoded:
        return encoded

    drive, rest = encoded.split("--", 1)
    drive_upper = drive.upper()
    sep = os.sep

    decoded_rest = rest.replace("-", sep)

    if os.name == "nt":
        return f"{drive_upper}:{sep}{decoded_rest}"
    else:
        return f"{drive_upper}{sep}{decoded_rest}"


# ---------------------------------------------------------------------------
# Scanning functions
# ---------------------------------------------------------------------------


def scan_projects(base_path: Path) -> Iterator[ProjectInfo]:
    """Yield a ProjectInfo for every project directory under *base_path*.

    Non-directory entries inside *base_path* are silently skipped.  If
    *base_path* does not exist the function returns without yielding anything.

    Args:
        base_path: Path to ``~/.claude/projects/``.

    Yields:
        ProjectInfo for each discovered project directory.
    """
    if not base_path.is_dir():
        return

    for entry in base_path.iterdir():
        if entry.is_dir():
            yield ProjectInfo(
                encoded_name=entry.name,
                decoded_path=decode_project_path(entry.name),
                directory=entry,
            )


def _is_valid_uuid(value: str) -> bool:
    """Return True if *value* is a valid UUID string."""
    try:
        uuid.UUID(value)
        return True
    except ValueError:
        return False


def scan_sessions(project_dir: Path) -> Iterator[SessionFileInfo]:
    """Yield a SessionFileInfo for each valid session file in *project_dir*.

    Only ``*.jsonl`` files whose stem is a valid UUID are returned.  Files in
    subdirectories are ignored.  If *project_dir* does not exist the function
    returns without yielding anything.

    Args:
        project_dir: Path to a specific project directory.

    Yields:
        SessionFileInfo for each discovered session file.
    """
    if not project_dir.is_dir():
        return

    for entry in project_dir.iterdir():
        if not entry.is_file():
            continue
        if entry.suffix != ".jsonl":
            continue
        session_id = entry.stem
        if not _is_valid_uuid(session_id):
            continue
        stat = entry.stat()
        yield SessionFileInfo(
            session_id=session_id,
            file_path=entry,
            file_size=stat.st_size,
            modified_time=stat.st_mtime,
        )


def scan_subagents(
    project_dir: Path, session_id: str
) -> Iterator[SubagentFileInfo]:
    """Yield a SubagentFileInfo for each subagent file belonging to *session_id*.

    Looks for files matching ``agent-*.jsonl`` inside::

        {project_dir}/{session_id}/subagents/

    If the subagents directory does not exist the function returns without
    yielding anything.

    Args:
        project_dir: Path to a specific project directory.
        session_id: UUID string identifying the parent session.

    Yields:
        SubagentFileInfo for each discovered subagent file.
    """
    subagents_dir = project_dir / session_id / "subagents"
    if not subagents_dir.is_dir():
        return

    for entry in subagents_dir.glob("agent-*.jsonl"):
        if not entry.is_file():
            continue
        # Strip "agent-" prefix and ".jsonl" suffix to get the agent ID.
        agent_id = entry.stem[len("agent-"):]
        yield SubagentFileInfo(
            agent_id=agent_id,
            file_path=entry,
            parent_session_id=session_id,
        )
