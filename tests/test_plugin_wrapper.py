import json
import subprocess
from pathlib import Path

import pytest

from hermes_continuation import plugin


class FakeCtx:
    def __init__(self):
        self.tools = []
        self.commands = []
        self.hooks = []

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

    def register_hook(self, hook_name, callback):
        self.hooks.append({"hook_name": hook_name, "callback": callback})


class ToolOnlyFakeCtx:
    def __init__(self):
        self.tools = []

    def register_tool(self, **kwargs):
        self.tools.append(kwargs)

    def register_hook(self, hook_name, callback):
        self.hooks = getattr(self, "hooks", [])
        self.hooks.append({"hook_name": hook_name, "callback": callback})


class IncompatibleCommandFakeCtx:
    def __init__(self):
        self.tools = []
        self.commands = []

    def register_tool(self, **kwargs):
        self.tools.append(kwargs)

    def register_command(self, name, handler):
        self.commands.append({"name": name, "handler": handler})


class MissingRegisterToolFakeCtx:
    pass


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
    assert names == [plugin.CREATE_TOOL, plugin.RESUME_TOOL, plugin.PREPARE_TOOL, plugin.WATCH_TOOL, plugin.DOCTOR_TOOL]
    assert all(item["toolset"] == plugin.TOOLSET for item in ctx.tools)
    assert ctx.tools[0]["schema"]["parameters"]["required"] == ["goal", "next_task"]
    assert "auto_task_state" in ctx.tools[0]["schema"]["parameters"]["properties"]
    assert ctx.tools[1]["schema"]["parameters"]["required"] == ["handoff_json"]
    assert ctx.tools[2]["schema"]["parameters"]["required"] == []
    assert "next" in ctx.tools[2]["schema"]["parameters"]["properties"]
    assert ctx.tools[3]["schema"]["parameters"]["required"] == []
    assert "tool_calls" in ctx.tools[3]["schema"]["parameters"]["properties"]
    assert ctx.tools[4]["schema"]["parameters"]["required"] == []
    assert "explicit_request" in ctx.tools[4]["schema"]["parameters"]["properties"]
    assert callable(ctx.tools[0]["handler"])
    assert callable(ctx.tools[1]["handler"])
    assert callable(ctx.tools[2]["handler"])
    assert callable(ctx.tools[3]["handler"])
    assert callable(ctx.tools[4]["handler"])

    assert len(ctx.commands) == 1
    command = ctx.commands[0]
    assert command["name"] == plugin.HANDOFF_COMMAND
    assert command["handler"] is plugin.hermes_handoff_command
    assert "create" in command["args_hint"]
    assert "resume" in command["args_hint"]
    assert "prepare" in command["args_hint"]


def test_register_hook_adds_on_turn_complete():
    ctx = FakeCtx()
    plugin.register(ctx)

    assert len(ctx.hooks) >= 1
    hook_names = [h["hook_name"] for h in ctx.hooks]
    assert "on_turn_complete" in hook_names


def test_on_turn_complete_handler_importable():
    """_on_turn_complete can be imported and called without error."""
    handler = plugin._on_turn_complete
    assert callable(handler)
    # Call with minimal args — should not raise
    handler(
        session_id="test-session",
        source_platform="",
        source_chat_id="",
        message_count=0,
        tool_call_count=0,
        model="",
    )


def test_on_turn_complete_below_threshold():
    """Below threshold should complete without exception."""
    handler = plugin._on_turn_complete
    handler(
        session_id="s1",
        source_platform="cli",
        source_chat_id="test",
        message_count=5,
        tool_call_count=2,
        model="gpt-4",
    )


def test_on_turn_complete_above_threshold():
    """Above threshold should complete without exception (graceful)."""
    handler = plugin._on_turn_complete
    handler(
        session_id="s1",
        source_platform="feishu",
        source_chat_id="nonexistent",
        message_count=40,
        tool_call_count=25,
        model="gpt-4",
    )


def test_tool_only_context_registers_hook():
    """ToolOnlyFakeCtx also registers the hook (has register_hook)."""
    ctx = ToolOnlyFakeCtx()
    plugin.register(ctx)
    assert len(ctx.hooks) >= 1


def test_register_without_command_api_still_registers_tools():
    ctx = ToolOnlyFakeCtx()
    plugin.register(ctx)

    names = [item["name"] for item in ctx.tools]
    assert names == [plugin.CREATE_TOOL, plugin.RESUME_TOOL, plugin.PREPARE_TOOL, plugin.WATCH_TOOL, plugin.DOCTOR_TOOL]


def test_register_with_incompatible_command_api_keeps_tools_and_records_warning():
    ctx = IncompatibleCommandFakeCtx()
    plugin.register(ctx)

    names = [item["name"] for item in ctx.tools]
    assert names == [plugin.CREATE_TOOL, plugin.RESUME_TOOL, plugin.PREPARE_TOOL, plugin.WATCH_TOOL, plugin.DOCTOR_TOOL]
    assert ctx.commands == []
    warnings = ctx._hermes_continuation_registration_warnings
    assert isinstance(warnings, list)
    assert len(warnings) == 1
    assert "optional /handoff command registration" in warnings[0]
    assert "register_command" in warnings[0]
    assert "incompatible API" in warnings[0]


def test_register_missing_register_tool_raises_runtime_error():
    with pytest.raises(RuntimeError, match="register_tool"):
        plugin.register(MissingRegisterToolFakeCtx())


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


def test_plugin_create_string_false_keeps_auto_task_state_opt_in(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    init_git_repo(repo)
    (repo / "PROGRESS.md").write_text("## Completed Work\n- Should stay uncollected\n", encoding="utf-8")
    output_dir = tmp_path / "handoffs"

    create_result = json.loads(
        plugin.hermes_handoff_create(
            {
                "repo_path": str(repo),
                "goal": "Do not auto collect",
                "next_task": "Inspect packet",
                "auto_task_state": "false",
                "output_dir": str(output_dir),
            }
        )
    )

    assert create_result["success"] is True
    packet = json.loads(Path(create_result["json_path"]).read_text(encoding="utf-8"))
    assert packet["task_state"]["completed_work"] == []


def test_plugin_create_invalid_boolean_fails_without_writing(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    output_dir = tmp_path / "handoffs"

    create_result = json.loads(
        plugin.hermes_handoff_create(
            {
                "repo_path": str(repo),
                "goal": "Invalid bool",
                "next_task": "Report error",
                "auto_task_state": "definitely",
                "output_dir": str(output_dir),
            }
        )
    )

    assert create_result["success"] is False
    assert "invalid boolean value" in create_result["error"]
    assert not output_dir.exists()


def test_plugin_prepare_success_is_read_only(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    init_git_repo(repo)

    prepare_result = json.loads(
        plugin.hermes_handoff_prepare(
            {
                "repo_path": str(repo),
                "goal": "Preview plugin prepare",
                "active_task": "wiring command UX",
                "next": "Run targeted tests",
                "auto_task_state": False,
                "verified": ["unit smoke"],
            }
        )
    )

    assert prepare_result["success"] is True
    preview = prepare_result["preview"]
    assert preview["level"] == "prepare"
    assert preview["would_write"] is False
    assert preview["proposed_goal"] == "Preview plugin prepare"
    assert preview["proposed_next_task"] == "Run targeted tests"
    assert preview["verification_status"] == "verified"
    assert preview["safe_create_command"] is not None
    assert not (repo / ".hermes" / "handoffs").exists()


def test_plugin_prepare_missing_next_degrades_to_advise_without_safe_create(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    init_git_repo(repo)

    prepare_result = json.loads(
        plugin.hermes_handoff_prepare({"repo_path": str(repo), "goal": "Known goal", "auto_task_state": False})
    )

    assert prepare_result["success"] is True
    preview = prepare_result["preview"]
    assert preview["level"] == "advise"
    assert "missing_required_prepare_input" in preview["signals"]
    assert preview["proposed_goal"] == "Known goal"
    assert preview["proposed_next_task"] is None
    assert preview["safe_create_command"] is None
    assert preview["would_write"] is False
    assert not (repo / ".hermes" / "handoffs").exists()


def test_plugin_prepare_invalid_boolean_fails_without_writing(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()

    prepare_result = json.loads(
        plugin.hermes_handoff_prepare(
            {
                "repo_path": str(repo),
                "goal": "Invalid bool",
                "next_task": "Report error",
                "auto_task_state": "definitely",
            }
        )
    )

    assert prepare_result["success"] is False
    assert "invalid boolean value" in prepare_result["error"]
    assert not (repo / ".hermes" / "handoffs").exists()


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

    markdown_resume_output = plugin.hermes_handoff_command(f"resume {handoff_files[0]} --markdown")
    assert markdown_resume_output.startswith("## Resume Prompt\n\n")
    assert "Ship command UX" in markdown_resume_output


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


def test_handoff_command_prepare_human_preview_is_read_only(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    init_git_repo(repo)

    output = plugin.hermes_handoff_command(
        f'prepare repo_path={repo} goal="Command prepare" next_task="Inspect preview" auto_task_state=false verified=unit'
    )

    assert "交接包預覽" in output
    assert "可準備交接" in output
    assert "純讀取模式" in output
    assert "目標: Command prepare" in output
    assert "下一步: Inspect preview" in output
    assert "安全的交接指令" in output
    assert not (repo / ".hermes" / "handoffs").exists()


def test_handoff_command_prepare_missing_next_is_advise_without_safe_create(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    init_git_repo(repo)

    output = plugin.hermes_handoff_command(f'prepare repo_path={repo} goal="Command advise" auto_task_state=false')

    assert "交接包預覽" in output
    assert "建議交接" in output
    assert "資訊不完整" in output
    assert "安全的交接指令" not in output
    assert not (repo / ".hermes" / "handoffs").exists()


def test_handoff_command_help_and_parse_errors():
    help_output = plugin.hermes_handoff_command("")
    assert "/handoff create" in help_output
    assert "/handoff prepare" in help_output
    assert "Bare /handoff shows this help" in help_output

    explicit_help_output = plugin.hermes_handoff_command("help")
    assert explicit_help_output == help_output

    error_output = plugin.hermes_handoff_command("create goal-only")
    assert "Handoff command error" in error_output
    assert "expected key=value" in error_output

    bool_error_output = plugin.hermes_handoff_command('create repo_path=. goal="Bool UX" next_task="Stop" auto_task_state=maybe')
    assert "Handoff command error" in bool_error_output
    assert "invalid boolean value" in bool_error_output

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
