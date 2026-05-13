# Changelog

All notable changes to Hermes Continuation.

## Unreleased

### Added
- Auto-doctor restart advisory payloads now include `restart_recommended`, `handoff_recommended`, count-based `metrics`, optional `task_execution` completeness, trigger `signals` / `reasons`, a user-facing `notice`, and a pasteable `handoff_prompt` draft.

### Fixed
- CLI output no longer crashes on Windows consoles that use legacy encodings when localized output contains symbols outside the active code page.
- Plugin slash-command parsing now preserves Windows path backslashes for key-value arguments and `/handoff resume` paths.

## [0.3.0] — 2026-05-12

### Added
- **Context Monitor** — `context_monitor.py`: auto-collects git changed_files + accepts injected session metrics (tool_calls / elapsed_minutes). Manual values always override auto values.
- **Auto-Trigger** — `auto_watch.py`: Gateway notification gating with threshold checks, cooldown deduplication, and config `enabled` switch. Includes `evaluate_and_log()` single-call entry point.
- **Cron Watch** — `handoff_watch_cron.py`: standalone cron script that scans configured repos, with per-repo dedup state tracking (only notifies on new commits).
- **Watch Logger** — `watch_logger.py`: local JSONL event logger (zero LLM-token cost). Logs level / tool_calls / elapsed / changed_files / trigger source. All fields sanitized, never records repo paths or file contents.
- **Two-Week Review Script** — `handoff_watch_review.py`: reads accumulated watch logs and prints a summary for threshold tuning (≥50 entries target, <30% false positive target).
- CI: Python 3.13 support, v0.3.0 module import verification, `handoff_watch_logs` dir excluded from secret scan.
- Docs: PROJECT_OVERVIEW.md and PROGRESS.md updated for v0.3.0 architecture and dogfood state.

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
