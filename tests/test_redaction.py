import pytest

from hermes_continuation.packet import build_packet
from hermes_continuation.redaction import RedactionBlocked, redact_obj, redact_text


def test_redacts_api_key_assignment():
    field = "api" + "_" + "key"
    sample = "example" + "-" + "placeholder" + "-" + "value" + "-1234567890"
    text, count = redact_text(f"{field}={sample}")
    assert count >= 1
    assert sample not in text
    assert "[REDACTED]" in text


def test_redacts_nested_object():
    field = "OPENAI" + "_" + "API" + "_" + "KEY"
    dummy_value = "dummy" + "-" + "placeholder" + "-1234567890"
    result = redact_obj({"goal": f"{field}={dummy_value}"})
    assert result.redaction_count >= 1
    assert dummy_value not in result.value["goal"]
    assert "[REDACTED]" in result.value["goal"]


def test_private_key_blocks():
    marker = "PRIVATE" + " " + "KEY"
    private = f"-----BEGIN {marker}-----\nabc\n-----END {marker}-----"
    with pytest.raises(RedactionBlocked):
        redact_text(private)


def test_private_key_blocks_inside_nested_objects():
    marker = "PRIVATE" + " " + "KEY"
    private = f"-----BEGIN {marker}-----\nabc\n-----END {marker}-----"
    with pytest.raises(RedactionBlocked):
        redact_obj({"notes": ["safe", private]})


def test_build_packet_redacts_sensitive_values_in_packet_and_prompt():
    field = "token"
    dummy_value = "dummy" + "-" + "placeholder" + "-1234567890"
    packet = build_packet(
        current_goal=f"Ship with {field}={dummy_value}",
        repo={
            "path": "/repo",
            "git_available": False,
            "branch": None,
            "head": None,
            "status_short": "",
            "changed_files": [],
        },
        next_recommended_task="Verify redaction",
    )

    assert dummy_value not in packet["current_goal"]
    assert dummy_value not in packet["resume_prompt"]
    assert "[REDACTED]" in packet["current_goal"]
    assert "[REDACTED]" in packet["resume_prompt"]
    assert packet["safety"]["redaction_count"] >= 1
