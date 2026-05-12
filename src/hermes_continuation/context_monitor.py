"""Collect minimal, content-safe context signals for handoff watch."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .git_state import collect_git_state


def _optional_int(value: int | None) -> int | None:
    if value is None:
        return None
    return int(value)


def collect_context(
    repo_path: str | Path,
    tool_calls: int | None = None,
    elapsed_minutes: int | None = None,
) -> dict[str, Any]:
    """Collect safe watch context without reading conversation or file contents.

    The monitor intentionally limits itself to caller-supplied counters plus git
    metadata from ``collect_git_state()``. It does not inspect conversation
    content, source file contents, environment variables, or other private data.
    """

    try:
        git_state = collect_git_state(repo_path)
        changed_files = git_state.get("changed_files") or []
    except Exception:
        changed_files = []

    manual = tool_calls is not None or elapsed_minutes is not None
    return {
        "tool_calls": _optional_int(tool_calls),
        "elapsed_minutes": _optional_int(elapsed_minutes),
        "changed_files": list(changed_files),
        "source": "manual" if manual else "auto",
    }
