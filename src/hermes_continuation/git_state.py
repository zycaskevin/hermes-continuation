"""Collect minimal git repository state for handoff packets."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any


def _run_git(repo: Path, args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=repo,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=10,
        check=False,
    )


def _parse_changed_files(status_short: str) -> list[dict[str, str]]:
    changed: list[dict[str, str]] = []
    for line in status_short.splitlines():
        if not line.strip():
            continue
        status = line[:2].strip() or line[:2]
        path = line[3:] if len(line) > 3 else ""
        changed.append({"path": path.strip(), "status": status})
    return changed


def collect_git_state(repo_path: str | Path) -> dict[str, Any]:
    repo = Path(repo_path).expanduser().resolve()
    base = {
        "path": str(repo),
        "git_available": False,
        "branch": None,
        "head": None,
        "status_short": "",
        "changed_files": [],
    }

    if not repo.exists() or not repo.is_dir():
        return base

    inside = _run_git(repo, ["rev-parse", "--is-inside-work-tree"])
    if inside.returncode != 0 or inside.stdout.strip() != "true":
        return base

    branch = _run_git(repo, ["branch", "--show-current"])
    head = _run_git(repo, ["rev-parse", "--short", "HEAD"])
    status = _run_git(repo, ["status", "--short"])

    status_short = status.stdout if status.returncode == 0 else ""
    return {
        "path": str(repo),
        "git_available": True,
        "branch": branch.stdout.strip() or None,
        "head": head.stdout.strip() or None,
        "status_short": status_short.rstrip(),
        "changed_files": _parse_changed_files(status_short),
    }
