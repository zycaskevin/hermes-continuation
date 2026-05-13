"""Auto-doctor: threshold-based restart + handoff advisory.

This module is invoked at the end of every agent turn in the Gateway.  It
inspects conversation length, elapsed time, tool-call count, and optional task
execution completeness signals.  When risk is high enough, it returns a
content-safe advisory payload that tells the wrapper whether to suggest a fresh
conversation and includes a pasteable handoff draft.

Key design decisions:
- No chat_context config needed — all data comes from the hook kwargs
  plus state.db (queried via dialogue_context).
- Doctor runs in plugin mode: no file path, no git state, no task state.
  Only dialogue context and session metrics are consulted.
- Thresholds are conservative to avoid notification spam.
- This module never restarts a session and never writes handoff packets.  It
  only recommends and prepares text for the user to approve.
"""

from __future__ import annotations

from typing import Any

from .redaction import RedactionBlocked, redact_obj

# ── Thresholds ──────────────────────────────────────────────────────────────
# These reflect real usage patterns: a single workflow (task delegation +
# iteration) typically consumes 30-50 messages + tool calls. A full project
# development spans 3-5+ such workflows.
#
# Advise threshold: ~1 full project cycle (100+ messages, 60+ tool calls)
# Recommend threshold: ~2-3+ project cycles (200+ messages, 120+ tool calls)

# Minimum messages before we even consider advising
MIN_MESSAGES_FOR_ADVISE = 100
MIN_TOOL_CALLS_FOR_ADVISE = 60
MIN_ELAPSED_MINUTES_FOR_ADVISE = 45

# Recommend threshold: strong signal the conversation has substantial context
MIN_MESSAGES_FOR_RECOMMEND = 200
MIN_TOOL_CALLS_FOR_RECOMMEND = 120
MIN_ELAPSED_MINUTES_FOR_RECOMMEND = 90

# Task-completeness signals do not trigger alone, but they strengthen an
# already meaningful context-risk signal.
MIN_COMPLETION_PERCENT_FOR_HANDOFF = 70
MAX_COMPLETION_PERCENT = 100


def _nonnegative_int(value: Any, default: int = 0) -> int:
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return default


def _optional_nonnegative_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    return _nonnegative_int(value)


def _count_items(value: Any) -> int:
    if value is None:
        return 0
    if isinstance(value, int):
        return max(0, value)
    if isinstance(value, (list, tuple, set)):
        return len([item for item in value if str(item).strip()])
    text = str(value).strip()
    if not text:
        return 0
    return len([part for part in text.split(",") if part.strip()])


def _normalize_completion(value: Any) -> int | None:
    """Normalize completion input to an integer percent in ``0..100``."""

    if value is None or value == "":
        return None
    if isinstance(value, str):
        stripped = value.strip().rstrip("%")
        if not stripped:
            return None
        value = stripped
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None
    if 0 <= numeric <= 1:
        numeric *= 100
    return min(MAX_COMPLETION_PERCENT, max(0, round(numeric)))


def _derive_completion(
    *,
    task_completion: Any = None,
    completed_tasks: Any = None,
    total_tasks: Any = None,
) -> int | None:
    explicit = _normalize_completion(task_completion)
    if explicit is not None:
        return explicit

    completed = _count_items(completed_tasks)
    total = _optional_nonnegative_int(total_tasks)
    if total and total > 0:
        return min(MAX_COMPLETION_PERCENT, round(completed / total * 100))
    return None


def _task_execution_state(
    *,
    task_completion: Any = None,
    completed_tasks: Any = None,
    total_tasks: Any = None,
    pending_tasks: Any = None,
    failing_gates: Any = None,
    not_run_gates: Any = None,
    active_task: str = "",
) -> dict[str, Any]:
    completion_percent = _derive_completion(
        task_completion=task_completion,
        completed_tasks=completed_tasks,
        total_tasks=total_tasks,
    )
    completed_count = _count_items(completed_tasks)
    total_count = _optional_nonnegative_int(total_tasks)
    pending_count = _count_items(pending_tasks)
    failing_count = _count_items(failing_gates)
    not_run_count = _count_items(not_run_gates)
    active = bool(str(active_task or "").strip())

    has_signal = bool(
        active
        or completion_percent is not None
        or completed_count
        or total_count
        or pending_count
        or failing_count
        or not_run_count
    )
    handoff_ready = (
        completion_percent is not None
        and completion_percent >= MIN_COMPLETION_PERCENT_FOR_HANDOFF
    )
    needs_follow_up = bool(active or pending_count or failing_count or not_run_count)

    return {
        "completion_percent": completion_percent,
        "completed_tasks": completed_count,
        "total_tasks": total_count,
        "pending_tasks": pending_count,
        "failing_gates": failing_count,
        "not_run_gates": not_run_count,
        "active_task_present": active,
        "has_signal": has_signal,
        "handoff_ready": handoff_ready,
        "needs_follow_up": needs_follow_up,
    }


def _risk_signals(
    *,
    message_count: int,
    tool_call_count: int,
    elapsed_minutes: int | None,
    task_execution: dict[str, Any],
) -> tuple[list[str], list[str], str | None]:
    signals: list[str] = []
    reasons: list[str] = []

    if message_count >= MIN_MESSAGES_FOR_ADVISE:
        signals.append("conversation_length_threshold")
        reasons.append(f"對話長度已達 {message_count} 則訊息。")
    if tool_call_count >= MIN_TOOL_CALLS_FOR_ADVISE:
        signals.append("tool_call_threshold")
        reasons.append(f"工具調用已達 {tool_call_count} 次。")
    if elapsed_minutes is not None and elapsed_minutes >= MIN_ELAPSED_MINUTES_FOR_ADVISE:
        signals.append("elapsed_time_threshold")
        reasons.append(f"任務已進行約 {elapsed_minutes} 分鐘。")

    completion = task_execution.get("completion_percent")
    if completion is not None:
        signals.append("task_completion_available")
        reasons.append(f"任務完成度約 {completion}%。")
    if task_execution.get("handoff_ready"):
        signals.append("task_handoff_boundary")
        reasons.append("任務進度已接近可交接邊界。")
    if task_execution.get("needs_follow_up"):
        signals.append("task_follow_up_needed")
        reasons.append("仍有進行中、待辦或驗證未完成的工作。")

    strong_signals = 0
    if message_count >= MIN_MESSAGES_FOR_RECOMMEND:
        strong_signals += 1
    if tool_call_count >= MIN_TOOL_CALLS_FOR_RECOMMEND:
        strong_signals += 1
    if elapsed_minutes is not None and elapsed_minutes >= MIN_ELAPSED_MINUTES_FOR_RECOMMEND:
        strong_signals += 1

    context_signals = len(
        [
            signal
            for signal in (
                message_count >= MIN_MESSAGES_FOR_ADVISE,
                tool_call_count >= MIN_TOOL_CALLS_FOR_ADVISE,
                elapsed_minutes is not None and elapsed_minutes >= MIN_ELAPSED_MINUTES_FOR_ADVISE,
            )
            if signal
        ]
    )

    level: str | None = None
    if strong_signals >= 2:
        level = "recommend"
    elif context_signals >= 2:
        level = "advise"
    elif context_signals >= 1 and task_execution.get("has_signal"):
        level = "advise"

    if level == "advise" and task_execution.get("handoff_ready") and context_signals >= 2:
        level = "recommend"

    return signals, reasons, level


def _safe_dialogue(dialogue: dict[str, Any]) -> tuple[dict[str, Any], int, bool]:
    try:
        result = redact_obj(dialogue)
    except RedactionBlocked:
        return (
            {
                "found": False,
                "session_id": None,
                "session_title": None,
                "message_count": 0,
                "conversation_summary": "",
                "signals": {},
                "error": "Dialogue context contained blocked sensitive material",
            },
            0,
            True,
        )
    value = result.value if isinstance(result.value, dict) else {}
    return value, result.redaction_count, False


def _build_handoff_prompt(
    *,
    level: str,
    session_id: str,
    source_platform: str,
    source_chat_id: str,
    message_count: int,
    tool_call_count: int,
    elapsed_minutes: int | None,
    model: str,
    dialogue: dict[str, Any],
    task_execution: dict[str, Any],
    reasons: list[str],
) -> str:
    """Build a concise, pasteable handoff draft without writing a packet."""

    title = dialogue.get("session_title") or "未命名對話"
    source_hint = f"{source_platform}:{source_chat_id[:12]}..." if source_chat_id else source_platform
    elapsed = f"{elapsed_minutes} 分鐘" if elapsed_minutes is not None else "未提供"
    completion = task_execution.get("completion_percent")
    completion_text = f"{completion}%" if completion is not None else "未提供"
    summary = str(dialogue.get("conversation_summary") or "").strip()
    signals = dialogue.get("signals") if isinstance(dialogue.get("signals"), dict) else {}
    last_user = str(signals.get("last_user_request") or "").strip()
    last_ai = str(signals.get("last_ai_response_excerpt") or "").strip()

    lines = [
        "## Hermes Conversation Handoff Draft",
        "",
        f"- 建議等級: {level}",
        f"- Session: {session_id or 'unknown'}",
        f"- 來源: {source_hint}",
        f"- 標題: {title}",
        f"- Model: {model or 'unknown'}",
        f"- 對話長度: {message_count} 則訊息",
        f"- 工具調用: {tool_call_count} 次",
        f"- 已進行時間: {elapsed}",
        f"- 任務完成度: {completion_text}",
        "",
        "### 觸發原因",
    ]
    lines.extend(f"- {reason}" for reason in reasons[:6])

    if last_user:
        lines.extend(["", "### 最後使用者需求", last_user[:500]])
    if last_ai:
        lines.extend(["", "### 最後助手回應摘要", last_ai[:500]])
    if summary:
        lines.extend(["", "### 最近對話摘要", summary[:1800]])

    lines.extend(
        [
            "",
            "### 建議下一步",
            "- 請使用者確認是否要開新對話。",
            "- 若同意，先執行 /handoff prepare 預覽交接內容。",
            "- 新對話開始後貼上這份草稿，並要求先核對狀態再繼續。",
        ]
    )
    return "\n".join(lines)


def format_turn_advice(result: dict[str, Any]) -> str:
    """Render a short user-facing restart advisory from ``evaluate_turn``."""

    level = result.get("level", "advise")
    metrics = result.get("metrics", {})
    task = result.get("task_execution", {})
    elapsed = metrics.get("elapsed_minutes")
    elapsed_text = f"{elapsed} 分鐘" if elapsed is not None else "未提供"
    completion = task.get("completion_percent")
    completion_text = f"{completion}%" if completion is not None else "未提供"

    lines = [
        "建議重啟對話並建立 handoff" if level == "recommend" else "建議準備 handoff",
        f"對話 {metrics.get('message_count', 0)} 則、工具 {metrics.get('tool_call_count', 0)} 次、時間 {elapsed_text}、完成度 {completion_text}。",
        "理由:",
    ]
    lines.extend(f"- {reason}" for reason in result.get("reasons", [])[:5])
    lines.append("下一步: 回覆 /handoff prepare 預覽交接內容；確認後再開新對話。")
    return "\n".join(lines)


def evaluate_turn(
    *,
    session_id: str,
    source_platform: str,
    source_chat_id: str,
    message_count: int,
    tool_call_count: int,
    model: str,
    elapsed_minutes: int | None = None,
    task_completion: Any = None,
    completed_tasks: Any = None,
    total_tasks: Any = None,
    pending_tasks: Any = None,
    failing_gates: Any = None,
    not_run_gates: Any = None,
    active_task: str = "",
) -> dict[str, Any] | None:
    """Evaluate a single turn and return advisory payload or None.

    This is the entry point called by the on_turn_complete hook handler.
    Returns ``None`` when no advisory is warranted (silent). Returns a
    dict with level + details when a threshold is met.
    """
    if not source_platform or not source_chat_id:
        return None

    normalized_message_count = _nonnegative_int(message_count)
    normalized_tool_calls = _nonnegative_int(tool_call_count)
    normalized_elapsed = _optional_nonnegative_int(elapsed_minutes)
    task_execution = _task_execution_state(
        task_completion=task_completion,
        completed_tasks=completed_tasks,
        total_tasks=total_tasks,
        pending_tasks=pending_tasks,
        failing_gates=failing_gates,
        not_run_gates=not_run_gates,
        active_task=active_task,
    )
    signals, reasons, level = _risk_signals(
        message_count=normalized_message_count,
        tool_call_count=normalized_tool_calls,
        elapsed_minutes=normalized_elapsed,
        task_execution=task_execution,
    )

    if level is None:
        return None  # Silent — nothing to report

    # ── Run doctor silently (plugin mode) ────────────────────────────────
    # We use the doctor in plugin mode: no repo_path needed, just
    # source_platform + source_chat_id to query state.db for dialogue.
    from .doctor import evaluate_handoff_recommendation
    from .dialogue_context import collect_dialogue_context

    dialogue = collect_dialogue_context(source_platform, source_chat_id, session_id=session_id)
    safe_dialogue, redaction_count, blocked_dialogue = _safe_dialogue(dialogue)
    doctor_result = evaluate_handoff_recommendation(
        repo_path=".",  # Placeholder — auto-detected as plugin mode via source_platform
        goal="",
        next_task="",
        auto_task_state=False,
        explicit_request=False,
        session_id=session_id,
        source_platform=source_platform,
        source_chat_id=source_chat_id,
    )

    if blocked_dialogue:
        signals.append("dialogue_context_blocked")
        reasons.append("對話上下文包含高風險敏感內容，已略過原文摘要。")
    elif redaction_count > 0:
        signals.append("dialogue_context_redacted")
        reasons.append("對話上下文中的疑似敏感內容已遮蔽。")

    payload = {
        "level": level,
        "session_id": session_id,
        "source_platform": source_platform,
        "source_chat_id": source_chat_id,
        "message_count": normalized_message_count,
        "tool_call_count": normalized_tool_calls,
        "elapsed_minutes": normalized_elapsed,
        "model": model,
        "signals": signals,
        "reasons": reasons,
        "restart_recommended": level == "recommend",
        "handoff_recommended": True,
        "task_execution": task_execution,
        "metrics": {
            "message_count": normalized_message_count,
            "tool_call_count": normalized_tool_calls,
            "elapsed_minutes": normalized_elapsed,
        },
        "dialogue": safe_dialogue,
        "doctor": doctor_result.to_dict(),
    }
    payload["handoff_prompt"] = _build_handoff_prompt(
        level=level,
        session_id=session_id,
        source_platform=source_platform,
        source_chat_id=source_chat_id,
        message_count=normalized_message_count,
        tool_call_count=normalized_tool_calls,
        elapsed_minutes=normalized_elapsed,
        model=model,
        dialogue=safe_dialogue,
        task_execution=task_execution,
        reasons=reasons,
    )
    payload["notice"] = format_turn_advice(payload)
    return payload
