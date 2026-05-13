"""Hermes plugin wrapper for the continuation handoff sidecar."""

from __future__ import annotations

import json
import os
import shlex
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from . import i18n
from .git_state import collect_git_state
from .packet import build_packet
from .doctor import evaluate_handoff_recommendation, format_recommendation
from .prepare import build_prepare_preview, format_prepare_preview
from .watch import build_watch_result, format_watch_result
from .redaction import RedactionBlocked
from .render_markdown import render_markdown
from .task_state import collect_task_state, merge_task_state
from .validate import ValidationError, validate_packet

TOOLSET = "hermes_continuation"
CREATE_TOOL = "hermes_handoff_create"
RESUME_TOOL = "hermes_handoff_resume"
PREPARE_TOOL = "hermes_handoff_prepare"
WATCH_TOOL = "hermes_handoff_watch"
DOCTOR_TOOL = "hermes_handoff_doctor"
HANDOFF_COMMAND = "handoff"


_HANDOFF_ARGS_HINT = "create <json|key=value>|resume <handoff.json>|prepare <json|key=value>|watch <json|key=value>|doctor <json|key=value>"

_HANDOFF_HELP = """Hermes handoff command usage:

/handoff create {"repo_path":".","goal":"Current goal","next_task":"Next step","auto_task_state":true}
/handoff create repo_path=. goal="Current goal" next_task="Next step" auto_task_state=true
/handoff {"repo_path":".","goal":"Current goal","next_task":"Next step"}
/handoff prepare {"repo_path":".","goal":"Current goal","next_task":"Next step","auto_task_state":true}
/handoff prepare repo_path=. goal="Current goal" next_task="Next step" auto_task_state=true
/handoff watch {"repo_path":".","goal":"Current goal","next_task":"Next step","tool_calls":10,"elapsed_minutes":35}
/handoff watch repo_path=. goal="Current goal" next_task="Next step" tool_calls=10 elapsed_minutes=35
/handoff doctor {"repo_path":".","goal":"Current goal","next_task":"Next step","auto_task_state":true}
/handoff doctor repo_path=. goal="Current goal" next_task="Next step" auto_task_state=true
/handoff resume .hermes/handoffs/<timestamp>-handoff.json
/handoff resume {"handoff_json":".hermes/handoffs/<timestamp>-handoff.json","markdown":true}

Notes:
- Bare /handoff shows this help instead of creating an underspecified packet.
- Create requires goal and next_task, matching hermes_handoff_create.
- Doctor is read-only; it analyzes local signals and recommends handoff actions.
- Prepare is read-only; it previews advisory state and never writes packet files.
- Watch is read-only one-shot advisory evaluation using local signals and thresholds.
- When invoked from a Gateway chat, doctor/prepare/watch inject
  source_platform and source_chat_id automatically — the doctor queries
  state.db for conversation context without needing a repo_path.
- auto_task_state is opt-in and conservatively reads repo-local docs only.
- locale=en or locale=zh-TW sets the output language (default: zh-TW).
- The plugin command is sidecar-only and does not modify Hermes core.
""".strip()

_LIST_ARG_KEYS = {"completed", "verified", "failing", "not_run", "known_issues", "blockers", "do_not_touch"}
_BOOL_ARG_KEYS = {"markdown", "auto_task_state"}


def _json_response(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False)


def _as_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, tuple):
        return [str(item).strip() for item in value if str(item).strip()]
    text = str(value).strip()
    return [text] if text else []


def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return _parse_bool(str(value))


def _error(exc: Exception | str) -> str:
    return _json_response({"success": False, "error": str(exc)})


def _parse_bool(value: str) -> bool:
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "y", "on"}:
        return True
    if normalized in {"0", "false", "no", "n", "off"}:
        return False
    raise ValueError(f"invalid boolean value: {value}")


def _parse_json_object(text: str) -> dict[str, Any]:
    data = json.loads(text)
    if not isinstance(data, dict):
        raise ValueError("JSON arguments must contain an object")
    return data


def _parse_key_value_args(text: str) -> dict[str, Any]:
    args: dict[str, Any] = {}
    for token in shlex.split(text):
        if "=" not in token:
            raise ValueError(f"expected key=value argument, got: {token}")
        key, value = token.split("=", 1)
        key = key.strip().replace("-", "_")
        if not key:
            raise ValueError("argument key must not be empty")
        if key in _LIST_ARG_KEYS:
            args[key] = [item.strip() for item in value.split(",") if item.strip()]
        elif key in _BOOL_ARG_KEYS:
            args[key] = _parse_bool(value)
        else:
            args[key] = value
    return args


def _parse_create_command_args(text: str) -> dict[str, Any]:
    payload = text.strip()
    if not payload:
        return {}
    if payload.startswith("{"):
        return _parse_json_object(payload)
    return _parse_key_value_args(payload)


def _parse_prepare_command_args(text: str) -> dict[str, Any]:
    payload = text.strip()
    if not payload:
        return {}
    if payload.startswith("{"):
        return _parse_json_object(payload)
    return _parse_key_value_args(payload)


def _parse_resume_command_args(text: str) -> dict[str, Any]:
    payload = text.strip()
    if not payload:
        return {}
    if payload.startswith("{"):
        return _parse_json_object(payload)

    tokens = shlex.split(payload)
    if not tokens:
        raise ValueError("resume requires a handoff JSON path")

    args: dict[str, Any] = {"handoff_json": tokens[0]}
    for token in tokens[1:]:
        if token in {"--markdown", "markdown"}:
            args["markdown"] = True
            continue
        if "=" not in token:
            raise ValueError(f"expected markdown=true/false option, got: {token}")
        key, value = token.split("=", 1)
        key = key.strip().replace("-", "_")
        if key != "markdown":
            raise ValueError(f"unsupported resume option: {key}")
        args["markdown"] = _parse_bool(value)
    return args


def _split_handoff_command(raw_args: str) -> tuple[str, str]:
    text = raw_args.strip()
    if not text:
        return "help", ""

    first, sep, rest = text.partition(" ")
    verb = first.strip().lower()
    if verb in {"help", "--help", "-h"}:
        return "help", ""
    if verb in {"create", "resume", "prepare", "watch", "doctor"}:
        return verb, rest.strip() if sep else ""
    if text.startswith("{") or "=" in first:
        return "create", text
    return verb, rest.strip() if sep else ""


def _load_handler_result(raw: str) -> dict[str, Any]:
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise ValueError("handler returned non-object JSON")
    return data


def _format_create_command_result(result: dict[str, Any]) -> str:
    if not result.get("success"):
        return f"Handoff create failed: {result.get('error', 'unknown error')}"
    return (
        "Created Hermes handoff packet.\n"
        f"- Markdown: {result.get('markdown_path')}\n"
        f"- JSON: {result.get('json_path')}\n"
        f"- Redactions: {result.get('redaction_count', 0)}\n\n"
        f"Resume later with: /handoff resume {result.get('json_path')}"
    )


def _format_resume_command_result(result: dict[str, Any]) -> str:
    if not result.get("success"):
        return f"Handoff resume failed: {result.get('error', 'unknown error')}"
    return str(result.get("output") or result.get("resume_prompt") or "")


def _format_prepare_command_result(result: dict[str, Any]) -> str:
    if not result.get("success"):
        return f"Handoff prepare failed: {result.get('error', 'unknown error')}"
    preview = result.get("preview")
    if not isinstance(preview, dict):
        return "Handoff prepare failed: handler returned missing preview"
    return format_prepare_preview(preview)


def _format_watch_command_result(result: dict[str, Any]) -> str:
    if not result.get("success"):
        return f"Handoff watch failed: {result.get('error', 'unknown error')}"
    return format_watch_result(result)


def _format_doctor_command_result(result: dict[str, Any]) -> str:
    if not result.get("success"):
        return f"Handoff doctor failed: {result.get('error', 'unknown error')}"
    recommendation = result.get("recommendation")
    if not isinstance(recommendation, dict):
        return "Handoff doctor failed: handler returned missing recommendation"
    from .doctor import DoctorRecommendation
    rec = DoctorRecommendation(
        level=recommendation.get("level", "observe"),
        summary=recommendation.get("summary", ""),
        recommendation=recommendation.get("recommendation", ""),
        reasons=recommendation.get("reasons", []),
        blockers=recommendation.get("blockers", []),
        signals=recommendation.get("signals", []),
        repo=recommendation.get("repo", {}),
        verification=recommendation.get("verification", {}),
        task_state_available=recommendation.get("task_state_available", False),
        redaction_count=recommendation.get("redaction_count", 0),
        safe_create_command=recommendation.get("safe_create_command"),
    )
    return format_recommendation(rec)


def _write_packet(packet: dict[str, Any], output_dir: Path) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    md_path = output_dir / f"{timestamp}-handoff.md"
    json_path = output_dir / f"{timestamp}-handoff.json"
    md_path.write_text(render_markdown(packet), encoding="utf-8")
    json_path.write_text(json.dumps(packet, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return md_path, json_path


def hermes_handoff_create(args: dict[str, Any], **_: Any) -> str:
    """Create a handoff packet and return a JSON result envelope."""
    try:
        repo_path = Path(str(args.get("repo_path") or ".")).expanduser().resolve()
        goal = str(args.get("goal") or "").strip()
        next_task = str(args.get("next_task") or args.get("next") or "").strip()
        if not goal:
            return _error("goal must not be empty")
        if not next_task:
            return _error("next_task must not be empty")

        output_arg = args.get("output_dir")
        output_dir = Path(str(output_arg)).expanduser().resolve() if output_arg else repo_path / ".hermes" / "handoffs"
        repo_state = collect_git_state(repo_path)
        auto_task_state = collect_task_state(repo_path, repo_state) if _as_bool(args.get("auto_task_state")) else None
        task_state = merge_task_state(
            auto_task_state,
            completed_work=_as_list(args.get("completed")),
            in_progress=str(args.get("active_task") or args.get("in_progress") or ""),
            known_blockers=_as_list(args.get("known_issues") or args.get("blockers")),
            do_not_touch=_as_list(args.get("do_not_touch")),
            next_task=next_task,
        )

        packet = build_packet(
            current_goal=goal,
            repo=repo_state,
            completed_work=task_state["completed_work"],
            in_progress=task_state["in_progress"],
            known_blockers=task_state["known_blockers"],
            do_not_touch=task_state["do_not_touch"],
            next_recommended_task=task_state["next_recommended_task"],
            verified_gates=_as_list(args.get("verified")),
            failing_gates=_as_list(args.get("failing")),
            not_run_gates=_as_list(args.get("not_run")),
        )
        validate_packet(packet)
        md_path, json_path = _write_packet(packet, output_dir)
        return _json_response(
            {
                "success": True,
                "markdown_path": str(md_path),
                "json_path": str(json_path),
                "resume_prompt": packet["resume_prompt"],
                "redaction_count": packet.get("safety", {}).get("redaction_count", 0),
            }
        )
    except (OSError, RedactionBlocked, ValidationError, ValueError) as exc:
        return _error(exc)


def hermes_handoff_prepare(args: dict[str, Any], **_: Any) -> str:
    """Build a read-only handoff prepare preview and return a JSON result envelope."""
    try:
        if "locale" in args:
            i18n.set_locale(args["locale"])
        repo_path = Path(str(args.get("repo_path") or ".")).expanduser().resolve()
        auto_task_state = _as_bool(args["auto_task_state"]) if "auto_task_state" in args else True
        preview = build_prepare_preview(
            repo_path,
            goal=str(args.get("goal") or "").strip(),
            next_task=str(args.get("next_task") or args.get("next") or "").strip(),
            in_progress=str(args.get("active_task") or args.get("in_progress") or "").strip(),
            auto_task_state=auto_task_state,
            verified_gates=_as_list(args.get("verified")),
            failing_gates=_as_list(args.get("failing")),
            not_run_gates=_as_list(args.get("not_run")),
            source_platform=args.get("source_platform"),
            source_chat_id=args.get("source_chat_id"),
        )
        return _json_response({"success": True, "preview": preview})
    except (OSError, ValidationError, ValueError) as exc:
        return _error(exc)


def hermes_handoff_watch(args: dict[str, Any], **_: Any) -> str:
    """Run a one-shot read-only handoff watch evaluation."""
    try:
        if "locale" in args:
            i18n.set_locale(args["locale"])
        repo_path = Path(str(args.get("repo_path") or ".")).expanduser().resolve()
        result = build_watch_result(
            repo_path,
            goal=str(args.get("goal") or "").strip(),
            next_task=str(args.get("next_task") or args.get("next") or "").strip(),
            in_progress=str(args.get("active_task") or args.get("in_progress") or "").strip(),
            auto_task_state=_as_bool(args["auto_task_state"]) if "auto_task_state" in args else True,
            tool_calls=args.get("tool_calls"),
            elapsed_minutes=args.get("elapsed_minutes"),
            dirty_threshold=args.get("dirty_threshold", 1),
            explicit_request=_as_bool(args.get("explicit_request")),
            verified_gates=_as_list(args.get("verified")),
            failing_gates=_as_list(args.get("failing")),
            not_run_gates=_as_list(args.get("not_run")),
            source_platform=args.get("source_platform"),
            source_chat_id=args.get("source_chat_id"),
        )
        return _json_response(result)
    except (OSError, ValidationError, ValueError) as exc:
        return _error(exc)


def hermes_handoff_doctor(args: dict[str, Any], **_: Any) -> str:
    """Run a read-only handoff doctor evaluation."""
    try:
        if "locale" in args:
            i18n.set_locale(args["locale"])
        repo_path = Path(str(args.get("repo_path") or ".")).expanduser().resolve()
        auto_task_state = _as_bool(args["auto_task_state"]) if "auto_task_state" in args else True
        source_platform = args.get("source_platform")
        source_chat_id = args.get("source_chat_id")
        is_plugin_mode = bool(source_platform and source_chat_id) and True
        result = evaluate_handoff_recommendation(
            repo_path=repo_path if not is_plugin_mode else ".",
            goal=str(args.get("goal") or "").strip(),
            next_task=str(args.get("next_task") or args.get("next") or "").strip(),
            in_progress=str(args.get("active_task") or args.get("in_progress") or "").strip(),
            auto_task_state=auto_task_state,
            explicit_request=_as_bool(args.get("explicit_request")),
            verified_gates=_as_list(args.get("verified")),
            failing_gates=_as_list(args.get("failing")),
            not_run_gates=_as_list(args.get("not_run")),
            is_plugin_mode=is_plugin_mode,
            session_id=args.get("session_id"),
            source_platform=source_platform,
            source_chat_id=source_chat_id,
        )
        return _json_response({"success": True, "recommendation": result.to_dict()})
    except (OSError, ValidationError, ValueError) as exc:
        return _error(exc)


def hermes_handoff_resume(args: dict[str, Any], **_: Any) -> str:
    """Read a handoff JSON and return its resume prompt."""
    try:
        handoff_json = str(args.get("handoff_json") or "").strip()
        if not handoff_json:
            return _error("handoff_json is required")
        handoff_path = Path(handoff_json).expanduser()
        if not handoff_path.is_file():
            return _error(f"handoff JSON not found: {handoff_path}")
        data = json.loads(handoff_path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return _error("handoff JSON must contain an object")
        validate_packet(data)
        prompt = str(data["resume_prompt"])
        output = f"## Resume Prompt\n\n{prompt}" if bool(args.get("markdown")) else prompt
        return _json_response({"success": True, "resume_prompt": prompt, "output": output})
    except (json.JSONDecodeError, OSError, ValidationError, ValueError) as exc:
        return _error(exc)


def hermes_handoff_command(raw_args: str = "", **kwargs: Any) -> str:
    """Handle the plugin `/handoff` slash command.

    Hermes passes the raw trailing text after `/handoff`. The command remains
    a UX shim: create/resume operations are delegated to the existing tool
    handlers so the success/error envelope and validation behavior stay in one
    place.

    When ``kwargs`` contains ``source_platform`` and ``source_chat_id``
    (injected by Gateway dispatcher), doctor/prepare/watch subcommands
    automatically receive them — no chat_context config needed. The doctor
    queries state.db for conversation context from the current chat, not
    from a file path.
    """
    source_platform = kwargs.get("source_platform")
    source_chat_id = kwargs.get("source_chat_id")
    session_id = kwargs.get("session_id")

    def _inject_source_context(args: dict[str, Any]) -> dict[str, Any]:
        """Inject source_platform, source_chat_id, and session_id into args."""
        if source_platform:
            args["source_platform"] = source_platform
        if source_chat_id:
            args["source_chat_id"] = source_chat_id
        if session_id:
            args["session_id"] = session_id
        return args

    try:
        verb, payload = _split_handoff_command(str(raw_args or ""))
        if verb == "help":
            return _HANDOFF_HELP
        if verb == "create":
            if not payload.strip():
                return _HANDOFF_HELP
            result = _load_handler_result(hermes_handoff_create(_parse_create_command_args(payload)))
            return _format_create_command_result(result)
        if verb == "prepare":
            result = _load_handler_result(hermes_handoff_prepare(_inject_source_context(_parse_prepare_command_args(payload))))
            return _format_prepare_command_result(result)
        if verb == "resume":
            result = _load_handler_result(hermes_handoff_resume(_parse_resume_command_args(payload)))
            return _format_resume_command_result(result)
        if verb == "watch":
            result = _load_handler_result(hermes_handoff_watch(_inject_source_context(_parse_prepare_command_args(payload))))
            return _format_watch_command_result(result)
        if verb == "doctor":
            result = _load_handler_result(hermes_handoff_doctor(_inject_source_context(_parse_prepare_command_args(payload))))
            return _format_doctor_command_result(result)
        return f"Unknown handoff subcommand: {verb}\n\n{_HANDOFF_HELP}"
    except (json.JSONDecodeError, ValueError) as exc:
        return f"Handoff command error: {exc}\n\n{_HANDOFF_HELP}"


_CREATE_SCHEMA: dict[str, Any] = {
    "name": CREATE_TOOL,
    "description": "Create a Hermes continuation handoff packet as Markdown and JSON.",
    "parameters": {
        "type": "object",
        "properties": {
            "repo_path": {"type": "string", "description": "Repository path to inspect. Defaults to the current directory."},
            "goal": {"type": "string", "description": "Current goal for the handoff."},
            "active_task": {"type": "string", "description": "Current in-progress work, if any."},
            "next_task": {"type": "string", "description": "Next recommended task for the fresh session."},
            "auto_task_state": {"type": "boolean", "description": "Opt in to conservative task-state collection from repo docs."},
            "output_dir": {"type": "string", "description": "Optional output directory. Defaults to <repo_path>/.hermes/handoffs."},
            "completed": {"type": "array", "items": {"type": "string"}},
            "verified": {"type": "array", "items": {"type": "string"}},
            "failing": {"type": "array", "items": {"type": "string"}},
            "not_run": {"type": "array", "items": {"type": "string"}},
            "known_issues": {"type": "array", "items": {"type": "string"}},
            "do_not_touch": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["goal", "next_task"],
    },
}

_RESUME_SCHEMA: dict[str, Any] = {
    "name": RESUME_TOOL,
    "description": "Extract the resume prompt from a Hermes continuation handoff JSON.",
    "parameters": {
        "type": "object",
        "properties": {
            "handoff_json": {"type": "string", "description": "Path to an existing handoff JSON file."},
            "markdown": {"type": "boolean", "description": "Wrap output under a Markdown heading when true."},
        },
        "required": ["handoff_json"],
    },
}

_PREPARE_SCHEMA: dict[str, Any] = {
    "name": PREPARE_TOOL,
    "description": "Read-only preview for a Hermes continuation handoff create command.",
    "parameters": {
        "type": "object",
        "properties": {
            "repo_path": {"type": "string", "description": "Repository path to inspect. Defaults to the current directory."},
            "goal": {"type": "string", "description": "Current goal to preview; missing values degrade to advisory output."},
            "active_task": {"type": "string", "description": "Current in-progress work, if any."},
            "in_progress": {"type": "string", "description": "Alias for active_task."},
            "next_task": {"type": "string", "description": "Next recommended task to preview."},
            "next": {"type": "string", "description": "Alias for next_task."},
            "auto_task_state": {"type": "boolean", "description": "Read conservative task-state hints from repo docs. Defaults to true."},
            "verified": {"type": "array", "items": {"type": "string"}},
            "failing": {"type": "array", "items": {"type": "string"}},
            "not_run": {"type": "array", "items": {"type": "string"}},
            "locale": {"type": "string", "enum": ["en", "zh-TW"], "description": "Output language (default: zh-TW)."},
        },
        "required": [],
    },
}

_WATCH_SCHEMA: dict[str, Any] = {
    "name": WATCH_TOOL,
    "description": "Run a one-shot read-only handoff watch evaluation using local signals and thresholds.",
    "parameters": {
        "type": "object",
        "properties": {
            "repo_path": {"type": "string", "description": "Repository path to inspect. Defaults to the current directory."},
            "goal": {"type": "string", "description": "Current goal; missing values degrade to advisory output."},
            "active_task": {"type": "string", "description": "Current in-progress work, if any."},
            "next_task": {"type": "string", "description": "Next recommended task."},
            "auto_task_state": {"type": "boolean", "description": "Read conservative task-state hints from repo docs. Defaults to true."},
            "tool_calls": {"type": "integer", "description": "Number of tool calls observed (threshold: 5+)."},
            "elapsed_minutes": {"type": "integer", "description": "Elapsed minutes observed (threshold: 30+)."},
            "dirty_threshold": {"type": "integer", "description": "Minimum changed files to trigger (default: 1)."},
            "explicit_request": {"type": "boolean", "description": "Whether the user explicitly requested a handoff."},
            "verified": {"type": "array", "items": {"type": "string"}},
            "failing": {"type": "array", "items": {"type": "string"}},
            "not_run": {"type": "array", "items": {"type": "string"}},
            "locale": {"type": "string", "enum": ["en", "zh-TW"], "description": "Output language (default: zh-TW)."},
        },
        "required": [],
    },
}

_DOCTOR_SCHEMA: dict[str, Any] = {
    "name": DOCTOR_TOOL,
    "description": "Run a read-only handoff doctor evaluation. Analyzes local signals and recommends handoff actions without writing files.",
    "parameters": {
        "type": "object",
        "properties": {
            "repo_path": {"type": "string", "description": "Repository path to inspect. Defaults to the current directory."},
            "goal": {"type": "string", "description": "Current goal; missing values degrade to advisory output."},
            "active_task": {"type": "string", "description": "Current in-progress work, if any."},
            "next_task": {"type": "string", "description": "Next recommended task."},
            "auto_task_state": {"type": "boolean", "description": "Read conservative task-state hints from repo docs. Defaults to true."},
            "explicit_request": {"type": "boolean", "description": "Whether the user explicitly requested a handoff."},
            "verified": {"type": "array", "items": {"type": "string"}},
            "failing": {"type": "array", "items": {"type": "string"}},
            "not_run": {"type": "array", "items": {"type": "string"}},
            "locale": {"type": "string", "enum": ["en", "zh-TW"], "description": "Output language (default: zh-TW)."},
        },
        "required": [],
    },
}


# ── Plugin system registration ──────────────────────────────────────────────
# The ``register(ctx)`` function is called by Hermes plugin loader.
# It registers lifecycle hooks (on_turn_complete for auto-doctor).


def _on_turn_complete(
    session_id: str = "",
    source_platform: str = "",
    source_chat_id: str = "",
    message_count: int = 0,
    tool_call_count: int = 0,
    model: str = "",
    **kwargs: Any,
) -> None:
    """Fire-and-forget auto-doctor evaluation after each agent turn.

    This is a non-blocking observer hook: it evaluates session metrics
    against thresholds and runs the doctor silently if warranted, but
    never raises and never blocks message delivery.
    """
    try:
        from .auto_doctor import evaluate_turn

        evaluate_turn(
            session_id=session_id,
            source_platform=source_platform,
            source_chat_id=source_chat_id,
            message_count=message_count,
            tool_call_count=tool_call_count,
            model=model,
        )
    except Exception:
        pass  # Non-fatal — hook failure must never break message flow


def register(ctx) -> None:
    """Register lifecycle hooks, tools, and slash commands."""
    # ── Hook registration (optional — older runtimes may lack it) ──────
    register_hook = getattr(ctx, "register_hook", None)
    if callable(register_hook):
        register_hook("on_turn_complete", _on_turn_complete)

    # ── Tool registration ───────────────────────────────────────────────
    register_tool = getattr(ctx, "register_tool", None)
    if not callable(register_tool):
        raise RuntimeError("PluginContext has no register_tool method")

    register_tool(
        name=CREATE_TOOL,
        toolset=TOOLSET,
        schema=_CREATE_SCHEMA,
        handler=hermes_handoff_create,
        description="Create a Hermes continuation handoff packet as Markdown and JSON.",
        emoji="📦",
    )
    register_tool(
        name=RESUME_TOOL,
        toolset=TOOLSET,
        schema=_RESUME_SCHEMA,
        handler=hermes_handoff_resume,
        description="Extract the resume prompt from a handoff JSON.",
        emoji="▶️",
    )
    register_tool(
        name=PREPARE_TOOL,
        toolset=TOOLSET,
        schema=_PREPARE_SCHEMA,
        handler=hermes_handoff_prepare,
        description="Read-only preview for a Hermes continuation handoff create command.",
        emoji="🔍",
    )
    register_tool(
        name=WATCH_TOOL,
        toolset=TOOLSET,
        schema=_WATCH_SCHEMA,
        handler=hermes_handoff_watch,
        description="Run a one-shot read-only handoff watch evaluation.",
        emoji="👀",
    )
    register_tool(
        name=DOCTOR_TOOL,
        toolset=TOOLSET,
        schema=_DOCTOR_SCHEMA,
        handler=hermes_handoff_doctor,
        description="Run a read-only handoff doctor evaluation.",
        emoji="🩺",
    )

    # ── Slash command registration ──────────────────────────────────────
    register_command = getattr(ctx, "register_command", None)
    if callable(register_command):
        try:
            register_command(
                HANDOFF_COMMAND,
                handler=hermes_handoff_command,
                description="Create, prepare, or resume Hermes continuation handoffs.",
                args_hint=_HANDOFF_ARGS_HINT,
            )
        except TypeError as exc:
            warning = (
                "Skipped optional /handoff command registration: register_command "
                f"appears to use an incompatible API ({exc})"
            )
            warnings = getattr(ctx, "_hermes_continuation_registration_warnings", None)
            if not isinstance(warnings, list):
                warnings = []
            warnings.append(warning)
            try:
                setattr(ctx, "_hermes_continuation_registration_warnings", warnings)
            except (AttributeError, TypeError):
                pass
