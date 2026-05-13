"""Auto-doctor: threshold-based handoff advisory triggered by on_turn_complete hook.

This module is invoked at the end of every agent turn in the Gateway.
It inspects session metrics (message_count, tool_call_count) against
predefined thresholds and, when appropriate, runs the doctor silently
to produce an advisory payload.

Key design decisions:
- No chat_context config needed — all data comes from the hook kwargs
  plus state.db (queried via dialogue_context).
- Doctor runs in plugin mode: no file path, no git state, no task state.
  Only dialogue context and session metrics are consulted.
- Thresholds are conservative to avoid notification spam.
"""

from __future__ import annotations

from typing import Any

# ── Thresholds ──────────────────────────────────────────────────────────────
# These are intentionally conservative. Turn counts are per-session, so a
# long conversation naturally accumulates them.

# Minimum messages before we even consider advising
MIN_MESSAGES_FOR_ADVISE = 20
MIN_TOOL_CALLS_FOR_ADVISE = 10

# Recommend threshold: strong signal the conversation has substantial context
MIN_MESSAGES_FOR_RECOMMEND = 35
MIN_TOOL_CALLS_FOR_RECOMMEND = 20


def evaluate_turn(
    *,
    session_id: str,
    source_platform: str,
    source_chat_id: str,
    message_count: int,
    tool_call_count: int,
    model: str,
) -> dict[str, Any] | None:
    """Evaluate a single turn and return advisory payload or None.

    This is the entry point called by the on_turn_complete hook handler.
    Returns ``None`` when no advisory is warranted (silent). Returns a
    dict with level + details when a threshold is met.
    """
    if not source_platform or not source_chat_id:
        return None

    level: str | None = None

    # ── Threshold check ──────────────────────────────────────────────────
    if message_count >= MIN_MESSAGES_FOR_RECOMMEND and tool_call_count >= MIN_TOOL_CALLS_FOR_RECOMMEND:
        level = "recommend"
    elif message_count >= MIN_MESSAGES_FOR_ADVISE and tool_call_count >= MIN_TOOL_CALLS_FOR_ADVISE:
        level = "advise"

    if level is None:
        return None  # Silent — nothing to report

    # ── Run doctor silently (plugin mode) ────────────────────────────────
    # We use the doctor in plugin mode: no repo_path needed, just
    # source_platform + source_chat_id to query state.db for dialogue.
    from .doctor import evaluate_handoff_recommendation
    from .dialogue_context import collect_dialogue_context

    dialogue = collect_dialogue_context(source_platform, source_chat_id)
    doctor_result = evaluate_handoff_recommendation(
        repo_path=".",  # Placeholder — auto-detected as plugin mode via source_platform
        goal="",
        next_task="",
        auto_task_state=False,
        explicit_request=False,
        source_platform=source_platform,
        source_chat_id=source_chat_id,
    )

    return {
        "level": level,
        "session_id": session_id,
        "source_platform": source_platform,
        "source_chat_id": source_chat_id,
        "message_count": message_count,
        "tool_call_count": tool_call_count,
        "model": model,
        "dialogue": dialogue,
        "doctor": doctor_result.to_dict(),
    }
