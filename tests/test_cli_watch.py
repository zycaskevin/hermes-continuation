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


def init_git(path: Path) -> None:
    subprocess.run(["git", "init"], cwd=path, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)


def test_watch_cli_json_smoke_is_read_only(tmp_path):
    init_git(tmp_path)

    result = run_cli(
        [
            "watch",
            "--repo",
            str(tmp_path),
            "--goal",
            "CLI watch",
            "--next",
            "Inspect JSON",
            "--explicit-request",
            "--json",
        ],
        tmp_path,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["success"] is True
    assert payload["level"] == "prepare"
    assert payload["would_write"] is False
    assert payload["preview"]["level"] == "prepare"
    assert payload["preview"]["would_write"] is False
    assert payload["preview"]["safe_create_command"] is not None
    assert not (tmp_path / ".hermes" / "handoffs").exists()


def test_watch_cli_human_smoke_is_read_only(tmp_path):
    init_git(tmp_path)

    result = run_cli(
        [
            "watch",
            "--repo",
            str(tmp_path),
            "--goal",
            "CLI watch",
            "--tool-calls",
            "5",
        ],
        tmp_path,
    )

    assert result.returncode == 0, result.stderr
    assert "Handoff watch: advise" in result.stdout
    assert "Read-only watch" in result.stdout
    assert "watch_tool_calls_threshold" in result.stdout
    assert "Safe create command" not in result.stdout
    assert not (tmp_path / ".hermes" / "handoffs").exists()


def test_watch_cli_block_exit_code_and_secret_safe_json(tmp_path):
    init_git(tmp_path)
    field = "api" + "_" + "key"
    dummy_value = "dummy" + "-" + "placeholder" + "-1234567890"

    result = run_cli(
        [
            "watch",
            "--repo",
            str(tmp_path),
            "--goal",
            f"{field}={dummy_value}",
            "--next",
            "Safe next",
            "--json",
        ],
        tmp_path,
    )

    assert result.returncode == 2
    assert dummy_value not in result.stdout
    payload = json.loads(result.stdout)
    assert payload["success"] is True
    assert payload["level"] == "block"
    assert payload["preview"] is None
    assert payload["recommendation"]["safe_create_command"] is None
    assert payload["would_write"] is False
    assert not (tmp_path / ".hermes" / "handoffs").exists()
