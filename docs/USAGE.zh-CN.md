# Hermes Continuation 使用说明（简体中文）

`hermes-continuation` 用来为长时间运行的 Hermes agent 工作创建结构化续工交接。它目前是一个 sidecar CLI，加上一层很薄的 Hermes plugin wrapper。真正的产品契约是 handoff packet：给人看的本地 Markdown，以及给 agent/tool 稳定读取的本地 JSON。

当前 MVP 刻意保持保守：`doctor` 只提出建议，`prepare` 只生成预览，`create` 才会写入 packet files，`watch` 则通过既有 doctor/prepare helpers 做一次性的只读 advisory 检查。它**不会**修改 Hermes core、不会自动重启 session、不会解析完整 Hermes transcript、不会启动新 agent、不会云端同步、不提供 dashboard、不会默认启动 daemon，也不会 hidden writes。

## 什么时候使用

适合在以下场景使用 `hermes-continuation`：

- 任务太长，不适合塞在同一个 session；
- context 变大、被压缩，或即将失去细节；
- 需要另一个 Hermes session 或队友安全接手；
- 希望下一个 agent 明确看到 repo 状态、验证结果、blocker 与边界；
- 需要一段可以直接贴到新 Hermes session 的 resume prompt，而且背后有结构化数据支撑。

不要把它当成 secret vault、完整 transcript archive、云端同步工具、后台监控器，或自动 session manager。

## Handoff 内容

每份 handoff packet 会记录：

- 当前目标；
- repository path、branch、HEAD、`git status --short`、changed files；
- 已完成工作与进行中工作；
- 已知 blocker；
- 不可触碰的边界；
- 已验证、失败、尚未执行的 gates；
- safety/redaction 状态；
- 给新 Hermes session 的 resume prompt。

默认输出位置：

```text
.hermes/handoffs/<timestamp>-handoff.md
.hermes/handoffs/<timestamp>-handoff.json
```

请把 `.hermes/handoffs/` 视为 runtime output。除非你已经明确审查并清理内容，否则不要 commit。

## 安装

<!-- Compatibility alias: ## 从 repo 安装 -->

进入此 repo，将包以 editable mode 安装到当前 Python environment：

```bash
cd /path/to/hermes-continuation
python -m pip install -e .
```

确认 CLI 可用：

```bash
hermes-handoff --help
python -m hermes_continuation.cli --help
```

如果找不到 `hermes-handoff`，可以先用 module form，或确认 shell 使用的是安装此包的 Python environment。

## CLI 使用方式

<!-- Compatibility alias: ## 使用 CLI 创建 handoff -->

`hermes-handoff create` 必须提供 `--goal` 与 `--next`；这两个字段是必填信息。

最小示例：

```bash
hermes-handoff create \
  --repo . \
  --goal "完成 dashboard QA" \
  --next "执行 build 与 browser smoke test"
```

较完整示例：

```bash
hermes-handoff create \
  --repo . \
  --goal "完成 dashboard QA" \
  --completed "更新 health-card 文案" \
  --completed "补上 health status mapping 的 unit coverage" \
  --in-progress "准备 release verification" \
  --verified "python -m pytest -q passed" \
  --failing "browser smoke test 仍卡在 loading state" \
  --not-run "production deploy dry run" \
  --blocker "等待 product sign-off 最终文案" \
  --do-not-touch "billing migrations" \
  --next "执行 build 与 browser smoke test"
```

等价的 module form：

```bash
python -m hermes_continuation.cli create --repo . --goal "Smoke test" --next "Inspect output"
```

常用选项：

- `--repo`：要检查的 repository path，默认是当前目录。
- `--output-dir`：自定义输出目录，默认是 `<repo>/.hermes/handoffs`。
- `--completed`、`--verified`、`--failing`、`--not-run`、`--blocker`、`--do-not-touch`：可重复使用的 list 字段。
- `--in-progress`：当前进行中的工作描述。

## 只读 doctor 与 prepare 预览

如果只想取得 handoff 建议而不创建任何文件，使用 `doctor`：

```bash
hermes-handoff doctor \
  --repo . \
  --goal "完成 dashboard QA" \
  --next "执行 build 与 browser smoke test"
```

如果想在写入前先看结构化预览，使用 `prepare`：

```bash
hermes-handoff prepare \
  --repo . \
  --goal "完成 dashboard QA" \
  --next "执行 build 与 browser smoke test"
```

白话边界：

- `doctor` 只建议是否该创建 handoff。
- `prepare` 只预览 proposed handoff state，可能显示安全的 `hermes-handoff create ...` command。
- `create` 才会实际写入 Markdown/JSON packet files；默认位置是 `.hermes/handoffs/`。
- `prepare` 是 read-only；即使打印 safe create command，也绝不创建 `.hermes/handoffs/` 目录或 packet files。
- safe create command 只是提示，不代表同意写入。用户必须明确执行 `hermes-handoff create ...` 才会写入 packet。
- 缺少 `goal` 或 `next` 时会降级为 `advise`，不会捏造状态。
- safety blockers 会返回 `block`，隐藏 safe create command，且不打印 secret values。

两个命令都支持 `--json`，可输出 machine-readable recommendation/preview envelope。

## 一次性 watch advisory

`hermes-handoff watch` 已实现为一次性的 CLI command，用于 advisory auto-trigger 检查。它只观察明确提供的本地 signals 一次，调用既有 doctor/prepare helpers，打印建议或 preview，然后退出。

示例：

```bash
hermes-handoff watch \
  --repo . \
  --goal "完成 dashboard QA" \
  --next "执行 build 与 browser smoke" \
  --tool-calls 8 \
  --elapsed-minutes 45 \
  --dirty-threshold 1 \
  --explicit-request
```

Machine-readable output：

```bash
hermes-handoff watch --repo . --goal "完成 QA" --next "执行 smoke" --explicit-request --json
```

支持的 watch flags 包含 `--goal`、`--next`、`--tool-calls`、`--elapsed-minutes`、`--dirty-threshold`、`--explicit-request`、`--json`。

Watch 边界：

- 仅 read-only/advisory：绝不写入 `.hermes/handoffs/` packet files，也不创建该目录；
- 没有 hidden create path：不会代替用户调用 `hermes-handoff create` 或 packet-writing helpers；
- 默认不是 daemon：只评估一次就退出；
- 缺少 `goal` 或 `next` 时会降级为 `advise`，不会捏造 preview state；
- `block` 结果会隐藏 secret values 与 safe create commands；
- 目前没有 plugin/gateway `/handoff watch`；这个 MVP 只提供 CLI `hermes-handoff watch`。

白话 side-effect 边界：`doctor` 只建议，`prepare` 只预览，`create` 才写入，`watch` 通过既有 doctor/prepare helpers 观察、建议、预览。

## 选择性自动收集 task state

自动收集 task state 默认是**关闭**的。必须明确加上：

```bash
hermes-handoff create \
  --repo . \
  --goal "完成 dashboard QA" \
  --auto-task-state \
  --completed "要保留的手动补充" \
  --next "执行 build 与 browser smoke test"
```

`--auto-task-state` 的边界：

- 只扫描保守的 repo-local Markdown：
  - `PROGRESS.md`
  - `README.md`
  - 直层 `docs/*.md`
- 只提取 Completed Work、In Progress、Blockers、Do Not Touch、Next Step 等 task-state heading 下方的 bullets；
- 跳过 generated/runtime paths，例如 `.git`、`.hermes`、`graphify-out`、`_knowledge_base`、`.pytest_cache`、`__pycache__`、`*.egg-info`；
- 限制收集的条目数与字数；
- 如果扫描到 private-key block，会 fail closed；
- 不会解析完整 Hermes transcript；
- 不会从 chat history 推测隐藏状态；
- manual list values 会追加在 auto-collected values 后面并去重；
- manual `--next` 永远优先。

重要信息请仍然使用手动 flags。自动收集只是方便预填，不是唯一事实来源。

## 从 handoff 继续

<!-- Compatibility alias: ## 从 handoff JSON 恢复续工 prompt -->

使用生成的 JSON 打印给新 session 的 prompt：

```bash
hermes-handoff resume .hermes/handoffs/<timestamp>-handoff.json
```

默认情况下，`resume` 只输出 prompt 文本，方便直接贴到新的 Hermes session 或 pipe 给其他工具。如果想输出带标题的 Markdown：

```bash
hermes-handoff resume --markdown .hermes/handoffs/<timestamp>-handoff.json
```

`resume` 会先验证 JSON packet。它不会创建新的 handoff、不会修改 handoff file，也不会推测缺失的任务状态。

## Hermes 插件包装器

<!-- Compatibility alias: ## Hermes plugin 安装与启用 -->

若要在 Hermes runtime/plugin 中使用，请把 `hermes-continuation` 安装到**运行 Hermes 的同一个 Python interpreter**。实际路径取决于你的 Hermes 安装方式。Plugin 需要选择启用，不会默认加载。

示例模式：

```bash
cd /path/to/hermes-continuation
/path/to/hermes/python -m pip install -e .
```

此包提供 entry point：

```toml
[project.entry-points."hermes_agent.plugins"]
hermes-continuation = "hermes_continuation.plugin"
```

请通过 Hermes 正常 plugin-management 流程启用，或在 Hermes config 加入：

```yaml
plugins:
  enabled:
    - hermes-continuation
  disabled: []
```

安装或修改 config 后，请重启 Hermes CLI/gateway。运行中的 Hermes process 会 cache plugin discovery。

加载后，wrapper 会注册三个 tools：

- `hermes_handoff_prepare`：创建 read-only prepare preview；不会写 packet files，且没有必填字段。
- `hermes_handoff_create`：创建 Markdown + JSON handoff packet。
- `hermes_handoff_resume`：从 handoff JSON 取出 resume prompt。

plugin create schema 必填：

- `goal`
- `next_task`

目前没有 watch 的 plugin tool 或 gateway/slash command。一次性 advisory auto-trigger MVP 请使用 CLI `hermes-handoff watch`。

## 斜线指令

<!-- Compatibility alias: ## `/handoff` slash command 用法 -->

在支持 plugin slash commands 的 Hermes build 上，wrapper 会注册 `/handoff`，且不修改 Hermes core。

Help：

```text
/handoff help
```

使用 JSON 生成 read-only prepare preview：

```text
/handoff prepare {"repo_path":".","goal":"完成 dashboard QA","next_task":"执行 build 与 browser smoke","auto_task_state":true}
```

使用 shell-style key/value arguments 生成 prepare preview：

```text
/handoff prepare repo_path=. goal="完成 dashboard QA" next_task="执行 build 与 browser smoke" auto_task_state=true
```

`/handoff prepare ...` 只会在支持 plugin slash-command registration 的兼容 Hermes runtime 上出现。它调用 `hermes_handoff_prepare`，不会写 `.hermes/handoffs/` packet files；如果显示 safe create command，用户仍必须明确通过 `create` 执行才会写入。

使用 JSON 创建；这是最稳定、最推荐的格式：

```text
/handoff create {"repo_path":".","goal":"完成 dashboard QA","next_task":"执行 build 与 browser smoke","auto_task_state":true}
```

使用 shell-style key/value arguments 创建：

```text
/handoff create repo_path=. goal="完成 dashboard QA" next_task="执行 build 与 browser smoke" auto_task_state=true
```

省略 `create` 的 implicit create：

```text
/handoff {"repo_path":".","goal":"完成 dashboard QA","next_task":"执行 build 与 browser smoke"}
```

Resume：

```text
/handoff resume .hermes/handoffs/<timestamp>-handoff.json
```

Resume 并加上 Markdown wrapper：

```text
/handoff resume {"handoff_json":".hermes/handoffs/<timestamp>-handoff.json","markdown":true}
```

单独输入 `/handoff` 或 `/handoff help` 只会显示 help，不会创建信息不足的 packet。Plugin `auto_task_state` 是选择性功能，边界与 CLI `--auto-task-state` 相同。目前尚未实现 plugin/gateway `/handoff watch` subcommand。

## 输出与 artifacts 政策

Runtime handoff packets 默认写入：

```text
.hermes/handoffs/
```

不要 commit generated/runtime artifacts：

- `.hermes/handoffs/`
- `graphify-out/`
- `_knowledge_base/`
- `.pytest_cache/`
- `__pycache__/`
- `*.egg-info`

如果要执行 smoke commands，建议使用 temporary repository，或用 `--output-dir` 指到 working tree 外部。

## Runtime smoke 兼容性

`tests/test_hermes_runtime_plugin_smoke.py` 刻意设计为可移植：

- 当 Hermes runtime 前置条件缺失时，会 clean skip；
- 默认 source fallback 路径为 `/home/zycas/.hermes/hermes-agent`；
- 默认 interpreter fallback 路径为 `/home/zycas/.hermes/hermes-agent/venv/bin/python3`。

可通过环境变量覆盖：

```bash
HERMES_AGENT_SOURCE="/path/to/hermes-agent" \
HERMES_AGENT_PYTHON="/path/to/hermes-agent/venv/bin/python3" \
python -m pytest -q tests/test_hermes_runtime_plugin_smoke.py
```

## 安全与遮蔽

<!-- Compatibility alias: ## Safety 与 redaction 边界 -->

Handoff 内容可能被贴到另一个 agent 或分享给队友，因此必须保持 secret-safe。

规则：

- 不要在 examples 或 handoff notes 放入真实 API keys、tokens、passwords、private keys、connection strings、chat IDs、message IDs 或客户 secrets。
- 使用明显 placeholder，例如 `[REDACTED]`、`sk-test-[REDACTED]`、`example-token-[REDACTED]`。
- CLI/plugin 会将常见 token/API-key/password-like patterns redacted 成 `[REDACTED]`。
- Private-key blocks 会 fail closed，避免写出 handoff。
- `doctor` 只提出建议，`prepare` 只生成预览；两者都是 read-only，绝不写入 `.hermes/handoffs/` packet files。
- `watch` 是一次性的 read-only CLI advisory；绝不写入 `.hermes/handoffs/`、不会 hidden create，也不会默认以 daemon 运行。
- `prepare` 可能显示 safe create command，但用户必须明确执行 `create`，才会写入 packet。
- Safety blockers 会返回 `block`，隐藏 safe create command，且不打印 secret values。
- 此工具不会自动解析完整 Hermes transcripts。
- Auto task-state collection 必须明确 opt in，且只限保守的 repo-local Markdown。
- 对外发送 handoff 前，请人工审查生成的 Markdown/JSON。

## 验证命令

发布 code 或 docs 前，建议执行以下检查。

完整测试：

```bash
python -m pytest -q
```

Hermes runtime/plugin smoke；仅在本机有兼容 Hermes runtime 时适用：

```bash
python -m pytest -q tests/test_hermes_runtime_plugin_smoke.py
```

CLI help smoke：

```bash
python -m hermes_continuation.cli --help
python -m hermes_continuation.cli doctor --help
python -m hermes_continuation.cli prepare --help
python -m hermes_continuation.cli watch --help
python -m hermes_continuation.cli create --help
python -m hermes_continuation.cli resume --help
```

在 temporary repo 执行 create/resume smoke：

```bash
tmpdir="$(mktemp -d)"
git -C "$tmpdir" init
python -m hermes_continuation.cli create \
  --repo "$tmpdir" \
  --goal "Smoke test" \
  --next "Inspect generated handoff"
json_file="$(find "$tmpdir/.hermes/handoffs" -name '*-handoff.json' | sort | tail -n 1)"
python -m hermes_continuation.cli resume "$json_file" >/dev/null
```

Secret scan concept：

```bash
python - <<'PY'
from pathlib import Path
patterns = ['BEGIN PRIVATE KEY', 'api_key=', 'password=', 'bearer ']
for path in [*Path('.').glob('*.md'), *Path('docs').glob('*.md')]:
    text = path.read_text(encoding='utf-8', errors='ignore').lower()
    hits = [p for p in patterns if p.lower() in text]
    if hits:
        print(f'{path}: review possible secret-like text {hits}')
PY
```

Whitespace diff check：

```bash
git diff --check
```

Graphify hook；如果 workspace 有提供：

```bash
command -v graphify >/dev/null && graphify . || true
```

如果生成 graph/report output，除非 maintainer 明确要求，否则不要 stage `graphify-out/`。

## 故障排查

<!-- Compatibility alias: ## Troubleshooting -->

### Plugin 要重启或 reset 后才出现

Hermes 会在运行中的 process cache plugin discovery。安装、启用、停用或修改 plugin 后，请重启 Hermes CLI/gateway。测试中如果 runtime 支持，可使用 forced plugin discovery。

### Entry point 看不到

请用 Hermes interpreter 安装，而不是只用 shell 默认 Python：

```bash
/path/to/hermes/python -m pip install -e /path/to/hermes-continuation
```

接着验证：

```bash
/path/to/hermes/python - <<'PY'
from importlib.metadata import entry_points
print([ep.name for ep in entry_points(group='hermes_agent.plugins')])
PY
```

应该能看到 `hermes-continuation`。

### Tools 存在但 `/handoff` 不见

你的 Hermes build 可能尚未提供 plugin slash-command registration。这在较旧版本是预期情况。Wrapper 仍会注册 `hermes_handoff_create` 与 `hermes_handoff_resume` tools。

### `/handoff watch` 不见

这是预期情况。Watch 目前只实现为一次性 CLI command `hermes-handoff watch`；尚未提供 plugin/gateway `/handoff watch` command。

### `git status` 出现 handoff files 或 generated artifacts

它们是 runtime artifacts。Commit 前请移除或忽略：

```bash
git status --short
```

不要 stage `.hermes/handoffs/`、`graphify-out/`、`_knowledge_base/`、caches 或 egg-info directories。

### 找不到 `hermes-handoff`

可以使用 module form：

```bash
python -m hermes_continuation.cli --help
```

或启用安装此 package 的 environment，并确认该 environment 的 scripts directory 在 `PATH` 中。

### 缺少 Hermes runtime

CLI 不需要 Hermes runtime imports。Plugin runtime smoke tests 可能因本机没有 Hermes 而 skip 或 fail。请在真实 Hermes environment 安装后，再执行 runtime smoke。

### `create` 因 private key 文本失败

这是刻意的 fail-closed 行为。请从 inputs/docs 移除 private-key block，并以 `[REDACTED]` 替代敏感内容后再创建 handoff。

## Developer contribution checklist

开 PR 或请他人 commit 前：

- 保持 scope 清楚。Sidecar/plugin-wrapper 工作不要修改 Hermes core。
- 不要 commit runtime/generated artifacts：`.hermes/handoffs/`、`graphify-out/`、`_knowledge_base/`、caches、`*.egg-info`。
- Examples 必须 secret-safe，只使用明显假数据或 placeholder。
- 维持当前产品事实：MVP 只 recommend/preview/create/resume handoff packets，并提供一次性 CLI watch advisory；不自动重启 session、不解析完整 transcripts、不运行 background watch daemon，也不 hidden writes。
- 维持 `doctor` 与 `prepare` read-only；它们不得写入 `.hermes/handoffs/` packet files。
- 维持 `watch` read-only/advisory 且 CLI-only；除非另有批准的 plugin/gateway watch task。
- CLI `create` 必须维持 `--goal` 与 `--next` 必填。
- Plugin `create` 必须维持 `goal` 与 `next_task` 必填。
- Auto task-state collection 必须维持 opt-in。
- 执行相关 tests，并记录任何 skipped checks。
- 交付前执行 `git diff --check`。
- Review `git diff`，确保 commit 只包含预期文件。

Scoped commit guidance：

```bash
git status --short
git diff -- README.md docs/USAGE.md docs/USAGE.zh-TW.md docs/USAGE.zh-CN.md
git diff --check
```

准备好时只 stage 目标文件。不要 stage unrelated progress files 或 generated directories。
