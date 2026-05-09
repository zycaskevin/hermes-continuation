"""Secret redaction helpers for handoff packets."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

PRIVATE_KEY_PATTERN = re.compile(
    r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----",
    re.DOTALL,
)

SENSITIVE_PATTERNS = [
    re.compile(r"(?i)\b(([A-Z0-9_]*)(?:api[_-]?key|token|secret|password)\s*[:=]\s*['\"]?)([A-Za-z0-9_./\-]{8,})(['\"]?)"),
    re.compile(r"(?i)\b(bearer\s+)([A-Za-z0-9_./\-]{8,})"),
    re.compile(r"\b(sk-[A-Za-z0-9_\-]{10,})\b"),
]


class RedactionBlocked(ValueError):
    """Raised when content is too sensitive to write safely."""


@dataclass(frozen=True)
class RedactionResult:
    value: Any
    redaction_count: int


def assert_no_private_key(text: str) -> None:
    if PRIVATE_KEY_PATTERN.search(text):
        raise RedactionBlocked("private key block detected; refusing to write handoff")


def redact_text(text: str) -> tuple[str, int]:
    assert_no_private_key(text)
    redactions = 0
    redacted = text

    def replace_match(match: re.Match[str]) -> str:
        nonlocal redactions
        redactions += 1
        if len(match.groups()) == 4:
            return f"{match.group(1)}[REDACTED]{match.group(4)}"
        if len(match.groups()) == 2:
            return f"{match.group(1)}[REDACTED]"
        return "[REDACTED]"

    for pattern in SENSITIVE_PATTERNS:
        redacted = pattern.sub(replace_match, redacted)
    return redacted, redactions


def redact_obj(value: Any) -> RedactionResult:
    if isinstance(value, str):
        redacted, count = redact_text(value)
        return RedactionResult(redacted, count)
    if isinstance(value, list):
        items = []
        total = 0
        for item in value:
            result = redact_obj(item)
            items.append(result.value)
            total += result.redaction_count
        return RedactionResult(items, total)
    if isinstance(value, dict):
        items = {}
        total = 0
        for key, item in value.items():
            key_result = redact_obj(key) if isinstance(key, str) else RedactionResult(key, 0)
            value_result = redact_obj(item)
            items[key_result.value] = value_result.value
            total += key_result.redaction_count + value_result.redaction_count
        return RedactionResult(items, total)
    return RedactionResult(value, 0)
