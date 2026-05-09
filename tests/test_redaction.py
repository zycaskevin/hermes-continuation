import pytest

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
