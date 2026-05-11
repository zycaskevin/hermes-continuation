"""Read-only handoff prepare preview assembly."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable

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
) -> dict[str, Any]:
    """Build a read-only handoff prepare preview.

    This helper intentionally delegates safety, redaction, validation of advisory
    state, and safe create-command formatting to the doctor evaluator. It never
    creates ``.hermes/handoffs/`` and never writes packet files.
    """

    repo = Path(repo_path).expanduser().resolve()
    # ``safe_create_command`` is rendered by the doctor evaluator and does not
    # carry prepare-specific output-dir state. Keep the preview aligned with the
    # command by always reporting the create command's default output location.
    # The optional parameter is accepted for backward-compatible callers but is
    # intentionally ignored.
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
    )
    return _preview_from_recommendation(
        result,
        repo_path=repo,
        output_dir=resolved_output_dir,
        goal=goal,
        next_task=next_task,
    )


def format_prepare_preview(preview: dict[str, Any]) -> str:
    """Render a human-readable, secret-safe prepare preview."""

    lines = [
        f"Handoff prepare preview: {preview.get('level')}",
        "Read-only preview: would_write=false; no handoff packet was created.",
        str(preview.get("summary") or ""),
        f"Recommendation: {preview.get('recommendation')}",
        f"Output directory if create is run later: {preview.get('output_dir')}",
        f"Safety status: {preview.get('safety_status')}",
        f"Verification status: {preview.get('verification_status')}",
    ]

    proposed_goal = preview.get("proposed_goal")
    proposed_next = preview.get("proposed_next_task")
    if proposed_goal:
        lines.append(f"Proposed goal: {proposed_goal}")
    if proposed_next:
        lines.append(f"Proposed next_task: {proposed_next}")

    reasons = preview.get("reasons") or []
    if reasons:
        lines.append("Reasons:")
        lines.extend(f"- {reason}" for reason in reasons)

    blockers = preview.get("blockers") or []
    if blockers:
        lines.append("Blockers:")
        lines.extend(f"- {blocker}" for blocker in blockers)

    signals = preview.get("signals") or []
    if signals:
        lines.append("Signals:")
        lines.extend(f"- {signal}" for signal in signals)

    command = preview.get("safe_create_command")
    if command:
        lines.append("Safe create command (run only if you want to write a packet):")
        lines.append(str(command))

    return "\n".join(line for line in lines if line) + "\n"
