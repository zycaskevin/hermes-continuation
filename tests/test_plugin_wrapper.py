import json
import subprocess
from pathlib import Path

from hermes_continuation import plugin


class FakeCtx:
    def __init__(self):
        self.tools = []
        self.commands = []

    def register_tool(self, **kwargs):
        self.tools.append(kwargs)

    def register_command(self, name, handler, description="", args_hint=""):
        self.commands.append(
            {
                "name": name,
                "handler": handler,
                "description": description,
                "args_hint": args_hint,
            }
        )


class ToolOnlyFakeCtx:
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


def test_register_adds_create_resume_tools_and_handoff_command():
    ctx = FakeCtx()
    plugin.register(ctx)

    names = [item["name"] for item in ctx.tools]
    assert names == [plugin.CREATE_TOOL, plugin.RESUME_TOOL]
    assert all(item["toolset"] == plugin.TOOLSET for item in ctx.tools)
    assert ctx.tools[0]["schema"]["parameters"]["required"] == ["goal", "next_task"]
    assert "auto_task_state" in ctx.tools[0]["schema"]["parameters"]["properties"]
    assert ctx.tools[1]["schema"]["parameters"]["required"] == ["handoff_json"]
    assert callable(ctx.tools[0]["handler"])
    assert callable(ctx.tools[1]["handler"])

    assert len(ctx.commands) == 1
    command = ctx.commands[0]
    assert command["name"] == plugin.HANDOFF_COMMAND
    assert command["handler"] is plugin.hermes_handoff_command
    assert "create" in command["args_hint"]
    assert "resume" in command["args_hint"]


def test_register_without_command_api_still_registers_tools():
    ctx = ToolOnlyFakeCtx()
    plugin.register(ctx)

    names = [item["name"] for item in ctx.tools]
    assert names == [plugin.CREATE_TOOL, plugin.RESUME_TOOL]


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


def test_plugin_create_auto_task_state_merges_manual_values(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    init_git_repo(repo)
    (repo / "PROGRESS.md").write_text(
        """# Progress

## Completed Work
- Auto plugin completed

## Active Task
- Auto plugin active

## Known Issues
- Auto plugin blocker

## Out of scope
- Auto plugin boundary

## Next Recommended Task
- Auto plugin next
""",
        encoding="utf-8",
    )
    output_dir = tmp_path / "handoffs"

    create_result = json.loads(
        plugin.hermes_handoff_create(
            {
                "repo_path": str(repo),
                "goal": "Auto plugin flow",
                "active_task": "Manual plugin active",
                "next_task": "Manual plugin next",
                "completed": ["Manual plugin completed"],
                "known_issues": ["Manual plugin blocker"],
                "do_not_touch": ["Manual plugin boundary"],
                "auto_task_state": True,
                "output_dir": str(output_dir),
            }
        )
    )

    assert create_result["success"] is True
    packet = json.loads(Path(create_result["json_path"]).read_text(encoding="utf-8"))
    task_state = packet["task_state"]
    assert "Auto plugin completed" in task_state["completed_work"]
    assert "Manual plugin completed" in task_state["completed_work"]
    assert "Auto plugin active" in task_state["in_progress"]
    assert "Manual plugin active" in task_state["in_progress"]
    assert "Auto plugin blocker" in task_state["known_blockers"]
    assert "Manual plugin blocker" in task_state["known_blockers"]
    assert "Auto plugin boundary" in task_state["do_not_touch"]
    assert "Manual plugin boundary" in task_state["do_not_touch"]
    assert task_state["next_recommended_task"] == "Manual plugin next"


def test_handoff_command_create_and_resume_roundtrip(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    init_git_repo(repo)
    output_dir = tmp_path / "handoffs"
    args = {
        "repo_path": str(repo),
        "goal": "Ship command UX",
        "next_task": "Run targeted tests",
        "output_dir": str(output_dir),
    }

    create_output = plugin.hermes_handoff_command(f"create {json.dumps(args)}")

    assert "Created Hermes handoff packet" in create_output
    assert "Resume later with: /handoff resume" in create_output
    handoff_files = sorted(output_dir.glob("*-handoff.json"))
    assert len(handoff_files) == 1

    resume_output = plugin.hermes_handoff_command(f"resume {handoff_files[0]}")
    assert "You are taking over" in resume_output
    assert "Ship command UX" in resume_output


def test_handoff_command_implicit_create_key_value_args(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    init_git_repo(repo)
    output_dir = tmp_path / "handoffs"

    output = plugin.hermes_handoff_command(
        f'repo_path={repo} output_dir={output_dir} goal="Implicit create" next_task="Verify command"'
    )

    assert "Created Hermes handoff packet" in output
    assert len(list(output_dir.glob("*-handoff.json"))) == 1


def test_handoff_command_help_and_parse_errors():
    help_output = plugin.hermes_handoff_command("")
    assert "/handoff create" in help_output
    assert "Bare /handoff shows this help" in help_output

    error_output = plugin.hermes_handoff_command("create goal-only")
    assert "Handoff command error" in error_output
    assert "expected key=value" in error_output

    unknown_output = plugin.hermes_handoff_command("frobnicate")
    assert "Unknown handoff subcommand: frobnicate" in unknown_output
    assert "/handoff create" in unknown_output


def test_plugin_resume_missing_file_returns_error(tmp_path):
    result = json.loads(plugin.hermes_handoff_resume({"handoff_json": str(tmp_path / "missing.json")}))
    assert result["success"] is False
    assert "not found" in result["error"]


def test_plugin_create_missing_required_fields_returns_error(tmp_path):
    result = json.loads(plugin.hermes_handoff_create({"repo_path": str(tmp_path), "goal": ""}))
    assert result["success"] is False
    assert "goal" in result["error"]
