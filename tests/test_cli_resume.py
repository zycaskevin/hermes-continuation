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


def packet_with_prompt(prompt="Resume exactly this prompt"):
    return {
        "schema_version": "0.1.0",
        "created_at": "2026-05-09T00:00:00+00:00",
        "source": "hermes-handoff",
        "current_goal": "Resume smoke",
        "repo": {
            "path": "/tmp/example",
            "git_available": False,
            "branch": None,
            "head": None,
            "status_short": "",
            "changed_files": [],
        },
        "task_state": {
            "completed_work": ["Created handoff"],
            "in_progress": "Resume command",
            "known_blockers": [],
            "do_not_touch": [],
            "next_recommended_task": "Continue from prompt",
        },
        "verification": {
            "verified_gates": [],
            "failing_gates": [],
            "not_run_gates": ["resume smoke"],
        },
        "safety": {
            "redaction_count": 0,
            "blocked": False,
            "blocked_reason": None,
        },
        "resume_prompt": prompt,
    }


def write_packet(tmp_path, packet):
    path = tmp_path / "handoff.json"
    path.write_text(json.dumps(packet), encoding="utf-8")
    return path


def test_resume_help_documents_markdown_option(tmp_path):
    result = run_cli(["resume", "--help"], tmp_path)

    assert result.returncode == 0
    assert "handoff_json" in result.stdout
    assert "--markdown" in result.stdout


def test_resume_prints_resume_prompt_only(tmp_path):
    prompt = "Resume exactly this prompt\nwith a second line"
    handoff = write_packet(tmp_path, packet_with_prompt(prompt))

    result = run_cli(["resume", str(handoff)], tmp_path)

    assert result.returncode == 0, result.stderr
    assert result.stdout == prompt
    assert result.stderr == ""


def test_resume_markdown_wraps_resume_prompt(tmp_path):
    prompt = "Resume in markdown mode"
    handoff = write_packet(tmp_path, packet_with_prompt(prompt))

    result = run_cli(["resume", "--markdown", str(handoff)], tmp_path)

    assert result.returncode == 0, result.stderr
    assert result.stdout == f"## Resume Prompt\n\n{prompt}"
    assert result.stderr == ""


def test_resume_fails_on_missing_file(tmp_path):
    result = run_cli(["resume", str(tmp_path / "missing.json")], tmp_path)

    assert result.returncode == 2
    assert result.stdout == ""
    assert "error:" in result.stderr
    assert "not found" in result.stderr


def test_resume_fails_on_invalid_json(tmp_path):
    handoff = tmp_path / "broken.json"
    handoff.write_text("{", encoding="utf-8")

    result = run_cli(["resume", str(handoff)], tmp_path)

    assert result.returncode == 2
    assert result.stdout == ""
    assert "error:" in result.stderr
    assert "invalid JSON" in result.stderr


def test_resume_fails_on_packet_missing_required_fields(tmp_path):
    handoff = write_packet(tmp_path, {"source": "hermes-handoff", "resume_prompt": "Resume"})

    result = run_cli(["resume", str(handoff)], tmp_path)

    assert result.returncode == 2
    assert result.stdout == ""
    assert "error:" in result.stderr
    assert "missing required fields" in result.stderr


def test_resume_fails_on_empty_resume_prompt(tmp_path):
    handoff = write_packet(tmp_path, packet_with_prompt("  \n  "))

    result = run_cli(["resume", str(handoff)], tmp_path)

    assert result.returncode == 2
    assert result.stdout == ""
    assert "error:" in result.stderr
    assert "resume_prompt" in result.stderr
