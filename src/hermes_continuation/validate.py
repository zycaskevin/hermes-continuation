"""Validation helpers for handoff packets."""

from __future__ import annotations

from typing import Any

REQUIRED_TOP_LEVEL_FIELDS = [
    "schema_version",
    "created_at",
    "source",
    "current_goal",
    "repo",
    "task_state",
    "verification",
    "safety",
    "resume_prompt",
]

REQUIRED_REPO_FIELDS = ["path", "git_available", "branch", "head", "status_short", "changed_files"]
REQUIRED_TASK_FIELDS = ["completed_work", "in_progress", "known_blockers", "do_not_touch", "next_recommended_task"]
REQUIRED_VERIFICATION_FIELDS = ["verified_gates", "failing_gates", "not_run_gates"]
REQUIRED_SAFETY_FIELDS = ["redaction_count", "blocked", "blocked_reason"]


class ValidationError(ValueError):
    """Raised when a handoff packet is structurally invalid."""


def _require_mapping(packet: dict[str, Any], key: str) -> dict[str, Any]:
    value = packet.get(key)
    if not isinstance(value, dict):
        raise ValidationError(f"{key} must be an object")
    return value


def validate_packet(packet: dict[str, Any]) -> None:
    missing = [field for field in REQUIRED_TOP_LEVEL_FIELDS if field not in packet]
    if missing:
        raise ValidationError(f"missing required fields: {', '.join(missing)}")
    if packet["source"] != "hermes-handoff":
        raise ValidationError("source must be hermes-handoff")
    if not str(packet.get("current_goal", "")).strip():
        raise ValidationError("current_goal must not be empty")

    repo = _require_mapping(packet, "repo")
    task_state = _require_mapping(packet, "task_state")
    verification = _require_mapping(packet, "verification")
    safety = _require_mapping(packet, "safety")

    for name, fields, obj in [
        ("repo", REQUIRED_REPO_FIELDS, repo),
        ("task_state", REQUIRED_TASK_FIELDS, task_state),
        ("verification", REQUIRED_VERIFICATION_FIELDS, verification),
        ("safety", REQUIRED_SAFETY_FIELDS, safety),
    ]:
        missing_nested = [field for field in fields if field not in obj]
        if missing_nested:
            raise ValidationError(f"{name} missing required fields: {', '.join(missing_nested)}")
