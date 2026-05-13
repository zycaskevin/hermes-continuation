"""Tests for auto_doctor: threshold-based handoff advisory."""
from __future__ import annotations

from hermes_continuation.auto_doctor import evaluate_turn


def test_below_threshold_returns_none():
    """Below advise threshold (100msg+60tools) → silent (None)."""
    result = evaluate_turn(
        session_id="s1",
        source_platform="feishu",
        source_chat_id="test",
        message_count=50,
        tool_call_count=30,
        model="gpt-4",
    )
    assert result is None, "Should be silent below threshold"


def test_empty_source_returns_none():
    """Missing source platform/chat_id → silent."""
    result = evaluate_turn(
        session_id="s1",
        source_platform="",
        source_chat_id="",
        message_count=200,
        tool_call_count=120,
        model="gpt-4",
    )
    assert result is None, "Should be silent without source context"


def test_cli_platform_returns_graceful():
    """CLI platform → threshold met, dialogue gracefully unavailable."""
    result = evaluate_turn(
        session_id="s1",
        source_platform="cli",
        source_chat_id="test",
        message_count=200,
        tool_call_count=120,
        model="gpt-4",
    )
    assert result is not None
    assert result["level"] == "recommend"
    assert result["dialogue"]["found"] is False
    assert "CLI/TUI" in result["dialogue"]["error"]


def test_tui_platform_returns_graceful():
    """TUI platform → threshold met, dialogue gracefully unavailable."""
    result = evaluate_turn(
        session_id="s1",
        source_platform="tui",
        source_chat_id="test",
        message_count=200,
        tool_call_count=120,
        model="gpt-4",
    )
    assert result is not None
    assert result["level"] == "recommend"
    assert result["dialogue"]["found"] is False
    assert "CLI/TUI" in result["dialogue"]["error"]


def test_advise_threshold_met():
    """≥100 messages and ≥60 tool calls → advisory level."""
    result = evaluate_turn(
        session_id="s1",
        source_platform="feishu",
        source_chat_id="test_chat",
        message_count=120,
        tool_call_count=70,
        model="gpt-4",
    )
    assert result is not None
    assert result["level"] == "advise"
    assert result["session_id"] == "s1"
    assert result["message_count"] == 120
    assert result["tool_call_count"] == 70
    assert result["restart_recommended"] is False
    assert result["handoff_recommended"] is True
    assert "conversation_length_threshold" in result["signals"]
    assert "tool_call_threshold" in result["signals"]
    assert "handoff_prompt" in result
    assert "/handoff prepare" in result["notice"]
    assert result["model"] == "gpt-4"


def test_recommend_threshold_met():
    """≥200 messages and ≥120 tool calls → recommend level."""
    result = evaluate_turn(
        session_id="s1",
        source_platform="feishu",
        source_chat_id="test_chat",
        message_count=250,
        tool_call_count=130,
        model="gpt-4",
    )
    assert result is not None
    assert result["level"] == "recommend"
    assert result["restart_recommended"] is True


def test_advise_at_exact_boundary():
    """Exactly 100 messages and 60 tool calls → advise."""
    result = evaluate_turn(
        session_id="s1",
        source_platform="feishu",
        source_chat_id="test_chat",
        message_count=100,
        tool_call_count=60,
        model="gpt-4",
    )
    assert result is not None
    assert result["level"] == "advise"


def test_recommend_at_exact_boundary():
    """Exactly 200 messages and 120 tool calls → recommend."""
    result = evaluate_turn(
        session_id="s1",
        source_platform="feishu",
        source_chat_id="test_chat",
        message_count=200,
        tool_call_count=120,
        model="gpt-4",
    )
    assert result is not None
    assert result["level"] == "recommend"


def test_high_messages_but_few_tools():
    """Many messages but few tool calls → silent."""
    result = evaluate_turn(
        session_id="s1",
        source_platform="feishu",
        source_chat_id="test_chat",
        message_count=150,
        tool_call_count=10,
        model="gpt-4",
    )
    assert result is None, "Should be silent with few tool calls"


def test_many_tools_but_few_messages():
    """Many tool calls but few messages → silent."""
    result = evaluate_turn(
        session_id="s1",
        source_platform="feishu",
        source_chat_id="test_chat",
        message_count=30,
        tool_call_count=90,
        model="gpt-4",
    )
    assert result is None, "Should be silent with few messages"


def test_one_workflow_cycle_not_enough():
    """A single workflow (30-50 msg+tools) should NOT trigger advisory."""
    result = evaluate_turn(
        session_id="s1",
        source_platform="feishu",
        source_chat_id="test_chat",
        message_count=45,
        tool_call_count=40,
        model="gpt-4",
    )
    assert result is None, "Single workflow cycle should be silent"


def test_dialogue_context_key_in_result():
    """Result dict includes dialogue context."""
    result = evaluate_turn(
        session_id="s1",
        source_platform="feishu",
        source_chat_id="nonexistent",
        message_count=200,
        tool_call_count=120,
        model="gpt-4",
    )
    assert result is not None
    assert "dialogue" in result
    assert "found" in result["dialogue"]


def test_doctor_result_in_result():
    """Result dict includes doctor evaluation."""
    result = evaluate_turn(
        session_id="s1",
        source_platform="feishu",
        source_chat_id="nonexistent",
        message_count=200,
        tool_call_count=120,
        model="gpt-4",
    )
    assert result is not None
    assert "doctor" in result
    assert isinstance(result["doctor"], dict)


def test_elapsed_time_with_active_task_triggers_advise():
    """Elapsed time can trigger when there is active task evidence."""
    result = evaluate_turn(
        session_id="s1",
        source_platform="feishu",
        source_chat_id="test_chat",
        message_count=20,
        tool_call_count=10,
        elapsed_minutes=60,
        active_task="Finish release checklist",
        model="gpt-4",
    )
    assert result is not None
    assert result["level"] == "advise"
    assert "elapsed_time_threshold" in result["signals"]
    assert "task_follow_up_needed" in result["signals"]
    assert result["task_execution"]["active_task_present"] is True


def test_task_completion_strengthens_restart_recommendation():
    """Near-complete work plus context risk recommends a restart handoff."""
    result = evaluate_turn(
        session_id="s1",
        source_platform="feishu",
        source_chat_id="test_chat",
        message_count=125,
        tool_call_count=75,
        elapsed_minutes=50,
        task_completion=0.8,
        not_run_gates=["browser smoke"],
        model="gpt-4",
    )
    assert result is not None
    assert result["level"] == "recommend"
    assert result["restart_recommended"] is True
    assert result["task_execution"]["completion_percent"] == 80
    assert "task_handoff_boundary" in result["signals"]
    assert "任務完成度約 80%" in result["handoff_prompt"]


def test_task_completion_alone_is_silent_to_avoid_noise():
    """Task completeness alone should not prompt without context risk."""
    result = evaluate_turn(
        session_id="s1",
        source_platform="feishu",
        source_chat_id="test_chat",
        message_count=10,
        tool_call_count=2,
        task_completion=95,
        model="gpt-4",
    )
    assert result is None
