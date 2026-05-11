import json
import os
import subprocess
import sys
from pathlib import Path

from hermes_continuation.prepare import build_prepare_preview, format_prepare_preview

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


def test_prepare_preview_from_safe_inputs_is_read_only(tmp_path):
    init_git(tmp_path)

    preview = build_prepare_preview(
        tmp_path,
        goal="Ship Phase 3B",
        next_task="Run verification",
        in_progress="Implement prepare helper",
        verified_gates=["prepare tests passed"],
        auto_task_state=True,
    )

    assert preview["level"] == "prepare"
    assert preview["would_write"] is False
    assert preview["proposed_goal"] == "Ship Phase 3B"
    assert preview["proposed_next_task"] == "Run verification"
    assert preview["output_dir"] == str(tmp_path / ".hermes" / "handoffs")
    assert preview["safety_status"] == "safe"
    assert preview["safety"]["blocked"] is False
    assert preview["verification_status"] == "verified"
    assert preview["safe_create_command"] is not None
    assert "hermes-handoff create" in preview["safe_create_command"]
    assert "--goal 'Ship Phase 3B'" in preview["safe_create_command"]
    assert not (tmp_path / ".hermes" / "handoffs").exists()


def test_prepare_missing_next_task_degrades_to_advise_without_fabricating(tmp_path):
    init_git(tmp_path)

    preview = build_prepare_preview(tmp_path, goal="Known goal", auto_task_state=False)

    assert preview["level"] == "advise"
    assert "missing_required_prepare_input" in preview["signals"]
    assert preview["proposed_goal"] == "Known goal"
    assert preview["proposed_next_task"] is None
    assert preview["safe_create_command"] is None
    assert preview["would_write"] is False
    assert not (tmp_path / ".hermes" / "handoffs").exists()


def test_prepare_blocks_private_key_in_docs_without_printing_secret(tmp_path):
    init_git(tmp_path)
    marker = "PRIVATE" + " " + "KEY"
    private = f"-----BEGIN {marker}-----\nabc\n-----END {marker}-----"
    (tmp_path / "PROGRESS.md").write_text(f"## In Progress\n- Safe item\n\n{private}\n", encoding="utf-8")

    preview = build_prepare_preview(
        tmp_path,
        goal="Safe goal",
        next_task="Safe next",
        auto_task_state=True,
    )

    assert preview["level"] == "block"
    assert preview["safety_status"] == "blocked"
    assert preview["safety"]["blocked"] is True
    assert preview["safe_create_command"] is None
    assert preview["proposed_goal"] is None
    assert preview["proposed_next_task"] is None
    rendered = json.dumps(preview)
    assert private not in rendered
    assert "abc" not in rendered
    assert "private-key" in rendered or "private_key" in rendered
    assert not (tmp_path / ".hermes" / "handoffs").exists()


def test_prepare_blocks_secret_like_repo_path_without_printing_path(tmp_path):
    field = "api" + "_" + "key"
    dummy_value = "dummy" + "-" + "placeholder" + "-1234567890"
    secret_repo = tmp_path / f"{field}={dummy_value}"
    secret_repo.mkdir()
    init_git(secret_repo)

    preview = build_prepare_preview(
        secret_repo,
        goal="Safe goal",
        next_task="Safe next",
        auto_task_state=False,
    )

    assert preview["level"] == "block"
    assert preview["repo_path"] is None
    assert preview["output_dir"] is None
    assert preview["safe_create_command"] is None
    assert preview["would_write"] is False
    rendered_json = json.dumps(preview)
    human = format_prepare_preview(preview)
    assert str(secret_repo) not in rendered_json
    assert str(secret_repo) not in human
    assert dummy_value not in rendered_json
    assert dummy_value not in human
    assert f"{field}={dummy_value}" not in rendered_json
    assert f"{field}={dummy_value}" not in human
    assert not (secret_repo / ".hermes" / "handoffs").exists()


def test_prepare_ignores_custom_output_dir_to_match_safe_create_command(tmp_path):
    init_git(tmp_path)
    custom_output_dir = tmp_path / "custom-handoffs"

    preview = build_prepare_preview(
        tmp_path,
        goal="Ship preview",
        next_task="Inspect output dir",
        auto_task_state=False,
        output_dir=custom_output_dir,
    )

    default_output_dir = tmp_path / ".hermes" / "handoffs"
    assert preview["level"] == "prepare"
    assert preview["output_dir"] == str(default_output_dir)
    assert preview["safe_create_command"] is not None
    assert str(custom_output_dir) not in preview["safe_create_command"]
    assert "--output-dir" not in preview["safe_create_command"]
    assert str(custom_output_dir) not in json.dumps(preview)
    assert not custom_output_dir.exists()
    assert not default_output_dir.exists()


def test_prepare_human_output_is_read_only_and_command_is_conditional(tmp_path):
    init_git(tmp_path)

    prepare = build_prepare_preview(tmp_path, goal="Ship preview", next_task="Inspect command", auto_task_state=False)
    advise = build_prepare_preview(tmp_path, goal="Ship preview", auto_task_state=False)

    prepare_text = format_prepare_preview(prepare)
    advise_text = format_prepare_preview(advise)

    assert "Handoff prepare preview: prepare" in prepare_text
    assert "Read-only preview" in prepare_text
    assert "Safe create command" in prepare_text
    assert "Handoff prepare preview: advise" in advise_text
    assert "Safe create command" not in advise_text


def test_prepare_cli_json_envelope_is_read_only(tmp_path):
    init_git(tmp_path)

    result = run_cli(
        ["prepare", "--repo", str(tmp_path), "--goal", "CLI preview", "--next", "Inspect JSON", "--json"],
        tmp_path,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["success"] is True
    preview = payload["preview"]
    assert preview["level"] == "prepare"
    assert preview["would_write"] is False
    assert preview["proposed_goal"] == "CLI preview"
    assert preview["proposed_next_task"] == "Inspect JSON"
    assert preview["safe_create_command"] is not None
    assert not (tmp_path / ".hermes" / "handoffs").exists()


def test_prepare_cli_block_exit_code_and_secret_safe_output(tmp_path):
    init_git(tmp_path)
    field = "api" + "_" + "key"
    dummy_value = "dummy" + "-" + "placeholder" + "-1234567890"

    result = run_cli(
        ["prepare", "--repo", str(tmp_path), "--goal", f"{field}={dummy_value}", "--next", "Safe next", "--json"],
        tmp_path,
    )

    assert result.returncode == 2
    assert dummy_value not in result.stdout
    payload = json.loads(result.stdout)
    assert payload["success"] is True
    assert payload["preview"]["level"] == "block"
    assert payload["preview"]["safe_create_command"] is None
    assert not (tmp_path / ".hermes" / "handoffs").exists()
