# Automatic Handoff Trigger Policy

This document defines the Phase 3 design and current public behavior for proactive handoff recommendations in `hermes-continuation`.

Phase 3A/3B/3C now provide read-only advisory and preview surfaces: `hermes-handoff doctor`, `hermes-handoff prepare`, plugin tool `hermes_handoff_prepare`, and `/handoff prepare ...` on compatible runtimes. Phase 3 still does **not** implement automatic session restart, Hermes core changes, transcript parsing, agent launching, cloud sync, dashboard behavior, or hidden writes.

## Purpose

Long-running agent work often becomes risky when the context is large, the working tree is dirty, verification is incomplete, or the user is about to leave the session. The goal of this policy is to help Hermes recommend a safe handoff at the right moment without taking hidden actions.

The first implementation should stay conservative:

- surface a handoff recommendation with `doctor`;
- explain why the recommendation appeared;
- build a read-only preview with `prepare`;
- show the exact command or tool arguments that would create the handoff when safe;
- require explicit user action before writing a new handoff packet.

In plain language: Hermes may say, “This is a good time to save a handoff,” but it should not secretly create one or restart the session.

## Design Principles

1. **User control first**
   - A recommendation is not consent.
   - The user must explicitly run the command, invoke the tool, or approve the write.

2. **No fabricated state**
   - If the trigger engine cannot see enough information, it should degrade to an advisory message.
   - It must not invent goals, next tasks, test results, git status, or session history.

3. **Secret-safe by default**
   - Packet previews must pass the existing redaction and private-key blocking behavior.
   - If safety blockers are found, the result level is `block`, safe create commands are suppressed, and secret values are not printed.
   - Sensitive examples must use `[REDACTED]`.

4. **Sidecar/plugin-wrapper boundary**
   - The first trigger mechanism should be implementable outside Hermes core.
   - It may use the existing CLI sidecar and plugin wrapper.
   - It must not depend on private Hermes internals.

5. **Generated artifacts stay local**
   - Handoff packets remain local runtime artifacts under `.hermes/handoffs/`.
   - They should not be committed.

## Trigger Levels

The trigger policy has four levels.

| Level | Meaning | User-facing behavior | Write allowed? |
| --- | --- | --- | --- |
| `observe` | Signals are collected but below the recommendation threshold. | No prompt. | No |
| `advise` | Hermes should recommend creating a handoff. | Show a short explanation and suggested command. | No |
| `prepare` | Hermes can assemble a preview or command from available safe state. | Show exact CLI/tool arguments and ask the user to run/approve. | Only after explicit user action |
| `block` | Safety checks indicate a handoff should not be written automatically. | Explain the blocker and suggest manual cleanup. | No |

The default behavior for unknown or incomplete state is `advise`, not `prepare`.

## Candidate Signals

A future trigger evaluator can combine these signals. Phase 3 only defines the policy; it does not implement the evaluator.

### Session and work signals

- Long task duration.
- High tool-call count.
- Context compression warning or context-risk metadata when exposed by Hermes.
- Repeated user references to continuation, fresh sessions, or “continue later.”
- Explicit user commands such as:
  - `handoff`
  - `save handoff`
  - `continue in a new session`
  - `fresh session`

### Repository signals

- Dirty tracked files.
- Untracked files that appear to be relevant source/docs/tests.
- Generated/runtime artifacts present in ignored directories.
- Local branch ahead/behind remote.
- Worktree contains staged changes.

### Verification signals

- Tests not run after a code change.
- Last known verification failed.
- Verification status is missing or stale.
- Docs gates not run after docs-only changes.
- Runtime smoke skipped because local Hermes runtime is unavailable.

### Safety signals

- Redaction scan failed.
- Private key material detected.
- Packet would include credentials, tokens, passwords, connection strings, chat IDs, or message IDs.
- Required packet fields are missing.
- The proposed handoff output path points outside the allowed runtime output directory.

Safety signals override convenience signals. If a safety signal is severe, the level should become `block`.

## Recommendation Matrix

| Situation | Recommended level | Rationale |
| --- | --- | --- |
| Short task, clean repo, no user continuation request | `observe` | Avoid noisy prompts. |
| Long task with many tool calls but no safety issue | `advise` | Helpful reminder; no hidden write. |
| User explicitly asks for a handoff and required fields are known | `prepare` | Show exact command/tool args for confirmation. |
| Dirty repo plus verification not run | `advise` | Recommend handoff after summarizing pending gates. |
| Redaction scan fails | `block` | Do not create packet until sensitive content is removed/redacted. |
| Private key detected | `block` | Existing fail-closed behavior must be preserved. |
| Missing goal or next task | `advise` | Ask user or show a template; do not fabricate state. |

## UX Contract

### Advisory message

A minimal recommendation should include:

1. why Hermes thinks a handoff may help;
2. what state is known;
3. what is unknown or not verified;
4. the command or tool call the user can run.

Example:

```text
Handoff recommended: this task has many tool calls and uncommitted changes.
Known state: docs changed, docs tests not run yet.
Suggested command:
hermes-handoff create --goal "[REDACTED GOAL]" --next "[REDACTED NEXT TASK]"
```

The example uses placeholder text because real goals may contain private project details.

### Prepare-level preview

A prepare-level preview may show a structured summary, but it must not write a packet until the user explicitly approves or runs the command. In current CLI behavior, `hermes-handoff prepare` is always read-only: it never creates `.hermes/handoffs/` directories or handoff packet files. It may show a safe `hermes-handoff create ...` command, but the user must explicitly run `create` to write.

Required preview fields:

- trigger level;
- detected signals;
- proposed `goal`;
- proposed `next_task`;
- output directory;
- safety status;
- verification status.

### Block message

A block message should be direct and actionable:

```text
Handoff packet not prepared because the safety scan found sensitive material.
Remove or redact the sensitive content, then run the handoff command again.
```

It should not print the secret value, and it should not include a safe create command.

## CLI Boundary

The CLI contract is split by side effect:

```bash
hermes-handoff doctor --goal "..." --next "..."   # recommends only
hermes-handoff prepare --goal "..." --next "..."  # read-only preview
hermes-handoff create --goal "..." --next "..."   # writes packet files
hermes-handoff resume path/to/handoff.json          # reads an existing packet
```

Plain language: `doctor` recommends; `prepare` previews; `create` writes. `prepare` is read-only and never writes `.hermes/handoffs/` packet files. A prepare preview may show a safe create command, but it is only guidance; the user must explicitly run `create` to write.

## Plugin Wrapper Boundary

The plugin wrapper exposes recommendation/preview behavior without changing Hermes core.

Current tools:

- `hermes_handoff_prepare` — read-only preview; never writes packet files.
- `hermes_handoff_create` — explicit write path for Markdown + JSON packets.
- `hermes_handoff_resume` — read existing handoff JSON.

On compatible runtimes, the optional slash command supports `/handoff prepare ...` as a UX shim over `hermes_handoff_prepare`. The command must preserve the Phase 2 compatibility rule:

- `register_tool` is required;
- incompatible optional command registration must not prevent tool registration;
- command-registration warnings must remain non-fatal.

## Safety Gates Before Any Future Automatic Write

Before any future implementation writes a handoff packet based on trigger policy, it must pass these gates:

1. Required packet fields are present.
2. Redaction scan passes.
3. Private-key detection does not trigger.
4. Output path is inside the configured local handoff directory.
5. Generated/runtime artifacts are excluded from commit guidance.
6. Verification status is represented honestly:
   - passed;
   - failed;
   - skipped;
   - not run;
   - unknown.
7. The user has explicitly requested or approved the write.

If any required gate is missing, the system must degrade to `advise` or `block`.

## Non-goals

Phase 3A/3B/3C intentionally do not implement:

- Hermes core modifications;
- automatic session restart;
- automatic fresh-session launch;
- full Hermes transcript parsing;
- hidden handoff packet writes;
- cross-agent handoff packet standardization;
- cloud sync;
- dashboard UI;
- background daemon monitoring.

These may be separate future projects, but they should not be smuggled into the first trigger policy.

## Implementation Phases

### Phase 3A: Advisory command

Current implemented shape:

```bash
hermes-handoff doctor
```

Output is human-readable by default, JSON with `--json`, and secret-safe. It recommends but does not write.

### Phase 3B: Prepare-only preview

Current implemented shape:

```bash
hermes-handoff prepare --goal "..." --next "..."
```

The preview is validatable and redacted, but not persisted unless the user runs `create`. It never writes `.hermes/handoffs/` packet files.

### Phase 3C: Plugin advisory surface

Current implemented plugin surface:

- `hermes_handoff_prepare` tool;
- `/handoff prepare ...` on Hermes runtimes with compatible plugin slash-command support.

Both surfaces are read-only previews and preserve the no-core-change boundary.

### Phase 3D: Optional approved write

Only after the advisory and preview flows are stable, allow an explicit approved write path.

The write path must still call the existing packet builder and redaction pipeline.

## Acceptance Criteria for This Design

This Phase 3 design is acceptable when:

- trigger levels are defined;
- candidate signals are documented;
- advisory vs prepare vs block behavior is clear;
- safety gates are explicit;
- non-goals preserve the conservative MVP boundary;
- no runtime behavior is changed by this document;
- docs gates pass;
- examples remain secret-safe.
