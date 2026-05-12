import json
import os
import subprocess
import sys
from pathlib import Path

from hermes_continuation.doctor import evaluate_handoff_recommendation

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


def test_doctor_observes_clean_low_risk_repo(tmp_path):
    init_git(tmp_path)

    result = evaluate_handoff_recommendation(tmp_path, auto_task_state=False)

    assert result.level == "observe"
    assert result.safe_create_command is None
    assert result.blockers == []


def test_doctor_advises_for_dirty_repo_and_missing_prepare_input(tmp_path):
    init_git(tmp_path)
    (tmp_path / "work.py").write_text("print('dirty')\n", encoding="utf-8")

    result = evaluate_handoff_recommendation(tmp_path, explicit_request=True, auto_task_state=False)

    assert result.level == "advise"
    assert "dirty_git_state" in result.signals
    assert "missing_required_prepare_input" in result.signals
    assert result.safe_create_command is None


def test_doctor_prepares_exact_command_from_safe_explicit_inputs(tmp_path):
    init_git(tmp_path)

    result = evaluate_handoff_recommendation(
        tmp_path,
        goal="Ship phase 3A",
        next_task="Run focused tests",
        in_progress="Implement doctor",
        verified_gates=["unit tests passed"],
        explicit_request=True,
        auto_task_state=True,
    )

    assert result.level == "prepare"
    assert result.safe_create_command is not None
    assert "hermes-handoff create" in result.safe_create_command
    assert "--repo" in result.safe_create_command
    assert "--goal 'Ship phase 3A'" in result.safe_create_command
    assert "--next 'Run focused tests'" in result.safe_create_command
    assert "--auto-task-state" in result.safe_create_command
    assert "--verified 'unit tests passed'" in result.safe_create_command


def test_doctor_blocks_private_key_in_docs_without_printing_secret(tmp_path):
    init_git(tmp_path)
    marker = "PRIVATE" + " " + "KEY"
    private = f"-----BEGIN {marker}-----\nabc\n-----END {marker}-----"
    (tmp_path / "PROGRESS.md").write_text(f"## In Progress\n- Safe item\n\n{private}\n", encoding="utf-8")

    result = evaluate_handoff_recommendation(
        tmp_path,
        goal="Safe goal",
        next_task="Safe next",
        explicit_request=True,
        auto_task_state=True,
    )

    assert result.level == "block"
    assert result.safe_create_command is None
    rendered = json.dumps(result.to_dict())
    assert private not in rendered
    assert "abc" not in rendered
    assert "private-key" in rendered or "private_key" in rendered


def test_doctor_cli_is_read_only_and_does_not_create_handoffs(tmp_path):
    init_git(tmp_path)

    result = run_cli(["doctor", "--repo", str(tmp_path), "--goal", "Read only", "--next", "Inspect"], tmp_path)

    assert result.returncode == 0, result.stderr
    assert "交接醫生診斷" in result.stdout
    assert "可準備交接" in result.stdout
    assert "純讀取" in result.stdout
    assert "安全的交接指令" in result.stdout
    assert not (tmp_path / ".hermes" / "handoffs").exists()


def test_doctor_cli_json_envelope(tmp_path):
    init_git(tmp_path)
    (tmp_path / "changed.md").write_text("dirty\n", encoding="utf-8")

    result = run_cli(["doctor", "--repo", str(tmp_path), "--explicit-request", "--json"], tmp_path)

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["success"] is True
    assert payload["recommendation"]["level"] == "advise"
    assert "dirty_git_state" in payload["recommendation"]["signals"]
    assert payload["recommendation"]["safe_create_command"] is None


def test_doctor_cli_block_exit_code_and_secret_safe_output(tmp_path):
    init_git(tmp_path)
    field = "api" + "_" + "key"
    dummy_value = "dummy" + "-" + "placeholder" + "-1234567890"

    result = run_cli(
        ["doctor", "--repo", str(tmp_path), "--goal", f"{field}={dummy_value}", "--next", "Safe next"],
        tmp_path,
    )

    assert result.returncode == 2
    assert "交接醫生診斷" in result.stdout
    assert "安全阻擋" in result.stdout
    assert dummy_value not in result.stdout
    assert not (tmp_path / ".hermes" / "handoffs").exists()
