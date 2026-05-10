from hermes_continuation.packet import build_packet
from hermes_continuation.validate import ValidationError, validate_packet


def repo_state():
    return {
        "path": "/tmp/repo",
        "git_available": True,
        "branch": "main",
        "head": "abc1234",
        "status_short": " M README.md",
        "changed_files": [{"path": "README.md", "status": "M"}],
    }


def test_build_packet_has_required_top_level_fields():
    packet = build_packet(current_goal="Ship MVP", repo=repo_state(), next_recommended_task="Run tests")
    for field in [
        "schema_version",
        "created_at",
        "source",
        "current_goal",
        "repo",
        "task_state",
        "verification",
        "safety",
        "resume_prompt",
    ]:
        assert field in packet
    assert packet["source"] == "hermes-handoff"
    assert "Required First Actions" in packet["resume_prompt"]


def test_validate_packet_fails_missing_field():
    packet = build_packet(current_goal="Ship MVP", repo=repo_state(), next_recommended_task="Run tests")
    packet.pop("resume_prompt")
    try:
        validate_packet(packet)
    except ValidationError as exc:
        assert "missing required fields" in str(exc)
    else:
        raise AssertionError("expected ValidationError")


def test_validate_packet_fails_missing_nested_required_field():
    packet = build_packet(current_goal="Ship MVP", repo=repo_state(), next_recommended_task="Run tests")
    packet["repo"].pop("changed_files")

    try:
        validate_packet(packet)
    except ValidationError as exc:
        assert "repo missing required fields" in str(exc)
        assert "changed_files" in str(exc)
    else:
        raise AssertionError("expected ValidationError")


def test_validate_packet_stays_structural_not_collector_policy():
    packet = build_packet(current_goal="Ship MVP", repo=repo_state(), next_recommended_task="Run tests")
    packet["repo"]["changed_files"] = [{"path": "graphify-out/report.json", "status": "??"}]
    packet["task_state"]["completed_work"] = []
    packet["task_state"]["in_progress"] = ""
    packet["task_state"]["known_blockers"] = []
    packet["task_state"]["do_not_touch"] = []

    validate_packet(packet)
