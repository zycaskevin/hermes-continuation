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


def test_create_blocks_private_key_before_write(tmp_path):
    marker = "PRIVATE" + " " + "KEY"
    private = f"-----BEGIN {marker}-----\nabc\n-----END {marker}-----"
    result = run_cli(["create", "--repo", str(tmp_path), "--goal", private, "--next", "Inspect output"], tmp_path)
    assert result.returncode == 2
    assert not (tmp_path / ".hermes" / "handoffs").exists()
