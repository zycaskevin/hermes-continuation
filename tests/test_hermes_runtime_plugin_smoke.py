"""Smoke the continuation plugin through the real local Hermes plugin runtime.

The test stays portable: it skips when the developer's Hermes checkout/venv is
not present, and it uses a temporary HERMES_HOME so ~/.hermes/config.yaml is not
read or modified.
"""

from __future__ import annotations

import os
import subprocess
import textwrap
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
REPO_SRC = REPO_ROOT / "src"
DEFAULT_HERMES_SOURCE = Path("/home/zycas/.hermes/hermes-agent")


def _resolve_hermes_source() -> Path:
    override = os.environ.get("HERMES_AGENT_SOURCE", "").strip()
    if override:
        return Path(override).expanduser()
    return DEFAULT_HERMES_SOURCE


def _resolve_hermes_python(hermes_source: Path) -> Path:
    override = os.environ.get("HERMES_AGENT_PYTHON", "").strip()
    if override:
        return Path(override).expanduser()
    return hermes_source / "venv" / "bin" / "python3"


RUNTIME_SMOKE_SCRIPT = r"""
import importlib.metadata
import json
import os
import sys
from pathlib import Path

repo_root = Path(sys.argv[1])
repo_src = repo_root / "src"
hermes_source = Path(sys.argv[2])

for path in (str(repo_src), str(hermes_source)):
    if path not in sys.path:
        sys.path.insert(0, path)

hermes_home = Path(os.environ["HERMES_HOME"])
config_path = hermes_home / "config.yaml"
assert config_path.is_file(), f"missing isolated Hermes config: {config_path}"
assert str(hermes_home) != str(Path.home() / ".hermes"), "smoke must not use default ~/.hermes"

entry_points = importlib.metadata.entry_points()
if hasattr(entry_points, "select"):
    group_eps = entry_points.select(group="hermes_agent.plugins")
elif isinstance(entry_points, dict):
    group_eps = entry_points.get("hermes_agent.plugins", [])
else:
    group_eps = [ep for ep in entry_points if ep.group == "hermes_agent.plugins"]

matches = [ep for ep in group_eps if ep.name == "hermes-continuation"]
assert matches, "hermes-continuation entry point not visible to Hermes interpreter"
assert matches[0].value == "hermes_continuation.plugin", matches[0]

from hermes_cli.plugins import (
    discover_plugins,
    get_plugin_command_handler,
    get_plugin_commands,
    get_plugin_manager,
    resolve_plugin_command_result,
)
from tools.registry import registry

discover_plugins(force=True)
manager = get_plugin_manager()
plugins = manager.list_plugins()
continuation = [
    plugin
    for plugin in plugins
    if plugin.get("key") == "hermes-continuation" or plugin.get("name") == "hermes-continuation"
]
assert continuation, json.dumps(plugins, indent=2, sort_keys=True)
info = continuation[0]
assert info["source"] == "entrypoint", info
assert info["enabled"] is True, info
assert info["error"] is None, info
assert info["tools"] == 4, info
assert info["commands"] == 1, info

create_entry = registry.get_entry("hermes_handoff_create")
resume_entry = registry.get_entry("hermes_handoff_resume")
prepare_entry = registry.get_entry("hermes_handoff_prepare")
watch_entry = registry.get_entry("hermes_handoff_watch")
assert create_entry is not None, "missing hermes_handoff_create registry entry"
assert resume_entry is not None, "missing hermes_handoff_resume registry entry"
assert prepare_entry is not None, "missing hermes_handoff_prepare registry entry"
assert watch_entry is not None, "missing hermes_handoff_watch registry entry"
assert create_entry.toolset == "hermes_continuation"
assert resume_entry.toolset == "hermes_continuation"
assert prepare_entry.toolset == "hermes_continuation"
assert watch_entry.toolset == "hermes_continuation"
assert callable(create_entry.handler)
assert callable(resume_entry.handler)
assert callable(prepare_entry.handler)
assert callable(watch_entry.handler)
assert create_entry.schema["parameters"]["required"] == ["goal", "next_task"]
assert resume_entry.schema["parameters"]["required"] == ["handoff_json"]
assert prepare_entry.schema["parameters"]["required"] == []
prepare_properties = prepare_entry.schema["parameters"]["properties"]
for field in (
    "repo_path",
    "goal",
    "active_task",
    "in_progress",
    "next_task",
    "next",
    "auto_task_state",
    "verified",
    "failing",
    "not_run",
):
    assert field in prepare_properties, prepare_entry.schema
assert prepare_properties["repo_path"]["type"] == "string"
assert prepare_properties["goal"]["type"] == "string"
assert prepare_properties["next_task"]["type"] == "string"
assert prepare_properties["auto_task_state"]["type"] == "boolean"
assert prepare_properties["verified"]["type"] == "array"
assert prepare_properties["failing"]["type"] == "array"
assert prepare_properties["not_run"]["type"] == "array"

commands = get_plugin_commands()
assert "handoff" in commands, commands
command_entry = commands["handoff"]
assert command_entry["plugin"] == "hermes-continuation", command_entry
assert callable(command_entry["handler"])
handler = get_plugin_command_handler("handoff")
assert callable(handler)
assert handler is command_entry["handler"]
help_text = resolve_plugin_command_result(handler("help"))
assert isinstance(help_text, str)
assert "/handoff create" in help_text
assert "Bare /handoff shows this help" in help_text

print("SMOKE_OK", json.dumps(info, sort_keys=True))
"""


def test_hermes_runtime_discovers_and_loads_continuation_plugin(tmp_path: Path) -> None:
    """Verify entry-point discovery, runtime loading, tools, and /handoff help."""
    hermes_source = _resolve_hermes_source()
    hermes_python = _resolve_hermes_python(hermes_source)

    if not hermes_source.is_dir():
        pytest.skip(
            "Hermes source checkout not found: "
            f"{hermes_source}. Set HERMES_AGENT_SOURCE to override "
            f"(default: {DEFAULT_HERMES_SOURCE})."
        )
    if not hermes_python.is_file():
        pytest.skip(
            "Hermes runtime Python not found: "
            f"{hermes_python}. Set HERMES_AGENT_PYTHON to override."
        )

    hermes_home = tmp_path / "hermes-home"
    hermes_home.mkdir()
    (hermes_home / "config.yaml").write_text(
        textwrap.dedent(
            """
            plugins:
              enabled:
                - hermes-continuation
              disabled: []
            """
        ).lstrip(),
        encoding="utf-8",
    )
    isolated_home = tmp_path / "home"
    isolated_home.mkdir()

    env = os.environ.copy()
    env["HERMES_HOME"] = str(hermes_home)
    env["HOME"] = str(isolated_home)
    env["PYTHONPATH"] = os.pathsep.join(
        [str(REPO_SRC), str(hermes_source), env.get("PYTHONPATH", "")]
    )

    completed = subprocess.run(
        [str(hermes_python), "-c", RUNTIME_SMOKE_SCRIPT, str(REPO_ROOT), str(hermes_source)],
        cwd=str(REPO_ROOT),
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=30,
    )

    assert completed.returncode == 0, (
        "Hermes runtime plugin smoke failed\n"
        f"command: {hermes_python} -c <script> {REPO_ROOT} {hermes_source}\n"
        f"stdout:\n{completed.stdout}\n"
        f"stderr:\n{completed.stderr}"
    )
    assert "SMOKE_OK" in completed.stdout
