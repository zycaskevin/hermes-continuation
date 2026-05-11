# Changelog

All notable changes to this project will be documented in this file.

## [0.1.0] - 2026-05-10

### Added

- Initial public `hermes-continuation` release as a Hermes sidecar/plugin wrapper.
- CLI support for structured handoff packet create/resume workflows.
- Plugin wrapper registration for `hermes_handoff_create`, `hermes_handoff_resume`, and `/handoff` (when runtime command APIs are available).
- Multi-language usage docs (`docs/USAGE.md`, `docs/USAGE.zh-TW.md`, `docs/USAGE.zh-CN.md`) and plugin wrapper reference.

### Public repo Phase 1 readiness notes

- Project metadata aligned with Apache-2.0 repository license and maintainer identity.
- Runtime smoke test portability improved via `HERMES_AGENT_SOURCE` and `HERMES_AGENT_PYTHON` environment overrides.
- Added GitHub Actions CI matrix (Python 3.11/3.12) with editable install, pytest, compile checks, lightweight secret scanning, and `git diff --check`.
- Runtime Hermes smoke remains optional and should skip cleanly when local Hermes runtime prerequisites are unavailable.
