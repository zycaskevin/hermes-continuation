# Resume Command and Plugin Wrapper Direction

## Goal

`hermes-handoff resume <handoff.json>` extracts the already-generated `resume_prompt` from a validated handoff packet so a user can paste or pipe it into a fresh Hermes session.

The command is intentionally narrow: it turns a machine-readable handoff JSON into the exact prompt text needed for continuation. It must not create a new handoff, mutate the input file, or infer missing session state.

## Command UX

Default usage prints only the prompt to stdout:

```bash
hermes-handoff resume .hermes/handoffs/20260509-153000-handoff.json
```

Expected stdout by default:

```text
You are taking over an in-progress Hermes long task.
...
```

There are no labels, headings, file paths, or status lines in default stdout. This keeps the command safe for copy/paste and shell piping.

Optional human-readable output may be requested with:

```bash
hermes-handoff resume --markdown .hermes/handoffs/20260509-153000-handoff.json
```

`--markdown` may wrap the prompt in a concise section for display, but it is not the default because fresh-session handoff should be prompt-only.

## Validation and Error Handling

Before printing anything, `resume` must:

1. Confirm the path exists and is a file.
2. Parse the file as JSON.
3. Confirm the decoded value is a JSON object.
4. Run the existing packet validation.
5. Confirm `resume_prompt` is present and non-empty after trimming whitespace.

Failures must return a nonzero exit code and print a clear `error: ...` message to stderr. Error cases include:

- missing file
- invalid JSON
- non-object JSON
- schema/validation failure
- missing or empty `resume_prompt`

The command must not write runtime artifacts or modify the handoff file.

## Why Sidecar First, Plugin Wrapper Later

The continuation packet format is still the product contract. A sidecar CLI is the smallest surface that can prove the contract without coupling to Hermes internals:

- It can be tested independently with normal Python tests.
- It avoids destabilizing Hermes core while packet shape and UX settle.
- It keeps generated handoffs local and explicit.
- It gives users a working create/resume loop before any plugin automation exists.

A later plugin wrapper can call the same sidecar commands or import the same package once the CLI contract is stable. The wrapper should add convenience, not change the packet semantics.

## Boundaries

Do not implement in this phase:

- Hermes core modifications.
- A built-in `/handoff` Hermes command.
- Automatic session restart or agent launch.
- Automatic transcript parsing.
- Automatic latest-handoff discovery.
- Cloud sync, dashboards, or multi-agent orchestration.

## Acceptance Gates

- Docs are updated before code changes for the resume implementation.
- `python -m hermes_continuation.cli --help` shows `resume`.
- `python -m hermes_continuation.cli resume --help` passes.
- `hermes-handoff resume <handoff.json>` validates the JSON and prints only `resume_prompt` by default.
- `--markdown` produces a concise human-readable wrapper without changing default behavior.
- Missing file, invalid JSON, invalid packet, and empty prompt cases fail nonzero with stderr errors.
- Existing `create` behavior and tests still pass.
- Resume does not write `.hermes/handoffs/` files or mutate the input handoff.
