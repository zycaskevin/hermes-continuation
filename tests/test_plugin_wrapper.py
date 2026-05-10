import json
import subprocess
from pathlib import Path

from hermes_continuation import plugin


class FakeCtx:
    def __init__(self):
        self.tools = []

    def register_tool(self, **kwargs):
        self.tools.append(kwargs)


def init_git_repo(path: Path) -> None:
    subprocess.run(["git", "init"], cwd=path, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=path, check=True)
    (path / "README.md").write_text("# Test\n", encoding="utf-8")
    subprocess.run(["git", "add", "README.md"], cwd=path, check=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=path, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)


def test_register_adds_create_and_resume_tools():
    ctx = FakeCtx()
    plugin.register(ctx)

    names = [item["name"] for item in ctx.tools]
    assert names == [plugin.CREATE_TOOL, plugin.RESUME_TOOL]
    assert all(item["toolset"] == plugin.TOOLSET for item in ctx.tools)
    assert ctx.tools[0]["schema"]["parameters"]["required"] == ["goal", "next_task"]
    assert ctx.tools[1]["schema"]["parameters"]["required"] == ["handoff_json"]
    assert callable(ctx.tools[0]["handler"])
    assert callable(ctx.tools[1]["handler"])


def test_plugin_create_and_resume_roundtrip(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    init_git_repo(repo)
    output_dir = tmp_path / "handoffs"

    create_result = json.loads(
        plugin.hermes_handoff_create(
            {
                "repo_path": str(repo),
                "goal": "Ship plugin wrapper",
                "active_task": "testing wrapper",
                "next_task": "Run verification",
                "completed": ["Documented design"],
                "verified": ["unit smoke"],
                "output_dir": str(output_dir),
            }
        )
    )

    assert create_result["success"] is True
    md_path = Path(create_result["markdown_path"])
    json_path = Path(create_result["json_path"])
    assert md_path.is_file()
    assert json_path.is_file()
    assert "You are taking over" in create_result["resume_prompt"]
    assert "## Resume Prompt" in md_path.read_text(encoding="utf-8")

    resume_result = json.loads(plugin.hermes_handoff_resume({"handoff_json": str(json_path)}))
    assert resume_result["success"] is True
    assert resume_result["resume_prompt"] == create_result["resume_prompt"]
    assert resume_result["output"] == create_result["resume_prompt"]

    markdown_result = json.loads(plugin.hermes_handoff_resume({"handoff_json": str(json_path), "markdown": True}))
    assert markdown_result["success"] is True
    assert markdown_result["output"].startswith("## Resume Prompt\n\n")


def test_plugin_resume_missing_file_returns_error(tmp_path):
    result = json.loads(plugin.hermes_handoff_resume({"handoff_json": str(tmp_path / "missing.json")}))
    assert result["success"] is False
    assert "not found" in result["error"]


def test_plugin_create_missing_required_fields_returns_error(tmp_path):
    result = json.loads(plugin.hermes_handoff_create({"repo_path": str(tmp_path), "goal": ""}))
    assert result["success"] is False
    assert "goal" in result["error"]
