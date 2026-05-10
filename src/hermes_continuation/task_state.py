"""Collect conservative task-state hints from repo-local documentation."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Iterable

from .redaction import assert_no_private_key

FIELD_KEYS = ("completed_work", "in_progress", "known_blockers", "do_not_touch")
EMPTY_TASK_STATE: dict[str, Any] = {
    "completed_work": [],
    "in_progress": [],
    "known_blockers": [],
    "do_not_touch": [],
    "next_recommended_task": "",
}

_MAX_FILES = 12
_MAX_FILE_BYTES = 64_000
_MAX_ITEMS_PER_FIELD = 5
_MAX_ITEM_CHARS = 240

_IGNORED_PARTS = {
    ".git",
    ".hermes",
    "graphify-out",
    "_knowledge_base",
    ".pytest_cache",
    "__pycache__",
}
_HEADING_RE = re.compile(r"^\s{0,3}(#{1,6})\s+(.+?)\s*$")
_BULLET_RE = re.compile(r"^\s*(?:[-*+]\s+|\d+[.)]\s+)(.+?)\s*$")
_CHECKBOX_RE = re.compile(r"^\[[ xX]\]\s+")

_COMPLETED_HEADINGS = frozenset({"completed", "completed work", "done"})
_IN_PROGRESS_HEADINGS = frozenset({"in progress", "active task", "active work", "current goal"})
_BLOCKER_HEADINGS = frozenset({"blocked", "blockers", "known blockers", "known issues", "known issues risks"})
_DO_NOT_TOUCH_HEADINGS = frozenset({"do not touch", "do not modify", "boundaries", "safety boundaries", "out of scope"})
_NEXT_HEADINGS = frozenset({"next", "next step", "next recommended task", "recommended next task", "remaining work"})
_STRICT_DOC_HEADINGS = {
    "completed work": "completed_work",
    "in progress": "in_progress",
    "active task": "in_progress",
    "known blockers": "known_blockers",
    "blockers": "known_blockers",
    "do not touch": "do_not_touch",
    "next recommended task": "next_recommended_task",
    "recommended next task": "next_recommended_task",
}
_RELEVANT_CHANGED_ROOTS = {"src", "tests", "docs"}
_RELEVANT_CHANGED_NAMES = {
    "README.md",
    "PROGRESS.md",
    "CHANGELOG.md",
    "pyproject.toml",
    "setup.cfg",
    "setup.py",
    "requirements.txt",
}
_RELEVANT_CHANGED_SUFFIXES = {
    ".c",
    ".cfg",
    ".cpp",
    ".css",
    ".go",
    ".h",
    ".html",
    ".ini",
    ".java",
    ".js",
    ".json",
    ".jsx",
    ".md",
    ".py",
    ".pyi",
    ".rs",
    ".rst",
    ".sh",
    ".toml",
    ".ts",
    ".tsx",
    ".txt",
    ".yaml",
    ".yml",
}


def _empty_state() -> dict[str, Any]:
    return {
        "completed_work": [],
        "in_progress": [],
        "known_blockers": [],
        "do_not_touch": [],
        "next_recommended_task": "",
    }


def _normalize_heading(text: str) -> str:
    text = re.sub(r"[`*_\[\]():]", " ", text.lower())
    text = text.replace("-", " ")
    return re.sub(r"\s+", " ", text).strip()


def _heading_field(heading: str, *, progress_doc: bool) -> str | None:
    normalized = _normalize_heading(heading)
    if not progress_doc:
        return _STRICT_DOC_HEADINGS.get(normalized)
    if normalized in _DO_NOT_TOUCH_HEADINGS:
        return "do_not_touch"
    if normalized in _BLOCKER_HEADINGS:
        return "known_blockers"
    if normalized in _NEXT_HEADINGS:
        return "next_recommended_task"
    if normalized in _IN_PROGRESS_HEADINGS:
        return "in_progress"
    if normalized in _COMPLETED_HEADINGS:
        return "completed_work"
    return None


def _clean_item(text: str) -> str:
    item = _CHECKBOX_RE.sub("", text.strip())
    item = re.sub(r"\s+", " ", item).strip()
    if len(item) > _MAX_ITEM_CHARS:
        item = item[: _MAX_ITEM_CHARS - 1].rstrip() + "…"
    return item


def _append_unique(items: list[str], value: str, *, cap: int = _MAX_ITEMS_PER_FIELD) -> None:
    cleaned = _clean_item(value)
    if not cleaned:
        return
    seen = {item.casefold() for item in items}
    if cleaned.casefold() in seen or len(items) >= cap:
        return
    items.append(cleaned)


def _dedupe(values: Iterable[str]) -> list[str]:
    result: list[str] = []
    for value in values:
        _append_unique(result, str(value), cap=10_000)
    return result


def _safe_markdown_files(repo: Path) -> list[Path]:
    candidates: list[Path] = []
    for relative in ("PROGRESS.md", "README.md"):
        path = repo / relative
        if path.is_file():
            candidates.append(path)

    docs_dir = repo / "docs"
    if docs_dir.is_dir():
        candidates.extend(sorted(path for path in docs_dir.glob("*.md") if path.is_file()))

    safe: list[Path] = []
    repo_resolved = repo.resolve()
    for path in candidates:
        if len(safe) >= _MAX_FILES:
            break
        try:
            resolved = path.resolve()
            resolved.relative_to(repo_resolved)
        except (OSError, ValueError):
            continue
        if any(part in _IGNORED_PARTS or part.endswith(".egg-info") for part in resolved.parts):
            continue
        safe.append(resolved)
    return safe


def _read_limited(path: Path) -> str:
    try:
        raw = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""
    if not raw:
        return ""
    assert_no_private_key(raw)
    return raw[:_MAX_FILE_BYTES]


def _changed_path_parts(path: str) -> tuple[str, ...]:
    normalized = path.replace("\\", "/").strip()
    if not normalized or normalized.startswith("/"):
        return ()
    parts = tuple(part for part in normalized.split("/") if part and part != ".")
    if not parts or any(part == ".." for part in parts):
        return ()
    return parts


def _is_ignored_changed_path(path: str) -> bool:
    parts = _changed_path_parts(path)
    return not parts or any(part in _IGNORED_PARTS or part.endswith(".egg-info") for part in parts)


def _is_relevant_changed_path(path: str) -> bool:
    if _is_ignored_changed_path(path):
        return False
    parts = _changed_path_parts(path)
    name = parts[-1]
    suffix = Path(name).suffix.lower()
    if name in _RELEVANT_CHANGED_NAMES:
        return True
    if parts[0] in _RELEVANT_CHANGED_ROOTS and suffix in _RELEVANT_CHANGED_SUFFIXES:
        return True
    return len(parts) == 1 and suffix in {".md", ".py", ".toml", ".yaml", ".yml"}


def _collect_from_markdown(text: str, state: dict[str, Any], *, progress_doc: bool) -> None:
    active_field: str | None = None
    in_fenced_block = False

    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("```") or stripped.startswith("~~~"):
            in_fenced_block = not in_fenced_block
            continue
        if in_fenced_block:
            continue

        heading = _HEADING_RE.match(line)
        if heading:
            active_field = _heading_field(heading.group(2), progress_doc=progress_doc)
            continue

        if not active_field:
            continue

        bullet = _BULLET_RE.match(line)
        if not bullet:
            continue

        item = bullet.group(1)
        if active_field == "next_recommended_task":
            if not state["next_recommended_task"]:
                state["next_recommended_task"] = _clean_item(item)
            continue

        _append_unique(state[active_field], item)


def _add_changed_file_hints(state: dict[str, Any], repo_state: dict[str, Any] | None) -> None:
    has_doc_evidence = any(state[key] for key in FIELD_KEYS) or bool(state["next_recommended_task"])
    if not repo_state or not has_doc_evidence:
        return
    changed_files = repo_state.get("changed_files")
    if not isinstance(changed_files, list) or not changed_files:
        return

    paths: list[str] = []
    for item in changed_files:
        if len(paths) >= 5:
            break
        if not isinstance(item, dict):
            continue
        path = str(item.get("path") or "").strip()
        status = str(item.get("status") or "").strip()
        if path and _is_relevant_changed_path(path):
            paths.append(f"{status}: {path}" if status else path)
    if paths:
        _append_unique(state["in_progress"], "Repo has uncommitted changes: " + ", ".join(paths))


def collect_task_state(repo_path: Path, repo_state: dict[str, Any] | None = None) -> dict[str, Any]:
    """Return task-state hints from safe repo-local Markdown docs.

    The collector is deliberately conservative: it only scans PROGRESS.md,
    README.md, and direct docs/*.md files; it skips generated/runtime
    directories; and it returns empty fields when no heading/bullet evidence is
    found. Raw Markdown is scanned for private-key blocks before any
    extraction/truncation so collection fails closed on high-risk material.
    """

    repo = Path(repo_path).expanduser().resolve()
    state = _empty_state()
    if not repo.exists() or not repo.is_dir():
        return state

    for path in _safe_markdown_files(repo):
        _collect_from_markdown(_read_limited(path), state, progress_doc=path.name == "PROGRESS.md")

    _add_changed_file_hints(state, repo_state)
    return state


def merge_task_state(
    auto_state: dict[str, Any] | None,
    *,
    completed_work: Iterable[str] | None = None,
    in_progress: str = "",
    known_blockers: Iterable[str] | None = None,
    do_not_touch: Iterable[str] | None = None,
    next_task: str = "",
) -> dict[str, Any]:
    """Merge auto-collected hints with manual task-state arguments.

    List fields preserve auto hints first, then manual values, with
    case-insensitive de-duplication. The scalar in_progress field preserves all
    distinct auto/manual values separated by newlines. A manual next_task wins;
    auto next is only a fallback for callers that permit it.
    """

    auto = auto_state or EMPTY_TASK_STATE
    auto_in_progress = auto.get("in_progress") or []
    if isinstance(auto_in_progress, str):
        auto_in_progress_values = [auto_in_progress]
    else:
        auto_in_progress_values = [str(item) for item in auto_in_progress]

    in_progress_values = _dedupe([*auto_in_progress_values, in_progress])
    manual_next = str(next_task or "").strip()
    auto_next = str(auto.get("next_recommended_task") or "").strip()

    return {
        "completed_work": _dedupe([*(auto.get("completed_work") or []), *(completed_work or [])]),
        "in_progress": "\n".join(in_progress_values),
        "known_blockers": _dedupe([*(auto.get("known_blockers") or []), *(known_blockers or [])]),
        "do_not_touch": _dedupe([*(auto.get("do_not_touch") or []), *(do_not_touch or [])]),
        "next_recommended_task": manual_next or auto_next,
    }
