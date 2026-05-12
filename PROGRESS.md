# Hermes Continuation Progress

## Current Status — v0.3.0 Task D + Docs Update Complete

- **Version:** v0.3.0
- **Repository:** `/home/zycas/hermes-continuation`
- **Branch:** `main`
- **Sync state:** `main` synced to `origin/main`
- **Last commit:** Task D + CI update + docs
- **Test status:** 124 tests passed ✅

## v0.3.0 Completed Product Surface

### CLI commands (5)

| Command | Function | Writes files? |
|---------|----------|:---:|
| `hermes-handoff create` | Write handoff packet (Markdown + JSON) | ✅ |
| `hermes-handoff resume` | Read existing handoff JSON | ❌ |
| `hermes-handoff doctor` | Analyze if handoff is recommended | ❌ |
| `hermes-handoff prepare` | Preview handoff content | ❌ |
| `hermes-handoff watch` | One-shot scan: tool calls, elapsed, changed files | ❌ |

### v0.3.0 New Modules

| Module | Purpose |
|--------|---------|
| `context_monitor.py` | Auto-collect git changed_files + accept injected session metrics |
| `auto_watch.py` | Gateway notification gating: thresholds + cooldown + config |
| `watch_logger.py` | Local JSONL event logger (zero token cost) |
| `handoff_watch_cron.py` | Standalone cron script with dedup state tracking |

### Plugin tools (5)

| Tool | Function |
|------|----------|
| `hermes_handoff_create` | Write handoff packet |
| `hermes_handoff_resume` | Read existing handoff |
| `hermes_handoff_prepare` | Preview handoff content |
| `hermes_handoff_watch` | One-shot watch evaluation |
| `hermes_handoff_doctor` | Analyze + recommend |

### Auto-trigger architecture (v0.3.0)

```
Trigger sources           Processing layer           Notification targets
┌──────────┐          ┌──────────┐          ┌──────────┐
│ Gateway  │ ──┬───→  │          │          │ Feishu   │
│ Wrapper  │   │      │  Watch   │ ──────→  │ 報告群    │
└──────────┘   │      │  Engine  │          └──────────┘
               │      │          │
┌──────────┐   │      │ (reuses   │          ┌──────────┐
│ Cron     │ ──┤      │ v0.2.0    │          │ Gateway  │
│ Jobs     │   │      │ doctor    │ ──────→  │ Session  │
└──────────┘   │      │ prepare   │          └──────────┘
               │      │ watch)    │
┌──────────┐   │      └──────────┘
│ Context  │ ──┘      ┌──────────┐
│ Monitor  │          │  Logger  │ → Local JSONL
└──────────┘          └──────────┘
```

### Auto-watch notification format

```
⚠️ 有一個開發中的專案建議交接
已開發約 45 分鐘，使用 80+ 次工具，12 個檔案有變更
→ 回對話中輸入 /handoff prepare 來預覽交接內容
```

Design principles:
- ❌ No repo name or path (prevents info leak in groups)
- ❌ No changed file names
- ✅ Approximate counts only (45 min, 80+ calls, 12 files)
- ✅ Actionable next step (`/handoff prepare`)
- ✅ Mobile-readable in one glance

### Watch event logger

Logs to `~/.hermes/logs/handoff_watch.jsonl`:
```jsonl
{"ts":"2026-05-15T14:30:00+00:00","level":"advise","tool_calls":8,"elapsed":45,"changed_files":3,"trigger":"gateway","recommendation_level":"prepare"}
```

Key properties:
- Zero LLM-token cost (not read by agent)
- No conversation content, file contents, or repo paths
- String fields capped at 200 characters
- Best-effort (never raises, never blocks)

### Config reference

```yaml
plugins:
  config:
    hermes-continuation:
      auto_watch:
        enabled: true
        tool_calls_threshold: 5
        elapsed_minutes_threshold: 30
        cooldown_minutes: 20
        notify_levels: ["advise", "prepare", "block"]
      watch_repos:
        - /home/zycas/hermes-continuation
        - /home/zycas/.hermes/hermes-agent
```

### CI gates

- Python 3.11 / 3.12 / 3.13 on GitHub Actions
- pytest suite (124 tests)
- compileall for all Python files
- v0.3.0 module import verification
- Lightweight secret scan (excludes `handoff_watch_logs` dir)
- Whitespace + conflict marker check

## Dogfood State

### D-1: Watch logger ✅
- `watch_logger.py` + 15 unit tests
- Integrated into `evaluate_and_log()` on `auto_watch.py`
- `auto_watch.py` tests updated with 5 new `evaluate_and_log` tests

### D-2: Threshold tuning (pending real data)
- Review script skeleton ready
- Requires ≥50 log entries before meaningful tuning
- Target: false positive rate <30%, zero noise complaints

## Remaining Work (Post-v0.3.0)

| Priority | Item | Depends on |
|:---:|------|------------|
| P0 | Two-week dogfood + threshold tuning | Real usage data |
| P1 | Output readability tuning for non-technical users | Dogfood feedback |
| P2 | Daemon background monitor (v0.4+) | Design boundaries defined in TRIGGER_POLICY.md |
