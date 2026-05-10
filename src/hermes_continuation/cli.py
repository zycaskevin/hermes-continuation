"""Command line interface for Hermes Continuation."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from .git_state import collect_git_state
from .packet import build_packet
from .redaction import RedactionBlocked
from .render_markdown import render_markdown
from .validate import ValidationError, validate_packet


def _add_repeatable(parser: argparse.ArgumentParser, name: str, help_text: str) -> None:
    parser.add_argument(name, action="append", default=[], help=help_text)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="hermes-handoff", description="Create and resume Hermes structured handoff packets")
    subparsers = parser.add_subparsers(dest="command")

    create = subparsers.add_parser("create", help="Create a Markdown + JSON handoff packet")
    create.add_argument("--repo", default=".", help="Repository path to inspect (default: current directory)")
    create.add_argument("--goal", required=True, help="Current goal for this handoff")
    create.add_argument("--in-progress", default="", help="Current in-progress work, if any")
    create.add_argument("--next", required=True, dest="next_task", help="Next recommended task")
    create.add_argument("--output-dir", default=None, help="Output directory (default: <repo>/.hermes/handoffs)")
    _add_repeatable(create, "--completed", "Completed work item; may be repeated")
    _add_repeatable(create, "--verified", "Verified gate; may be repeated")
    _add_repeatable(create, "--failing", "Failing gate; may be repeated")
    _add_repeatable(create, "--not-run", "Not-run gate; may be repeated")
    _add_repeatable(create, "--blocker", "Known blocker; may be repeated")
    _add_repeatable(create, "--do-not-touch", "Safety boundary; may be repeated")
    create.set_defaults(func=handle_create)

    resume = subparsers.add_parser("resume", help="Print the resume prompt from a handoff JSON")
    resume.add_argument("handoff_json", help="Path to an existing handoff JSON file")
    resume.add_argument("--markdown", action="store_true", help="Wrap the prompt in a concise Markdown section")
    resume.set_defaults(func=handle_resume)
    return parser


def handle_create(args: argparse.Namespace) -> int:
    repo_path = Path(args.repo).expanduser().resolve()
    output_dir = Path(args.output_dir).expanduser().resolve() if args.output_dir else repo_path / ".hermes" / "handoffs"

    try:
        packet = build_packet(
            current_goal=args.goal,
            repo=collect_git_state(repo_path),
            completed_work=args.completed,
            in_progress=args.in_progress,
            known_blockers=args.blocker,
            do_not_touch=args.do_not_touch,
            next_recommended_task=args.next_task,
            verified_gates=args.verified,
            failing_gates=args.failing,
            not_run_gates=args.not_run,
        )
        validate_packet(packet)
        markdown = render_markdown(packet)
    except (RedactionBlocked, ValidationError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    md_path = output_dir / f"{timestamp}-handoff.md"
    json_path = output_dir / f"{timestamp}-handoff.json"
    md_path.write_text(markdown, encoding="utf-8")
    json_path.write_text(json.dumps(packet, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(f"markdown: {md_path}")
    print(f"json: {json_path}")
    return 0


def handle_resume(args: argparse.Namespace) -> int:
    handoff_path = Path(args.handoff_json).expanduser()
    if not handoff_path.is_file():
        print(f"error: handoff JSON not found: {handoff_path}", file=sys.stderr)
        return 2

    try:
        data = json.loads(handoff_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        print(f"error: invalid JSON in {handoff_path}: {exc.msg}", file=sys.stderr)
        return 2
    except OSError as exc:
        print(f"error: could not read {handoff_path}: {exc}", file=sys.stderr)
        return 2

    if not isinstance(data, dict):
        print("error: handoff JSON must contain an object", file=sys.stderr)
        return 2

    try:
        validate_packet(data)
    except ValidationError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    prompt = str(data["resume_prompt"])
    if args.markdown:
        sys.stdout.write(f"## Resume Prompt\n\n{prompt}")
    else:
        sys.stdout.write(prompt)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not hasattr(args, "func"):
        parser.print_help()
        return 0
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
