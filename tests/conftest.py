import tempfile

import pytest


@pytest.fixture
def temp_log_dir(monkeypatch):
    """Temporary directory for HERMES_WATCH_LOG_DIR (shared by all test files)."""
    with tempfile.TemporaryDirectory() as tmp:
        monkeypatch.setenv("HERMES_WATCH_LOG_DIR", tmp)
        yield tmp
