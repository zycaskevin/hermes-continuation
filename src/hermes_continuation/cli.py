"""Command line interface for Hermes Continuation."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from .doctor import evaluate_handoff_recommendation, format_recommendation
from .git_state import collect_git_state
from .packet import build_packet
from .prepare import build_prepare_preview, format_prepare_preview
from .redaction import RedactionBlocked
from .render_markdown import render_markdown
from .task_state import collect_task_state, merge_task_state
from .validate import ValidationError, validate_packet
from .watch import build_watch_result, format_watch_result


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
    create.add_argument("--auto-task-state", action="store_true", help="Opt in to conservative task-state collection from repo docs")
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

    doctor = subparsers.add_parser(
        "doctor",
        help="Read-only handoff recommendation doctor (exits 2 if safety blocks preparation)",
    )
    doctor.add_argument("--repo", default=".", help="Repository path to inspect (default: current directory)")
    doctor.add_argument("--goal", default="", help="Current goal, used only to suggest a safe create command")
    doctor.add_argument("--in-progress", default="", help="Current in-progress work, included only in a safe suggested command")
    doctor.add_argument("--next", default="", dest="next_task", help="Next recommended task, used only to suggest a safe create command")
    doctor.add_argument("--auto-task-state", dest="auto_task_state", action="store_true", default=True, help="Read conservative task-state hints from repo docs (default)")
    doctor.add_argument("--no-auto-task-state", dest="auto_task_state", action="store_false", help="Do not read repo docs for task-state hints")
    _add_repeatable(doctor, "--verified", "Verified gate; may be repeated")
    _add_repeatable(doctor, "--failing", "Failing gate; may be repeated")
    _add_repeatable(doctor, "--not-run", "Not-run gate; may be repeated")
    doctor.add_argument("--explicit-request", action="store_true", help="Treat this invocation as an explicit user handoff request")
    doctor.add_argument("--json", action="store_true", help="Print a JSON recommendation envelope")
    doctor.set_defaults(func=handle_doctor)

    prepare = subparsers.add_parser(
        "prepare",
        help="Read-only handoff create preview; never writes packet files (exits 2 if blocked)",
    )
    prepare.add_argument("--repo", default=".", help="Repository path to inspect (default: current directory)")
    prepare.add_argument("--goal", default="", help="Current goal to preview; missing values degrade to advise")
    prepare.add_argument("--in-progress", default="", help="Current in-progress work, included only in a safe suggested command")
    prepare.add_argument("--next", default="", dest="next_task", help="Next recommended task to preview; missing values degrade to advise")
    prepare.add_argument("--auto-task-state", dest="auto_task_state", action="store_true", default=True, help="Read conservative task-state hints from repo docs (default)")
    prepare.add_argument("--no-auto-task-state", dest="auto_task_state", action="store_false", help="Do not read repo docs for task-state hints")
    _add_repeatable(prepare, "--verified", "Verified gate; may be repeated")
    _add_repeatable(prepare, "--failing", "Failing gate; may be repeated")
    _add_repeatable(prepare, "--not-run", "Not-run gate; may be repeated")
    prepare.add_argument("--json", action="store_true", help="Print a JSON prepare preview envelope")
    prepare.set_defaults(func=handle_prepare)

    watch = subparsers.add_parser(
        "watch",
        help="One-shot read-only handoff watch advisory; never writes packet files (exits 2 if blocked)",
    )
    watch.add_argument("--repo", default=".", help="Repository path to inspect (default: current directory)")
    watch.add_argument("--goal", default="", help="Current goal, used only for safe advisory/preview output")
    watch.add_argument("--in-progress", default="", help="Current in-progress work, included only in safe advisory/preview output")
    watch.add_argument("--next", default="", dest="next_task", help="Next recommended task, used only for safe advisory/preview output")
    watch.add_argument("--auto-task-state", dest="auto_task_state", action="store_true", default=True, help="Read conservative task-state hints from repo docs (default)")
    watch.add_argument("--no-auto-task-state", dest="auto_task_state", action="store_false", help="Do not read repo docs for task-state hints")
    watch.add_argument("--tool-calls", type=int, default=None, help="Observed tool-call count for watch advisory thresholding")
    watch.add_argument("--elapsed-minutes", type=int, default=None, help="Observed elapsed minutes for watch advisory thresholding")
    watch.add_argument("--dirty-threshold", type=int, default=1, help="Changed-file count threshold for watch advisory strength (default: 1)")
    _add_repeatable(watch, "--verified", "Verified gate; may be repeated")
    _add_repeatable(watch, "--failing", "Failing gate; may be repeated")
    _add_repeatable(watch, "--not-run", "Not-run gate; may be repeated")
    watch.add_argument("--explicit-request", action="store_true", help="Treat this invocation as an explicit user handoff request")
    watch.add_argument("--json", action="store_true", help="Print a JSON watch result envelope")
    watch.set_defaults(func=handle_watch)
    return parser


def handle_create(args: argparse.Namespace) -> int:
    repo_path = Path(args.repo).expanduser().resolve()
    output_dir = Path(args.output_dir).expanduser().resolve() if args.output_dir else repo_path / ".hermes" / "handoffs"

    try:
        repo_state = collect_git_state(repo_path)
        auto_task_state = collect_task_state(repo_path, repo_state) if args.auto_task_state else None
        task_state = merge_task_state(
            auto_task_state,
            completed_work=args.completed,
            in_progress=args.in_progress,
            known_blockers=args.blocker,
            do_not_touch=args.do_not_touch,
            next_task=args.next_task,
        )
        packet = build_packet(
            current_goal=args.goal,
            repo=repo_state,
            completed_work=task_state["completed_work"],
            in_progress=task_state["in_progress"],
            known_blockers=task_state["known_blockers"],
            do_not_touch=task_state["do_not_touch"],
            next_recommended_task=task_state["next_recommended_task"],
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


def handle_doctor(args: argparse.Namespace) -> int:
    repo_path = Path(args.repo).expanduser().resolve()
    result = evaluate_handoff_recommendation(
        repo_path,
        goal=args.goal,
        next_task=args.next_task,
        in_progress=args.in_progress,
        auto_task_state=args.auto_task_state,
        verified_gates=args.verified,
        failing_gates=args.failing,
        not_run_gates=args.not_run,
        explicit_request=args.explicit_request,
    )

    if args.json:
        print(json.dumps({"success": True, "recommendation": result.to_dict()}, ensure_ascii=False, indent=2))
    else:
        sys.stdout.write(format_recommendation(result))
    return 2 if result.level == "block" else 0


def handle_prepare(args: argparse.Namespace) -> int:
    preview = build_prepare_preview(
        Path(args.repo).expanduser().resolve(),
        goal=args.goal,
        next_task=args.next_task,
        in_progress=args.in_progress,
        auto_task_state=args.auto_task_state,
        verified_gates=args.verified,
        failing_gates=args.failing,
        not_run_gates=args.not_run,
    )

    if args.json:
        print(json.dumps({"success": True, "preview": preview}, ensure_ascii=False, indent=2))
    else:
        sys.stdout.write(format_prepare_preview(preview))
    return 2 if preview["level"] == "block" else 0


def handle_watch(args: argparse.Namespace) -> int:
    result = build_watch_result(
        Path(args.repo).expanduser().resolve(),
        goal=args.goal,
        next_task=args.next_task,
        in_progress=args.in_progress,
        auto_task_state=args.auto_task_state,
        tool_calls=args.tool_calls,
        elapsed_minutes=args.elapsed_minutes,
        dirty_threshold=args.dirty_threshold,
        verified_gates=args.verified,
        failing_gates=args.failing,
        not_run_gates=args.not_run,
        explicit_request=args.explicit_request,
    )

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        sys.stdout.write(format_watch_result(result))
    return 2 if result["level"] == "block" else 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not hasattr(args, "func"):
        parser.print_help()
        return 0
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
