"""Render handoff packets as Markdown."""

from __future__ import annotations

from typing import Any


def _bullets(values: list[str]) -> str:
    if not values:
        return "- None recorded"
    return "\n".join(f"- {value}" for value in values)


def render_markdown(packet: dict[str, Any]) -> str:
    repo = packet["repo"]
    task = packet["task_state"]
    verification = packet["verification"]
    safety = packet["safety"]
    changed_files = repo.get("changed_files", [])
    changed = "- None" if not changed_files else "\n".join(
        f"- `{item.get('status', '').strip()}` {item.get('path', '')}" for item in changed_files
    )

    return f"""# Hermes Handoff Packet

## Metadata

- Schema version: `{packet['schema_version']}`
- Created at: `{packet['created_at']}`
- Source: `{packet['source']}`

## Current Goal

{packet['current_goal']}

## Repo State

- Path: `{repo.get('path')}`
- Git available: `{repo.get('git_available')}`
- Branch: `{repo.get('branch')}`
- HEAD: `{repo.get('head')}`

### Git Status

```text
{repo.get('status_short') or 'clean / empty'}
```

### Changed Files

{changed}

## Task State

### Completed Work

{_bullets(task.get('completed_work', []))}

### In Progress

{task.get('in_progress') or 'None recorded'}

### Known Blockers

{_bullets(task.get('known_blockers', []))}

### Do Not Touch

{_bullets(task.get('do_not_touch', []))}

### Next Recommended Task

{task.get('next_recommended_task')}

## Verification

### Verified Gates

{_bullets(verification.get('verified_gates', []))}

### Failing Gates

{_bullets(verification.get('failing_gates', []))}

### Not Run Gates

{_bullets(verification.get('not_run_gates', []))}

## Safety

- Redaction count: `{safety.get('redaction_count')}`
- Blocked: `{safety.get('blocked')}`
- Blocked reason: `{safety.get('blocked_reason')}`

## Resume Prompt

```markdown
{packet['resume_prompt']}
```
""".strip() + "\n"
