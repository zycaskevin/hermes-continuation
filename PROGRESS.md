# Hermes Continuation Progress

## Current Status — No Active Implementation Task

- **No active implementation task is currently open.**
- Repository: `/home/zycas/hermes-continuation`
- Branch: `main`
- Sync state: `main` is synced to `origin/main` after the latest pushed documentation/dogfood update.
- GitHub PR status: PR #1 is merged; open PRs: none.
- This document is now current-status-first so future agents do not reopen completed historical plans.

## Completed Product Surface

The public sidecar/plugin product currently includes these implemented surfaces:

- CLI command: `hermes-handoff create`
  - Writes paired Markdown and JSON handoff packets under `.hermes/handoffs/`.
  - Captures repo state, task state, verification notes, safety/redaction status, and resume prompt.
- CLI command: `hermes-handoff resume`
  - Reads an existing handoff JSON and prints the stored `resume_prompt` for a fresh session.
  - Does not mutate the packet or create new handoff artifacts.
- CLI command: `hermes-handoff doctor`
  - Provides read-only advisory recommendations using local sidecar signals.
  - Supports recommendation levels such as `observe`, `advise`, `prepare`, and `block`.
- CLI command: `hermes-handoff prepare`
  - Builds a read-only preview of a safe create command and packet intent.
  - Does not write `.hermes/handoffs/` output.
- CLI option: `--auto-task-state`
  - Opt-in repo-local task-state collection from safe project documents and git context.
  - Manual values remain authoritative over inferred values.
- Plugin tool: `hermes_handoff_create`
  - Exposes the create flow through the Hermes plugin wrapper.
- Plugin tool: `hermes_handoff_resume`
  - Exposes the resume flow through the Hermes plugin wrapper.
- Plugin tool: `hermes_handoff_prepare`
  - Exposes the advisory prepare preview through the Hermes plugin wrapper.
- Plugin slash command: `/handoff create`
  - Plugin-only command surface; it is not a Hermes core command.
- Plugin slash command: `/handoff resume`
  - Plugin-only resume surface using the existing sidecar resume behavior.
- Plugin slash command: `/handoff prepare`
  - Plugin-only prepare preview surface; advisory/read-only.
- CI and verification gates are present for public readiness:
  - Python 3.11/3.12 GitHub CI.
  - Public documentation tests.
  - Hermes runtime/plugin smoke coverage.
  - Prepare/advisory behavior tests.
  - Secret scan gates.
  - `git diff --check` whitespace gate.
  - Graphify maintenance/rebuild gate.

## Current Boundaries / Non-goals

The current product remains a sidecar/plugin integration with explicit user control:

- No Hermes core changes.
- No automatic session restart.
- No full Hermes transcript parsing.
- No fresh-agent launch.
- No cloud sync or dashboard.
- No hidden writes:
  - `doctor` recommends.
  - `prepare` previews.
  - `create` writes only when explicitly invoked.
- `/handoff` exists only through the plugin wrapper on compatible Hermes runtimes; it is not a built-in Hermes core command.
- Generated runtime artifacts such as `.hermes/handoffs/`, `graphify-out/`, caches, and package build outputs should not be committed unless a future task explicitly asks for that.

## Recommended Next Roadmap

Only these are future tasks; completed historical phase plans should not be reopened as active work.

### P1 — Real dogfood in Arthur's Hermes runtime/gateway

Status: completed for CLI and local Hermes runtime plugin path on 2026-05-11.

Verified:

- Hermes v0.13.0 is installed at `/home/zycas/.local/bin/hermes`.
- `~/.hermes/config.yaml` enables `hermes-continuation`.
- The Hermes venv can import this checkout's `hermes_continuation` package.
- CLI dogfood passed:
  - `hermes-handoff prepare` human output returned `prepare`.
  - JSON output returned `preview.level == "prepare"` and `would_write == false`.
  - Missing `next` degraded to `advise` with no safe create command.
  - No `.hermes/handoffs/` directory was created in the dogfood repo.
- Hermes runtime plugin dogfood passed:
  - Real plugin runtime loaded `hermes-continuation` with 3 tools and 1 command.
  - Registry tool `hermes_handoff_prepare` returned `preview.level == "prepare"` and `would_write == false`.
  - Plugin command handler `/handoff prepare ...` returned human-readable preview text.
  - No handoff artifacts were written.

Remaining optional observation:

- Inspect Feishu/Telegram message readability during a natural future task. Runtime command execution is verified; visual copy/readability can be refined later if the output feels too technical.

### P2 — Release/tag flow

- Select a release version, for example `v0.1.0` or another chosen version.
- Create release notes from the completed product surface and latest verification.
- Re-check install documentation against the packaged/released flow.
- Tag and publish only when explicitly requested by a release task.

### P3 — Optional watch/advisory auto-trigger design and implementation

Status: planning completed; implementation has not started.

- Implementation plan created: `docs/WATCH_ADVISORY_TRIGGER_PLAN.md`.
- Recommended start is one-shot CLI `hermes-handoff watch`, no plugin/gateway command until the CLI contract is stable.
- Keep the policy advisory-first.
- Preserve explicit-write-only behavior: automated checks may recommend or preview, but must not silently create packets.
- Continue to avoid Hermes core session lifecycle changes unless a separate approved task changes the boundary.

### P4 — Optional docs cleanup if more drift appears

- Remove or rewrite stale active-language references if future docs drift again.
- Keep status docs current-status-first.
- Preserve useful historical context only as past-tense archive material.

## Latest Verified Gates

Latest dogfood verification recorded on 2026-05-11:

- CLI `hermes-handoff prepare` human and JSON output passed in a temp git repo.
- CLI missing-`next` case degraded to `advise` with no safe create command.
- Hermes runtime plugin loaded `hermes-continuation` with 3 tools and 1 command.
- Runtime registry tool `hermes_handoff_prepare` passed.
- Runtime plugin command handler `/handoff prepare ...` passed.
- Dogfood checks created no `.hermes/handoffs/` artifacts.

Latest merged verification recorded for `30dd05d feat: add advisory and prepare handoff previews`:

- Local full pytest passed: `80 passed`.
- Public docs tests passed.
- Runtime smoke, plugin, and prepare tests passed.
- Strict secret scan passed: `STRICT_SECRET_SCAN_OK files=37`.
- `git diff --check` passed.
- Graphify rebuild completed: `853 nodes, 1180 edges, 62 communities`.
- GitHub CI test matrix succeeded on Python 3.11 and 3.12.

## Source of Truth

Spec pack:

- `/home/zycas/_knowledge_base/hermes-continuation-mvp/`

Key decisions already made:

- Build a Hermes-native sidecar first; do not modify Hermes core in the MVP/current product.
- Output both human-readable Markdown and machine-readable JSON.
- Manual command generation came first; advisory helpers now exist, but automatic hidden writes remain out of scope.
- Handoff packets include repo state, task state, verification gates, safety/redaction status, and a fresh-session resume prompt.
- Automatic task-state collection is repo-local and opt-in via `--auto-task-state`; it does not parse full Hermes transcripts.
- The plugin wrapper may expose tools and plugin-only `/handoff` commands on compatible Hermes runtimes, but it does not change Hermes core.

## Known Issues / Risks

- Terminal/file tools were previously affected by a stale missing cwd (`/tmp/vault-for-llm-verify-vDN0F3`); use absolute paths from `/home/zycas` if needed.
- OpenCode/delegate/subagent outputs must be verified by checking actual files and test results; self-report is not evidence.
- Do not commit generated smoke handoff artifacts unless intentionally documenting examples.
- The plugin wrapper now exposes plugin-only `/handoff` surfaces where compatible, but it still does not add a Hermes core `/handoff` command.
- The sidecar remains explicit-action oriented: there is no automatic context-risk detection that writes packets or restarts sessions.
- Secret safety remains central: examples and docs should omit real API keys, tokens, passwords, chat IDs, message IDs, and connection strings or show them only as `[REDACTED]`.

## Historical Archive

The items below are history. They describe completed milestones or superseded plans in past tense and are not active implementation instructions.

### MVP create flow

- The project started from the MVP spec pack and a document-first `PROGRESS.md`.
- The Python package skeleton and CLI help smoke path were created.
- `hermes-handoff create` was implemented.
- The git state collector was implemented with degraded non-git behavior.
- Packet assembly, schema validation, Markdown rendering, resume prompt generation, redaction, and private-key fail-closed behavior were implemented.
- Documentation, examples, and core tests were added.
- Runtime handoff outputs were intentionally ignored via `.gitignore`.

### Resume subcommand

- `hermes-handoff resume <handoff.json>` was implemented after the create flow stabilized.
- Resume reuses packet validation and requires a non-empty `resume_prompt`.
- Default output is prompt-only for copy/paste or piping into a fresh Hermes session.
- Error handling was added for missing files, invalid JSON, invalid packets, and empty resume prompts.
- Resume was kept read-only and does not discover, create, or mutate handoff artifacts automatically.

### Plugin wrapper and plugin-only command UX

- The sidecar was exposed through a pip-installable Hermes plugin entry point without modifying Hermes core.
- Plugin tools `hermes_handoff_create` and `hermes_handoff_resume` were implemented first.
- The plugin wrapper reused existing CLI/business logic instead of duplicating packet, git-state, validation, redaction, or Markdown code.
- A plugin-only `/handoff` command surface was added for compatible runtimes that expose `register_command`.
- Compatibility handling was added so tool registration remains useful even when command registration is absent or incompatible.
- `/handoff create`, implicit create forms, `/handoff resume`, and `/handoff help` were verified through fake-context tests.

### Automatic task-state collection

- Direction B, automatic task-state collection, was selected and implemented as an opt-in sidecar improvement.
- The collector scans safe repo-local evidence such as `PROGRESS.md`, `README.md`, and docs when available.
- Manual CLI/plugin values remain authoritative when auto collection is enabled.
- Missing docs, non-git repos, unreadable files, or weak signals degrade to valid packets rather than hard failures.
- Collected text remains subject to redaction and validation before any write.

### Public repo hardening and runtime compatibility

- Public metadata, licensing, maintainer identity, and GitHub-facing usage docs were aligned for public readiness.
- Usage docs were added or strengthened in Traditional Chinese, Simplified Chinese, and English.
- CI was added for install, tests, compile checks, secret scanning, and whitespace checks on Python 3.11/3.12.
- Runtime smoke tests were made portable through `HERMES_AGENT_SOURCE` and `HERMES_AGENT_PYTHON` overrides.
- The Hermes runtime plugin smoke test verifies entry-point discovery and plugin registration while using isolated temporary runtime state.

### Advisory trigger policy, doctor, and prepare

- The automatic handoff trigger policy was designed as advisory-first and sidecar/plugin-based.
- The trigger levels were documented as `observe`, `advise`, `prepare`, and `block`.
- `hermes-handoff doctor` was implemented as a read-only recommendation command.
- `hermes-handoff prepare` was implemented as a read-only preview command.
- `hermes_handoff_prepare` and plugin-only `/handoff prepare` were implemented for compatible Hermes plugin runtimes.
- The boundary `doctor` recommends, `prepare` previews, and `create` writes was established and documented.
- The older phase-plan wording near the top of this file was superseded by this current-status-first document.
