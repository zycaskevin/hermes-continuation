"""Tests for handoff_watch_review.py."""

import datetime
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory

from hermes_continuation.handoff_watch_review import (
    _count_by_key,
    _parse_ts,
    _percent,
    _threshold_suggestion,
    review,
)


# ---------------------------------------------------------------------------
# Unit tests for helpers
# ---------------------------------------------------------------------------

class TestParseTs:
    def test_valid_iso_with_tz(self):
        ts = _parse_ts({"ts": "2026-05-12T14:30:00+00:00"})
        assert ts is not None
        assert ts.year == 2026
        assert ts.month == 5
        assert ts.day == 12

    def test_valid_iso_with_z_suffix(self):
        ts = _parse_ts({"ts": "2026-05-12T14:30:00Z"})
        assert ts is not None
        assert ts.year == 2026

    def test_valid_iso_no_tz(self):
        ts = _parse_ts({"ts": "2026-05-12T14:30:00"})
        assert ts is not None
        assert ts.year == 2026

    def test_invalid_format(self):
        ts = _parse_ts({"ts": "not-a-date"})
        assert ts is None

    def test_missing_ts(self):
        ts = _parse_ts({})
        assert ts is None

    def test_none_ts(self):
        ts = _parse_ts({"ts": None})
        assert ts is None


class TestPercent:
    def test_zero_total(self):
        assert _percent(5, 0) == "0%"

    def test_normal(self):
        assert _percent(3, 10) == "30%"

    def test_rounding(self):
        assert _percent(1, 3) in ("33%", "34%")  # float rounding


class TestCountByKey:
    def test_basic(self):
        entries = [
            {"level": "advise"},
            {"level": "prepare"},
            {"level": "advise"},
            {"level": "block"},
        ]
        counts = _count_by_key(entries, "level")
        assert counts == {"advise": 2, "prepare": 1, "block": 1}

    def test_missing_key(self):
        entries = [{"other": "x"}, {}]
        counts = _count_by_key(entries, "level")
        assert counts == {}

    def test_empty_list(self):
        assert _count_by_key([], "level") == {}


class TestThresholdSuggestion:
    def test_with_data(self):
        entries = [
            {"tool_calls": 3},
            {"tool_calls": 5},
            {"tool_calls": 8},
            {"tool_calls": 12},
            {"tool_calls": 20},
        ] * 20  # 100 entries
        result = _threshold_suggestion(entries, "tool_calls", 5)
        assert "p50=" in result
        assert "p70=" in result
        assert "p90=" in result

    def test_no_data_key(self):
        entries = [{"other": 1}] * 10
        result = _threshold_suggestion(entries, "tool_calls", 5)
        assert "no data" in result


# ---------------------------------------------------------------------------
# Integration tests with temporary log files
# ---------------------------------------------------------------------------

def _make_entry(
    *,
    ts: str = "2026-05-12T10:00:00+00:00",
    level: str = "advise",
    tool_calls: int = 8,
    elapsed: int = 45,
    changed_files: int = 3,
    trigger: str = "gateway",
    recommendation_level: str = "prepare",
    cooldown_active: bool = False,
) -> dict:
    return {
        "ts": ts,
        "level": level,
        "tool_calls": tool_calls,
        "elapsed": elapsed,
        "changed_files": changed_files,
        "trigger": trigger,
        "recommendation_level": recommendation_level,
        "cooldown_active": cooldown_active,
    }


def _write_log(lines: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for line in lines:
            f.write(json.dumps(line, ensure_ascii=False) + "\n")


def test_review_empty_log(monkeypatch):
    """Empty log should return the '尚無資料' message."""
    tmp = TemporaryDirectory()
    try:
        log_dir = Path(tmp.name) / "logs"
        log_file = log_dir / "handoff_watch.jsonl"
        log_dir.mkdir(parents=True)
        log_file.touch()  # empty file

        monkeypatch.setenv("HERMES_WATCH_LOG_DIR", str(log_dir))
        result = review(days=None)
        assert "尚無" in result
    finally:
        tmp.cleanup()


def test_review_under_fifty(monkeypatch):
    """Fewer than 50 entries should include a warning."""
    tmp = TemporaryDirectory()
    try:
        log_dir = Path(tmp.name) / "logs"
        entries = [_make_entry(ts=f"2026-05-{10 + i:02d}T10:00:00+00:00") for i in range(20)]
        _write_log(entries, log_dir / "handoff_watch.jsonl")

        monkeypatch.setenv("HERMES_WATCH_LOG_DIR", str(log_dir))
        result = review(days=None)
        assert "記錄總數：20" in result
        assert "少於建議的 50 筆" in result
    finally:
        tmp.cleanup()


def test_review_over_fifty(monkeypatch):
    """50+ entries should produce a full report without the warning."""
    tmp = TemporaryDirectory()
    try:
        log_dir = Path(tmp.name) / "logs"
        entries = [_make_entry() for _ in range(55)]
        _write_log(entries, log_dir / "handoff_watch.jsonl")

        monkeypatch.setenv("HERMES_WATCH_LOG_DIR", str(log_dir))
        result = review(days=None)
        assert "記錄總數：55" in result
        assert "少於建議的 50 筆" not in result
        assert "觸發等級分佈" in result
        assert "觸發來源" in result
        assert "Cooldown 狀態" in result
        assert "平均指標" in result
        assert "閾值調整建議" in result
    finally:
        tmp.cleanup()


def test_review_level_distribution(monkeypatch):
    """Level counts should be accurate."""
    tmp = TemporaryDirectory()
    try:
        log_dir = Path(tmp.name) / "logs"
        entries = []
        entries.extend([_make_entry(level="observe") for _ in range(10)])
        entries.extend([_make_entry(level="advise") for _ in range(30)])
        entries.extend([_make_entry(level="prepare") for _ in range(15)])
        entries.extend([_make_entry(level="block") for _ in range(5)])
        _write_log(entries, log_dir / "handoff_watch.jsonl")

        monkeypatch.setenv("HERMES_WATCH_LOG_DIR", str(log_dir))
        result = review(days=None)
        assert "observe :   10" in result
        assert "advise  :   30" in result
        assert "prepare :   15" in result
        assert "block   :    5" in result
    finally:
        tmp.cleanup()


def test_review_trigger_sources(monkeypatch):
    """Trigger source breakdown should be accurate."""
    tmp = TemporaryDirectory()
    try:
        log_dir = Path(tmp.name) / "logs"
        entries = []
        entries.extend([_make_entry(trigger="gateway") for _ in range(40)])
        entries.extend([_make_entry(trigger="cron") for _ in range(10)])
        entries.extend([_make_entry(trigger="cli") for _ in range(2)])
        _write_log(entries, log_dir / "handoff_watch.jsonl")

        monkeypatch.setenv("HERMES_WATCH_LOG_DIR", str(log_dir))
        result = review(days=None)
        assert "gateway" in result
        assert "cron" in result
        assert "cli" in result
    finally:
        tmp.cleanup()


def test_review_cooldown_ratio(monkeypatch):
    """Cooldown counts should be accurate."""
    tmp = TemporaryDirectory()
    try:
        log_dir = Path(tmp.name) / "logs"
        entries = []
        entries.extend([_make_entry(cooldown_active=True) for _ in range(12)])
        entries.extend([_make_entry(cooldown_active=False) for _ in range(48)])
        _write_log(entries, log_dir / "handoff_watch.jsonl")

        monkeypatch.setenv("HERMES_WATCH_LOG_DIR", str(log_dir))
        result = review(days=None)
        assert "cooldown active:" in result
        assert "12" in result  # count
        assert "20%" in result  # 12/60
    finally:
        tmp.cleanup()


def test_review_days_filter(monkeypatch):
    """--days filter should exclude old entries."""
    tmp = TemporaryDirectory()
    try:
        log_dir = Path(tmp.name) / "logs"

        today = datetime.datetime.now(datetime.timezone.utc)
        entries = [
            _make_entry(ts=(today - datetime.timedelta(days=5)).isoformat()),
            _make_entry(ts=(today - datetime.timedelta(days=10)).isoformat()),
            _make_entry(ts=(today - datetime.timedelta(days=1)).isoformat()),
        ] * 20  # 60 entries total, but only 40 are within 7 days
        _write_log(entries, log_dir / "handoff_watch.jsonl")

        monkeypatch.setenv("HERMES_WATCH_LOG_DIR", str(log_dir))
        result = review(days=7)
        assert "記錄總數：40" in result
        assert "少於建議的 50 筆" in result
    finally:
        tmp.cleanup()


def test_review_days_filter_empty(monkeypatch):
    """Filtering to 0 days should show empty."""
    tmp = TemporaryDirectory()
    try:
        log_dir = Path(tmp.name) / "logs"
        entries = [_make_entry(ts="2020-01-01T00:00:00+00:00") for _ in range(5)]
        _write_log(entries, log_dir / "handoff_watch.jsonl")

        monkeypatch.setenv("HERMES_WATCH_LOG_DIR", str(log_dir))
        result = review(days=1)
        assert "尚無" in result or "0 天內" in result
    finally:
        tmp.cleanup()


def test_review_malformed_lines(monkeypatch):
    """Malformed JSON lines should not crash the review."""
    tmp = TemporaryDirectory()
    try:
        log_dir = Path(tmp.name) / "logs"
        log_path = log_dir / "handoff_watch.jsonl"
        log_dir.mkdir(parents=True)
        with log_path.open("w", encoding="utf-8") as f:
            f.write('{"ts":"2026-05-12T10:00:00+00:00","level":"advise","tool_calls":8,"elapsed":45,"changed_files":3}\n')
            f.write("this is not json\n")
            f.write('{"ts":"2026-05-12T11:00:00+00:00","level":"prepare","tool_calls":12,"elapsed":60,"changed_files":5}\n')
            f.write("\n")  # blank line

        monkeypatch.setenv("HERMES_WATCH_LOG_DIR", str(log_dir))
        result = review(days=None)
        assert "尚無" not in result
    finally:
        tmp.cleanup()


def test_review_progress_bar(monkeypatch):
    """Progress bar should appear."""
    tmp = TemporaryDirectory()
    try:
        log_dir = Path(tmp.name) / "logs"
        entries = [_make_entry() for _ in range(25)]
        _write_log(entries, log_dir / "handoff_watch.jsonl")

        monkeypatch.setenv("HERMES_WATCH_LOG_DIR", str(log_dir))
        result = review(days=None)
        assert "調優準備進度" in result
        assert "25/50" in result
        assert "50%" in result
    finally:
        tmp.cleanup()
