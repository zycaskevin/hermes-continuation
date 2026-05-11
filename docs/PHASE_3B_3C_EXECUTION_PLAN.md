# Phase 3B / 3C Execution Plan

> **For Hermes:** Use `subagent-driven-development` to implement this plan task-by-task. Keep changes sidecar/plugin-only; do not modify Hermes core.

**Goal:** Add a safe prepare-only preview flow and expose advisory recommendations through the Hermes continuation plugin without writing handoff packets unless the user explicitly runs the existing create flow.

**Architecture:** Phase 3B should reuse the existing doctor evaluator, packet builder, redaction, validation, and Markdown rendering pipeline to produce a preview envelope that is never persisted. Phase 3C should expose that advisory/preview behavior through the plugin wrapper as an additional tool and optional `/handoff` command surface while preserving all existing tool names and contracts.

**Tech Stack:** Python package in `src/hermes_continuation/`, pytest, existing Hermes plugin wrapper fake-context tests, optional real Hermes runtime smoke.

---

## Scope Boundary

### In scope

- Add `hermes-handoff prepare` as a **read-only preview** command.
- Add a reusable prepare helper in the sidecar package.
- Produce a structured preview envelope with:
  - trigger level;
  - detected signals;
  - proposed `goal`;
  - proposed `next_task`;
  - output directory;
  - safety status;
  - verification status;
  - safe create command;
  - optional Markdown preview text.
- Ensure prepare does **not** create `.hermes/handoffs/` or write packet files.
- Add plugin advisory surface without Hermes core changes:
  - likely new tool: `hermes_handoff_prepare`;
  - `/handoff doctor ...` and/or `/handoff prepare ...` command routing if command registration is available.
- Preserve current contracts for:
  - `hermes_handoff_create`;
  - `hermes_handoff_resume`;
  - `/handoff create`;
  - `/handoff resume`.
- Add tests and docs for read-only behavior, safety degradation, and plugin compatibility.

### Out of scope

- Hermes core modifications.
- Automatic session restart.
- Fresh Hermes agent launch.
- Full Hermes transcript parsing.
- Background daemon monitoring.
- Cloud sync or dashboard UI.
- Any hidden write to `.hermes/handoffs/`.
- Committing `graphify-out/`, `.hermes/handoffs/`, caches, build artifacts, or local article/checklist drafts.

---

## Dependency Order

1. **Phase 3B helper first** — add pure/read-only prepare logic before CLI or plugin UX.
2. **CLI second** — expose `hermes-handoff prepare` and lock down no-write behavior.
3. **Plugin tool third** — wrap the same helper in `hermes_handoff_prepare`.
4. **Slash command fourth** — extend `/handoff` routing only after the tool helper is stable.
5. **Docs and smoke last** — update public docs, run full verification, rebuild Graphify, and commit scoped changes.

---

## Task Plan

### Task 1: Add prepare helper module

**Objective:** Centralize preview assembly so CLI and plugin do not duplicate logic.

**Files:**

- Create: `src/hermes_continuation/prepare.py`
- Test: `tests/test_prepare.py`

**Implementation notes:**

- Add a function such as `build_prepare_preview(...) -> dict[str, Any]`.
- Inputs should mirror doctor/create-safe fields:
  - `repo_path`;
  - `goal`;
  - `next_task`;
  - `in_progress` / `active_task`;
  - `auto_task_state`;
  - `verified`, `failing`, `not_run`.
- It may call `evaluate_handoff_recommendation()`.
- If the recommendation is `prepare`, include a safe create command and preview metadata.
- If safety blocks are detected, return level `block` and no create command.
- Missing required state should degrade to `advise`, not fabricate values.
- It must not call `_write_packet()` or write to `.hermes/handoffs/`.

**Verification:**

```bash
python -m pytest -q tests/test_prepare.py
```

Expected: tests prove prepare/advise/block paths and no `.hermes/handoffs/` directory creation.

---

### Task 2: Add `hermes-handoff prepare` CLI

**Objective:** Expose prepare-only preview from the sidecar CLI.

**Files:**

- Modify: `src/hermes_continuation/cli.py`
- Modify/Test: `tests/test_prepare.py` or create `tests/test_cli_prepare.py`

**Implementation notes:**

- Add a `prepare` subparser.
- Arguments should align with `doctor` where possible:
  - `--repo`;
  - `--goal`;
  - `--in-progress`;
  - `--next`;
  - `--auto-task-state` / `--no-auto-task-state`;
  - repeatable `--verified`, `--failing`, `--not-run`;
  - `--json`.
- Human output should be clear and secret-safe.
- JSON output should be a stable envelope, e.g.:

```json
{
  "success": true,
  "preview": {
    "level": "prepare",
    "signals": [],
    "safe_create_command": "hermes-handoff create ...",
    "would_write": false
  }
}
```

- Exit code:
  - `0` for `observe`, `advise`, and `prepare` preview;
  - `2` for `block`, matching doctor safety behavior.

**Verification:**

```bash
python -m hermes_continuation.cli prepare --repo . --goal "Ship Phase 3B" --next "Run verification" --json
python -m pytest -q tests/test_prepare.py tests/test_doctor.py
```

Expected: command prints preview but creates no runtime packet files.

---

### Task 3: Add plugin prepare tool

**Objective:** Surface the same preview behavior to Hermes through the plugin wrapper.

**Files:**

- Modify: `src/hermes_continuation/plugin.py`
- Modify: `tests/test_plugin_wrapper.py`

**Implementation notes:**

- Add constants:
  - `PREPARE_TOOL = "hermes_handoff_prepare"`.
- Register the tool only through the existing required `ctx.register_tool` path.
- Do not rename or change `CREATE_TOOL`, `RESUME_TOOL`, or `TOOLSET`.
- Handler should return a JSON string and use the same `success` field convention.
- If prepare is blocked, return `success: false` or `success: true` with `level: block` only if tests and docs define that contract clearly. Prefer a conservative stable envelope:

```json
{
  "success": true,
  "preview": {
    "level": "block",
    "safe_create_command": null,
    "would_write": false
  }
}
```

- Ensure command-registration incompatibility remains non-fatal.

**Verification:**

```bash
python -m pytest -q tests/test_plugin_wrapper.py
```

Expected: fake contexts see three tools on compatible runtime; tool-only runtime still works; incompatible command API warning remains non-fatal.

---

### Task 4: Extend `/handoff` command advisory surface

**Objective:** Let users ask for advisory/prepare output from the plugin command without creating packets by accident.

**Files:**

- Modify: `src/hermes_continuation/plugin.py`
- Modify: `tests/test_plugin_wrapper.py`

**Supported forms:**

```text
/handoff doctor repo_path=. goal="..." next_task="..."
/handoff prepare repo_path=. goal="..." next_task="..." auto_task_state=true
/handoff prepare {"repo_path":".","goal":"...","next_task":"..."}
```

**Rules:**

- Bare `/handoff` must still show help.
- `/handoff create ...` must still write only through `hermes_handoff_create`.
- `/handoff prepare ...` must never write files.
- Unknown subcommands should show help.
- Existing implicit create shortcut must remain compatible for JSON/key-value arguments that do not start with `doctor` or `prepare`.

**Verification:**

```bash
python -m pytest -q tests/test_plugin_wrapper.py
```

Expected: command tests cover help, prepare output, create/resume compatibility, parse errors, and no-write behavior.

---

### Task 5: Update public docs and progress

**Objective:** Make the new Phase 3B/3C behavior understandable and discoverable.

**Files:**

- Modify: `README.md`
- Modify: `docs/USAGE.md`
- Modify: `docs/USAGE.zh-TW.md`
- Modify: `docs/USAGE.zh-CN.md`
- Modify: `docs/PLUGIN_WRAPPER.md`
- Modify: `docs/AUTOMATIC_HANDOFF_TRIGGER_POLICY.md`
- Modify: `PROGRESS.md`

**Documentation must state:**

- `prepare` is read-only.
- `doctor` recommends; `prepare` previews; `create` writes.
- Existing generated artifacts remain under `.hermes/handoffs/` and should not be committed.
- No Hermes core changes, no auto-restart, no transcript parsing, no hidden writes.
- Example secrets and IDs must be `[REDACTED]`.

**Verification:**

```bash
python -m pytest -q tests/test_public_docs.py
```

Expected: public docs tests pass and cover negative MVP boundaries.

---

### Task 6: Full verification and scoped commit

**Objective:** Prove the implementation and commit only intended source/docs/tests.

**Commands:**

```bash
python -m py_compile src/hermes_continuation/*.py tests/*.py
python -m pytest -q tests/test_public_docs.py
python -m pytest -q
python -m pytest -q tests/test_hermes_runtime_plugin_smoke.py
python -m hermes_continuation.cli prepare --repo . --goal "Phase 3B smoke" --next "Inspect preview" --json
python -m hermes_continuation.cli doctor --repo . --goal "Phase 3C smoke" --next "Inspect recommendation" --json
git diff --check
python3 -c "from graphify.watch import _rebuild_code; from pathlib import Path; _rebuild_code(Path('.'))"
```

**Secret scan:** run the existing repository secret-scan command/pattern used in prior phases, or an equivalent Python scan across committable source/docs/tests/config files.

**Scoped staging:**

```bash
git add \
  src/hermes_continuation/prepare.py \
  src/hermes_continuation/cli.py \
  src/hermes_continuation/plugin.py \
  tests/test_prepare.py \
  tests/test_cli_prepare.py \
  tests/test_plugin_wrapper.py \
  tests/test_public_docs.py \
  README.md \
  docs/USAGE.md \
  docs/USAGE.zh-TW.md \
  docs/USAGE.zh-CN.md \
  docs/PLUGIN_WRAPPER.md \
  docs/AUTOMATIC_HANDOFF_TRIGGER_POLICY.md \
  docs/PHASE_3B_3C_EXECUTION_PLAN.md \
  PROGRESS.md

git diff --cached --stat
git commit -m "feat: add prepare-only handoff preview"
```

Do **not** stage:

- `graphify-out/`;
- `.hermes/handoffs/`;
- caches;
- generated artifacts;
- local article/checklist drafts currently untracked in the repo root.

---

## Acceptance Criteria

### Phase 3B prepare-only preview

- `hermes-handoff prepare` exists.
- Prepare produces human and JSON output.
- Prepare includes level, signals, proposed goal/next task, output directory, safety status, verification status, and safe create command when available.
- Prepare never writes handoff packet files.
- Missing goal/next task degrades to `advise`, not fabricated `prepare`.
- Private-key or sensitive blocker paths return `block` without printing secret values.

### Phase 3C plugin advisory surface

- Plugin registers existing create/resume tools unchanged.
- Plugin registers prepare tool on compatible contexts.
- Optional `/handoff` supports advisory/prepare forms when command API is compatible.
- Tool-only and incompatible-command runtimes remain compatible.
- Runtime plugin smoke passes or cleanly skips by existing environment guard.

### Repo quality gates

- Full pytest passes.
- Public docs tests pass.
- Runtime smoke passes or cleanly skips.
- Source secret scan reports 0 findings.
- `git diff --check` passes.
- Graphify maintenance hook is executed.
- Commit excludes generated/runtime artifacts.

---

## Risk Matrix

| Risk | Likelihood | Impact | Mitigation |
| --- | --- | --- | --- |
| Prepare accidentally writes files | Medium | High | Add explicit no-write tests checking `.hermes/handoffs/` absence after CLI/plugin prepare. |
| CLI/plugin duplicate preview logic drifts | Medium | Medium | Centralize preview in `prepare.py`; CLI/plugin only format or wrap results. |
| Existing `/handoff` implicit create behavior breaks | Medium | High | Add regression tests for help, implicit create, explicit create, and resume. |
| Safety blocker leaks secret values in preview output | Low | High | Reuse redaction/blocking pipeline; add tests that dummy secret/private-key body is absent from output. |
| Runtime plugin command API differs | Medium | Medium | Preserve Phase 2 optional command registration fallback; test incompatible fake context. |
| Public docs imply auto-restart or hidden writes | Medium | Medium | Update docs tests to require negative MVP boundaries. |
| Generated artifacts get staged | Medium | Medium | Use scoped `git add` and verify `git diff --cached --stat`. |

---

## Recommended Start Sequence

1. Implement Task 1 and Task 2 together in a focused subagent because they share CLI/helper contracts.
2. Verify no-write behavior locally before plugin work.
3. Implement Task 3 and Task 4 in a second focused subagent.
4. Run targeted plugin tests.
5. Update docs in a third pass.
6. Run full gates and make one scoped feature commit.

---

## Handoff Notes for Implementer

- Do not trust previous summaries as proof; rerun gates live.
- Do not use `git add -A`.
- Avoid touching unrelated root drafts:
  - `HERMES_V2026_5_7_FACEBOOK_ARTICLE.md`;
  - `HERMES_V2026_5_7_UPGRADE_CHECKLIST.md`.
- Keep all examples secret-safe.
- If Graphify rebuild changes `graphify-out/`, leave it uncommitted.
