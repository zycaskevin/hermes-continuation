# Hermes Continuation

`hermes-continuation` is a small Hermes-native sidecar/plugin wrapper for creating structured handoff packets during long-running agent work — and from v0.3.0, it can also **proactively remind you** when a handoff is overdue.

The current feature set: `doctor` recommends, `prepare` previews, `watch` performs one-shot read-only advisory checks, `create` writes a local Markdown + JSON handoff packet, and `resume` reads it for a fresh session. **Auto-trigger** (v0.3.0) optionally pushes handoff reminders to Feishu via Gateway wrapper and/or cron jobs. It does **not** modify Hermes core, auto-restart sessions, parse full Hermes transcripts, launch new agents, sync to cloud, provide a dashboard, or run a daemon.

## Usage guides

- [English usage guide](docs/USAGE.md)
- [繁體中文使用說明](docs/USAGE.zh-TW.md)
- [简体中文使用说明](docs/USAGE.zh-CN.md)

Additional reference docs:

- [Hermes plugin wrapper contract](docs/PLUGIN_WRAPPER.md)
- [Automatic handoff trigger policy](docs/AUTOMATIC_HANDOFF_TRIGGER_POLICY.md)
- [Resume command behavior](docs/RESUME_COMMAND.md)
- [Handoff packet schema](docs/HANDOFF_SCHEMA.md)
- [Examples](docs/EXAMPLES.md)
- [Project overview (Chinese)](PROJECT_OVERVIEW.md)

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

Read-only advisory and preview commands are available before writing a packet:

```bash
hermes-handoff doctor --repo . --goal "Finish QA" --next "Run browser smoke"
hermes-handoff prepare --repo . --goal "Finish QA" --next "Run browser smoke"
```

One-shot advisory watch is also available from the CLI:

```bash
hermes-handoff watch \
  --repo . \
  --goal "Finish QA" \
  --next "Run browser smoke" \
  --tool-calls 8 \
  --elapsed-minutes 45 \
  --dirty-threshold 1 \
  --explicit-request
```

`hermes-handoff watch` observes local signals once, prints advice or a prepare preview, and exits. It is read-only/advisory: it never writes `.hermes/handoffs/`, never calls hidden `create`, and does not start a daemon by default. Supported watch flags include `--goal`, `--next`, `--tool-calls`, `--elapsed-minutes`, `--dirty-threshold`, `--explicit-request`, and `--json`. Missing `goal` or `next` degrades to `advise`; `block` suppresses secret values and safe create commands.

Plain-language boundary: `doctor` recommends whether a handoff is useful; `prepare` builds a read-only preview and may show a safe `hermes-handoff create ...` command; `create` writes `.hermes/handoffs/` packet files; `watch` observes/advises/previews through existing doctor/prepare helpers. If safety blockers are found, the level is `block`, secret values are suppressed, and no create command is shown. To write a packet after a preview, the user must explicitly run the shown `create` command or invoke create through the plugin.

## Auto-watch (v0.3.0)

Instead of remembering to run `/handoff watch` yourself, Hermes can check automatically and notify you via Feishu when a handoff is overdue:

```
⚠️ 有一個開發中的專案建議交接
已開發約 45 分鐘，使用 80+ 次工具，12 個檔案有變更
→ 回對話中輸入 /handoff prepare 來預覽交接內容
```

### Three trigger modes

| Mode | How it works | Best for |
|------|-------------|----------|
| **Gateway Wrapper** | After every Hermes response, call `evaluate_and_log()` | Active conversations |
| **Cron Jobs** | Scan configured repos every 30 min | When you're away |
| **Manual** `/handoff watch` | You run it yourself | Any time |

### Quick config

```yaml
plugins:
  config:
    hermes-continuation:
      auto_watch:
        enabled: true
        tool_calls_threshold: 5      # notify when ≥5 tool calls
        elapsed_minutes_threshold: 30  # notify when ≥30 min
        cooldown_minutes: 20           # don't spam — wait 20 min between pings
        notify_levels: ["advise", "prepare", "block"]
      watch_repos:                     # cron mode: repos to scan
        - /home/zycas/hermes-continuation
```

One-click off switch: set `enabled: false` to silence all auto-triggers instantly — no downgrade needed. All auto-triggers are **read-only**, never write packets, and never include repo names or file paths in notifications.

#### Config file locations

Auto-watch supports two config sources depending on how you run it:

| Environment | Config path | Format |
|-------------|-------------|--------|
| **Hermes plugin** | `~/.hermes/config.yaml` — under `plugins.config.hermes-continuation.auto_watch` | YAML |
| **Standalone (cron / CLI-only)** | `~/.hermes/hermes-continuation/auto_watch.json` | JSON or TOML |

The standalone JSON config uses the same keys without the YAML nesting:

```json
{
  "enabled": true,
  "tool_calls": 5,
  "elapsed": 30,
  "cooldown": 20,
  "notify_levels": ["advise", "prepare", "block"]
}
```

Override either path with `HERMES_CONTINUATION_AUTO_WATCH_CONFIG=/path/to/config.{json,toml}`.

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
/handoff prepare {"repo_path":".","goal":"Finish dashboard QA","next_task":"Run build and browser smoke","auto_task_state":true}
/handoff prepare repo_path=. goal="Finish dashboard QA" next_task="Run build and browser smoke" auto_task_state=true
/handoff create {"repo_path":".","goal":"Finish dashboard QA","next_task":"Run build and browser smoke","auto_task_state":true}
/handoff create repo_path=. goal="Finish dashboard QA" next_task="Run build and browser smoke" auto_task_state=true
/handoff {"repo_path":".","goal":"Finish dashboard QA","next_task":"Run build and browser smoke"}
/handoff resume .hermes/handoffs/<timestamp>-handoff.json
```

The plugin also registers **five tools**: `hermes_handoff_prepare`, `hermes_handoff_watch`, `hermes_handoff_create`, `hermes_handoff_resume`, and `hermes_handoff_doctor`. Plugin `prepare` and `watch` are read-only and have no required fields; plugin `create` requires `goal` and `next_task`. On compatible runtimes, `/handoff prepare ...` and `/handoff watch ...` expose the same behavior through optional slash commands.

## Safety boundaries

- Do not put raw secrets in goals, task notes, verification notes, or handoff files.
- Common token/API-key/password-like values are redacted to `[REDACTED]`.
- Private-key blocks fail closed instead of writing a handoff.
- `doctor` and `prepare` are read-only; they never write `.hermes/handoffs/` packet files.
- `watch` is a one-shot read-only CLI advisory; it never writes `.hermes/handoffs/`, never invokes hidden create behavior, and does not run as a daemon by default.
- `prepare` may show a safe create command, but the user must explicitly run `create` before any packet is written.
- Safety blockers return `block`, suppress safe create commands, and do not print secret values.
- No full Hermes transcript parsing is performed.
- Auto task-state collection is opt-in and limited to conservative repo-local Markdown files.
- **Auto-watch notifications never include repo names, file paths, or content** (v0.3.0).
- **Auto-watch can be disabled instantly** via `auto_watch.enabled: false` (v0.3.0).
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

Runtime smoke compatibility notes:

- The runtime smoke test is portable and may be skipped when a local Hermes runtime checkout/interpreter is unavailable.
- Default local fallback paths are:
  - source: `/home/zycas/.hermes/hermes-agent`
  - python: `/home/zycas/.hermes/hermes-agent/venv/bin/python3`
- Override these for your machine or CI-like local checks:

```bash
HERMES_AGENT_SOURCE="/path/to/hermes-agent" \
HERMES_AGENT_PYTHON="/path/to/hermes-agent/venv/bin/python3" \
python -m pytest -q tests/test_hermes_runtime_plugin_smoke.py
```

For complete operational guidance, troubleshooting, and contribution checklist, see the full usage guide in your preferred language.
