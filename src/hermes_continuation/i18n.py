"""Locale-aware text strings for hermes-continuation user-facing output.

Design rule: logic/JSON fields use English identifiers; format functions use
this module to render human-readable Traditional Chinese when ``locale`` is
set to ``zh-TW`` (the default for Arthur).
"""

from __future__ import annotations

from typing import Literal

LocaleTag = Literal["en", "zh-TW"]

_DEFAULT_LOCALE: LocaleTag = "zh-TW"

# ── level labels ──

_LEVEL_LABELS: dict[str, dict[LocaleTag, str]] = {
    "observe": {"en": "Observe", "zh-TW": "👀 觀察"},
    "advise": {"en": "Advise", "zh-TW": "💡 建議交接"},
    "prepare": {"en": "Prepare", "zh-TW": "📋 可準備交接"},
    "block": {"en": "Block", "zh-TW": "🚫 安全阻擋"},
}

_LEVEL_SUMMARIES: dict[str, dict[LocaleTag, str]] = {
    "observe": {
        "en": "No handoff recommendation threshold was reached.",
        "zh-TW": "✅ 一切正常，目前不需要交接。",
    },
    "advise": {
        "en": "A handoff may be useful, but required safe state is incomplete or verification needs attention.",
        "zh-TW": "⚠️ 建議做交接，但目前還缺一些資訊（目標、下一步，或測試還沒跑）。",
    },
    "prepare": {
        "en": "Safe explicit state is available to suggest an exact handoff create command.",
        "zh-TW": "📋 資料齊全！可以直接預覽交接包內容。",
    },
    "block": {
        "en": "Safety checks blocked handoff preparation.",
        "zh-TW": "🚫 安全檢查發現問題，已阻擋交接。",
    },
}

# ── signal labels ──

_SIGNAL_LABELS: dict[str, dict[LocaleTag, str]] = {
    "dirty_git_state": {"en": "uncommitted changes", "zh-TW": "有未存檔的修改"},
    "failing_gates": {"en": "failed verification", "zh-TW": "有測試失敗"},
    "not_run_gates": {"en": "unverified gates", "zh-TW": "有測試還沒跑"},
    "known_blockers": {"en": "known blockers", "zh-TW": "有已知障礙"},
    "safety_boundaries": {"en": "safety boundaries", "zh-TW": "有安全邊界限制"},
    "git_state_incomplete": {"en": "no git repo", "zh-TW": "不是 Git 專案"},
    "task_state_available": {"en": "docs found", "zh-TW": "找到專案文檔"},
    "auto_task_state_disabled": {"en": "auto-scan off", "zh-TW": "自動收集已關閉"},
    "explicit_request": {"en": "manual request", "zh-TW": "手動請求"},
    "private_key_detected": {"en": "private key", "zh-TW": "偵測到私鑰"},
    "sensitive_value_redacted": {"en": "secrets redacted", "zh-TW": "已遮蔽敏感內容"},
    "missing_required_prepare_input": {"en": "incomplete input", "zh-TW": "資訊不完整"},
}

# ── reason messages ──

_REASON_MESSAGES: dict[str, dict[LocaleTag, str]] = {
    "dirty_git_state": {
        "en": "Repository has uncommitted changes.",
        "zh-TW": "專案中有還沒 commit 的修改。",
    },
    "failing_gates": {
        "en": "One or more verification gates are currently failing.",
        "zh-TW": "有測試目前是失敗的狀態。",
    },
    "not_run_gates": {
        "en": "One or more verification gates have not been run.",
        "zh-TW": "有些測試還沒跑過。",
    },
    "known_blockers": {
        "en": "Repository task state lists known blockers.",
        "zh-TW": "專案文檔中有記錄已知的障礙。",
    },
    "safety_boundaries": {
        "en": "Repository task state includes safety boundaries to preserve.",
        "zh-TW": "專案文檔中有標記不可碰觸的區域。",
    },
    "git_state_incomplete": {
        "en": "Git state is unavailable or the path is not a Git work tree.",
        "zh-TW": "無法讀取 Git 狀態，可能不是 Git 專案。",
    },
}

# ── recommendation text ──

_RECOMMENDATION_TEXT: dict[str, dict[LocaleTag, str]] = {
    "advise_default": {
        "en": "Consider creating a handoff after resolving blockers or supplying complete safe inputs.",
        "zh-TW": "建議補上目標和下一步的資訊後再產生交接包，或先用 /handoff prepare 預覽看看。",
    },
    "observe_default": {
        "en": "Continue working; no read-only handoff advisory is needed right now.",
        "zh-TW": "目前一切乾淨，專心開發就好！",
    },
    "block_private_key": {
        "en": "Remove or redact the sensitive material before preparing a handoff.",
        "zh-TW": "請先移除專案中的私鑰或敏感資料再產生交接包。",
    },
    "block_secrets": {
        "en": "Review and remove credential-like values before preparing a handoff.",
        "zh-TW": "請檢查並移除專案中的密碼/token 再產生交接包。",
    },
    "prepare_ready": {
        "en": "Review the suggested command and run it only if you want to create a handoff packet.",
        "zh-TW": "以下是建議的交接指令，確認沒問題後再手動執行。",
    },
    "explicit_missing": {
        "en": "Explicit handoff request is missing {missing}.",
        "zh-TW": "手動請求交接但缺少 {missing}。",
    },
    "partial_input": {
        "en": "Only partial prepare input is available; missing goal or next task prevents an exact command.",
        "zh-TW": "目標或下一步資訊不完全，無法產生精確的交接指令。",
    },
    "dirty_but_complete": {
        "en": "Complete prepare input exists, but dirty/incomplete repository or verification state keeps this advisory-only.",
        "zh-TW": "資訊齊全但專案有未存檔修改或測試未完成，先處理這些再交接更安全。",
    },
}

# ── block reasons ──

_BLOCK_REASONS: dict[str, dict[LocaleTag, str]] = {
    "safety_first": {
        "en": "Safety blockers override convenience signals.",
        "zh-TW": "安全優先，不因方便而妥協。",
    },
    "private_key_input": {
        "en": "Sensitive private-key material was detected in supplied input.",
        "zh-TW": "在輸入內容中偵測到私鑰資料。",
    },
    "private_key_repo": {
        "en": "Sensitive private-key material was detected in repository metadata.",
        "zh-TW": "在專案 metadata 中偵測到私鑰資料。",
    },
    "private_key_docs": {
        "en": "Sensitive private-key material was detected in repository documentation.",
        "zh-TW": "在專案文檔中偵測到私鑰資料。",
    },
    "secrets_redacted": {
        "en": "Sensitive credential-like material was redacted from available state.",
        "zh-TW": "已從資料中遮蔽疑似密碼/token 的內容。",
    },
}

# ── format labels ──

_FORMAT_LABELS: dict[str, dict[LocaleTag, str]] = {
    "doctor_title": {"en": "Handoff doctor", "zh-TW": "🩺 交接醫生診斷"},
    "prepare_title": {"en": "Handoff prepare preview", "zh-TW": "📋 交接包預覽"},
    "watch_title": {"en": "Handoff watch", "zh-TW": "👀 交接掃描"},
    "read_only": {"en": "Read-only: would_write=false; no handoff packet was created.", "zh-TW": "🔒 純讀取模式：沒有寫出任何交接包檔案。"},
    "read_only_watch": {"en": "Read-only watch: would_write=false; no handoff packet was created.", "zh-TW": "🔒 純掃描模式：沒有寫出任何交接包檔案。"},
    "recommendation": {"en": "Recommendation", "zh-TW": "💬 建議"},
    "reasons": {"en": "Reasons", "zh-TW": "🔍 原因"},
    "blockers": {"en": "Blockers", "zh-TW": "🚫 阻擋"},
    "signals": {"en": "Signals", "zh-TW": "📡 偵測訊號"},
    "watch_signals": {"en": "Watch signals", "zh-TW": "📡 掃描訊號"},
    "output_dir": {"en": "Output directory if create is run later", "zh-TW": "📁 交接包輸出位置"},
    "safety_status": {"en": "Safety status", "zh-TW": "🔒 安全狀態"},
    "verification_status": {"en": "Verification status", "zh-TW": "🧪 驗證狀態"},
    "proposed_goal": {"en": "Proposed goal", "zh-TW": "🎯 目標"},
    "proposed_next": {"en": "Proposed next_task", "zh-TW": "➡️ 下一步"},
    "safe_create_command": {"en": "Safe create command (run only if you want to write a packet)", "zh-TW": "📝 安全的交接指令（確認後手動執行）"},
    "no_create_command": {"en": "No create command was run; watch is advisory only.", "zh-TW": "🔒 純建議模式，沒有執行任何寫入操作。"},
    "prepare_preview_label": {"en": "Prepare preview", "zh-TW": "📋 預覽內容"},
    "footer_read_only": {"en": "Read-only: no handoff packet was created, no session was restarted, and no agent was launched.", "zh-TW": "🔒 純讀取：沒有寫出交接包、沒有重啟對話、沒有啟動新 Agent。"},
    "safety_blocked": {"en": "blocked", "zh-TW": "🚫 已阻擋"},
    "safety_safe": {"en": "safe", "zh-TW": "✅ 安全"},
    "verification_failing": {"en": "failing", "zh-TW": "❌ 有失敗"},
    "verification_not_run": {"en": "not_run", "zh-TW": "⏳ 尚未執行"},
    "verification_verified": {"en": "verified", "zh-TW": "✅ 已通過"},
    "verification_not_provided": {"en": "not_provided", "zh-TW": "📭 未提供"},
    "field_goal": {"en": "goal", "zh-TW": "目標"},
    "field_next_task": {"en": "next task", "zh-TW": "下一步"},
}


# ── public API ──

_session_locale: LocaleTag = _DEFAULT_LOCALE


def set_locale(locale: LocaleTag) -> None:
    """Set the session locale for all subsequent i18n calls (thread-safe-ish)."""
    global _session_locale
    if locale in ("en", "zh-TW"):
        _session_locale = locale


def current_locale() -> LocaleTag:
    """Return the session locale tag."""
    return _session_locale


def level_label(level: str, locale: LocaleTag | None = None) -> str:
    loc = locale or _session_locale
    return _LEVEL_LABELS.get(level, {}).get(loc, level)


def level_summary(level: str, locale: LocaleTag | None = None) -> str:
    loc = locale or _session_locale
    return _LEVEL_SUMMARIES.get(level, {}).get(loc, level)


def signal_label(signal: str, locale: LocaleTag | None = None) -> str:
    loc = locale or _session_locale
    return _SIGNAL_LABELS.get(signal, {}).get(loc, signal)


def reason_message(reason_key: str, locale: LocaleTag | None = None) -> str:
    """Translate a structured reason key to human-readable text."""
    loc = locale or _session_locale
    return _REASON_MESSAGES.get(reason_key, {}).get(loc, reason_key)


def rec_text(key: str, locale: LocaleTag | None = None, **fmt: str) -> str:
    """Translate recommendation text with optional format substitution."""
    loc = locale or _session_locale
    template = _RECOMMENDATION_TEXT.get(key, {}).get(loc, key)
    if fmt:
        template = template.format(**fmt)
    return template


def block_reason(key: str, locale: LocaleTag | None = None) -> str:
    loc = locale or _session_locale
    return _BLOCK_REASONS.get(key, {}).get(loc, key)


def fmt_label(key: str, locale: LocaleTag | None = None) -> str:
    loc = locale or _session_locale
    return _FORMAT_LABELS.get(key, {}).get(loc, key)
