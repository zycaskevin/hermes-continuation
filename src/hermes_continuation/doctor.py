"""Read-only advisory evaluator for handoff recommendations.

Locale-aware: format functions default to zh-TW (Traditional Chinese) via i18n.
"""

from __future__ import annotations

import shlex
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Literal

from . import i18n
from .dialogue_context import collect_dialogue_context
from .git_state import collect_git_state
from .redaction import RedactionBlocked, redact_obj, redact_text
from .task_state import collect_task_state

RecommendationLevel = Literal["observe", "advise", "prepare", "block"]


@dataclass(frozen=True)
class DoctorRecommendation:
    """Result from the read-only handoff recommendation evaluator."""

    level: RecommendationLevel
    summary: str
    recommendation: str
    reasons: list[str] = field(default_factory=list)
    blockers: list[str] = field(default_factory=list)
    signals: list[str] = field(default_factory=list)
    safe_create_command: str | None = None
    repo: dict[str, Any] = field(default_factory=dict)
    verification: dict[str, list[str]] = field(default_factory=dict)
    task_state_available: bool = False
    redaction_count: int = 0
    dialogue_context: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable representation."""

        return {
            "level": self.level,
            "summary": self.summary,
            "recommendation": self.recommendation,
            "reasons": list(self.reasons),
            "blockers": list(self.blockers),
            "signals": list(self.signals),
            "safe_create_command": self.safe_create_command,
            "repo": dict(self.repo),
            "verification": {key: list(value) for key, value in self.verification.items()},
            "task_state_available": self.task_state_available,
            "redaction_count": self.redaction_count,
            "dialogue_context": dict(self.dialogue_context),
        }


def _list(values: Iterable[str] | None) -> list[str]:
    return [str(value).strip() for value in (values or []) if str(value).strip()]


def _safe_text(value: str) -> tuple[str, int]:
    redacted, count = redact_text(str(value or ""))
    return redacted.strip(), count


def _safe_repo(repo_state: dict[str, Any]) -> tuple[dict[str, Any], int]:
    """Redact repo metadata before returning or printing it."""

    result = redact_obj(repo_state)
    value = result.value if isinstance(result.value, dict) else {}
    return value, result.redaction_count


def _task_state_has_evidence(task_state: dict[str, Any] | None) -> bool:
    if not task_state:
        return False
    return bool(
        task_state.get("completed_work")
        or task_state.get("in_progress")
        or task_state.get("known_blockers")
        or task_state.get("do_not_touch")
        or task_state.get("next_recommended_task")
    )


def _render_create_command(
    repo_path: Path,
    *,
    goal: str,
    next_task: str,
    in_progress: str = "",
    auto_task_state: bool,
    verified_gates: list[str],
) -> str:
    parts = [
        "hermes-handoff",
        "create",
        "--repo",
        str(repo_path),
        "--goal",
        goal,
        "--next",
        next_task,
    ]
    if in_progress:
        parts.extend(["--in-progress", in_progress])
    if auto_task_state:
        parts.append("--auto-task-state")
    for gate in verified_gates:
        parts.extend(["--verified", gate])
    return " ".join(shlex.quote(part) for part in parts)


def _result(
    level: RecommendationLevel,
    *,
    recommendation: str,
    reasons: list[str],
    blockers: list[str],
    signals: list[str],
    repo: dict[str, Any],
    verification: dict[str, list[str]],
    task_state_available: bool,
    redaction_count: int,
    safe_create_command: str | None = None,
    dialogue_context: dict[str, Any] | None = None,
) -> DoctorRecommendation:
    return DoctorRecommendation(
        level=level,
        summary=i18n.level_summary(level),
        recommendation=recommendation,
        reasons=reasons,
        blockers=blockers,
        signals=signals,
        safe_create_command=safe_create_command,
        repo=repo,
        verification=verification,
        task_state_available=task_state_available,
        redaction_count=redaction_count,
        dialogue_context=dialogue_context or {},
    )


def evaluate_handoff_recommendation(
    repo_path: str | Path = ".",
    *,
    goal: str = "",
    next_task: str = "",
    auto_task_state: bool = True,
    verified_gates: Iterable[str] | None = None,
    failing_gates: Iterable[str] | None = None,
    not_run_gates: Iterable[str] | None = None,
    explicit_request: bool = False,
    in_progress: str = "",
    source_platform: str | None = None,
    source_chat_id: str | None = None,
) -> DoctorRecommendation:
    """Evaluate local signals and return a read-only handoff recommendation.

    The evaluator never writes handoff packets, starts sessions, launches agents,
    or parses full transcripts. Missing or incomplete state degrades to
    ``advise`` rather than fabricating a ``prepare`` result.

    When ``source_platform`` and ``source_chat_id`` are provided (from a gateway
    session), the evaluator queries state.db for recent conversation context
    from that chat — making the recommendation about *dialogue* content, not just
    filesystem state.

    In **plugin mode** (no explicit repo_path, source context available), the
    evaluator skips filesystem analysis (git state, task state) and produces a
    conversation-aware recommendation using session metrics and dialogue context.
    """

    is_plugin_mode = bool(source_platform and source_chat_id) and (
        str(repo_path) in (".", "", "None")
    )

    repo = Path(repo_path).expanduser().resolve() if str(repo_path) not in (".", "", "None") else Path(".").resolve()
    blockers: list[str] = []
    reasons: list[str] = []
    signals: list[str] = []
    redaction_count = 0

    verified = _list(verified_gates)
    failing = _list(failing_gates)
    not_run = _list(not_run_gates)
    verification = {
        "verified_gates": verified,
        "failing_gates": failing,
        "not_run_gates": not_run,
    }

    try:
        safe_goal, count = _safe_text(goal)
        redaction_count += count
        safe_next, count = _safe_text(next_task)
        redaction_count += count
        safe_in_progress, count = _safe_text(in_progress)
        redaction_count += count
        redacted_verification = redact_obj(verification)
        verification = redacted_verification.value
        redaction_count += redacted_verification.redaction_count
    except RedactionBlocked:
        safe_repo = {"path": "[REDACTED]", "git_available": False, "changed_files": []}
        safe_verification = {"verified_gates": [], "failing_gates": [], "not_run_gates": []}
        blockers.append(i18n.block_reason("private_key_input"))
        return _result(
            "block",
            recommendation=i18n.rec_text("block_private_key"),
            reasons=[i18n.block_reason("safety_first")],
            blockers=blockers,
            signals=["private_key_detected"],
            repo=safe_repo,
            verification=safe_verification,
            task_state_available=False,
            redaction_count=redaction_count,
            dialogue_context={},
        )

    # ── Repo & git state (skipped in plugin mode) ──────────────────────
    safe_repo: dict[str, Any] = {
        "path": str(repo),
        "git_available": True,
        "changed_files": [] if is_plugin_mode else None,
    }
    task_state: dict[str, Any] | None = None
    task_state_available = False

    if not is_plugin_mode:
        repo_state = collect_git_state(repo)
        try:
            safe_repo, count = _safe_repo(repo_state)
            redaction_count += count
        except RedactionBlocked:
            safe_repo = {"path": "[REDACTED]", "git_available": False, "changed_files": []}
            blockers.append(i18n.block_reason("private_key_repo"))
            return _result(
                "block",
                recommendation=i18n.rec_text("block_private_key"),
                reasons=[i18n.block_reason("safety_first")],
                blockers=blockers,
                signals=["private_key_detected"],
                repo=safe_repo,
                verification=verification,
                task_state_available=False,
                redaction_count=redaction_count,
                dialogue_context={},
            )

        if auto_task_state:
            try:
                task_state = collect_task_state(repo, repo_state)
                redacted_task_state = redact_obj(task_state)
                task_state = redacted_task_state.value
                redaction_count += redacted_task_state.redaction_count
                task_state_available = _task_state_has_evidence(task_state)
                if task_state_available:
                    signals.append("task_state_available")
            except RedactionBlocked:
                blockers.append(i18n.block_reason("private_key_docs"))
                return _result(
                    "block",
                    recommendation=i18n.rec_text("block_private_key"),
                    reasons=[i18n.block_reason("safety_first")],
                    blockers=blockers,
                    signals=["private_key_detected"],
                    repo=safe_repo,
                    verification=verification,
                    task_state_available=False,
                    redaction_count=redaction_count,
                    dialogue_context={},
                )
        else:
            signals.append("auto_task_state_disabled")
    else:
        signals.append("plugin_mode")

    # ── Dialogue context from state.db ─────────────────────────────────
    dialogue_ctx: dict[str, Any] = {}
    if source_platform and source_chat_id:
        dialogue_ctx = collect_dialogue_context(
            source_platform, source_chat_id
        )
        if dialogue_ctx.get("found"):
            signals.append("dialogue_context_found")
            reasons.append(
                f"對話上下文：{dialogue_ctx['message_count']} 條訊息"
                f"（來自 {source_platform}:{source_chat_id[:12]}...）"
            )
        else:
            err = dialogue_ctx.get("error")
            if err:
                signals.append("dialogue_context_unavailable")
                reasons.append(f"對話上下文不可用：{err}")
    else:
        dialogue_ctx = {}

    if redaction_count > 0:
        blockers.append(i18n.block_reason("secrets_redacted"))
        return _result(
            "block",
            recommendation=i18n.rec_text("block_secrets"),
            reasons=[i18n.block_reason("safety_first")],
            blockers=blockers,
            signals=[*signals, "sensitive_value_redacted"],
            repo=safe_repo,
            verification=verification,
            task_state_available=task_state_available,
            redaction_count=redaction_count,
            dialogue_context=dialogue_ctx,
        )

    if explicit_request:
        signals.append("explicit_request")
    if not safe_repo.get("git_available"):
        signals.append("git_state_incomplete")
        reasons.append(i18n.reason_message("git_state_incomplete"))
    elif safe_repo.get("changed_files"):
        signals.append("dirty_git_state")
        reasons.append(i18n.reason_message("dirty_git_state"))

    if failing:
        signals.append("failing_gates")
        reasons.append(i18n.reason_message("failing_gates"))
    if not_run:
        signals.append("not_run_gates")
        reasons.append(i18n.reason_message("not_run_gates"))
    if task_state and task_state.get("known_blockers"):
        signals.append("known_blockers")
        reasons.append(i18n.reason_message("known_blockers"))
    if task_state and task_state.get("do_not_touch"):
        signals.append("safety_boundaries")
        reasons.append(i18n.reason_message("safety_boundaries"))

    has_goal = bool(safe_goal)
    has_next = bool(safe_next)
    has_prepare_input = has_goal and has_next
    has_advise_signal = bool(reasons or explicit_request or safe_repo.get("changed_files") or failing or not_run)
    verification_attention = bool(failing or not_run)
    repo_dirty = bool(safe_repo.get("changed_files"))

    if has_prepare_input and not verification_attention and not repo_dirty and safe_repo.get("git_available"):
        command = _render_create_command(
            repo,
            goal=safe_goal,
            next_task=safe_next,
            in_progress=safe_in_progress,
            auto_task_state=auto_task_state,
            verified_gates=verified,
        )
        prepare_reasons = list(reasons)
        if explicit_request:
            prepare_reasons.append(
                "Explicit handoff request has complete safe goal and next-task inputs."
            )
        else:
            prepare_reasons.append(
                "Complete safe goal and next-task inputs are present."
            )
        return _result(
            "prepare",
            recommendation=i18n.rec_text("prepare_ready"),
            reasons=prepare_reasons,
            blockers=[],
            signals=signals,
            safe_create_command=command,
            repo=safe_repo,
            verification=verification,
            task_state_available=task_state_available,
            redaction_count=redaction_count,
            dialogue_context=dialogue_ctx,
        )

    if explicit_request and not has_prepare_input:
        missing_fields = []
        if not has_goal:
            missing_fields.append(i18n.fmt_label("field_goal"))
        if not has_next:
            missing_fields.append(i18n.fmt_label("field_next_task"))
        reasons.append(i18n.rec_text("explicit_missing", missing=" + ".join(missing_fields)))
        signals.append("missing_required_prepare_input")
        has_advise_signal = True
    elif (has_goal or has_next) and not has_prepare_input:
        reasons.append(i18n.rec_text("partial_input"))
        signals.append("missing_required_prepare_input")
        has_advise_signal = True
    elif has_prepare_input and (verification_attention or repo_dirty or not safe_repo.get("git_available")):
        reasons.append(i18n.rec_text("dirty_but_complete"))
        has_advise_signal = True

    if has_advise_signal:
        return _result(
            "advise",
            recommendation=i18n.rec_text("advise_default"),
            reasons=reasons or ["A handoff was requested or local state needs attention."],
            blockers=[],
            signals=signals,
            repo=safe_repo,
            verification=verification,
            task_state_available=task_state_available,
            redaction_count=redaction_count,
            dialogue_context=dialogue_ctx,
        )

    return _result(
        "observe",
        recommendation=i18n.rec_text("observe_default"),
        reasons=["Repository state is clean and no handoff or verification signals were provided."],
        blockers=[],
        signals=signals,
        repo=safe_repo,
        verification=verification,
        task_state_available=task_state_available,
        redaction_count=redaction_count,
        dialogue_context=dialogue_ctx,
    )


def format_recommendation(result: DoctorRecommendation) -> str:
    """Render a human-readable, secret-safe, locale-aware recommendation."""
    loc = i18n.current_locale()

    lines = [
        f"{i18n.fmt_label('doctor_title')}: {i18n.level_label(result.level)}",
        result.summary,
        f"{i18n.fmt_label('recommendation')}: {result.recommendation}",
    ]
    repo_path = result.repo.get("path", "")
    if repo_path:
        lines.insert(1, f"📁 掃描目錄：`{repo_path}`")

    # ── Dialogue context section ───────────────────────────────────────
    dc = result.dialogue_context
    if dc.get("found"):
        session_title = dc.get("session_title") or "(未命名)"
        msg_count = dc.get("message_count", 0)
        lines.append(f"💬 對話上下文：`{session_title}` ({msg_count} 條訊息)")
        conv_summary = dc.get("conversation_summary", "")
        if conv_summary:
            lines.append("")
            lines.append(conv_summary)

    if result.reasons:
        lines.append(f"{i18n.fmt_label('reasons')}:")
        lines.extend(f"  - {reason}" for reason in result.reasons)
    if result.blockers:
        lines.append(f"{i18n.fmt_label('blockers')}:")
        lines.extend(f"  - {blocker}" for blocker in result.blockers)
    if result.signals:
        lines.append(f"{i18n.fmt_label('signals')}:")
        lines.extend(f"  - {i18n.signal_label(s)}" for s in result.signals)
    if result.safe_create_command:
        lines.append(f"{i18n.fmt_label('safe_create_command')}:")
        lines.append(result.safe_create_command)
    lines.append(i18n.fmt_label("footer_read_only"))
    return "\n".join(lines) + "\n"
