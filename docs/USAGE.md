# Hermes Continuation Usage Guide

`hermes-continuation` creates structured continuation handoffs for long-running Hermes agent work. It is a sidecar CLI plus a thin Hermes plugin wrapper. The packet contract is the product: a local Markdown file for humans and a local JSON file for agents/tools.

The MVP is intentionally conservative. `doctor` recommends, `prepare` previews, `create` writes packet files, and `watch` runs a one-shot read-only advisory check through the existing doctor/prepare helpers. It does **not** modify Hermes core, auto-restart sessions, parse full Hermes transcripts, launch fresh agents, sync to cloud, provide a dashboard, run a daemon by default, or perform hidden writes.

## When to use it

Use `hermes-continuation` when:

- a task is too long for one comfortable session;
- context is getting large or compressed;
- you need another Hermes session or teammate to continue safely;
- you want the next agent to see concrete repository state, verification gates, blockers, and boundaries;
- you need a copy-paste resume prompt that is backed by a structured packet.

Do not use it as a secret vault, transcript archive, cloud sync system, background monitor, or automatic session manager.

## What a handoff contains

A handoff packet records:

- current goal;
- repository path, branch, HEAD, `git status --short`, and changed files;
- completed work and active work;
- known blockers;
- do-not-touch boundaries;
- verified, failing, and not-run gates;
- safety/redaction status;
- a resume prompt for the fresh Hermes session.

Default output:

```text
.hermes/handoffs/<timestamp>-handoff.md
.hermes/handoffs/<timestamp>-handoff.json
```

Treat `.hermes/handoffs/` as runtime output. Do not commit it unless you have deliberately reviewed and sanitized a packet for sharing.

## Installation

Clone or enter the repo, then install editable into your active Python environment:

```bash
cd /path/to/hermes-continuation
python -m pip install -e .
```

Confirm the CLI is visible:

```bash
hermes-handoff --help
python -m hermes_continuation.cli --help
```

If `hermes-handoff` is not on `PATH`, use the module form or check that your shell is using the Python environment where you installed the package.

## CLI usage

<!-- Compatibility alias: ## Create a handoff with the CLI -->

`hermes-handoff create` requires `--goal` and `--next`.

Minimal create:

```bash
hermes-handoff create \
  --repo . \
  --goal "Finish dashboard QA" \
  --next "Run build and browser smoke test"
```

Richer create:

```bash
hermes-handoff create \
  --repo . \
  --goal "Finish dashboard QA" \
  --completed "Updated health-card copy" \
  --completed "Added unit coverage for health status mapping" \
  --in-progress "Preparing release verification" \
  --verified "python -m pytest -q passed" \
  --failing "browser smoke test still fails on loading state" \
  --not-run "production deploy dry run" \
  --blocker "Need product sign-off for final copy" \
  --do-not-touch "billing migrations" \
  --next "Run build and browser smoke test"
```

Equivalent module form:

```bash
python -m hermes_continuation.cli create --repo . --goal "Smoke test" --next "Inspect output"
```

Useful options:

- `--repo`: repository path to inspect. Defaults to the current directory.
- `--output-dir`: custom output directory. Defaults to `<repo>/.hermes/handoffs`.
- `--completed`, `--verified`, `--failing`, `--not-run`, `--blocker`, `--do-not-touch`: repeatable list fields.
- `--in-progress`: current active work text.

## Read-only doctor and prepare preview

Use `doctor` when you want a recommendation without creating anything:

```bash
hermes-handoff doctor \
  --repo . \
  --goal "Finish dashboard QA" \
  --next "Run build and browser smoke test"
```

Use `prepare` when you want a structured preview before deciding to write a packet:

```bash
hermes-handoff prepare \
  --repo . \
  --goal "Finish dashboard QA" \
  --next "Run build and browser smoke test"
```

Boundary in plain language:

- `doctor` recommends whether a handoff is useful.
- `prepare` previews the proposed handoff state and may show a safe `hermes-handoff create ...` command.
- `create` is the only CLI command here that writes Markdown/JSON packet files under `.hermes/handoffs/` by default.
- `prepare` is read-only: it never creates `.hermes/handoffs/` directories or packet files, even when it prints a safe create command.
- A safe create command is guidance, not consent. The user must explicitly run `hermes-handoff create ...` to write a packet.
- Missing `goal` or `next` degrades to `advise` rather than fabricating state.
- Safety blockers return `block`, suppress the safe create command, and do not print secret values.

Both commands support `--json` when a machine-readable recommendation/preview envelope is needed.

## One-shot watch advisory

`hermes-handoff watch` is implemented as a one-shot CLI command for advisory auto-trigger checks. It observes explicit local signals once, calls the existing doctor/prepare helpers, prints advice or a preview, and exits.

Example:

```bash
hermes-handoff watch \
  --repo . \
  --goal "Finish dashboard QA" \
  --next "Run build and browser smoke" \
  --tool-calls 8 \
  --elapsed-minutes 45 \
  --dirty-threshold 1 \
  --explicit-request
```

Machine-readable output:

```bash
hermes-handoff watch --repo . --goal "Finish QA" --next "Run smoke" --explicit-request --json
```

Supported watch flags include `--goal`, `--next`, `--tool-calls`, `--elapsed-minutes`, `--dirty-threshold`, `--explicit-request`, and `--json`.

Watch boundaries:

- read-only/advisory only: it never writes `.hermes/handoffs/` packet files and never creates that directory;
- no hidden create path: it never calls `hermes-handoff create` or packet-writing helpers on the user's behalf;
- no daemon by default: it evaluates once and exits;
- missing `goal` or `next` degrades to `advise` instead of fabricating preview state;
- `block` results suppress secret values and safe create commands;
- no plugin/gateway `/handoff watch` exists yet; this MVP exposes watch only as CLI `hermes-handoff watch`.

Plain-language side-effect boundary: `doctor` recommends, `prepare` previews, `create` writes, and `watch` observes/advises/previews through existing doctor/prepare helpers.

## Opt-in automatic task-state collection

Automatic task-state collection is **off by default**. Enable it explicitly:

```bash
hermes-handoff create \
  --repo . \
  --goal "Finish dashboard QA" \
  --auto-task-state \
  --completed "Manual note to preserve" \
  --next "Run build and browser smoke test"
```

Boundaries of `--auto-task-state`:

- scans only conservative repo-local Markdown sources:
  - `PROGRESS.md`
  - `README.md`
  - direct `docs/*.md` files
- looks for bullets under task-state headings such as Completed Work, In Progress, Blockers, Do Not Touch, and Next Step;
- skips generated/runtime paths such as `.git`, `.hermes`, `graphify-out`, `_knowledge_base`, `.pytest_cache`, `__pycache__`, and `*.egg-info`;
- limits the number and size of collected items;
- fails closed if scanned Markdown contains a private-key block;
- does not parse full Hermes transcripts;
- does not infer hidden state from chat history;
- appends manual list values after auto-collected values with de-duplication;
- keeps manual `--next` authoritative.

Use manual flags for anything important. Treat auto collection as a convenience prefill, not as a source of truth.

## Resume from a handoff

<!-- Compatibility alias: ## Resume from a handoff JSON -->

Use the generated JSON to print the fresh-session prompt:

```bash
hermes-handoff resume .hermes/handoffs/<timestamp>-handoff.json
```

By default, `resume` prints only the prompt text so it can be pasted or piped into a new Hermes session. If you want a labeled Markdown section:

```bash
hermes-handoff resume --markdown .hermes/handoffs/<timestamp>-handoff.json
```

`resume` validates the JSON packet before printing. It does not create a new handoff, mutate the handoff file, or infer missing task state.

## Hermes plugin wrapper

For plugin use, install `hermes-continuation` into the same Python interpreter that runs Hermes. The exact path depends on your Hermes installation.

Example pattern:

```bash
cd /path/to/hermes-continuation
/path/to/hermes/python -m pip install -e .
```

This package exposes the entry point:

```toml
[project.entry-points."hermes_agent.plugins"]
hermes-continuation = "hermes_continuation.plugin"
```

Enable it through Hermes' normal plugin-management flow, or add it to Hermes config:

```yaml
plugins:
  enabled:
    - hermes-continuation
  disabled: []
```

Restart the Hermes CLI/gateway after install or config changes. Plugin discovery is cached inside a running Hermes process.

When loaded, the wrapper registers three tools:

- `hermes_handoff_prepare`: build a read-only prepare preview; it never writes packet files and has no required fields.
- `hermes_handoff_create`: create a Markdown + JSON handoff packet.
- `hermes_handoff_resume`: extract the resume prompt from a handoff JSON.

The tool schema for create requires:

- `goal`
- `next_task`

There is no plugin tool or gateway/slash command for watch yet. Use CLI `hermes-handoff watch` for the one-shot advisory auto-trigger MVP.

## Slash command

<!-- Compatibility alias: ## `/handoff` slash command -->

On Hermes builds that expose plugin slash commands, the wrapper registers `/handoff` without modifying Hermes core.

Help:

```text
/handoff help
```

Prepare a read-only preview with JSON:

```text
/handoff prepare {"repo_path":".","goal":"Finish dashboard QA","next_task":"Run build and browser smoke","auto_task_state":true}
```

Prepare with shell-style key/value arguments:

```text
/handoff prepare repo_path=. goal="Finish dashboard QA" next_task="Run build and browser smoke" auto_task_state=true
```

`/handoff prepare ...` is available only on compatible Hermes runtimes that expose plugin slash-command registration. It calls `hermes_handoff_prepare`, never writes `.hermes/handoffs/` packet files, and may show a safe create command that the user must explicitly run through `create` to write.

Create with JSON, recommended for predictability:

```text
/handoff create {"repo_path":".","goal":"Finish dashboard QA","next_task":"Run build and browser smoke","auto_task_state":true}
```

Create with shell-style key/value arguments:

```text
/handoff create repo_path=. goal="Finish dashboard QA" next_task="Run build and browser smoke" auto_task_state=true
```

Implicit create shortcut:

```text
/handoff {"repo_path":".","goal":"Finish dashboard QA","next_task":"Run build and browser smoke"}
```

Resume:

```text
/handoff resume .hermes/handoffs/<timestamp>-handoff.json
```

Resume with Markdown wrapper:

```text
/handoff resume {"handoff_json":".hermes/handoffs/<timestamp>-handoff.json","markdown":true}
```

Bare `/handoff` or `/handoff help` shows help instead of creating an underspecified packet. Plugin `auto_task_state` is optional and follows the same boundaries as CLI `--auto-task-state`. No plugin/gateway `/handoff watch` subcommand is implemented yet.

## Output and artifacts policy

Runtime handoff packets are written to:

```text
.hermes/handoffs/
```

Do not commit generated/runtime artifacts:

- `.hermes/handoffs/`
- `graphify-out/`
- `_knowledge_base/`
- `.pytest_cache/`
- `__pycache__/`
- `*.egg-info`

If you run smoke commands, prefer a temporary repository or `--output-dir` pointing outside your working tree.

## Runtime smoke compatibility

`tests/test_hermes_runtime_plugin_smoke.py` intentionally stays portable for contributors:

- it skips cleanly when Hermes runtime prerequisites are missing;
- default fallback source path is `/home/zycas/.hermes/hermes-agent`;
- default fallback interpreter path is `/home/zycas/.hermes/hermes-agent/venv/bin/python3`.

You can override both defaults with environment variables:

```bash
HERMES_AGENT_SOURCE="/path/to/hermes-agent" \
HERMES_AGENT_PYTHON="/path/to/hermes-agent/venv/bin/python3" \
python -m pytest -q tests/test_hermes_runtime_plugin_smoke.py
```

## Safety and redaction

Handoff content may be copied into another agent or shared with a teammate. Keep it secret-safe.

Rules:

- Never include real API keys, tokens, passwords, private keys, connection strings, chat IDs, message IDs, or customer secrets in examples or handoff notes.
- Use obvious placeholders such as `[REDACTED]`, `sk-test-[REDACTED]`, or `example-token-[REDACTED]`.
- The CLI/plugin redacts common token/API-key/password-like patterns to `[REDACTED]`.
- Private-key blocks fail closed and should prevent handoff output.
- `doctor` recommends and `prepare` previews; both are read-only and never write `.hermes/handoffs/` packet files.
- `watch` is a one-shot read-only CLI advisory: it never writes `.hermes/handoffs/`, never invokes hidden create behavior, and does not run as a daemon by default.
- `prepare` may show a safe create command, but the user must explicitly run `create` before any packet is written.
- Safety blockers return `block`, suppress the safe create command, and do not print secret values.
- The tool does not parse full Hermes transcripts automatically.
- Auto task-state collection is explicit opt-in and limited to conservative repo-local Markdown files.
- Review generated handoff packets before sending them anywhere.

## Verification commands

Run these before publishing code or documentation changes.

Full tests:

```bash
python -m pytest -q
```

Hermes runtime/plugin smoke, if a compatible local Hermes runtime is available:

```bash
python -m pytest -q tests/test_hermes_runtime_plugin_smoke.py
```

CLI help smoke:

```bash
python -m hermes_continuation.cli --help
python -m hermes_continuation.cli doctor --help
python -m hermes_continuation.cli prepare --help
python -m hermes_continuation.cli watch --help
python -m hermes_continuation.cli create --help
python -m hermes_continuation.cli resume --help
```

Runtime create/resume smoke in a temporary repo:

```bash
tmpdir="$(mktemp -d)"
git -C "$tmpdir" init
python -m hermes_continuation.cli create \
  --repo "$tmpdir" \
  --goal "Smoke test" \
  --next "Inspect generated handoff"
json_file="$(find "$tmpdir/.hermes/handoffs" -name '*-handoff.json' | sort | tail -n 1)"
python -m hermes_continuation.cli resume "$json_file" >/dev/null
```

Secret scan concept:

```bash
python - <<'PY'
from pathlib import Path
patterns = ['BEGIN PRIVATE KEY', 'api_key=', 'password=', 'bearer ']
for path in [*Path('.').glob('*.md'), *Path('docs').glob('*.md')]:
    text = path.read_text(encoding='utf-8', errors='ignore').lower()
    hits = [p for p in patterns if p.lower() in text]
    if hits:
        print(f'{path}: review possible secret-like text {hits}')
PY
```

Whitespace diff check:

```bash
git diff --check
```

Graphify hook, when available in your workspace:

```bash
command -v graphify >/dev/null && graphify . || true
```

If graph/report output is generated, do not stage `graphify-out/` unless a maintainer explicitly asks for it.

## Troubleshooting

### Plugin does not show up until restart/reset

Hermes caches plugin discovery in a running process. Restart the Hermes CLI/gateway after installing, enabling, disabling, or editing the plugin. In tests, use forced plugin discovery if the runtime supports it.

### Entry point is not visible

Install with the Hermes interpreter, not only your shell's default Python:

```bash
/path/to/hermes/python -m pip install -e /path/to/hermes-continuation
```

Then verify:

```bash
/path/to/hermes/python - <<'PY'
from importlib.metadata import entry_points
print([ep.name for ep in entry_points(group='hermes_agent.plugins')])
PY
```

You should see `hermes-continuation`.

### `/handoff` is missing but tools exist

Your Hermes build may not expose plugin slash-command registration. This is expected on older builds. The wrapper still registers `hermes_handoff_create` and `hermes_handoff_resume` tools.

### `/handoff watch` is missing

That is expected. Watch is currently implemented only as the one-shot CLI command `hermes-handoff watch`; no plugin/gateway `/handoff watch` command exists yet.

### Handoff files or generated artifacts appear in `git status`

They are runtime artifacts. Remove or ignore generated files before committing:

```bash
git status --short
```

Do not stage `.hermes/handoffs/`, `graphify-out/`, `_knowledge_base/`, caches, or egg-info directories.

### `hermes-handoff` command not found

Use the module form:

```bash
python -m hermes_continuation.cli --help
```

Or activate the environment where you installed the package and ensure its script directory is on `PATH`.

### Missing Hermes runtime

CLI usage does not require Hermes runtime imports. Plugin runtime smoke tests may skip or fail if Hermes is not installed locally. Install into the real Hermes environment and run the runtime smoke only where Hermes is available.

### `create` fails on private key text

This is intentional fail-closed behavior. Remove the private key block from inputs/docs and replace sensitive material with `[REDACTED]` before creating a handoff.

## Developer contribution checklist

Before opening a PR or asking someone to commit:

- Keep changes scoped. Do not modify Hermes core for sidecar/plugin-wrapper work.
- Do not commit runtime/generated artifacts: `.hermes/handoffs/`, `graphify-out/`, `_knowledge_base/`, caches, or `*.egg-info`.
- Keep examples secret-safe and use obvious fake placeholders only.
- Preserve product truth: this MVP recommends/previews/creates/resumes handoff packets and offers one-shot CLI watch advice; it does not auto-restart sessions, parse full transcripts, run background watch daemons, or perform hidden writes.
- Keep `doctor` and `prepare` read-only; they must not write `.hermes/handoffs/` packet files.
- Keep `watch` read-only/advisory and CLI-only until a separate plugin/gateway watch task is approved.
- Keep `create` requiring `--goal` and `--next` in the CLI.
- Keep plugin `create` requiring `goal` and `next_task`.
- Keep auto task-state collection opt-in only.
- Run relevant tests and document any skipped checks.
- Run `git diff --check` before handing off.
- Review `git diff` so the commit contains only intended files.

Scoped commit guidance:

```bash
git status --short
git diff -- README.md docs/USAGE.md docs/USAGE.zh-TW.md docs/USAGE.zh-CN.md
git diff --check
```

Stage only the intended documentation files when you are ready. Do not stage unrelated local progress files or generated directories.
