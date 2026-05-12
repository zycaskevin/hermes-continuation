"""Gateway auto-trigger helpers for handoff watch notifications.

This module is intentionally small and side-effect-light: Gateway wrappers can call
``should_notify`` after a watch evaluation, then render ``format_notification`` if
it returns true. The notification text is count-only and never includes repository
names, file names, paths, or other potentially sensitive state.
"""

from __future__ import annotations

import json
import os
import time
import tomllib
from pathlib import Path
from typing import Any

DEFAULT_AUTO_WATCH_CONFIG: dict[str, Any] = {
    "enabled": True,
    "tool_calls": 5,
    "elapsed": 30,
    "cooldown": 20,
    "notify_levels": ["advise", "prepare", "block"],
}

_CONFIG_ENV_VAR = "HERMES_CONTINUATION_AUTO_WATCH_CONFIG"
_DEFAULT_CONFIG_PATH = Path.home() / ".config" / "hermes-continuation" / "auto_watch.json"


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _first_value(mapping: dict[str, Any], *keys: str, default: Any = None) -> Any:
    for key in keys:
        if key in mapping:
            return mapping[key]
    return default


def _as_bool(value: Any, *, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "on"}:
            return True
        if normalized in {"0", "false", "no", "off"}:
            return False
    return bool(value)


def _as_nonnegative_int(value: Any, *, default: int = 0) -> int:
    if value is None:
        return default
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return default


def _as_notify_levels(value: Any) -> list[str]:
    if isinstance(value, str):
        raw_levels = value.split(",")
    elif isinstance(value, (list, tuple, set)):
        raw_levels = value
    else:
        raw_levels = DEFAULT_AUTO_WATCH_CONFIG["notify_levels"]
    return [str(level).strip().lower() for level in raw_levels if str(level).strip()]


def _auto_watch_section(config: dict[str, Any] | None) -> dict[str, Any]:
    root = _as_dict(config)
    section = _as_dict(root.get("auto_watch"))
    if not section:
        return dict(root)
    merged = dict(root)
    merged.update(section)
    merged.pop("auto_watch", None)
    return merged


def _thresholds_section(config: dict[str, Any]) -> dict[str, Any]:
    thresholds = _as_dict(config.get("thresholds"))
    merged = dict(thresholds)
    merged.update(config)
    return merged


def _normalize_config(config: dict[str, Any] | None) -> dict[str, Any]:
    supplied = _thresholds_section(_auto_watch_section(config))
    return {
        "enabled": _as_bool(supplied.get("enabled"), default=True),
        "tool_calls": _as_nonnegative_int(
            _first_value(supplied, "tool_calls", "tool_call_threshold", default=DEFAULT_AUTO_WATCH_CONFIG["tool_calls"]),
            default=DEFAULT_AUTO_WATCH_CONFIG["tool_calls"],
        ),
        "elapsed": _as_nonnegative_int(
            _first_value(
                supplied,
                "elapsed",
                "elapsed_minutes",
                "elapsed_threshold",
                "elapsed_minutes_threshold",
                default=DEFAULT_AUTO_WATCH_CONFIG["elapsed"],
            ),
            default=DEFAULT_AUTO_WATCH_CONFIG["elapsed"],
        ),
        "cooldown": _as_nonnegative_int(
            _first_value(
                supplied,
                "cooldown",
                "cooldown_minutes",
                "cooldown_threshold",
                default=DEFAULT_AUTO_WATCH_CONFIG["cooldown"],
            ),
            default=DEFAULT_AUTO_WATCH_CONFIG["cooldown"],
        ),
        "notify_levels": _as_notify_levels(supplied.get("notify_levels")),
    }


def _nested_mappings(result: dict[str, Any]) -> list[dict[str, Any]]:
    recommendation = _as_dict(result.get("recommendation"))
    return [
        result,
        _as_dict(result.get("context")),
        recommendation,
        _as_dict(recommendation.get("context")),
    ]


def _extract_int(result: dict[str, Any], *keys: str) -> int:
    for mapping in _nested_mappings(result):
        for key in keys:
            if key in mapping:
                return _as_nonnegative_int(mapping.get(key), default=0)
    return 0


def _changed_file_count(result: dict[str, Any]) -> int:
    for mapping in _nested_mappings(result):
        changed = mapping.get("changed_files")
        if isinstance(changed, list):
            return len(changed)
        if isinstance(changed, int):
            return max(0, changed)

    recommendation = _as_dict(result.get("recommendation"))
    repo = _as_dict(recommendation.get("repo"))
    changed = repo.get("changed_files")
    if isinstance(changed, list):
        return len(changed)
    if isinstance(changed, int):
        return max(0, changed)
    return 0


def _level(result: dict[str, Any]) -> str:
    recommendation = _as_dict(result.get("recommendation"))
    return str(result.get("level") or recommendation.get("level") or "").strip().lower()


def _cooldown_passed(last_notification: float | None, cooldown_minutes: int) -> bool:
    if last_notification is None:
        return True
    try:
        elapsed_seconds = time.time() - float(last_notification)
    except (TypeError, ValueError):
        return False
    return elapsed_seconds >= cooldown_minutes * 60


def _log_from_notify(result: dict, config: dict, level: str, notify: bool, cooldown_active: bool) -> None:
    """Log the watch evaluation outcome (best-effort, never raises)."""
    try:
        from .watch_logger import log_watch_event

        recommendation_level = None
        if isinstance(result.get("recommendation"), dict):
            recommendation_level = result["recommendation"].get("level")
        if recommendation_level is None:
            recommendation_level = level

        log_watch_event(
            level=level,
            tool_calls=_extract_int(result, "tool_calls", "tool_call_count"),
            elapsed_minutes=_extract_int(result, "elapsed", "elapsed_minutes"),
            changed_files=_changed_file_count(result),
            recommendation_level=str(recommendation_level),
            cooldown_active=cooldown_active,
        )
    except Exception:
        pass


def should_notify(result: dict, config: dict, last_notification: float | None) -> bool:
    """Return whether a Gateway wrapper should send an auto-watch notification.

    Notification requires every gate to pass:
    enabled config, non-observe level in ``notify_levels``, tool-call threshold,
    elapsed-minutes threshold, and cooldown deduplication.
    """

    if not isinstance(result, dict):
        return False

    normalized = _normalize_config(config)
    if not normalized["enabled"]:
        return False

    level = _level(result)
    if level == "observe" or level not in normalized["notify_levels"]:
        return False

    tool_calls = _extract_int(result, "tool_calls", "tool_call_count")
    if tool_calls < normalized["tool_calls"]:
        return False

    elapsed = _extract_int(result, "elapsed", "elapsed_minutes")
    if elapsed < normalized["elapsed"]:
        return False

    return _cooldown_passed(last_notification, normalized["cooldown"])


def format_notification(result: dict) -> str:
    """Render a brief Traditional Chinese notification with count-only context."""

    safe_result = result if isinstance(result, dict) else {}
    elapsed = _extract_int(safe_result, "elapsed", "elapsed_minutes")
    tool_calls = _extract_int(safe_result, "tool_calls", "tool_call_count")
    changed_files = _changed_file_count(safe_result)

    return (
        "⚠️ 有一個開發中的專案建議交接\n"
        f"已開發約 {elapsed} 分鐘，使用 {tool_calls}+ 次工具，{changed_files} 個檔案有變更\n"
        "→ 回對話中輸入 /handoff prepare 來預覽交接內容"
    )


def _read_config_file(path: Path) -> dict[str, Any]:
    if not path.exists() or not path.is_file():
        return {}
    try:
        if path.suffix.lower() == ".toml":
            with path.open("rb") as handle:
                data = tomllib.load(handle)
        else:
            data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, tomllib.TOMLDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def evaluate_and_log(
    result: dict,
    config: dict | None = None,
    last_notification: float | None = None,
) -> tuple[bool, bool]:
    """Evaluate watch result + log the outcome atomically.

    Returns ``(should_send_notification, was_cooldown_active)``.
    This is the preferred single-call entry point for Gateway wrappers.
    """

    normalized = _normalize_config(config)
    level = _level(result)
    cooldown_active = not _cooldown_passed(last_notification, normalized["cooldown"])
    notify = should_notify(result, config, last_notification)

    _log_from_notify(
        result,
        normalized,
        level=level,
        notify=notify,
        cooldown_active=cooldown_active,
    )
    return notify, cooldown_active


def load_auto_watch_config() -> dict:
    """Load auto-watch config, falling back to safe defaults.

    The default hypothetical path is
    ``~/.config/hermes-continuation/auto_watch.json``. Tests or wrappers may set
    ``HERMES_CONTINUATION_AUTO_WATCH_CONFIG`` to point at a JSON or TOML file.
    Missing or invalid config files simply return defaults.
    """

    config_path = Path(os.environ.get(_CONFIG_ENV_VAR) or _DEFAULT_CONFIG_PATH).expanduser()
    loaded = _read_config_file(config_path)
    return _normalize_config(loaded)
