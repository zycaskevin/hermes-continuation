import json
import subprocess
from pathlib import Path

from hermes_continuation.context_monitor import collect_context
from hermes_continuation.watch import build_watch_result


def init_git(path: Path) -> None:
    subprocess.run(
        ["git", "init"],
        cwd=path,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=True,
    )


def test_collects_changed_files_in_git_repo(tmp_path):
    init_git(tmp_path)
    (tmp_path / "changed.txt").write_text("changed")

    context = collect_context(tmp_path)

    assert context["source"] == "auto"
    assert context["changed_files"]
    assert context["changed_files"][0]["path"] == "changed.txt"


def test_degrade_non_git_directory(tmp_path):
    context = collect_context(tmp_path)

    assert context == {
        "tool_calls": None,
        "elapsed_minutes": None,
        "changed_files": [],
        "source": "auto",
    }


def test_manual_values_override_auto(tmp_path):
    context = collect_context(tmp_path, tool_calls=7, elapsed_minutes=42)

    assert context["tool_calls"] == 7
    assert context["elapsed_minutes"] == 42


def test_source_field_marks_auto_vs_manual(tmp_path):
    assert collect_context(tmp_path)["source"] == "auto"
    assert collect_context(tmp_path, tool_calls=0)["source"] == "manual"
    assert collect_context(tmp_path, elapsed_minutes=0)["source"] == "manual"


def test_never_collects_conversation_content(tmp_path, monkeypatch):
    init_git(tmp_path)
    private_marker = "private-conversation-token-12345"
    (tmp_path / "conversation.md").write_text(private_marker)

    def fail_read_text(self, *args, **kwargs):
        raise AssertionError(f"unexpected file content read: {self}")

    def fail_read_bytes(self, *args, **kwargs):
        raise AssertionError(f"unexpected file content read: {self}")

    monkeypatch.setattr(Path, "read_text", fail_read_text)
    monkeypatch.setattr(Path, "read_bytes", fail_read_bytes)

    context = collect_context(tmp_path)

    assert private_marker not in json.dumps(context)
    assert context["changed_files"][0]["path"] == "conversation.md"


def test_integration_with_watch(tmp_path):
    init_git(tmp_path)
    context = collect_context(tmp_path, tool_calls=5, elapsed_minutes=30)

    result = build_watch_result(
        tmp_path,
        goal="Finish context monitor",
        context=context,
        auto_task_state=False,
    )

    assert result["level"] == "advise"
    assert "watch_tool_calls_threshold" in result["watch_signals"]
    assert "watch_elapsed_minutes_threshold" in result["watch_signals"]
    assert result["would_write"] is False
