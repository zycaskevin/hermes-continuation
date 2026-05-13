"""Collect conversation context from Hermes state.db for handoff advisory.

This is the key piece that makes handoff about *dialogue context*, not just
filesystem state.  Given a source_platform + source_chat_id (e.g.
"feishu:oc_703c7e05..."), it finds the most recent active session in
state.db and extracts the last N messages as structured context.

Architecture
------------
The Hermes gateway stores every conversation in state.db:

    sessions:  id (TEXT PK), source (TEXT — "{platform}:{chat_id}"),
               started_at, ended_at, title, message_count, ...

    messages:  id (INT PK), session_id (FK → sessions.id),
               role (user/assistant/tool), content, tool_name,
               tool_calls, timestamp, ...

Two FTS5 virtual tables (messages_fts, messages_fts_trigram) enable
full-text search across message content + tool metadata.

Flow
----
1. Compose source_key = f"{platform}:{chat_id}"
2. Query sessions WHERE source = source_key, ORDER BY started_at DESC
   → take the most recent active (or ended) session
3. Query messages WHERE session_id = ?, ORDER BY timestamp DESC
   → take the last N messages
4. Summarise into structured context: topics, recent decisions, last goal

If state.db is unreachable or no session matches, returns empty context.
"""

from __future__ import annotations

import json
import logging
import sqlite3
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

DEFAULT_DB_PATH = Path.home() / ".hermes" / "state.db"

# How many recent messages to fetch for context analysis
RECENT_MESSAGE_LIMIT = 30

# How many messages to include in the summary (recent first)
SUMMARY_MESSAGE_LIMIT = 15


def _find_db() -> Path | None:
    """Return the state.db path if it exists, else None."""
    db = DEFAULT_DB_PATH
    return db if db.is_file() else None


def _open_db(db_path: Path) -> sqlite3.Connection | None:
    """Open state.db read-only, return connection or None on failure."""
    try:
        conn = sqlite3.connect(str(db_path), timeout=2.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA query_only = ON")
        return conn
    except (sqlite3.OperationalError, sqlite3.DatabaseError) as exc:
        logger.debug("Cannot open state.db (%s): %s", db_path, exc)
        return None


def _find_latest_session(
    conn: sqlite3.Connection, source_key: str
) -> dict[str, Any] | None:
    """Find the most recent session matching the source key.

    Prefers active sessions (ended_at IS NULL), falls back to most recent
    ended session.
    """
    cursor = conn.execute(
        "SELECT id, source, title, started_at, ended_at, message_count "
        "FROM sessions "
        "WHERE source = ? "
        "ORDER BY ended_at IS NULL DESC, started_at DESC "
        "LIMIT 1",
        (source_key,),
    )
    row = cursor.fetchone()
    if row is None:
        return None
    return dict(row)


def _fetch_recent_messages(
    conn: sqlite3.Connection,
    session_id: str,
    limit: int = RECENT_MESSAGE_LIMIT,
) -> list[dict[str, Any]]:
    """Fetch the most recent messages for a session, newest first."""
    cursor = conn.execute(
        "SELECT id, role, content, tool_name, tool_calls, timestamp "
        "FROM messages "
        "WHERE session_id = ? "
        "ORDER BY timestamp DESC, id DESC "
        "LIMIT ?",
        (session_id, limit),
    )
    return [dict(row) for row in cursor.fetchall()]


def _fold_messages_into_conversation(
    messages: list[dict[str, Any]],
    max_conversation: int = SUMMARY_MESSAGE_LIMIT,
) -> str:
    """Fold the raw messages into a readable conversation summary.

    Messages are newest-first from SQL; this reverses them so the summary
    reads chronologically.
    """
    if not messages:
        return ""

    # Reverse to chronological order
    chronological = list(reversed(messages))

    # Take the last N for the summary body
    tail = chronological[-max_conversation:]

    lines: list[str] = []
    total = len(chronological)
    if total > max_conversation:
        lines.append(f"<{total - max_conversation} earlier messages omitted>")
        lines.append("")

    for msg in tail:
        role = msg.get("role", "?")
        content = (msg.get("content") or "").strip()
        tool_name = msg.get("tool_name") or ""
        tool_calls_raw = msg.get("tool_calls") or ""

        if role == "user":
            preview = content[:500]
            lines.append(f"👤 User: {preview}")
        elif role == "assistant":
            if tool_calls_raw:
                # Tool-calling turn — show the function name(s)
                try:
                    calls = json.loads(tool_calls_raw) if isinstance(tool_calls_raw, str) else tool_calls_raw
                    if isinstance(calls, list):
                        names = [c.get("function", {}).get("name", "?") for c in calls]
                        lines.append(f"🤖 Assistant → tools: {', '.join(names)}")
                    else:
                        lines.append(f"🤖 Assistant → tools: {tool_name or '?'}")
                except (json.JSONDecodeError, TypeError):
                    lines.append(f"🤖 Assistant → tools: {tool_name or '?'}")
            elif content:
                preview = content[:500]
                # Only include substantial responses to keep summary readable
                if len(content) > 20:
                    lines.append(f"🤖 Assistant: {preview}")
            else:
                lines.append(f"🤖 Assistant: <empty response>")
        elif role == "tool":
            result_preview = (content or "")[:120]
            lines.append(f"🔧 Tool ({tool_name or '?'}): {result_preview}")

    return "\n".join(lines)


def _summarise_conversation(messages: list[dict[str, Any]]) -> dict[str, Any]:
    """Extract high-level conversation signals from the message list."""
    # Chronological order
    chronological = list(reversed(messages))

    last_user_msg = ""
    last_ai_msg = ""
    user_turn_count = 0
    tool_names: set[str] = set()
    topics: list[str] = []

    for msg in chronological:
        role = msg.get("role", "")
        content = (msg.get("content") or "").strip()
        tool_name = msg.get("tool_name") or ""
        tool_calls_raw = msg.get("tool_calls") or ""

        if role == "user":
            user_turn_count += 1
            if content and not last_user_msg:
                last_user_msg = content[:300]

        elif role == "assistant":
            if content and not last_ai_msg and len(content) > 30:
                last_ai_msg = content[:300]
            if tool_calls_raw:
                try:
                    calls = json.loads(tool_calls_raw) if isinstance(tool_calls_raw, str) else tool_calls_raw
                    if isinstance(calls, list):
                        for c in calls:
                            name = c.get("function", {}).get("name", "")
                            if name:
                                tool_names.add(name)
                except (json.JSONDecodeError, TypeError):
                    if tool_name:
                        tool_names.add(tool_name)
            elif tool_name:
                tool_names.add(tool_name)

        elif role == "tool":
            pass  # Don't add tool names from result messages

    return {
        "user_turn_count": user_turn_count,
        "last_user_request": last_user_msg,
        "last_ai_response_excerpt": last_ai_msg,
        "tools_used": sorted(tool_names),
        "has_recent_conversation": len(chronological) >= 3,
    }


def collect_dialogue_context(
    source_platform: str | None,
    source_chat_id: str | None,
    *,
    session_id: str | None = None,
    db_path: Path | str | None = None,
) -> dict[str, Any]:
    """Collect conversation context from state.db for the given source.

    When ``session_id`` is provided, it takes precedence — that specific session
    is queried directly. Otherwise, the function finds the most recent active
    session matching the source.

    Returns a dict with keys:
        found              — bool, whether a matching session was found
        session_id         — str | None
        session_title      — str | None
        message_count      — int
        conversation_summary — str (folded text of recent messages)
        signals            — dict (user_turn_count, last_user_request, etc.)
        error              — str | None

    Returns ``found=False`` if state.db is unavailable or no session matches.
    """
    if not source_platform or not source_chat_id:
        return {
            "found": False,
            "session_id": None,
            "session_title": None,
            "message_count": 0,
            "conversation_summary": "",
            "signals": {},
            "error": "No source context provided",
        }

    if source_platform in ("cli", "tui"):
        return {
            "found": False,
            "session_id": None,
            "session_title": None,
            "message_count": 0,
            "conversation_summary": "",
            "signals": {},
            "error": "CLI/TUI sessions have no persistent dialogue context",
        }

    source_key = f"{source_platform}:{source_chat_id}"

    db = _find_db()
    if db is None:
        return {
            "found": False,
            "session_id": None,
            "session_title": None,
            "message_count": 0,
            "conversation_summary": "",
            "signals": {},
            "error": "state.db not found",
        }

    conn = _open_db(db)
    if conn is None:
        return {
            "found": False,
            "session_id": None,
            "session_title": None,
            "message_count": 0,
            "conversation_summary": "",
            "signals": {},
            "error": "Cannot open state.db",
        }

    try:
        # If a specific session_id is given, query it directly (most precise)
        resolved_session_id: str | None = None
        resolved_msg_count: int = 0
        resolved_title: str | None = None

        if session_id:
            cursor = conn.execute(
                "SELECT id, title, message_count FROM sessions WHERE id = ?",
                (session_id,),
            )
            row = cursor.fetchone()
            if row is not None:
                resolved_session_id = row["id"]
                resolved_msg_count = row["message_count"] or 0
                resolved_title = row["title"]

        if resolved_session_id is None:
            # Fall back to source-based lookup
            # Try composite key first, then platform-only
            session = _find_latest_session(conn, source_key)
            if session is None:
                session = _find_latest_session(conn, source_platform)
            if session is not None:
                resolved_session_id = session["id"]
                resolved_msg_count = session.get("message_count", 0)
                resolved_title = session.get("title")

        if resolved_session_id is None:
            return {
                "found": False,
                "session_id": None,
                "session_title": None,
                "message_count": 0,
                "conversation_summary": "",
                "signals": {},
                "error": f"No session found for source: {source_key}",
            }

        messages = _fetch_recent_messages(conn, resolved_session_id)

        conversation_summary = _fold_messages_into_conversation(messages)
        signals = _summarise_conversation(messages)


        return {
            "found": True,
            "session_id": resolved_session_id,
            "session_title": resolved_title,
            "message_count": resolved_msg_count,
            "conversation_summary": conversation_summary,
            "signals": signals,
            "error": None,
        }
    finally:
        try:
            conn.close()
        except Exception:
            pass
