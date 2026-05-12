import time

from hermes_continuation.auto_watch import format_notification, should_notify


BASE_CONFIG = {
    "enabled": True,
    "tool_calls": 5,
    "elapsed": 30,
    "cooldown": 20,
    "notify_levels": ["advise", "prepare", "block"],
}


def watch_result(
    *,
    level: str = "advise",
    tool_calls: int = 5,
    elapsed_minutes: int = 30,
    changed_files: list[dict[str, str]] | None = None,
) -> dict:
    if changed_files is None:
        changed_files = [
            {"path": "src/secret_project/app.py", "status": "modified"},
            {"path": "tests/test_secret_project.py", "status": "modified"},
        ]
    return {
        "success": True,
        "level": level,
        "context": {
            "tool_calls": tool_calls,
            "elapsed_minutes": elapsed_minutes,
            "changed_files": changed_files,
        },
        "recommendation": {
            "level": level,
            "repo": {
                "path": "/home/arthur/secret-project",
                "changed_files": changed_files,
            },
        },
    }


def test_observe_does_not_trigger():
    assert should_notify(watch_result(level="observe"), BASE_CONFIG, None) is False


def test_advise_triggers_with_conditions_met():
    old_notification = time.time() - (BASE_CONFIG["cooldown"] + 1) * 60

    assert should_notify(watch_result(level="advise"), BASE_CONFIG, old_notification) is True


def test_cooldown_prevents_duplicate():
    recent_notification = time.time() - 60

    assert should_notify(watch_result(level="advise"), BASE_CONFIG, recent_notification) is False


def test_config_disabled_suppresses_all():
    config = dict(BASE_CONFIG, enabled=False)

    assert should_notify(watch_result(level="block"), config, None) is False


def test_missing_level_not_in_notify_levels():
    config = dict(BASE_CONFIG, notify_levels=["prepare", "block"])

    assert should_notify(watch_result(level="advise"), config, None) is False


def test_notification_format_no_repo_name():
    notification = format_notification(watch_result())

    assert "secret-project" not in notification
    assert "secret_project" not in notification
    assert "/home/arthur" not in notification
    assert "src/secret_project/app.py" not in notification
    assert "tests/test_secret_project.py" not in notification


def test_notification_format_mobile_readable():
    notification = format_notification(watch_result())

    assert len(notification) < 200
    assert notification.startswith("⚠️ 有一個開發中的專案建議交接")
    assert "/handoff prepare" in notification


def test_below_threshold_no_trigger():
    assert should_notify(watch_result(tool_calls=4), BASE_CONFIG, None) is False
