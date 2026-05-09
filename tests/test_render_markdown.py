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
