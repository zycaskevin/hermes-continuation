from hermes_continuation.packet import build_packet
from hermes_continuation.render_markdown import render_markdown


def test_markdown_contains_resume_prompt_section():
    packet = build_packet(
        current_goal="Create handoff",
        repo={
            "path": "/repo",
            "git_available": False,
            "branch": None,
            "head": None,
            "status_short": "",
            "changed_files": [],
        },
        next_recommended_task="Inspect output",
    )
    markdown = render_markdown(packet)
    assert "## Resume Prompt" in markdown
    assert "## Current Goal" in markdown
    assert "Create handoff" in markdown


def test_markdown_renders_changed_files_safety_and_trailing_newline():
    packet = build_packet(
        current_goal="Render readiness",
        repo={
            "path": "/repo",
            "git_available": True,
            "branch": "main",
            "head": "abc1234",
            "status_short": " M src/app.py",
            "changed_files": [{"status": "M", "path": "src/app.py"}],
        },
        next_recommended_task="Inspect markdown",
    )
    packet["safety"]["redaction_count"] = 1

    markdown = render_markdown(packet)

    assert markdown.endswith("\n")
    assert "```text\n M src/app.py\n```" in markdown
    assert "- `M` src/app.py" in markdown
    assert "- Redaction count: `1`" in markdown
    assert "```markdown" in markdown
