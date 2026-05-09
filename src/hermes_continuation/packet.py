"""Build structured handoff packets."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Iterable

from .redaction import redact_obj
from .validate import validate_packet

SCHEMA_VERSION = "0.1.0"
SOURCE = "hermes-handoff"


def _list(values: Iterable[str] | None) -> list[str]:
    return [str(value).strip() for value in (values or []) if str(value).strip()]


def build_resume_prompt(packet_without_prompt: dict[str, Any]) -> str:
    repo = packet_without_prompt["repo"]
    task = packet_without_prompt["task_state"]
    verification = packet_without_prompt["verification"]

    def bullets(values: list[str]) -> str:
        if not values:
            return "- None recorded"
        return "\n".join(f"- {value}" for value in values)

    changed_files = repo.get("changed_files", [])
    changed = "- None" if not changed_files else "\n".join(
        f"- {item.get('status', '').strip()}: {item.get('path', '')}" for item in changed_files
    )

    return f"""You are taking over an in-progress Hermes long task.

Rules:
1. This is a handoff, not a new requirement. Do not redo completed work.
2. Read the full handoff before acting.
3. Do not guess facts missing from the handoff; verify with tools.
4. Test/QA status from this handoff is reference only. Re-run critical checks in the new session before reporting success.
5. Strictly obey Do Not Touch boundaries.
6. If repo reality differs from the handoff, report the difference first.

# Current Goal
{packet_without_prompt['current_goal']}

# Repo State
- Path: {repo.get('path')}
- Git available: {repo.get('git_available')}
- Branch: {repo.get('branch')}
- HEAD: {repo.get('head')}
- Status:
{repo.get('status_short') or 'clean / empty'}

# Changed Files
{changed}

# Completed Work
{bullets(task.get('completed_work', []))}

# In Progress
{task.get('in_progress') or 'None recorded'}

# Verified Gates
{bullets(verification.get('verified_gates', []))}

# Failing Gates
{bullets(verification.get('failing_gates', []))}

# Not Run Gates
{bullets(verification.get('not_run_gates', []))}

# Known Blockers
{bullets(task.get('known_blockers', []))}

# Do Not Touch
{bullets(task.get('do_not_touch', []))}

# Next Recommended Task
{task.get('next_recommended_task')}

# Required First Actions
1. Check the repo path exists.
2. Check git branch/status against this handoff.
3. Inspect changed files.
4. Only after confirming state, execute the next recommended task.
5. After progress, update or create a new handoff.
""".strip()


def build_packet(
    *,
    current_goal: str,
    repo: dict[str, Any],
    completed_work: Iterable[str] | None = None,
    in_progress: str = "",
    known_blockers: Iterable[str] | None = None,
    do_not_touch: Iterable[str] | None = None,
    next_recommended_task: str,
    verified_gates: Iterable[str] | None = None,
    failing_gates: Iterable[str] | None = None,
    not_run_gates: Iterable[str] | None = None,
    created_at: str | None = None,
) -> dict[str, Any]:
    raw_packet: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "created_at": created_at or datetime.now(timezone.utc).isoformat(),
        "source": SOURCE,
        "current_goal": current_goal,
        "repo": repo,
        "task_state": {
            "completed_work": _list(completed_work),
            "in_progress": in_progress.strip(),
            "known_blockers": _list(known_blockers),
            "do_not_touch": _list(do_not_touch),
            "next_recommended_task": next_recommended_task.strip(),
        },
        "verification": {
            "verified_gates": _list(verified_gates),
            "failing_gates": _list(failing_gates),
            "not_run_gates": _list(not_run_gates),
        },
        "safety": {
            "redaction_count": 0,
            "blocked": False,
            "blocked_reason": None,
        },
        "resume_prompt": "",
    }

    redacted = redact_obj(raw_packet)
    packet = redacted.value
    packet["safety"]["redaction_count"] = redacted.redaction_count
    packet["resume_prompt"] = build_resume_prompt(packet)
    prompt_result = redact_obj(packet["resume_prompt"])
    packet["resume_prompt"] = prompt_result.value
    packet["safety"]["redaction_count"] += prompt_result.redaction_count
    validate_packet(packet)
    return packet
