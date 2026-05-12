"""Tests for watch_logger."""

import json
import tempfile
from pathlib import Path

import pytest

from hermes_continuation.watch_logger import (
    _MAX_FIELD_LENGTH,
    log_watch_event,
    read_watch_log,
)


@pytest.fixture
def temp_log_dir(monkeypatch):
    with tempfile.TemporaryDirectory() as tmp:
        monkeypatch.setenv("HERMES_WATCH_LOG_DIR", tmp)
        yield tmp


class TestLogWatchEvent:
    def test_appends_jsonl_line(self, temp_log_dir):
        log_watch_event(
            level="advise",
            tool_calls=8,
            elapsed_minutes=45,
            changed_files=3,
            trigger="gateway",
        )
        entries = read_watch_log()
        assert len(entries) == 1
        entry = entries[0]
        assert entry["level"] == "advise"
        assert entry["tool_calls"] == 8
        assert entry["elapsed"] == 45
        assert entry["changed_files"] == 3
        assert entry["trigger"] == "gateway"
        assert "ts" in entry

    def test_accepts_list_for_changed_files(self, temp_log_dir):
        log_watch_event(changed_files=["a.py", "b.py"])
        assert read_watch_log()[0]["changed_files"] == 2

    def test_accepts_none_for_changed_files(self, temp_log_dir):
        log_watch_event()
        assert read_watch_log()[0]["changed_files"] == 0

    def test_default_level_is_observe(self, temp_log_dir):
        log_watch_event()
        assert read_watch_log()[0]["level"] == "observe"

    def test_default_trigger_is_gateway(self, temp_log_dir):
        log_watch_event()
        assert read_watch_log()[0]["trigger"] == "gateway"

    def test_multiple_lines_append(self, temp_log_dir):
        log_watch_event(level="observe")
        log_watch_event(level="advise")
        assert len(read_watch_log()) == 2

    def test_recommendation_level_recorded(self, temp_log_dir):
        log_watch_event(level="advise", recommendation_level="prepare")
        assert read_watch_log()[0]["recommendation_level"] == "prepare"

    def test_cooldown_active_recorded(self, temp_log_dir):
        log_watch_event(cooldown_active=True)
        assert read_watch_log()[0]["cooldown_active"] is True

    def test_cooldown_false_not_written(self, temp_log_dir):
        log_watch_event(cooldown_active=False)
        assert "cooldown_active" not in read_watch_log()[0]

    def test_string_fields_are_capped(self, temp_log_dir):
        long_text = "x" * (_MAX_FIELD_LENGTH + 100)
        log_watch_event(level=long_text, trigger=long_text)
        entry = read_watch_log()[0]
        assert len(entry["level"]) <= _MAX_FIELD_LENGTH + 1  # +1 for the "…"
        assert len(entry["trigger"]) <= _MAX_FIELD_LENGTH + 1

    def test_none_tool_calls_becomes_zero(self, temp_log_dir):
        log_watch_event(tool_calls=None)
        assert read_watch_log()[0]["tool_calls"] == 0

    def test_none_elapsed_becomes_zero(self, temp_log_dir):
        log_watch_event(elapsed_minutes=None)
        assert read_watch_log()[0]["elapsed"] == 0


class TestReadWatchLog:
    def test_empty_file_returns_empty_list(self, temp_log_dir):
        assert read_watch_log() == []

    def test_limit_truncates_results(self, temp_log_dir):
        for _ in range(5):
            log_watch_event()
        assert len(read_watch_log(limit=2)) == 2

    def test_corrupt_line_becomes_parse_error_entry(self, temp_log_dir):
        log_path = (
            Path(temp_log_dir)
            / "handoff_watch.jsonl"
        )
        log_path.write_text('{"bad json\n', "utf-8")
        entries = read_watch_log()
        assert len(entries) == 1
        assert entries[0]["ts"] == "parse-error"
        assert "line" in entries[0]
