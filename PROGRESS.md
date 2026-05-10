# Hermes Continuation Progress

## Current Goal

Extend the completed MVP Python CLI sidecar with a documented, validated resume path:

1. Lock the continuation direction in progress/design docs before code.
2. Implement `hermes-handoff resume <handoff.json>` as a prompt-only extractor for fresh Hermes sessions.
3. Keep plugin-wrapper work as a later sidecar integration layer; do not modify Hermes core yet.

## Source of Truth

Spec pack: `/home/zycas/_knowledge_base/hermes-continuation-mvp/`

Key decisions already made:

- Build a Hermes-native sidecar first; do not modify Hermes core in MVP.
- Output both human-readable Markdown and machine-readable JSON.
- First version is manual command generation, not automatic context-risk detection.
- Handoff packet must include repo state, task state, verification gates, safety/redaction status, and a fresh-session resume prompt.

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
- `/handoff` slash command
- Automatic session restart
- Automatic transcript parsing
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

## Verification Gates

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
- Plugin wrapper remains a later sidecar integration layer after the CLI contract stabilizes.
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

## Known Issues / Risks

- Terminal/file tools were previously affected by a stale missing cwd (`/tmp/vault-for-llm-verify-vDN0F3`); use Python execution with absolute paths from `/home/zycas` if needed.
- OpenCode/delegate outputs must be verified by checking actual files and test results; self-report is not evidence.
- Do not commit generated smoke handoff artifacts unless intentionally documenting examples.
- This sidecar is still manual: it does not add a Hermes core `/handoff` command or automatic context-risk detection yet.
