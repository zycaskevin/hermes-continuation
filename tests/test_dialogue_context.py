"""Tests for dialogue_context: conversation context from Hermes state.db."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from hermes_continuation.dialogue_context import (
    _find_db,
    _open_db,
    _find_latest_session,
    _fetch_recent_messages,
    collect_dialogue_context,
)


def test_no_source_returns_not_found():
    """Missing source platform/chat_id → found=False with error."""
    result = collect_dialogue_context(None, None)
    assert result["found"] is False
    assert result["error"] == "No source context provided"


def test_cli_platform_graceful():
    """CLI platform → found=False with graceful error."""
    result = collect_dialogue_context("cli", "test")
    assert result["found"] is False
    assert "CLI/TUI" in result["error"]


def test_tui_platform_graceful():
    """TUI platform → found=False with graceful error."""
    result = collect_dialogue_context("tui", "test")
    assert result["found"] is False
    assert "CLI/TUI" in result["error"]


def test_find_db_nonexistent():
    """_find_db returns None when no state.db exists."""
    with patch.object(Path, "is_file", return_value=False):
        result = _find_db()
    assert result is None


def test_open_db_nonexistent():
    """_open_db returns None when file doesn't exist."""
    result = _open_db(Path("/nonexistent/state.db"))
    assert result is None


def test_find_latest_session_empty(tmp_path):
    """_find_latest_session returns None for empty DB."""
    db_path = tmp_path / "state.db"
    import sqlite3
    conn = sqlite3.connect(str(db_path))
    conn.execute("CREATE TABLE sessions (id TEXT PRIMARY KEY, source TEXT, title TEXT, started_at TEXT, ended_at TEXT, message_count INTEGER)")
    conn.commit()

    result = _find_latest_session(conn, "feishu:test")
    assert result is None
    conn.close()


def test_fetch_recent_messages_empty(tmp_path):
    """_fetch_recent_messages returns [] for empty session."""
    db_path = tmp_path / "state.db"
    import sqlite3
    conn = sqlite3.connect(str(db_path))
    conn.execute("CREATE TABLE sessions (id TEXT PRIMARY KEY, source TEXT, title TEXT, started_at TEXT, ended_at TEXT, message_count INTEGER)")
    conn.execute("CREATE TABLE messages (id INTEGER PRIMARY KEY, session_id TEXT, role TEXT, content TEXT, tool_name TEXT, tool_calls TEXT, timestamp TEXT)")
    conn.commit()

    result = _fetch_recent_messages(conn, "s1")
    assert result == []
    conn.close()


def test_collect_dialogue_db_not_found(tmp_path):
    """collect_dialogue_context when state.db not found."""
    with patch.object(Path, "is_file", return_value=False):
        result = collect_dialogue_context("feishu", "test_chat")
    assert result["found"] is False
    assert result["error"] == "state.db not found"
