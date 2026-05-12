import json
import subprocess
from pathlib import Path

from hermes_continuation.watch import build_watch_result, format_watch_result


def init_git(path: Path) -> None:
    subprocess.run(["git", "init"], cwd=path, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)


def test_watch_observes_low_signals_clean_repo_without_writes(tmp_path):
    init_git(tmp_path)

    result = build_watch_result(tmp_path, auto_task_state=False)

    assert result["success"] is True
    assert result["level"] == "observe"
    assert result["watch_signals"] == []
    assert result["preview"] is None
    assert result["would_write"] is False
    assert result["recommendation"]["safe_create_command"] is None
    assert not (tmp_path / ".hermes" / "handoffs").exists()


def test_watch_high_tool_calls_missing_next_advises_without_preview_or_write(tmp_path):
    init_git(tmp_path)

    result = build_watch_result(
        tmp_path,
        goal="Finish watch MVP",
        tool_calls=5,
        auto_task_state=False,
    )

    assert result["level"] == "advise"
    assert "watch_tool_calls_threshold" in result["watch_signals"]
    assert "missing_required_prepare_input" in result["recommendation"]["signals"]
    assert result["preview"] is None
    assert result["recommendation"]["safe_create_command"] is None
    assert result["would_write"] is False
    human = format_watch_result(result)
    assert "安全的交接指令" not in human
    assert "交接掃描" in human
    assert "建議交接" in human
    assert not (tmp_path / ".hermes" / "handoffs").exists()


def test_watch_high_elapsed_without_goal_or_next_elevates_to_advise(tmp_path):
    init_git(tmp_path)

    result = build_watch_result(tmp_path, elapsed_minutes=30, auto_task_state=False)

    assert result["level"] == "advise"
    assert "watch_elapsed_minutes_threshold" in result["watch_signals"]
    assert result["preview"] is None
    assert result["recommendation"]["safe_create_command"] is None
    assert result["would_write"] is False
    assert not (tmp_path / ".hermes" / "handoffs").exists()


def test_watch_explicit_request_safe_goal_next_prepares_preview_without_writes(tmp_path):
    init_git(tmp_path)

    result = build_watch_result(
        tmp_path,
        goal="Ship watch MVP",
        next_task="Run focused tests",
        in_progress="Implement watch helper",
        verified_gates=["watch tests passed"],
        explicit_request=True,
        auto_task_state=False,
    )

    assert result["level"] == "prepare"
    assert result["would_write"] is False
    preview = result["preview"]
    assert preview is not None
    assert preview["level"] == "prepare"
    assert preview["would_write"] is False
    assert preview["proposed_goal"] == "Ship watch MVP"
    assert preview["proposed_next_task"] == "Run focused tests"
    assert preview["safe_create_command"] is not None
    assert "hermes-handoff create" in preview["safe_create_command"]
    assert not (tmp_path / ".hermes" / "handoffs").exists()


def test_watch_blocks_private_key_input_without_leaking_secret_or_writing(tmp_path):
    init_git(tmp_path)
    marker = "PRIVATE" + " " + "KEY"
    private = f"-----BEGIN {marker}-----\nabc\n-----END {marker}-----"

    result = build_watch_result(
        tmp_path,
        goal=private,
        next_task="Safe next",
        explicit_request=True,
        auto_task_state=False,
    )

    assert result["level"] == "block"
    assert result["preview"] is None
    assert result["recommendation"]["safe_create_command"] is None
    assert result["would_write"] is False
    rendered_json = json.dumps(result)
    human = format_watch_result(result)
    assert private not in rendered_json
    assert private not in human
    assert "abc" not in rendered_json
    assert "abc" not in human
    assert not (tmp_path / ".hermes" / "handoffs").exists()


def test_watch_blocks_secret_like_repo_path_without_leaking_path_or_writing(tmp_path):
    field = "api" + "_" + "key"
    dummy_value = "dummy" + "-" + "placeholder" + "-1234567890"
    secret_repo = tmp_path / f"{field}={dummy_value}"
    secret_repo.mkdir()
    init_git(secret_repo)

    result = build_watch_result(
        secret_repo,
        goal="Safe goal",
        next_task="Safe next",
        explicit_request=True,
        auto_task_state=False,
    )

    assert result["level"] == "block"
    assert result["preview"] is None
    assert result["recommendation"]["safe_create_command"] is None
    rendered_json = json.dumps(result)
    human = format_watch_result(result)
    assert str(secret_repo) not in rendered_json
    assert str(secret_repo) not in human
    assert dummy_value not in rendered_json
    assert dummy_value not in human
    assert f"{field}={dummy_value}" not in rendered_json
    assert f"{field}={dummy_value}" not in human
    assert not (secret_repo / ".hermes" / "handoffs").exists()
