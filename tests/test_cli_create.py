import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"


def run_cli(args, cwd):
    env = os.environ.copy()
    env["PYTHONPATH"] = str(SRC)
    return subprocess.run(
        [sys.executable, "-m", "hermes_continuation.cli", *args],
        cwd=cwd,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
        check=False,
    )


def test_help_smoke(tmp_path):
    result = run_cli(["--help"], tmp_path)
    assert result.returncode == 0
    assert "hermes-handoff" in result.stdout


def test_create_writes_markdown_and_json(tmp_path):
    result = run_cli(["create", "--repo", str(tmp_path), "--goal", "Smoke test", "--next", "Inspect output"], tmp_path)
    assert result.returncode == 0, result.stderr
    handoffs = tmp_path / ".hermes" / "handoffs"
    md_files = list(handoffs.glob("*-handoff.md"))
    json_files = list(handoffs.glob("*-handoff.json"))
    assert len(md_files) == 1
    assert len(json_files) == 1
    packet = json.loads(json_files[0].read_text())
    assert packet["current_goal"] == "Smoke test"
    assert "## Resume Prompt" in md_files[0].read_text()


def test_create_without_auto_task_state_ignores_progress_docs(tmp_path):
    (tmp_path / "PROGRESS.md").write_text("## Completed Work\n- Auto-only item\n", encoding="utf-8")

    result = run_cli(["create", "--repo", str(tmp_path), "--goal", "Manual only", "--next", "Inspect output"], tmp_path)

    assert result.returncode == 0, result.stderr
    json_file = next((tmp_path / ".hermes" / "handoffs").glob("*-handoff.json"))
    packet = json.loads(json_file.read_text())
    assert packet["task_state"]["completed_work"] == []


def test_create_with_auto_task_state_merges_auto_and_manual(tmp_path):
    (tmp_path / "PROGRESS.md").write_text(
        """# Progress

## Completed Work
- Auto completed item

## In Progress
- Auto active item

## Blockers
- Auto blocker item

## Boundaries
- Auto boundary item

## Next Step
- Auto next item
""",
        encoding="utf-8",
    )

    result = run_cli(
        [
            "create",
            "--repo",
            str(tmp_path),
            "--goal",
            "Auto merge",
            "--auto-task-state",
            "--completed",
            "Manual completed item",
            "--in-progress",
            "Manual active item",
            "--blocker",
            "Manual blocker item",
            "--do-not-touch",
            "Manual boundary item",
            "--next",
            "Manual next item",
        ],
        tmp_path,
    )

    assert result.returncode == 0, result.stderr
    json_file = next((tmp_path / ".hermes" / "handoffs").glob("*-handoff.json"))
    packet = json.loads(json_file.read_text())
    task_state = packet["task_state"]
    assert "Auto completed item" in task_state["completed_work"]
    assert "Manual completed item" in task_state["completed_work"]
    assert "Auto active item" in task_state["in_progress"]
    assert "Manual active item" in task_state["in_progress"]
    assert "Auto blocker item" in task_state["known_blockers"]
    assert "Manual blocker item" in task_state["known_blockers"]
    assert "Auto boundary item" in task_state["do_not_touch"]
    assert "Manual boundary item" in task_state["do_not_touch"]
    assert task_state["next_recommended_task"] == "Manual next item"


def test_create_blocks_private_key_before_write(tmp_path):
    marker = "PRIVATE" + " " + "KEY"
    private = f"-----BEGIN {marker}-----\nabc\n-----END {marker}-----"
    result = run_cli(["create", "--repo", str(tmp_path), "--goal", private, "--next", "Inspect output"], tmp_path)
    assert result.returncode == 2
    assert not (tmp_path / ".hermes" / "handoffs").exists()


def test_create_auto_task_state_blocks_private_key_in_docs_before_write(tmp_path):
    marker = "PRIVATE" + " " + "KEY"
    private = f"-----BEGIN {marker}-----\nabc\n-----END {marker}-----"
    (tmp_path / "PROGRESS.md").write_text(
        f"## In Progress\n- Safe-looking extracted line\n\n{private}\n",
        encoding="utf-8",
    )

    result = run_cli(
        ["create", "--repo", str(tmp_path), "--goal", "Auto doc safety", "--next", "Inspect output", "--auto-task-state"],
        tmp_path,
    )

    assert result.returncode == 2
    assert "private key block detected" in result.stderr
    assert not (tmp_path / ".hermes" / "handoffs").exists()
