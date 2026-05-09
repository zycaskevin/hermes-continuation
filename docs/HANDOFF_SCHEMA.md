# Handoff Packet Schema

## 1. Design Principle

Handoff packet 同時服務兩種讀者：

1. **Human**：看 Markdown，快速知道目前狀態。
2. **Machine / Agent**：看 JSON，穩定解析與續工。

因此 MVP 產出兩個檔案：

```text
.hermes/handoffs/<timestamp>.md
.hermes/handoffs/<timestamp>.json
```

## 2. Top-Level Fields

```json
{
  "schema_version": "0.1.0",
  "created_at": "2026-05-09T15:30:00+08:00",
  "source": "hermes-handoff",
  "current_goal": "...",
  "repo": {},
  "task_state": {},
  "verification": {},
  "safety": {},
  "resume_prompt": "..."
}
```

## 3. JSON Schema Draft

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://nancyai.dev/schemas/hermes-handoff.schema.json",
  "title": "Hermes Handoff Packet",
  "type": "object",
  "required": [
    "schema_version",
    "created_at",
    "source",
    "current_goal",
    "repo",
    "task_state",
    "verification",
    "safety",
    "resume_prompt"
  ],
  "properties": {
    "schema_version": { "type": "string" },
    "created_at": { "type": "string", "format": "date-time" },
    "source": { "type": "string", "const": "hermes-handoff" },
    "current_goal": { "type": "string", "minLength": 1 },
    "repo": {
      "type": "object",
      "required": ["path", "git_available", "branch", "head", "status_short", "changed_files"],
      "properties": {
        "path": { "type": "string" },
        "git_available": { "type": "boolean" },
        "branch": { "type": ["string", "null"] },
        "head": { "type": ["string", "null"] },
        "status_short": { "type": "string" },
        "changed_files": {
          "type": "array",
          "items": {
            "type": "object",
            "required": ["path", "status"],
            "properties": {
              "path": { "type": "string" },
              "status": { "type": "string" }
            }
          }
        }
      }
    },
    "task_state": {
      "type": "object",
      "required": [
        "completed_work",
        "in_progress",
        "known_blockers",
        "next_recommended_task",
        "do_not_touch"
      ],
      "properties": {
        "completed_work": { "type": "array", "items": { "type": "string" } },
        "in_progress": { "type": "array", "items": { "type": "string" } },
        "known_blockers": { "type": "array", "items": { "type": "string" } },
        "next_recommended_task": { "type": "string" },
        "do_not_touch": { "type": "array", "items": { "type": "string" } }
      }
    },
    "verification": {
      "type": "object",
      "required": ["verified_gates", "failing_gates", "not_run_gates"],
      "properties": {
        "verified_gates": { "type": "array", "items": { "type": "string" } },
        "failing_gates": { "type": "array", "items": { "type": "string" } },
        "not_run_gates": { "type": "array", "items": { "type": "string" } }
      }
    },
    "safety": {
      "type": "object",
      "required": ["redaction_count", "blocked", "blocked_reason"],
      "properties": {
        "redaction_count": { "type": "integer", "minimum": 0 },
        "blocked": { "type": "boolean" },
        "blocked_reason": { "type": ["string", "null"] }
      }
    },
    "resume_prompt": { "type": "string", "minLength": 1 }
  }
}
```

## 4. Markdown Output Structure

```markdown
# Hermes Handoff — <current_goal>

## Resume Prompt
[可直接貼給新 session]

## Current Goal
...

## Repo State
- Path:
- Branch:
- HEAD:
- Changed files:

## Completed Work
...

## In Progress
...

## Verified Gates
...

## Failing / Not Run Gates
...

## Known Blockers
...

## Do Not Touch
...

## Next Recommended Task
...

## Safety
- Blocked:
- Blocked reason:
- Redaction count:
```

## 5. Redaction Rules

必須掃描並 redacted：

- API keys
- bearer tokens
- password
- private keys
- database connection strings
- OAuth tokens
- webhook secrets

輸出中出現這類 pattern 時，替換為：

```text
[REDACTED]
```

若偵測到 private key block：

```text
-----BEGIN ... PRIVATE KEY-----
```

MVP 建議直接 fail closed，不寫 handoff，提示使用者清理輸入。

## 6. Minimal Example

```json
{
  "schema_version": "0.1.0",
  "created_at": "2026-05-09T15:30:00+08:00",
  "source": "hermes-handoff",
  "current_goal": "完成 Dashboard health page QA",
  "repo": {
    "path": "/home/zycas/project",
    "git_available": true,
    "branch": "main",
    "head": "abc1234",
    "status_short": " M src/App.tsx",
    "changed_files": [{ "path": "src/App.tsx", "status": "M" }]
  },
  "task_state": {
    "completed_work": ["完成 health API mapping"],
    "in_progress": ["browser QA"],
    "known_blockers": [],
    "next_recommended_task": "Run npm build and browser smoke test",
    "do_not_touch": ["billing code"]
  },
  "verification": {
    "verified_gates": ["unit tests pass"],
    "failing_gates": [],
    "not_run_gates": ["browser QA"]
  },
  "safety": {
    "redaction_count": 0,
    "blocked": false,
    "blocked_reason": null
  },
  "resume_prompt": "You are resuming a Hermes long-running task..."
}
```
