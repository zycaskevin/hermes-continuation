"""Hermes plugin wrapper for the continuation handoff sidecar."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .git_state import collect_git_state
from .packet import build_packet
from .redaction import RedactionBlocked
from .render_markdown import render_markdown
from .validate import ValidationError, validate_packet

TOOLSET = "hermes_continuation"
CREATE_TOOL = "hermes_handoff_create"
RESUME_TOOL = "hermes_handoff_resume"


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


def _error(exc: Exception | str) -> str:
    return _json_response({"success": False, "error": str(exc)})


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

        packet = build_packet(
            current_goal=goal,
            repo=collect_git_state(repo_path),
            completed_work=_as_list(args.get("completed")),
            in_progress=str(args.get("active_task") or args.get("in_progress") or ""),
            known_blockers=_as_list(args.get("known_issues") or args.get("blockers")),
            do_not_touch=_as_list(args.get("do_not_touch")),
            next_recommended_task=next_task,
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


def register(ctx: Any) -> None:
    """Register Hermes continuation tools with Hermes' plugin context."""
    ctx.register_tool(
        name=CREATE_TOOL,
        toolset=TOOLSET,
        schema=_CREATE_SCHEMA,
        handler=hermes_handoff_create,
        description="Create a structured Hermes handoff packet.",
        emoji="🧾",
    )
    ctx.register_tool(
        name=RESUME_TOOL,
        toolset=TOOLSET,
        schema=_RESUME_SCHEMA,
        handler=hermes_handoff_resume,
        description="Extract a fresh-session resume prompt from a handoff packet.",
        emoji="🔁",
    )
