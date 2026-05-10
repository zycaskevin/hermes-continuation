# Hermes Plugin Wrapper

## Purpose

The plugin wrapper lets Hermes load the continuation sidecar as a normal plugin without changing Hermes core.

The wrapper is intentionally thin:

- Hermes discovers the package through the `hermes_agent.plugins` entry point.
- `register(ctx)` registers plugin tools with Hermes' normal tool registry.
- When Hermes exposes `ctx.register_command`, `register(ctx)` also registers a plugin slash command named `/handoff`.
- Tool handlers call the existing sidecar modules for git state, packet building, validation, redaction, and Markdown rendering.
- The wrapper returns JSON strings because Hermes tool handlers expect JSON-compatible string output.

## Install / Enable

From this repository, local CLI development can use the active Python environment:

```bash
python -m pip install -e .
```

Hermes runtime discovery must see the package from the interpreter that runs Hermes. On this local checkout, install with the Hermes venv Python:

```bash
cd /home/zycas/hermes-continuation
/home/zycas/.hermes/hermes-agent/venv/bin/python3 -m pip install -e .
```

The package exposes this entry point:

```toml
[project.entry-points."hermes_agent.plugins"]
hermes-continuation = "hermes_continuation.plugin"
```

Hermes entry-point plugins are opt-in. Enable `hermes-continuation` with Hermes' normal plugin-management flow, or add it to Hermes config:

```yaml
plugins:
  enabled:
    - hermes-continuation
  disabled: []
```

Restart the Hermes CLI/gateway after install or config changes so runtime plugin discovery refreshes.

## Registered Tools

### `hermes_handoff_create`

Creates a Markdown + JSON handoff packet.

Main parameters:

- `repo_path`: repository path to inspect. Defaults to `.`.
- `goal`: current goal. Required.
- `next_task`: next recommended task. Required.
- `active_task`: current in-progress work.
- `completed`, `verified`, `failing`, `not_run`, `known_issues`, `do_not_touch`: optional string lists.
- `output_dir`: optional output directory. Defaults to `<repo_path>/.hermes/handoffs`.

Success response:

```json
{
  "success": true,
  "markdown_path": "...",
  "json_path": "...",
  "resume_prompt": "...",
  "redaction_count": 0
}
```

### `hermes_handoff_resume`

Reads a handoff JSON and returns the stored resume prompt.

Main parameters:

- `handoff_json`: path to an existing handoff JSON file. Required.
- `markdown`: when true, wraps the prompt under `## Resume Prompt`.

Success response:

```json
{
  "success": true,
  "resume_prompt": "...",
  "output": "..."
}
```

## Registered Slash Command

When running on a Hermes build with plugin command support, the wrapper registers:

```text
/handoff [create <args>|resume <handoff.json>|help]
```

The local Hermes plugin API used for this MVP is:

```python
ctx.register_command(
    "handoff",
    handler=hermes_handoff_command,
    description="Create or resume Hermes continuation handoffs.",
    args_hint="create <json>|resume <handoff.json>",
)
```

The command handler receives the trailing text as `raw_args: str` and returns a display string. If `ctx.register_command` is not present, the plugin still registers the two tools and skips command registration.

### Create through `/handoff`

Use JSON for the most predictable behavior:

```text
/handoff create {"repo_path":".","goal":"Fix dashboard health page","next_task":"Run build and browser QA"}
```

The leading `create` is optional when the remaining text is JSON or key/value create arguments:

```text
/handoff {"repo_path":".","goal":"Fix dashboard health page","next_task":"Run build and browser QA"}
```

Simple shell-style key/value arguments are also accepted for scalar fields:

```text
/handoff create repo_path=. goal="Fix dashboard health page" next_task="Run build and browser QA"
```

Create uses the existing `hermes_handoff_create` handler, so `goal` and `next_task` remain required and the result contract still uses `success` in the underlying JSON envelope.

### Resume through `/handoff`

Resume from an existing handoff JSON:

```text
/handoff resume .hermes/handoffs/<timestamp>-handoff.json
```

You may also pass JSON if you need the Markdown wrapper option:

```text
/handoff resume {"handoff_json":".hermes/handoffs/<timestamp>-handoff.json","markdown":true}
```

Resume uses the existing `hermes_handoff_resume` handler and returns the stored prompt text for pasting into a fresh session.

## Safety Boundaries

- The wrapper does not modify Hermes core.
- The wrapper does not start or restart Hermes sessions.
- The wrapper does not parse full transcripts automatically.
- The `/handoff` command is plugin-only and gracefully disappears on Hermes versions without `register_command`.
- The wrapper does not bypass the existing redaction/private-key fail-closed behavior.
- Runtime handoff artifacts remain under `.hermes/handoffs/` by default and should not be committed.

## Error Contract

Handlers fail safely and return a JSON envelope instead of raising raw exceptions to the agent:

```json
{
  "success": false,
  "error": "..."
}
```

Errors are intentionally concise. They should not include credentials, tokens, connection strings, or private keys.

## Runtime Smoke Gate

The repository includes a real Hermes runtime/plugin smoke test:

```bash
cd /home/zycas/hermes-continuation
python -m pytest -q tests/test_hermes_runtime_plugin_smoke.py
```

What it verifies:

- Uses `/home/zycas/.hermes/hermes-agent/venv/bin/python3` in a subprocess when that local Hermes checkout exists; otherwise pytest skips so the repository stays portable.
- Sets `PYTHONPATH` to this repo's `src/` plus `/home/zycas/.hermes/hermes-agent` so Hermes runtime APIs and this editable source are imported together.
- Uses a temporary `HERMES_HOME` containing only:

  ```yaml
  plugins:
    enabled:
      - hermes-continuation
    disabled: []
  ```

- Does **not** read or modify `~/.hermes/config.yaml`.
- Confirms the `hermes_agent.plugins` entry point is visible to the Hermes interpreter and resolves to `hermes_continuation.plugin`.
- Calls Hermes runtime APIs: `discover_plugins`, `get_plugin_manager`, `get_plugin_commands`, `get_plugin_command_handler`, and `resolve_plugin_command_result`.
- Asserts the runtime lists `hermes-continuation` as an enabled entry-point plugin with no error, 2 tools, and 1 command.
- Asserts the real `tools.registry.registry` contains `hermes_handoff_create` and `hermes_handoff_resume` under the `hermes_continuation` toolset with the expected required schema fields.
- Resolves `/handoff help` through the runtime command registry and checks that help contains `/handoff create` plus `Bare /handoff shows this help`.
- Avoids creating runtime handoff packets; it only invokes `/handoff help`.

Expected success output includes `SMOKE_OK` in the subprocess stdout.

## Troubleshooting

### Plugin not listed

Likely causes:

- The package is installed into a different Python environment than Hermes uses.
- The `hermes_agent.plugins` entry point metadata is not visible to the Hermes interpreter.
- Hermes was not restarted after install.

Fix:

```bash
cd /home/zycas/hermes-continuation
/home/zycas/.hermes/hermes-agent/venv/bin/python3 -m pip install -e .
python -m pytest -q tests/test_hermes_runtime_plugin_smoke.py
```

If you are not on the local `/home/zycas` Hermes checkout, replace the venv path with the Python interpreter used by your Hermes CLI.

### Plugin listed but not enabled

Hermes entry-point plugins are opt-in. Enable `hermes-continuation` in the normal Hermes plugin flow or configure:

```yaml
plugins:
  enabled:
    - hermes-continuation
  disabled: []
```

Also check that `plugins.disabled` does not contain `hermes-continuation`. Restart the Hermes CLI/gateway after changing config.

### `/handoff` missing

Confirm the plugin is enabled and loaded first. If the tools are present but `/handoff` is missing, the Hermes build may be too old or may not expose `PluginContext.register_command`. In that case the wrapper still registers the two tools and intentionally skips command registration for backward compatibility.

### Entry point not visible to Hermes interpreter

Run install with the Hermes interpreter, not just `python` from the shell:

```bash
/home/zycas/.hermes/hermes-agent/venv/bin/python3 -m pip install -e /home/zycas/hermes-continuation
```

The source tree currently includes `src/hermes_continuation.egg-info`, which can make entry-point metadata visible under `PYTHONPATH` during tests, but the canonical runtime install is still editable install into Hermes' interpreter.

### Generated artifacts

Runtime handoff packets are written under `.hermes/handoffs/` by default and should not be committed. Local graph/report output such as `graphify-out/` is generated maintenance output and should not be staged unless explicitly requested.

### Restart/reset needed

Plugin discovery is cached in a running Hermes process. After install, enable/disable, or source changes, restart the Hermes CLI/gateway. For in-process tests, use `discover_plugins(force=True)` to refresh the runtime plugin manager.

## Acceptance Gates

- `register(ctx)` registers both tools with OpenAI-style schemas.
- Real Hermes runtime smoke passes: `python -m pytest -q tests/test_hermes_runtime_plugin_smoke.py`.
- On Hermes builds with `register_command`, `register(ctx)` registers `/handoff` with a raw-text command handler.
- On contexts without `register_command`, `register(ctx)` still succeeds and registers the tools.
- `hermes_handoff_create` writes both Markdown and JSON in a temporary repo smoke test.
- `hermes_handoff_resume` returns the same prompt from the generated JSON.
- `/handoff create ...` writes through the existing create handler, and `/handoff resume ...` reads through the existing resume handler.
- Invalid/missing handoff JSON returns `success: false`.
- Full project tests pass.
- Secret scan finds no credentials.
