# Hermes Continuation

`hermes-continuation` is a small Hermes-native sidecar that creates structured handoff packets for long-running agent work.

The first MVP does **one thing only**: generate a local Markdown + JSON handoff packet that a fresh Hermes session can read before continuing work.

## Why

Long agent tasks can become brittle when context grows, gets compressed, or needs to move to a fresh session. A normal chat summary is not enough because the next agent needs concrete state:

- current goal
- repository path, branch, commit, and changed files
- completed work and next recommended task
- verified / failing / not-run gates
- known blockers
- do-not-touch boundaries
- safety/redaction status
- a copy-paste resume prompt

## Install

For local CLI development, install into your active Python environment:

```bash
python -m pip install -e .
```

For Hermes runtime/plugin use, install the package into the same interpreter that runs Hermes. On this local Hermes checkout that is:

```bash
cd /home/zycas/hermes-continuation
/home/zycas/.hermes/hermes-agent/venv/bin/python3 -m pip install -e .
```

The package exposes the `hermes-continuation = hermes_continuation.plugin` entry point in the `hermes_agent.plugins` group.

## CLI usage

```bash
hermes-handoff create \
  --repo . \
  --goal "Fix dashboard health page" \
  --completed "Updated health copy" \
  --verified "pytest -q passed" \
  --not-run "browser QA" \
  --do-not-touch "billing code" \
  --next "Run build and browser QA"
```

Equivalent module form:

```bash
python -m hermes_continuation.cli create --repo . --goal "Smoke test" --next "Inspect output"
```

Output:

```text
.hermes/handoffs/<timestamp>-handoff.md
.hermes/handoffs/<timestamp>-handoff.json
```

Resume from a handoff:

```bash
hermes-handoff resume .hermes/handoffs/<timestamp>-handoff.json
```

By default, `resume` prints only the clean resume prompt so it can be pasted into a fresh Hermes session. Use `--markdown` when you want a labeled Markdown section.

## Hermes plugin wrapper

The package also exposes a thin Hermes plugin wrapper through the `hermes_agent.plugins` entry point. Hermes entry-point plugins are opt-in. Enable this plugin in Hermes config:

```yaml
plugins:
  enabled:
    - hermes-continuation
  disabled: []
```

Alternatively, use Hermes' normal plugin-management flow to enable `hermes-continuation`, then restart the Hermes CLI/gateway so plugin discovery refreshes.

When loaded, the plugin registers two tools:

- `hermes_handoff_create` — create a Markdown + JSON handoff packet.
- `hermes_handoff_resume` — extract the resume prompt from a handoff JSON.

On Hermes builds that expose plugin slash commands, the same wrapper also registers `/handoff` without modifying Hermes core:

```text
/handoff help
/handoff create {"repo_path":".","goal":"Fix dashboard health page","next_task":"Run build and browser QA"}
/handoff create repo_path=. goal="Fix dashboard health page" next_task="Run build and browser QA"
/handoff {"repo_path":".","goal":"Fix dashboard health page","next_task":"Run build and browser QA"}
/handoff resume .hermes/handoffs/<timestamp>-handoff.json
```

`/handoff <json-or-key-value-args>` is treated as an implicit create shortcut. Bare `/handoff` or `/handoff help` shows the supported MVP forms instead of creating an underspecified packet.

### Verify Hermes discovery/load

After installing into Hermes' interpreter and enabling the plugin, verify from the Hermes runtime:

```bash
cd /home/zycas/hermes-continuation
python -m pytest -q tests/test_hermes_runtime_plugin_smoke.py
```

The smoke test uses `/home/zycas/.hermes/hermes-agent/venv/bin/python3`, an isolated temporary `HERMES_HOME`, and `/handoff help` only. It does not modify `~/.hermes/config.yaml` and does not create handoff packets.

For a manual runtime probe, inspect Hermes plugin state with the normal Hermes plugin commands or confirm that `/handoff help` is available in a restarted Hermes session.

See `docs/PLUGIN_WRAPPER.md` for the plugin contract, safety boundaries, runtime smoke gate, and troubleshooting.

## MVP boundaries

This MVP intentionally does **not** modify Hermes core. It does not auto-restart sessions, parse the full Hermes transcript, launch fresh agents, sync to cloud, or provide a dashboard.

Those can come later after the packet schema proves useful.

## Safety

Handoff files may be committed, sent to another agent, or pasted into a new chat. For that reason the CLI redacts common token/API-key patterns and fails closed when it sees private key blocks.
