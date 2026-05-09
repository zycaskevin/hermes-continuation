# Hermes Continuation Progress

## Current Goal

Build the MVP Python CLI sidecar `hermes-handoff create` for structured Hermes long-task handoff packets.

## Source of Truth

Spec pack: `/home/zycas/_knowledge_base/hermes-continuation-mvp/`

Key decisions already made:

- Build a Hermes-native sidecar first; do not modify Hermes core in MVP.
- Output both human-readable Markdown and machine-readable JSON.
- First version is manual command generation, not automatic context-risk detection.
- Handoff packet must include repo state, task state, verification gates, safety/redaction status, and a fresh-session resume prompt.

## MVP Scope

Implement:

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

Do not implement yet:

- Hermes core modifications
- `/handoff` slash command
- Automatic session restart
- Automatic transcript parsing
- Dashboard / cloud sync / multi-agent workflow engine

## Minimal Development Plan

1. Create Python package skeleton and CLI help smoke test.
2. Implement git state collector.
3. Implement packet builder and resume prompt.
4. Implement redaction and validation gates.
5. Implement Markdown renderer.
6. Wire `create` command to write `.md` + `.json`.
7. Add README/docs/examples.
8. Run full tests and smoke command.
9. Commit and push scoped changes.

## Verification Gates

- `pytest -q` passes.
- `python -m hermes_continuation.cli --help` passes.
- `python -m hermes_continuation.cli create --repo . --goal "Smoke test" --next "Inspect output"` writes `.md` + `.json`.
- Generated JSON contains required top-level fields.
- Generated Markdown contains `## Resume Prompt`.
- Secret redaction tests prove obvious secrets do not leak.
- Private key block is blocked before file write.

## Current Status

- Repo cloned: `/home/zycas/hermes-continuation`
- Branch: `main`
- Initial repo contents before MVP work: `LICENSE` only
- Spec pack read and accepted as implementation source of truth
- This `PROGRESS.md` created before code implementation per Arthur's document-first rule
- MVP package, CLI, docs, schema notes, and tests are implemented.
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

## Known Issues / Risks

- Terminal/file tools were previously affected by a stale missing cwd (`/tmp/vault-for-llm-verify-vDN0F3`); use Python execution with absolute paths from `/home/zycas` if needed.
- OpenCode/delegate outputs must be verified by checking actual files and test results; self-report is not evidence.
- Do not commit generated smoke handoff artifacts unless intentionally documenting examples.
- This MVP is still manual: it does not add a Hermes core `/handoff` command or automatic context-risk detection yet.
