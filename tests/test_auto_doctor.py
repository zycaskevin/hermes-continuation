"""Tests for auto_doctor: threshold-based handoff advisory."""
from __future__ import annotations

from hermes_continuation.auto_doctor import evaluate_turn


def test_below_threshold_returns_none():
    """Less than 20 messages and 10 tool calls → silent (None)."""
    result = evaluate_turn(
        session_id="s1",
        source_platform="feishu",
        source_chat_id="test",
        message_count=5,
        tool_call_count=2,
        model="gpt-4",
    )
    assert result is None, "Should be silent below threshold"


def test_empty_source_returns_none():
    """Missing source platform/chat_id → silent."""
    result = evaluate_turn(
        session_id="s1",
        source_platform="",
        source_chat_id="",
        message_count=40,
        tool_call_count=25,
        model="gpt-4",
    )
    assert result is None, "Should be silent without source context"


def test_cli_platform_returns_graceful():
    """CLI platform → threshold met, dialogue gracefully unavailable."""
    result = evaluate_turn(
        session_id="s1",
        source_platform="cli",
        source_chat_id="test",
        message_count=40,
        tool_call_count=25,
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
        message_count=40,
        tool_call_count=25,
        model="gpt-4",
    )
    assert result is not None
    assert result["level"] == "recommend"
    assert result["dialogue"]["found"] is False
    assert "CLI/TUI" in result["dialogue"]["error"]


def test_advise_threshold_met():
    """≥20 messages and ≥10 tool calls → advisory level."""
    result = evaluate_turn(
        session_id="s1",
        source_platform="feishu",
        source_chat_id="test_chat",
        message_count=25,
        tool_call_count=12,
        model="gpt-4",
    )
    assert result is not None
    assert result["level"] == "advise"
    assert result["session_id"] == "s1"
    assert result["message_count"] == 25
    assert result["tool_call_count"] == 12
    assert result["model"] == "gpt-4"


def test_recommend_threshold_met():
    """≥35 messages and ≥20 tool calls → recommend level."""
    result = evaluate_turn(
        session_id="s1",
        source_platform="feishu",
        source_chat_id="test_chat",
        message_count=40,
        tool_call_count=25,
        model="gpt-4",
    )
    assert result is not None
    assert result["level"] == "recommend"


def test_advise_at_exact_boundary():
    """Exactly 20 messages and 10 tool calls → advise."""
    result = evaluate_turn(
        session_id="s1",
        source_platform="feishu",
        source_chat_id="test_chat",
        message_count=20,
        tool_call_count=10,
        model="gpt-4",
    )
    assert result is not None
    assert result["level"] == "advise"


def test_recommend_at_exact_boundary():
    """Exactly 35 messages and 20 tool calls → recommend."""
    result = evaluate_turn(
        session_id="s1",
        source_platform="feishu",
        source_chat_id="test_chat",
        message_count=35,
        tool_call_count=20,
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
        message_count=50,
        tool_call_count=2,
        model="gpt-4",
    )
    assert result is None, "Should be silent with few tool calls"


def test_many_tools_but_few_messages():
    """Many tool calls but few messages → silent."""
    result = evaluate_turn(
        session_id="s1",
        source_platform="feishu",
        source_chat_id="test_chat",
        message_count=5,
        tool_call_count=30,
        model="gpt-4",
    )
    assert result is None, "Should be silent with few messages"


def test_dialogue_context_key_in_result():
    """Result dict includes dialogue context (may be empty if no real state.db)."""
    result = evaluate_turn(
        session_id="s1",
        source_platform="feishu",
        source_chat_id="nonexistent",
        message_count=35,
        tool_call_count=20,
        model="gpt-4",
    )
    assert result is not None
    assert "dialogue" in result
    # dialogue.found will be False since we don't have a real state.db in tests
    assert "found" in result["dialogue"]


def test_doctor_result_in_result():
    """Result dict includes doctor evaluation."""
    result = evaluate_turn(
        session_id="s1",
        source_platform="feishu",
        source_chat_id="nonexistent",
        message_count=35,
        tool_call_count=20,
        model="gpt-4",
    )
    assert result is not None
    assert "doctor" in result
    assert isinstance(result["doctor"], dict)
