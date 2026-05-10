import pytest

from hermes_continuation.redaction import RedactionBlocked
from hermes_continuation.task_state import collect_task_state, merge_task_state


def test_collect_task_state_extracts_progress_sections(tmp_path):
    (tmp_path / "PROGRESS.md").write_text(
        """# Work log

## Completed Work
- Added packet builder
- Added packet builder
- Wrote CLI tests

## In Progress
- Implement auto task-state collection

## Known Issues
- Need plugin schema coverage

## Do Not Touch
- Do not modify Hermes core

## Next Step
- Run targeted tests
- Write broader docs
""",
        encoding="utf-8",
    )

    state = collect_task_state(tmp_path)

    assert state["completed_work"] == ["Added packet builder", "Wrote CLI tests"]
    assert state["in_progress"] == ["Implement auto task-state collection"]
    assert state["known_blockers"] == ["Need plugin schema coverage"]
    assert state["do_not_touch"] == ["Do not modify Hermes core"]
    assert state["next_recommended_task"] == "Run targeted tests"


def test_collect_task_state_is_conservative_without_heading_bullets(tmp_path):
    (tmp_path / "README.md").write_text("# Project\n\nThis has prose but no matching task-state bullets.\n", encoding="utf-8")
    (tmp_path / ".hermes").mkdir()
    (tmp_path / ".hermes" / "PROGRESS.md").write_text("## Completed\n- ignored runtime file\n", encoding="utf-8")

    state = collect_task_state(tmp_path, {"changed_files": [{"status": "M", "path": "README.md"}]})

    assert state == {
        "completed_work": [],
        "in_progress": [],
        "known_blockers": [],
        "do_not_touch": [],
        "next_recommended_task": "",
    }


def test_collect_task_state_filters_generated_changed_file_hints(tmp_path):
    (tmp_path / "PROGRESS.md").write_text("## In Progress\n- Fix review findings\n", encoding="utf-8")
    repo_state = {
        "changed_files": [
            {"status": "??", "path": "graphify-out/report.json"},
            {"status": "??", "path": ".hermes/handoffs/packet.json"},
            {"status": "??", "path": "_knowledge_base/session.md"},
            {"status": "??", "path": ".pytest_cache/v/cache/nodeids"},
            {"status": "??", "path": "__pycache__/module.pyc"},
            {"status": "??", "path": "pkg.egg-info/PKG-INFO"},
            {"status": "M", "path": "../outside.py"},
            {"status": "M", "path": "/tmp/outside.py"},
            {"status": "M", "path": "src/hermes_continuation/task_state.py"},
        ]
    }

    state = collect_task_state(tmp_path, repo_state)

    joined = "\n".join(state["in_progress"])
    assert "src/hermes_continuation/task_state.py" in joined
    assert "graphify-out" not in joined
    assert ".hermes" not in joined
    assert "_knowledge_base" not in joined
    assert ".pytest_cache" not in joined
    assert "__pycache__" not in joined
    assert "egg-info" not in joined
    assert "outside.py" not in joined


def test_collect_task_state_degrades_for_missing_repo(tmp_path):
    state = collect_task_state(tmp_path / "missing")

    assert state == {
        "completed_work": [],
        "in_progress": [],
        "known_blockers": [],
        "do_not_touch": [],
        "next_recommended_task": "",
    }


def test_collect_task_state_ignores_stale_broad_progress_headings(tmp_path):
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "PLUGIN_WRAPPER.md").write_text(
        """# Plugin docs

## Safety Boundaries

- The wrapper does not modify Hermes core.
- The wrapper does not restart sessions.
""",
        encoding="utf-8",
    )
    (tmp_path / "PROGRESS.md").write_text(
        """# Hermes Continuation Progress

## Completed MVP Scope

Implemented:

- `hermes-handoff create`

Still out of scope for this sidecar phase:

- Automatic session restart

## Next Scope: Resume Subcommand

Implement now:

- `hermes-handoff resume <handoff.json>`

## Automatic Task-State Collection Plan

Selected direction: automatic task-state collection.

## In Progress

- Fix automatic task-state review findings

## Next Recommended Task

- Run targeted task-state regression tests
""",
        encoding="utf-8",
    )

    state = collect_task_state(tmp_path)

    assert state["next_recommended_task"] == "Run targeted task-state regression tests"
    assert "Fix automatic task-state review findings" in state["in_progress"]
    assert not any("resume <handoff.json>" in item for item in state["in_progress"])
    assert not any("Automatic session restart" in item for item in state["completed_work"])
    assert not any("Automatic session restart" in item for item in state["do_not_touch"])
    assert not any("wrapper does not" in item for item in state["do_not_touch"])


def test_collect_task_state_blocks_private_key_in_raw_markdown(tmp_path):
    marker = "PRIVATE" + " " + "KEY"
    private = f"-----BEGIN {marker}-----\nabc\n-----END {marker}-----"
    (tmp_path / "PROGRESS.md").write_text(
        f"## In Progress\n- Safe-looking extracted line\n\n{private}\n",
        encoding="utf-8",
    )

    with pytest.raises(RedactionBlocked):
        collect_task_state(tmp_path)


def test_merge_task_state_preserves_auto_and_manual_values():
    state = merge_task_state(
        {
            "completed_work": ["Auto completed"],
            "in_progress": ["Auto active"],
            "known_blockers": ["Auto blocker"],
            "do_not_touch": ["Auto boundary"],
            "next_recommended_task": "Auto next",
        },
        completed_work=["Manual completed", "Auto completed"],
        in_progress="Manual active",
        known_blockers=["Manual blocker"],
        do_not_touch=["Manual boundary"],
        next_task="Manual next",
    )

    assert state["completed_work"] == ["Auto completed", "Manual completed"]
    assert state["in_progress"] == "Auto active\nManual active"
    assert state["known_blockers"] == ["Auto blocker", "Manual blocker"]
    assert state["do_not_touch"] == ["Auto boundary", "Manual boundary"]
    assert state["next_recommended_task"] == "Manual next"
