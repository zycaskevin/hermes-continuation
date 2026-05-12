# Changelog

All notable changes to Hermes Continuation.

## [0.2.0] — 2026-05-11

### Added
- **`hermes-handoff doctor`** — read-only advisory command that recommends handoff actions using local sidecar signals. Supports `observe` / `advise` / `prepare` / `block` recommendation levels.
- **`hermes-handoff prepare`** — read-only preview that builds a safe create command and packet intent without writing any artifacts.
- **`hermes-handoff watch`** — one-shot read-only auto-trigger evaluation (CLI only). Observes local signals and reuses doctor/prepare helpers.
- **`hermes_handoff_prepare` plugin tool** — exposes the prepare preview through the Hermes plugin wrapper.
- **`hermes_handoff_watch` plugin tool** — one-shot read-only watch evaluation through the plugin wrapper, with `/handoff watch` slash command on compatible runtimes.
- **`/handoff prepare` plugin slash command** — plugin-only prepare preview surface.
- **`/handoff watch` plugin slash command** — plugin-only watch evaluation surface.
- **`--auto-task-state`** — opt-in repo-local task-state collection from safe project documents and git context.
- **`hermes_handoff_resume` plugin tool** — exposes resume flow through the plugin wrapper.
- **Plugin slash commands** — `/handoff create`, `/handoff resume`, `/handoff prepare`, `/handoff watch` for compatible Hermes runtimes.
- **Hermes runtime plugin wrapper** — pip-installable entry point for Hermes plugin integration.
- **Multilingual usage guides** — Traditional Chinese, Simplified Chinese, and English.
- **GitHub Actions CI** — pytest, compileall, secret scan, whitespace/conflict-marker check on Python 3.11/3.12.
- **Automatic handoff trigger policy** — `AUTOMATIC_HANDOFF_TRIGGER_POLICY.md` with daemon design boundaries and degraded behavior docs.

### Changed
- Public metadata aligned for open-source readiness (license, authors, URLs).

## [0.1.0] — 2026-05-10

### Added
- **`hermes-handoff create`** — produces paired Markdown and JSON handoff packets under `.hermes/handoffs/`.
- **`hermes-handoff resume`** — reads an existing handoff JSON and prints the stored `resume_prompt`.
- Git state collector with non-git degraded behavior.
- Packet assembly, schema validation, Markdown rendering, and resume prompt generation.
- Redaction and private-key fail-closed safety.
- Core pytest suite.

[0.2.0]: https://github.com/zycaskevin/hermes-continuation/releases/tag/v0.2.0
[0.1.0]: https://github.com/zycaskevin/hermes-continuation/releases/tag/v0.1.0
