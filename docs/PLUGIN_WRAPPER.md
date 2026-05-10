# Hermes Plugin Wrapper

## Purpose

The plugin wrapper lets Hermes load the continuation sidecar as a normal plugin without changing Hermes core.

The wrapper is intentionally thin:

- Hermes discovers the package through the `hermes_agent.plugins` entry point.
- `register(ctx)` registers plugin tools with Hermes' normal tool registry.
- Tool handlers call the existing sidecar modules for git state, packet building, validation, redaction, and Markdown rendering.
- The wrapper returns JSON strings because Hermes tool handlers expect JSON-compatible string output.

## Install / Enable

From this repository:

```bash
python -m pip install -e .
```

The package exposes this entry point:

```toml
[project.entry-points."hermes_agent.plugins"]
hermes-continuation = "hermes_continuation.plugin"
```

Hermes plugin loading is still controlled by Hermes' plugin configuration. If a local Hermes build requires explicit plugin enablement, enable `hermes-continuation` in the normal Hermes plugin flow and restart the session/gateway so tool discovery refreshes.

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

## Safety Boundaries

- The wrapper does not modify Hermes core.
- The wrapper does not start or restart Hermes sessions.
- The wrapper does not parse full transcripts automatically.
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

## Acceptance Gates

- `register(ctx)` registers both tools with OpenAI-style schemas.
- `hermes_handoff_create` writes both Markdown and JSON in a temporary repo smoke test.
- `hermes_handoff_resume` returns the same prompt from the generated JSON.
- Invalid/missing handoff JSON returns `success: false`.
- Full project tests pass.
- Secret scan finds no credentials.
