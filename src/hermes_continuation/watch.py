"""One-shot read-only handoff watch/advisory orchestration. Locale-aware (zh-TW)."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable

from . import i18n
from .doctor import evaluate_handoff_recommendation
from .prepare import build_prepare_preview

_TOOL_CALL_THRESHOLD = 5
_ELAPSED_MINUTES_THRESHOLD = 30


def _list(values: Iterable[str] | None) -> list[str]:
    return [str(value).strip() for value in (values or []) if str(value).strip()]


def _nonnegative_int(value: int | None) -> int | None:
    if value is None:
        return None
    return max(0, int(value))


def _dirty_threshold(value: int) -> int:
    return max(1, int(value))


def _changed_file_count(recommendation: dict[str, Any]) -> int:
    repo = recommendation.get("repo") if isinstance(recommendation, dict) else None
    changed = repo.get("changed_files") if isinstance(repo, dict) else None
    return len(changed) if isinstance(changed, list) else 0


def _watch_threshold_signals(
    recommendation: dict[str, Any],
    *,
    tool_calls: int | None,
    elapsed_minutes: int | None,
    dirty_threshold: int,
) -> tuple[list[str], list[str]]:
    """Return watch-specific signal names and human-safe reasons."""

    signals: list[str] = []
    reasons: list[str] = []

    normalized_tool_calls = _nonnegative_int(tool_calls)
    if normalized_tool_calls is not None and normalized_tool_calls >= _TOOL_CALL_THRESHOLD:
        signals.append("watch_tool_calls_threshold")
        reasons.append(
            f"Watch observed {normalized_tool_calls} tool calls, meeting the {_TOOL_CALL_THRESHOLD}+ advisory threshold."
        )

    normalized_elapsed = _nonnegative_int(elapsed_minutes)
    if normalized_elapsed is not None and normalized_elapsed >= _ELAPSED_MINUTES_THRESHOLD:
        signals.append("watch_elapsed_minutes_threshold")
        reasons.append(
            f"Watch observed {normalized_elapsed} elapsed minutes, meeting the {_ELAPSED_MINUTES_THRESHOLD}+ advisory threshold."
        )

    changed_count = _changed_file_count(recommendation)
    normalized_dirty_threshold = _dirty_threshold(dirty_threshold)
    if changed_count >= normalized_dirty_threshold and changed_count > 0:
        signals.append("watch_dirty_threshold")
        reasons.append(
            f"Watch observed {changed_count} changed file(s), meeting the dirty threshold of {normalized_dirty_threshold}."
        )

    return signals, reasons


def _merge_unique(values: Iterable[str]) -> list[str]:
    merged: list[str] = []
    for value in values:
        if value not in merged:
            merged.append(value)
    return merged


def _advise_from_watch_thresholds(
    recommendation: dict[str, Any],
    *,
    watch_signals: list[str],
    watch_reasons: list[str],
) -> dict[str, Any]:
    """Elevate an otherwise-observe doctor result to advisory using watch-only signals."""

    elevated = dict(recommendation)
    elevated["level"] = "advise"
    elevated["summary"] = (
        "A watch threshold indicates a handoff may be useful, but watch remains read-only."
    )
    elevated["recommendation"] = (
        "Consider preparing a handoff after supplying complete safe goal and next-task inputs."
    )
    elevated["reasons"] = _merge_unique([*(recommendation.get("reasons") or []), *watch_reasons])
    elevated["signals"] = _merge_unique([*(recommendation.get("signals") or []), *watch_signals])
    elevated["safe_create_command"] = None
    return elevated


def build_watch_result(
    repo_path: str | Path,
    *,
    goal: str = "",
    next_task: str = "",
    in_progress: str = "",
    auto_task_state: bool = True,
    tool_calls: int | None = None,
    elapsed_minutes: int | None = None,
    context: dict[str, Any] | None = None,
    dirty_threshold: int = 1,
    verified_gates: Iterable[str] | None = None,
    failing_gates: Iterable[str] | None = None,
    not_run_gates: Iterable[str] | None = None,
    explicit_request: bool = False,
    source_platform: str | None = None,
    source_chat_id: str | None = None,
) -> dict[str, Any]:
    """Build a one-shot read-only watch result.

    ``watch`` is an advisory orchestrator over the existing doctor and prepare
    helpers. It never invokes the create path, never writes packet files, and
    never creates ``.hermes/handoffs/``.
    """

    repo = Path(repo_path).expanduser().resolve()
    doctor_result = evaluate_handoff_recommendation(
        repo,
        goal=goal,
        next_task=next_task,
        in_progress=in_progress,
        auto_task_state=auto_task_state,
        verified_gates=_list(verified_gates),
        failing_gates=_list(failing_gates),
        not_run_gates=_list(not_run_gates),
        explicit_request=explicit_request,
        source_platform=source_platform,
        source_chat_id=source_chat_id,
    )
    recommendation = doctor_result.to_dict()

    if context is not None:
        if tool_calls is None:
            tool_calls = context.get("tool_calls")
        if elapsed_minutes is None:
            elapsed_minutes = context.get("elapsed_minutes")

    watch_signals, watch_reasons = _watch_threshold_signals(
        recommendation,
        tool_calls=tool_calls,
        elapsed_minutes=elapsed_minutes,
        dirty_threshold=dirty_threshold,
    )

    if watch_signals:
        recommendation["signals"] = _merge_unique([*recommendation.get("signals", []), *watch_signals])
        recommendation["reasons"] = _merge_unique([*recommendation.get("reasons", []), *watch_reasons])

    if recommendation.get("level") == "observe" and watch_signals:
        recommendation = _advise_from_watch_thresholds(
            recommendation,
            watch_signals=watch_signals,
            watch_reasons=watch_reasons,
        )

    preview: dict[str, Any] | None = None
    if doctor_result.level == "prepare" and recommendation.get("level") == "prepare":
        preview = build_prepare_preview(
            repo,
            goal=goal,
            next_task=next_task,
            in_progress=in_progress,
            auto_task_state=auto_task_state,
            verified_gates=_list(verified_gates),
            failing_gates=_list(failing_gates),
            not_run_gates=_list(not_run_gates),
            source_platform=source_platform,
            source_chat_id=source_chat_id,
        )

    level = str(recommendation.get("level") or doctor_result.level)
    return {
        "success": True,
        "level": level,
        "watch_signals": watch_signals,
        "recommendation": recommendation,
        "preview": preview,
        "would_write": False,
    }


def format_watch_result(result: dict[str, Any]) -> str:
    """Render a human-readable, secret-safe, locale-aware watch result."""

    recommendation = result.get("recommendation") if isinstance(result.get("recommendation"), dict) else {}
    preview = result.get("preview") if isinstance(result.get("preview"), dict) else None
    level = result.get("level") or recommendation.get("level") or (preview or {}).get("level")

    lines = [
        f"{i18n.fmt_label('watch_title')}: {i18n.level_label(level)}",
        i18n.fmt_label("read_only_watch"),
        str(recommendation.get("summary") or ""),
        f"{i18n.fmt_label('recommendation')}: {recommendation.get('recommendation')}",
    ]

    watch_signals = result.get("watch_signals") or []
    if watch_signals:
        lines.append(f"{i18n.fmt_label('watch_signals')}:")
        lines.extend(f"  - {signal}" for signal in watch_signals)

    reasons = recommendation.get("reasons") or []
    if reasons:
        lines.append(f"{i18n.fmt_label('reasons')}:")
        lines.extend(f"  - {reason}" for reason in reasons)

    blockers = recommendation.get("blockers") or []
    if blockers:
        lines.append(f"{i18n.fmt_label('blockers')}:")
        lines.extend(f"  - {blocker}" for blocker in blockers)

    signals = recommendation.get("signals") or []
    if signals:
        lines.append(f"{i18n.fmt_label('signals')}:")
        lines.extend(f"  - {i18n.signal_label(s)}" for s in signals)

    if preview is not None:
        lines.append(f"{i18n.fmt_label('prepare_preview_label')}:")
        lines.append(f"  - would_write=false")
        lines.append(f"  - output_dir: {preview.get('output_dir')}")
        lines.append(f"  - safety_status: {preview.get('safety_status')}")
        lines.append(f"  - verification_status: {preview.get('verification_status')}")
        proposed_goal = preview.get("proposed_goal")
        proposed_next = preview.get("proposed_next_task")
        if proposed_goal:
            lines.append(f"  - proposed_goal: {proposed_goal}")
        if proposed_next:
            lines.append(f"  - proposed_next_task: {proposed_next}")
        command = preview.get("safe_create_command")
        if command:
            lines.append(f"  {i18n.fmt_label('safe_create_command')}:")
            lines.append(f"  {command}")

    lines.append(i18n.fmt_label("no_create_command"))
    return "\n".join(line for line in lines if line) + "\n"
