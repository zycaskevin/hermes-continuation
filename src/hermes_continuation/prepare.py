"""Read-only handoff prepare preview assembly. Locale-aware (zh-TW default)."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable

from . import i18n
from .doctor import DoctorRecommendation, evaluate_handoff_recommendation


def _list(values: Iterable[str] | None) -> list[str]:
    return [str(value).strip() for value in (values or []) if str(value).strip()]


def _verification_status(verification: dict[str, list[str]]) -> str:
    if verification.get("failing_gates"):
        return "failing"
    if verification.get("not_run_gates"):
        return "not_run"
    if verification.get("verified_gates"):
        return "verified"
    return "not_provided"


def _local_verification_status(status: str) -> str:
    key_map = {
        "failing": "verification_failing",
        "not_run": "verification_not_run",
        "verified": "verification_verified",
        "not_provided": "verification_not_provided",
    }
    return i18n.fmt_label(key_map.get(status, "verification_not_provided"))


def _local_safety_status(blocked: bool) -> str:
    return i18n.fmt_label("safety_blocked" if blocked else "safety_safe")


def _preview_from_recommendation(
    result: DoctorRecommendation,
    *,
    repo_path: Path,
    output_dir: Path,
    goal: str,
    next_task: str,
) -> dict[str, Any]:
    """Convert a doctor recommendation into a stable read-only preview."""

    blocked = result.level == "block"
    verification = {key: list(value) for key, value in result.verification.items()}
    visible_repo_path = None if blocked else str(repo_path)
    visible_output_dir = None if blocked else str(output_dir)
    return {
        "level": result.level,
        "summary": result.summary,
        "recommendation": result.recommendation,
        "reasons": list(result.reasons),
        "blockers": list(result.blockers),
        "signals": list(result.signals),
        "proposed_goal": None if blocked else (goal.strip() or None),
        "proposed_next_task": None if blocked else (next_task.strip() or None),
        "repo_path": visible_repo_path,
        "output_dir": visible_output_dir,
        "safety_status": "blocked" if blocked else "safe",
        "safety": {
            "blocked": blocked,
            "blockers": list(result.blockers),
            "redaction_count": result.redaction_count,
        },
        "verification_status": _verification_status(verification),
        "verification": verification,
        "task_state_available": result.task_state_available,
        "safe_create_command": None if blocked else result.safe_create_command,
        "would_write": False,
        "dialogue_context": {
            "found": result.dialogue_context.get("found", False),
            "session_title": result.dialogue_context.get("session_title") if not blocked else None,
            "message_count": result.dialogue_context.get("message_count", 0),
            "summary": result.dialogue_context.get("conversation_summary", "") if not blocked else None,
        },
    }


def build_prepare_preview(
    repo_path: str | Path,
    *,
    goal: str = "",
    next_task: str = "",
    in_progress: str = "",
    auto_task_state: bool = True,
    verified_gates: Iterable[str] | None = None,
    failing_gates: Iterable[str] | None = None,
    not_run_gates: Iterable[str] | None = None,
    output_dir: str | Path | None = None,
    source_platform: str | None = None,
    source_chat_id: str | None = None,
) -> dict[str, Any]:
    """Build a read-only handoff prepare preview.

    This helper intentionally delegates safety, redaction, validation of advisory
    state, and safe create-command formatting to the doctor evaluator. It never
    creates ``.hermes/handoffs/`` and never writes packet files.
    """

    repo = Path(repo_path).expanduser().resolve()
    _ = output_dir
    resolved_output_dir = repo / ".hermes" / "handoffs"
    result = evaluate_handoff_recommendation(
        repo,
        goal=goal,
        next_task=next_task,
        in_progress=in_progress,
        auto_task_state=auto_task_state,
        verified_gates=_list(verified_gates),
        failing_gates=_list(failing_gates),
        not_run_gates=_list(not_run_gates),
        explicit_request=True,
        source_platform=source_platform,
        source_chat_id=source_chat_id,
    )
    return _preview_from_recommendation(
        result,
        repo_path=repo,
        output_dir=resolved_output_dir,
        goal=goal,
        next_task=next_task,
    )


def format_prepare_preview(preview: dict[str, Any]) -> str:
    """Render a human-readable, secret-safe, locale-aware prepare preview."""

    blocked = preview.get("safety", {}).get("blocked", False)
    verif_status_raw = preview.get("verification_status", "not_provided")

    lines = [
        f"{i18n.fmt_label('prepare_title')}: {i18n.level_label(preview.get('level', 'unknown'))}",
        i18n.fmt_label("read_only"),
        str(preview.get("summary") or ""),
        f"{i18n.fmt_label('recommendation')}: {preview.get('recommendation')}",
    ]

    if not blocked:
        lines.append(f"{i18n.fmt_label('output_dir')}: {preview.get('output_dir')}")

    # ── Dialogue context ───────────────────────────────────────────────
    dc = preview.get("dialogue_context", {})
    if dc.get("found"):
        session_title = dc.get("session_title") or "(未命名)"
        msg_count = dc.get("message_count", 0)
        lines.append(f"💬 對話上下文：`{session_title}` ({msg_count} 條訊息)")
        summary = dc.get("summary", "")
        if summary and not blocked:
            lines.append("")
            lines.append(summary)

    lines.append(f"{i18n.fmt_label('safety_status')}: {_local_safety_status(blocked)}")
    lines.append(
        f"{i18n.fmt_label('verification_status')}: {_local_verification_status(verif_status_raw)}"
    )

    proposed_goal = preview.get("proposed_goal")
    proposed_next = preview.get("proposed_next_task")
    if proposed_goal:
        lines.append(f"  {i18n.fmt_label('proposed_goal')}: {proposed_goal}")
    if proposed_next:
        lines.append(f"  {i18n.fmt_label('proposed_next')}: {proposed_next}")

    reasons = preview.get("reasons") or []
    if reasons:
        lines.append(f"{i18n.fmt_label('reasons')}:")
        lines.extend(f"  - {reason}" for reason in reasons)

    blockers = preview.get("blockers") or []
    if blockers:
        lines.append(f"{i18n.fmt_label('blockers')}:")
        lines.extend(f"  - {blocker}" for blocker in blockers)

    signals = preview.get("signals") or []
    if signals:
        lines.append(f"{i18n.fmt_label('signals')}:")
        lines.extend(f"  - {i18n.signal_label(s)}" for s in signals)

    command = preview.get("safe_create_command")
    if command:
        lines.append(f"{i18n.fmt_label('safe_create_command')}:")
        lines.append(str(command))

    return "\n".join(line for line in lines if line) + "\n"
