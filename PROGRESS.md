# Hermes Continuation Progress

## Current Goal

Complete the public GitHub readiness pass for the Hermes continuation sidecar/plugin MVP:

1. Strengthen the test suite so CLI, plugin wrapper, packet validation, redaction, rendering, git-state collection, automatic task-state collection, and Hermes runtime smoke behavior are covered by explicit regression tests.
2. Update the GitHub-facing usage documentation in **Traditional Chinese, Simplified Chinese, and English** so users can install, enable, run, verify, troubleshoot, and safely operate the sidecar/plugin without reading prior chat history.
3. Keep the implementation as a sidecar/plugin-wrapper capability; do not modify Hermes core, do not commit generated runtime artifacts, and keep all handoff documentation secret-safe.

## Public GitHub Readiness Plan

Implement now:

- Expand regression coverage for the existing sidecar/plugin behavior without changing the core product contract.
- Add GitHub-facing usage documentation in three languages:
  - Traditional Chinese: `docs/USAGE.zh-TW.md`
  - Simplified Chinese: `docs/USAGE.zh-CN.md`
  - English: `docs/USAGE.md`
- Keep `README.md` as the public landing page and link clearly to all three usage guides.
- Document installation, CLI create/resume, `--auto-task-state`, plugin enablement, `/handoff` command usage, packet output locations, verification commands, troubleshooting, and safety boundaries.
- Keep all examples secret-safe. Any API key, token, password, credential, connection string, chat id, or message id must be omitted or shown as `[REDACTED]`.

Acceptance gates before commit:

- Full test suite passes with `python -m pytest -q`.
- Hermes runtime plugin smoke test passes or is cleanly skipped by its existing environment guard.
- CLI smoke covers help, create with `--auto-task-state`, and resume.
- Source secret scan reports 0 findings in committable source/docs/tests/config files.
- `git diff --check` passes.
- Graphify maintenance hook is executed after code/doc changes.
- Commit is scoped and excludes `_knowledge_base/`, `graphify-out/`, `.hermes/handoffs/`, cache directories, and package build artifacts.

Still out of scope:

- Hermes core modifications.
- Automatic session restart.
- Full Hermes transcript parsing or context-risk detection.
- Committing generated handoff packets or Graphify output.

## Phase 1 Public Repo Hardening Plan

Implement now (small-scoped edits only):

1. Align `pyproject.toml` public metadata with repository licensing and maintainer identity.
2. Make runtime smoke test path selection portable through explicit env overrides.
3. Add a minimal CI workflow for Python 3.11/3.12 install, test, compile, secret scan, and whitespace checks.
4. Add `CHANGELOG.md` for `0.1.0` with Phase 1 readiness notes.
5. Update public docs to clarify runtime-smoke compatibility and env overrides.

Do not modify:

- `graphify-out/`
- `_knowledge_base/`
- `.hermes/handoffs/`
- caches
- `*.egg-info`

Phase 1 acceptance gates:

- `pyproject.toml` license metadata states Apache-2.0 and author reflects Arthur Liao.
- `tests/test_hermes_runtime_plugin_smoke.py` supports:
  - `HERMES_AGENT_SOURCE` for Hermes source checkout path
  - `HERMES_AGENT_PYTHON` for Hermes interpreter path
  - preserved fallback: `/home/zycas/.hermes/hermes-agent`
  - clean, actionable skip messages when runtime is unavailable
- `.github/workflows/ci.yml` exists and runs:
  - `actions/checkout`
  - `actions/setup-python` matrix: 3.11, 3.12
  - `python -m pip install -e .`
  - `pytest`
  - compile checks (`compileall` and `py_compile`)
  - lightweight secret scan across committable source/docs/tests/config
  - `git diff --check`
- Runtime Hermes smoke test remains optional/portable (skip is acceptable when Hermes runtime is absent).
- `CHANGELOG.md`, `README.md`, `docs/USAGE*.md`, and `docs/PLUGIN_WRAPPER.md` document compatibility and env overrides.

## Phase 2 Runtime Compatibility Plan

Implement now (small-scoped compatibility hardening only):

1. Inspect the current plugin wrapper registration path against Hermes runtime plugin APIs.
2. Make plugin API capability detection explicit and conservative:
   - `register_tool` is required for the plugin wrapper to be useful.
   - `/handoff` command registration remains optional.
   - Missing command registration must not prevent the two handoff tools from loading.
   - Incompatible command-registration signatures should degrade gracefully instead of crashing plugin load.
3. Add boundary regression tests for runtimes that:
   - expose full tool + command APIs;
   - expose tool APIs only;
   - expose command APIs with an incompatible signature;
   - lack the required tool registration API.
4. Preserve the current tool contracts and JSON result envelopes; do not rename tools, toolset, command, or success fields.
5. Keep this as a sidecar/plugin-wrapper compatibility pass; do not modify Hermes core.

Phase 2 acceptance gates:

- `register(ctx)` still registers `hermes_handoff_create` and `hermes_handoff_resume` on compatible Hermes plugin contexts.
- `/handoff` registers only when the runtime command API is available and compatible.
- Command API incompatibility is recorded on the plugin context when possible and does not crash tool registration.
- Missing required `register_tool` fails with an explicit error instead of silently pretending the plugin loaded.
- Existing CLI create/resume behavior remains unchanged.
- `python -m pytest -q` passes.
- `python -m pytest -q tests/test_hermes_runtime_plugin_smoke.py` passes or is cleanly skipped when Hermes runtime is unavailable.
- `python -m py_compile src/hermes_continuation/*.py tests/*.py` passes.
- Source secret scan reports 0 findings in committable source/docs/tests/config files.
- `git diff --check` passes.
- Graphify maintenance hook is executed after code/doc changes.
- Commit is scoped and excludes `_knowledge_base/`, `graphify-out/`, `.hermes/handoffs/`, cache directories, and package build artifacts.

Still out of scope for Phase 2:

- Hermes core modifications.
- Automatic session restart or context-risk detection.
- Cross-agent packet standardization.
- Expanding auto task-state beyond the existing conservative repo-doc collector.
- Committing generated handoff packets or Graphify output.


## Source of Truth

Spec pack: `/home/zycas/_knowledge_base/hermes-continuation-mvp/`

Key decisions already made:

- Build a Hermes-native sidecar first; do not modify Hermes core in MVP.
- Output both human-readable Markdown and machine-readable JSON.
- First version is manual command generation, not automatic context-risk detection.
- Handoff packet must include repo state, task state, verification gates, safety/redaction status, and a fresh-session resume prompt.
- B: automatic task-state collection is the next sidecar improvement. It should infer task state from repo-local evidence, not from full Hermes transcript parsing.

## Completed MVP Scope

Implemented:

- `hermes-handoff create`
- `.hermes/handoffs/<timestamp>.md`
- `.hermes/handoffs/<timestamp>.json`
- Git repo state collector with degraded non-git behavior
- Packet assembly with required schema fields
- Markdown renderer
- Secret redaction + private-key fail-closed behavior
- Validation before write
- README + docs/examples
- Test suite covering core behavior and CLI smoke

Still out of scope for this sidecar phase:

- Hermes core modifications
- Automatic session restart
- Automatic full transcript parsing or context-risk detection
- Dashboard / cloud sync / multi-agent workflow engine

## Next Scope: Resume Subcommand

Implement now:

- `hermes-handoff resume <handoff.json>`
- Read an existing handoff JSON without mutating it.
- Validate the packet with the same structural validation used by `create`.
- Print only `resume_prompt` to stdout by default, suitable for copy/paste or piping into a fresh Hermes session.
- Fail nonzero with stderr errors for missing file, invalid JSON, validation errors, and missing/empty `resume_prompt`.
- Optional `--markdown` may wrap the prompt in a concise human-readable section, but default remains prompt-only.

Do not implement yet:

- Hermes core changes or internal plugin hooks.
- Automatic discovery of the latest handoff.
- Session launching/restart automation.
- Transcript parsing or context-risk detection.

## Original MVP Development Plan

1. Create Python package skeleton and CLI help smoke test.
2. Implement git state collector.
3. Implement packet builder and resume prompt.
4. Implement redaction and validation gates.
5. Implement Markdown renderer.
6. Wire `create` command to write `.md` + `.json`.
7. Add README/docs/examples.
8. Run full tests and smoke command.
9. Commit and push scoped changes.

## Resume Development Plan

1. Update this progress file and add a functional resume/plugin direction doc.
2. Add the `resume` parser and handler to the existing CLI.
3. Reuse `validate_packet()` and add explicit `resume_prompt` non-empty enforcement.
4. Add CLI tests for successful prompt-only output and error paths.
5. Run compile, pytest, help, resume-help, create/resume smoke, and git status verification.


## Plugin Wrapper Development Plan

Implement now:

- Keep Hermes core untouched; expose the sidecar through a pip-installable Hermes plugin entry point.
- Register two thin plugin tools around the existing CLI contracts:
  - `hermes_handoff_create` builds and writes Markdown + JSON handoff packets.
  - `hermes_handoff_resume` reads an existing handoff JSON and returns the resume prompt.
- Reuse existing packet, git-state, validation, redaction, and Markdown rendering modules instead of duplicating business logic.
- Return JSON strings from handlers because Hermes plugin tools are registered through the normal tool registry.
- Add tests with a fake plugin context plus integration-style handler calls against a temporary git repo.

Do not implement yet:

- Hermes core changes.
- Automatic session restart or transcript parsing.
- A built-in `/handoff` slash command.
- Dashboard/cloud sync.

Plugin-wrapper acceptance gates:

- `docs/PLUGIN_WRAPPER.md` documents install/enable/use, boundaries, and safety behavior.
- `pyproject.toml` exposes the `hermes_agent.plugins` entry point.
- `register(ctx)` registers exactly `hermes_handoff_create` and `hermes_handoff_resume`.
- Plugin handlers return JSON strings with safe success/error envelopes.
- Existing CLI tests continue passing.

## Command UX Development Plan

Implement now:

- Keep Hermes core untouched; expose `/handoff` through the sidecar plugin only.
- Register a plugin slash command with `ctx.register_command` when the local Hermes plugin API provides it.
- Keep registration backward-compatible: older/minimal plugin contexts that only expose `register_tool` must continue to load the two existing tools without crashing.
- Support a safe MVP command surface:
  - `/handoff create <json-or-key-value-args>` creates a Markdown + JSON packet through `hermes_handoff_create`.
  - `/handoff <json-or-key-value-args>` is an implicit create shortcut.
  - `/handoff resume <handoff.json>` extracts the stored resume prompt through `hermes_handoff_resume`.
  - `/handoff help` documents the supported forms.
- Reuse existing tool handlers and keep their JSON envelopes using `success`; do not introduce a generic `ok` contract.
- Add fake-context tests for command registration, graceful absence of `register_command`, and command handler behavior.

Do not implement:

- Hermes core command registry changes.
- Automatic transcript parsing/session restart.
- Runtime handoff artifacts in git.

Command-UX acceptance gates:

- Docs explain the `/handoff` plugin command, argument formats, and no-core-modification boundary.
- `register(ctx)` still registers `hermes_handoff_create` and `hermes_handoff_resume` tools.
- `register(ctx)` additionally registers `/handoff` only when `register_command` exists.
- `/handoff create ...` and `/handoff resume ...` route through existing handlers.
- Targeted plugin-wrapper tests pass.

## Automatic Task-State Collection Plan

Selected direction: **B. Automatic task-state collection**.

Why this is next:

- The handoff packet already has the right `task_state` shape, but today most values come from manual CLI flags or plugin arguments.
- A useful continuation tool should reduce manual handoff typing by extracting likely completed work, active work, blockers, do-not-touch boundaries, and next steps from repo-local evidence.
- The collector should improve the packet while keeping the existing explicit/manual flags as the highest-priority source of truth.

Implement now:

- Add a small sidecar collector module that scans safe, repo-local project documents such as `PROGRESS.md`, `README.md`, and docs under `docs/` when present.
- Use existing git state as context, especially changed-file summaries, without treating untracked generated artifacts as tasks.
- Add an opt-in CLI/plugin flag such as `--auto-task-state` / `auto_task_state` so existing create behavior stays backward-compatible.
- Merge behavior must be predictable: manual values override or append to automatically inferred values, never get silently discarded.
- Preserve the current packet schema by mapping inferred values into existing `task_state.completed_work`, `in_progress`, `known_blockers`, `do_not_touch`, and `next_recommended_task` fields.
- Keep degraded behavior: missing docs, non-git repos, unreadable files, or weak signals should produce a valid packet with the manual/default values rather than failing hard.
- Keep all collected text redaction-safe through the existing redaction/validation path.

Do not implement now:

- Hermes core modifications.
- Automatic session restart or launching a fresh Hermes session.
- Full Hermes transcript parsing, context-risk detection, or cloud/dashboard sync.
- Committing generated `.hermes/handoffs/` packets or `graphify-out/`.

Automatic task-state acceptance gates:

- Existing CLI/plugin create behavior remains compatible when auto collection is not enabled.
- Auto collection can populate useful task-state fields from a temp repo with `PROGRESS.md` evidence.
- Manual CLI/plugin values remain present when auto collection is enabled.
- Secret/private-key safety behavior remains fail-closed or redacted before write.
- Full pytest, runtime plugin smoke, source secret scan, `git diff --check`, and the Graphify hook pass before commit.

- `pytest -q` passes.
- `python -m hermes_continuation.cli --help` passes.
- `python -m hermes_continuation.cli create --repo . --goal "Smoke test" --next "Inspect output"` writes `.md` + `.json`.
- Generated JSON contains required top-level fields.
- Generated Markdown contains `## Resume Prompt`.
- Secret redaction tests prove obvious secrets do not leak.
- Private key block is blocked before file write.

Resume-specific gates:

- `python -m hermes_continuation.cli resume --help` passes.
- `hermes-handoff resume <handoff.json>` prints only the prompt by default.
- Invalid JSON, structurally invalid packets, missing files, and empty `resume_prompt` fail nonzero on stderr.
- Resume does not create or modify handoff artifacts.

## Current Status

- Repo cloned: `/home/zycas/hermes-continuation`
- Branch: `main`
- Initial repo contents before MVP work: `LICENSE` only
- Spec pack read and accepted as implementation source of truth
- This `PROGRESS.md` created before code implementation per Arthur's document-first rule
- MVP package, `create` CLI, docs, schema notes, and tests are implemented.
- `resume` subcommand design is tracked in `docs/RESUME_COMMAND.md`.
- `hermes-handoff resume <handoff.json>` is implemented and verified.
- Plugin wrapper is implemented as a sidecar integration layer after the CLI contract stabilized.
- `/handoff` command UX is implemented as a plugin-only layer after confirming local Hermes exposes `PluginContext.register_command(name, handler, description="", args_hint="")` with handler signature `fn(raw_args: str) -> str | None`.
- Runtime outputs are intentionally ignored via `.gitignore`: `.hermes/handoffs/`, `*.egg-info/`, `.pytest_cache/`, and local env files.

## Latest Verified Gates

Verified on 2026-05-09:

- `python -m py_compile src/hermes_continuation/*.py tests/*.py` passed.
- `python -m pytest -q` passed: 11 tests.
- `python -m hermes_continuation.cli --help` passed.
- `python -m hermes_continuation.cli create --repo . --goal "Smoke test" --next "Inspect output"` wrote Markdown + JSON.
- Generated JSON passed `validate_packet()` and nested schema probes for `repo`, `task_state`, `verification`, and `safety`.
- Generated Markdown contains `## Resume Prompt`.
- Source secret scan passed: 0 findings in committable files.
- Runtime smoke artifacts under `.hermes/handoffs/` were removed after verification and remain ignored by `.gitignore`.

Resume verification on 2026-05-10:

- `python -m py_compile src/hermes_continuation/*.py tests/*.py` passed.
- `python -m pytest -q` passed: 17 tests.
- `python -m hermes_continuation.cli --help` passed and lists `create` + `resume`.
- `python -m hermes_continuation.cli resume --help` passed.
- Temp `create` + `resume` smoke passed: default resume stdout extracted a usable 1,201-character `resume_prompt`.
- `--markdown` resume smoke passed and wrapped the prompt under `## Resume Prompt`.
- Source secret scan covered 20 committable files and found 0 findings.
- `git diff --check` passed.
- Graphify maintenance hook passed and rebuilt `graphify-out/`.
- Temp smoke artifacts were created under `/tmp` and removed.

Command UX verification on 2026-05-10:

- `python -m py_compile src/hermes_continuation/*.py tests/*.py` passed.
- `python -m pytest -q tests/test_plugin_wrapper.py` passed: 8 tests.
- `python -m pytest -q` passed: 25 tests.
- `git diff --check` passed.
- Fake-context coverage verifies `/handoff` registration when `register_command` exists and tool-only compatibility when it does not.
- Command-handler coverage verifies help, create/resume roundtrip, implicit key/value create, and parse-error output.

Automatic task-state verification on 2026-05-10:

- `python -m py_compile src/hermes_continuation/*.py tests/*.py` passed.
- `python -m pytest -q` passed: 36 tests.
- `python -m pytest -q tests/test_hermes_runtime_plugin_smoke.py` passed: 1 test.
- `python -m hermes_continuation.cli --help` passed.
- `python -m hermes_continuation.cli create --help` passed.
- Temp CLI `create --auto-task-state` + `resume` smoke passed and removed its temp handoff artifacts.
- Source secret scan passed: 0 findings in committable files.
- `git diff --check` passed.
- Graphify maintenance hook passed and rebuilt `graphify-out/`: 147 nodes, 295 edges, 12 communities.

## Known Issues / Risks

- Terminal/file tools were previously affected by a stale missing cwd (`/tmp/vault-for-llm-verify-vDN0F3`); use Python execution with absolute paths from `/home/zycas` if needed.
- OpenCode/delegate outputs must be verified by checking actual files and test results; self-report is not evidence.
- Do not commit generated smoke handoff artifacts unless intentionally documenting examples.
- This sidecar is still manual: the plugin wrapper exposes tools, but it does not add a Hermes core `/handoff` command or automatic context-risk detection yet.
## Runtime Smoke + Install Docs Plan

Implement now:

- A: Add a real Hermes runtime smoke gate that verifies the installed package is discoverable through the `hermes_agent.plugins` entry point and that the plugin `register(ctx)` path registers the expected handoff tools/command using Hermes' real `PluginContext` shape.
- B: Strengthen install/use docs with exact editable install, plugin discovery verification, `/handoff` command examples, runtime smoke command, and troubleshooting.

Acceptance gates:

- Runtime smoke test passes without modifying Hermes core.
- Full pytest passes.
- Secret scan reports 0 findings.
- `git diff --check` passes.
- Graphify rebuild hook is executed after code/doc changes.
- Commit is scoped and excludes generated runtime artifacts such as `graphify-out/`.

Still out of scope:

- Hermes core changes.
- Automatic session restart.
- Cloud sync/dashboard.
- Committing generated handoff packets or graph output.

Runtime smoke/doc implementation on 2026-05-10:

- Added `tests/test_hermes_runtime_plugin_smoke.py`, a portable pytest that skips when the local Hermes source/venv is absent.
- The smoke runs `/home/zycas/.hermes/hermes-agent/venv/bin/python3` in a subprocess with temporary `HERMES_HOME`, an isolated `HOME`, and `PYTHONPATH` containing this repo's `src/` plus `/home/zycas/.hermes/hermes-agent`.
- The smoke verifies `hermes_agent.plugins` entry-point metadata, Hermes runtime plugin discovery/loading, real registry entries for `hermes_handoff_create` and `hermes_handoff_resume`, and `/handoff help` through Hermes' plugin command APIs without creating handoff packets or modifying `~/.hermes/config.yaml`.
- Strengthened `README.md` install/usage docs for Hermes runtime editable install, opt-in plugin config, `/handoff` forms, and the runtime smoke command.
- Strengthened `docs/PLUGIN_WRAPPER.md` with the exact runtime smoke gate, temporary `HERMES_HOME` isolation, and troubleshooting for plugin listing/enabling, `/handoff` availability, entry-point visibility, generated artifacts, and restart/reset behavior.

Runtime smoke verification on 2026-05-10:

- `python -m pytest -q tests/test_hermes_runtime_plugin_smoke.py` passed: 1 test.
- `git diff --check` passed.
- Full pytest, secret scan, and graphify rebuild were not run in this pass.
