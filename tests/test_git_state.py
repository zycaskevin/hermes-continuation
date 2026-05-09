import subprocess

from hermes_continuation.git_state import collect_git_state


def test_collect_git_state_degrades_for_non_git(tmp_path):
    state = collect_git_state(tmp_path)
    assert state["path"] == str(tmp_path.resolve())
    assert state["git_available"] is False
    assert state["changed_files"] == []


def test_collect_git_state_for_git_repo(tmp_path):
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, stdout=subprocess.PIPE)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=tmp_path, check=True)
    (tmp_path / "hello.txt").write_text("hello")
    subprocess.run(["git", "add", "hello.txt"], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-m", "initial"], cwd=tmp_path, check=True, stdout=subprocess.PIPE)
    (tmp_path / "hello.txt").write_text("changed")

    state = collect_git_state(tmp_path)

    assert state["git_available"] is True
    assert state["head"]
    assert "hello.txt" in state["status_short"]
    assert state["changed_files"][0]["path"] == "hello.txt"
