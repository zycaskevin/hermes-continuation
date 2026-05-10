# Hermes Continuation

`hermes-continuation` is a small Hermes-native sidecar/plugin wrapper for creating structured handoff packets during long-running agent work.

The current MVP is intentionally narrow: it writes a local Markdown + JSON handoff packet that a fresh Hermes session can read before continuing. It does **not** modify Hermes core, auto-restart sessions, parse full Hermes transcripts, launch new agents, sync to cloud, or provide a dashboard.

## Usage guides

- [English usage guide](docs/USAGE.md)
- [繁體中文使用說明](docs/USAGE.zh-TW.md)
- [简体中文使用说明](docs/USAGE.zh-CN.md)

Additional reference docs:

- [Hermes plugin wrapper contract](docs/PLUGIN_WRAPPER.md)
- [Resume command behavior](docs/RESUME_COMMAND.md)
- [Handoff packet schema](docs/HANDOFF_SCHEMA.md)
- [Examples](docs/EXAMPLES.md)

## What it creates

Each handoff contains:

- the current goal
- repository path, branch, commit, and changed files
- completed work, active work, blockers, and do-not-touch boundaries
- verified / failing / not-run gates
- redaction status
- a copy-paste resume prompt for a fresh Hermes session

Default output location:

```text
.hermes/handoffs/<timestamp>-handoff.md
.hermes/handoffs/<timestamp>-handoff.json
```

These runtime handoff packets are local artifacts and should not be committed.

## Install

From this repository, install into your active Python environment for CLI use:

```bash
python -m pip install -e .
```

For Hermes plugin use, install the package into the same Python interpreter that runs Hermes, then enable the `hermes-continuation` entry-point plugin and restart Hermes so plugin discovery refreshes.

## CLI quick start

`create` requires both `--goal` and `--next`:

```bash
hermes-handoff create \
  --repo . \
  --goal "Finish dashboard QA" \
  --completed "Updated health-card copy" \
  --verified "pytest -q passed" \
  --not-run "browser smoke test" \
  --do-not-touch "billing migrations" \
  --next "Run build and browser smoke test"
```

Resume later from the generated JSON:

```bash
hermes-handoff resume .hermes/handoffs/<timestamp>-handoff.json
```

Optional automatic task-state collection is explicit opt-in only:

```bash
hermes-handoff create --repo . --goal "Finish QA" --next "Run browser smoke" --auto-task-state
```

`--auto-task-state` conservatively reads repo-local Markdown docs (`PROGRESS.md`, `README.md`, and direct `docs/*.md`) and skips generated/runtime directories. Manual values are preserved, and manual `--next` remains authoritative.

## Hermes plugin quick start

The package exposes this entry point:

```toml
[project.entry-points."hermes_agent.plugins"]
hermes-continuation = "hermes_continuation.plugin"
```

Enable it through Hermes' normal plugin-management flow, or configure:

```yaml
plugins:
  enabled:
    - hermes-continuation
  disabled: []
```

After restarting Hermes, builds with plugin slash-command support may expose:

```text
/handoff help
/handoff create {"repo_path":".","goal":"Finish dashboard QA","next_task":"Run build and browser smoke","auto_task_state":true}
/handoff create repo_path=. goal="Finish dashboard QA" next_task="Run build and browser smoke" auto_task_state=true
/handoff {"repo_path":".","goal":"Finish dashboard QA","next_task":"Run build and browser smoke"}
/handoff resume .hermes/handoffs/<timestamp>-handoff.json
```

The plugin also registers two tools: `hermes_handoff_create` and `hermes_handoff_resume`. Plugin `create` requires `goal` and `next_task`.

## Safety boundaries

- Do not put raw secrets in goals, task notes, verification notes, or handoff files.
- Common token/API-key/password-like values are redacted to `[REDACTED]`.
- Private-key blocks fail closed instead of writing a handoff.
- No full Hermes transcript parsing is performed.
- Auto task-state collection is opt-in and limited to conservative repo-local Markdown files.
- Generated/runtime artifacts such as `.hermes/handoffs/`, `graphify-out/`, `_knowledge_base/`, `.pytest_cache/`, `__pycache__/`, and `*.egg-info` should not be committed.

## Verification

Common checks before publishing changes:

```bash
python -m pytest -q
python -m pytest -q tests/test_hermes_runtime_plugin_smoke.py
python -m hermes_continuation.cli --help
SMOKE_REPO="$(mktemp -d)"
git -C "$SMOKE_REPO" init
python -m hermes_continuation.cli create \
  --repo "$SMOKE_REPO" \
  --goal "Smoke test" \
  --next "Inspect output"
SMOKE_JSON="$(find "$SMOKE_REPO/.hermes/handoffs" -name '*-handoff.json' | sort | tail -n 1)"
python -m hermes_continuation.cli resume "$SMOKE_JSON" >/dev/null
git diff --check
```

For complete operational guidance, troubleshooting, and contribution checklist, see the full usage guide in your preferred language.
