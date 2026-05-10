import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"

REQUIRED_PUBLIC_DOCS = [
    Path("README.md"),
    Path("docs/USAGE.md"),
    Path("docs/USAGE.zh-TW.md"),
    Path("docs/USAGE.zh-CN.md"),
]

REQUIRED_README_LINKS = [
    "docs/USAGE.md",
    "docs/USAGE.zh-TW.md",
    "docs/USAGE.zh-CN.md",
]

COMMON_USAGE_TOKENS = [
    "hermes-handoff create",
    "hermes-handoff resume",
    "--goal",
    "--next",
    "--auto-task-state",
    "hermes_handoff_create",
    "hermes_handoff_resume",
    "/handoff",
    "auto_task_state",
    "[REDACTED]",
]

LOCAL_MD_LINK_RE = re.compile(r"\[[^\]]+\]\((?!https?://|mailto:|#)([^)#]+)(?:#[^)]+)?\)")
ARTIFACT_TOKENS = [
    ".hermes/handoffs",
    "graphify-out",
    "_knowledge_base",
    ".pytest_cache",
    "__pycache__",
    "*.egg-info",
]


MVP_BOUNDARY_TOKENS = {
    Path("README.md"): [
        ("no Hermes core modification", ("does **not**", "modify Hermes core")),
        ("no auto restart", ("auto-restart sessions",)),
        ("no full transcript parsing", ("parse full Hermes transcripts",)),
        ("no launching agents", ("launch new agents",)),
        ("no cloud sync/dashboard", ("sync to cloud", "dashboard")),
    ],
    Path("docs/USAGE.md"): [
        ("no Hermes core modification", ("does **not**", "modify Hermes core")),
        ("no auto restart", ("auto-restart sessions", "automatic session manager")),
        ("no full transcript parsing", ("parse full Hermes transcripts",)),
        ("no launching agents", ("launch fresh agents",)),
        ("no cloud sync/dashboard", ("sync to cloud", "cloud sync", "dashboard")),
    ],
    Path("docs/USAGE.zh-TW.md"): [
        ("no Hermes core modification", ("不會", "修改 Hermes core")),
        ("no auto restart", ("不會", "自動重啟 session")),
        ("no full transcript parsing", ("不會", "解析完整 Hermes transcript")),
        ("no launching agents", ("不會", "啟動新 agent")),
        ("no cloud sync/dashboard", ("不會", "雲端同步", "dashboard")),
    ],
    Path("docs/USAGE.zh-CN.md"): [
        ("no Hermes core modification", ("不会", "修改 Hermes core")),
        ("no auto restart", ("不会", "自动重启 session")),
        ("no full transcript parsing", ("不会", "解析完整 Hermes transcript")),
        ("no launching agents", ("不会", "启动新 agent")),
        ("no cloud sync/dashboard", ("不会", "云端同步", "dashboard")),
    ],
}


def read_doc(relative: Path) -> str:
    path = ROOT / relative
    assert path.is_file(), f"missing public documentation file: {relative}"
    return path.read_text(encoding="utf-8")


def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text)


def assert_contains_one(text: str, alternatives: tuple[str, ...]) -> None:
    assert any(token in text for token in alternatives), f"missing one of: {alternatives!r}"


def assert_contains_all(text: str, label: str, tokens: tuple[str, ...]) -> None:
    haystack = normalize(text)
    missing = [token for token in tokens if token not in haystack]
    assert missing == [], f"missing {label}: {missing!r}"


def test_required_public_documentation_files_exist():
    missing = [str(relative) for relative in REQUIRED_PUBLIC_DOCS if not (ROOT / relative).is_file()]
    assert missing == []


def test_readme_links_all_public_usage_guides():
    readme = read_doc(Path("README.md"))

    for link in REQUIRED_README_LINKS:
        assert link in readme
        assert (ROOT / link).is_file(), f"README links missing file: {link}"


def test_readme_verification_smoke_uses_temporary_git_repo():
    readme = read_doc(Path("README.md"))

    assert "$TMPDIR/hermes-continuation-smoke" not in readme
    assert 'SMOKE_REPO="$(mktemp -d)"' in readme
    assert 'git -C "$SMOKE_REPO" init' in readme
    assert 'python -m hermes_continuation.cli create \\' in readme
    assert '--repo "$SMOKE_REPO"' in readme
    assert 'python -m hermes_continuation.cli resume "$SMOKE_JSON"' in readme


def test_english_usage_guide_covers_public_cli_plugin_and_safety_contracts():
    usage = read_doc(Path("docs/USAGE.md"))

    required_token_groups = [
        ("# Hermes Continuation Usage",),
        ("## Installation",),
        ("## CLI usage",),
        ("## Resume from a handoff",),
        ("## Hermes plugin wrapper",),
        ("## Slash command",),
        ("## Safety and redaction",),
        ("## Troubleshooting",),
    ]
    for group in required_token_groups:
        assert_contains_one(usage, group)
    for token in COMMON_USAGE_TOKENS:
        assert token in usage

    assert "--auto-task-state" in usage
    assert "off by default" in usage.lower() or "opt-in" in usage.lower()
    assert "goal" in usage and "next_task" in usage


def test_traditional_chinese_usage_guide_covers_public_contracts():
    usage = read_doc(Path("docs/USAGE.zh-TW.md"))

    required_token_groups = [
        ("# Hermes Continuation 使用說明",),
        ("## 安裝",),
        ("## CLI 使用方式",),
        ("## 從 handoff 繼續",),
        ("## Hermes 外掛包裝器",),
        ("## 斜線指令",),
        ("## 安全與遮蔽",),
        ("## 疑難排解",),
        ("必須提供",),
        ("選擇性",),
    ]
    for group in required_token_groups:
        assert_contains_one(usage, group)
    for token in COMMON_USAGE_TOKENS:
        assert token in usage


def test_simplified_chinese_usage_guide_covers_public_contracts():
    usage = read_doc(Path("docs/USAGE.zh-CN.md"))

    required_token_groups = [
        ("# Hermes Continuation 使用说明",),
        ("## 安装",),
        ("## CLI 使用方式",),
        ("## 从 handoff 继续",),
        ("## Hermes 插件包装器",),
        ("## 斜线指令",),
        ("## 安全与遮蔽",),
        ("## 故障排查",),
        ("必须提供",),
        ("选择性",),
    ]
    for group in required_token_groups:
        assert_contains_one(usage, group)
    for token in COMMON_USAGE_TOKENS:
        assert token in usage


def test_public_docs_state_negative_mvp_boundaries_explicitly():
    for relative, expectations in MVP_BOUNDARY_TOKENS.items():
        text = read_doc(relative)
        for label, tokens in expectations:
            assert_contains_all(text, f"{label} in {relative}", tokens)


def test_public_docs_state_generated_artifact_exclusions():
    for relative in REQUIRED_PUBLIC_DOCS:
        text = read_doc(relative)
        missing = [token for token in ARTIFACT_TOKENS if token not in text]
        assert missing == [], f"missing artifact exclusions in {relative}: {missing!r}"


def test_public_docs_state_redaction_and_private_key_safety():
    for relative in REQUIRED_PUBLIC_DOCS:
        text = read_doc(relative)
        lowered = text.lower()
        assert "[redacted]" in lowered, f"missing redaction placeholder in {relative}"
        assert "private-key" in lowered or "private key" in lowered, (
            f"missing private-key/private key warning in {relative}"
        )
        assert "fail closed" in lowered or "fail-closed" in lowered, (
            f"missing fail-closed private-key behavior in {relative}"
        )


def test_public_markdown_local_links_resolve():
    for relative in REQUIRED_PUBLIC_DOCS:
        text = read_doc(relative)
        base = (ROOT / relative).parent
        for link in LOCAL_MD_LINK_RE.findall(text):
            target = (base / link).resolve()
            assert target.exists(), f"broken Markdown link in {relative}: {link}"
