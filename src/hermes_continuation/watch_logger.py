"""Content-safe watch event logger (JSONL, zero LLM-token cost).

Every watch evaluation writes one line of structured metadata. The logger
intentionally omits conversation content, file contents, repo paths, and any
other potentially sensitive data. It is a local-only append and is never
exposed to LLM context or cloud storage.
"""

from __future__ import annotations

import datetime
import json
import os
from pathlib import Path
from typing import Any

_DEFAULT_LOG_DIR = Path.home() / ".hermes" / "logs"
_DEFAULT_LOG_FILE = "handoff_watch.jsonl"
_ENV_LOG_DIR = "HERMES_WATCH_LOG_DIR"

_MAX_FIELD_LENGTH = 200  # safety cap on any single field value


def _log_path() -> Path:
    directory = Path(os.environ.get(_ENV_LOG_DIR) or _DEFAULT_LOG_DIR)
    directory.mkdir(parents=True, exist_ok=True)
    return directory / _DEFAULT_LOG_FILE


def _sanitize_string(value: Any) -> str:
    """Clamp any string field to a safe length."""
    text = str(value).strip()
    if len(text) > _MAX_FIELD_LENGTH:
        return text[:_MAX_FIELD_LENGTH] + "…"
    return text


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _safe_list_len(value: Any) -> int:
    if isinstance(value, list):
        return len(value)
    if isinstance(value, int):
        return max(0, value)
    return 0


def log_watch_event(
    *,
    level: str = "observe",
    tool_calls: int | None = None,
    elapsed_minutes: int | None = None,
    changed_files: int | list | None = None,
    trigger: str = "gateway",
    recommendation_level: str | None = None,
    cooldown_active: bool = False,
) -> None:
    """Append one watch event to the local JSONL log.

    All fields are sanitised before writing: strings are capped, ints are
    clamped, and no file content or repo path is ever recorded.
    """

    line: dict[str, Any] = {
        "ts": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "level": _sanitize_string(level),
        "tool_calls": _safe_int(tool_calls),
        "elapsed": _safe_int(elapsed_minutes),
        "changed_files": _safe_int(changed_files)
        if isinstance(changed_files, (int, type(None)))
        else _safe_list_len(changed_files),
        "trigger": _sanitize_string(trigger),
    }

    if recommendation_level:
        line["recommendation_level"] = _sanitize_string(recommendation_level)
    if cooldown_active:
        line["cooldown_active"] = True

    record = json.dumps(line, ensure_ascii=False, separators=(",", ":"))
    path = _log_path()
    with path.open("a", encoding="utf-8") as handle:
        handle.write(record + "\n")


def read_watch_log(*, limit: int | None = None) -> list[dict[str, Any]]:
    """Read the log file back as a list of parsed event dicts.

    Returns an empty list when the file does not exist or is unreadable.
    """
    path = _log_path()
    if not path.exists() or not path.is_file():
        return []

    entries: list[dict[str, Any]] = []
    try:
        with path.open("r", encoding="utf-8") as handle:
            for line_num, raw in enumerate(handle, start=1):
                if limit is not None and len(entries) >= limit:
                    break
                stripped = raw.strip()
                if not stripped:
                    continue
                try:
                    entries.append(json.loads(stripped))
                except json.JSONDecodeError:
                    entries.append(
                        {
                            "ts": "parse-error",
                            "line": line_num,
                            "raw": stripped[:_MAX_FIELD_LENGTH],
                        }
                    )
    except OSError:
        return []
    return entries
