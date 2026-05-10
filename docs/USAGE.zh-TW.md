# Hermes Continuation 使用說明（繁體中文）

`hermes-continuation` 用來替長時間執行的 Hermes agent 工作建立結構化續工交接。它目前是一個 sidecar CLI，加上一層很薄的 Hermes plugin wrapper。真正的產品契約是 handoff packet：給人看的本機 Markdown，以及給 agent/tool 穩定讀取的本機 JSON。

目前 MVP 刻意保持保守：它**不會**修改 Hermes core、不會自動重啟 session、不會解析完整 Hermes transcript、不會啟動新 agent、不會雲端同步，也不提供 dashboard。

## 什麼時候使用

適合在以下情境使用 `hermes-continuation`：

- 任務長到不適合塞在同一個 session；
- context 變大、被壓縮，或即將失去細節；
- 需要另一個 Hermes session 或隊友安全接手；
- 希望下一個 agent 明確看到 repo 狀態、驗證結果、blocker 與邊界；
- 需要一段可以直接貼到新 Hermes session 的 resume prompt，而且背後有結構化資料支撐。

不要把它當成 secret vault、完整 transcript archive、雲端同步工具，或自動 session manager。

## Handoff 內容

每份 handoff packet 會記錄：

- 目前目標；
- repository path、branch、HEAD、`git status --short`、changed files；
- 已完成工作與進行中工作；
- 已知 blocker；
- 不可碰觸的邊界；
- 已驗證、失敗、尚未執行的 gates；
- safety/redaction 狀態；
- 給新 Hermes session 的 resume prompt。

預設輸出位置：

```text
.hermes/handoffs/<timestamp>-handoff.md
.hermes/handoffs/<timestamp>-handoff.json
```

請把 `.hermes/handoffs/` 視為 runtime output。除非你已經明確審查並清理內容，否則不要 commit。

## 安裝

<!-- Compatibility alias: ## 從 repo 安裝 -->

進入此 repo，將套件以 editable mode 安裝到目前 Python environment：

```bash
cd /path/to/hermes-continuation
python -m pip install -e .
```

確認 CLI 可用：

```bash
hermes-handoff --help
python -m hermes_continuation.cli --help
```

如果找不到 `hermes-handoff`，可以先用 module form，或確認 shell 使用的是安裝此套件的 Python environment。

## CLI 使用方式

<!-- Compatibility alias: ## 使用 CLI 建立 handoff -->

`hermes-handoff create` 必須提供 `--goal` 與 `--next`；這兩個欄位是必要資訊。

最小範例：

```bash
hermes-handoff create \
  --repo . \
  --goal "完成 dashboard QA" \
  --next "執行 build 與 browser smoke test"
```

較完整範例：

```bash
hermes-handoff create \
  --repo . \
  --goal "完成 dashboard QA" \
  --completed "更新 health-card 文案" \
  --completed "補上 health status mapping 的 unit coverage" \
  --in-progress "準備 release verification" \
  --verified "python -m pytest -q passed" \
  --failing "browser smoke test 仍卡在 loading state" \
  --not-run "production deploy dry run" \
  --blocker "等待 product sign-off 最終文案" \
  --do-not-touch "billing migrations" \
  --next "執行 build 與 browser smoke test"
```

等價的 module form：

```bash
python -m hermes_continuation.cli create --repo . --goal "Smoke test" --next "Inspect output"
```

常用選項：

- `--repo`：要檢查的 repository path，預設是目前目錄。
- `--output-dir`：自訂輸出目錄，預設是 `<repo>/.hermes/handoffs`。
- `--completed`、`--verified`、`--failing`、`--not-run`、`--blocker`、`--do-not-touch`：可重複使用的 list 欄位。
- `--in-progress`：目前進行中的工作描述。

## 選擇性自動收集 task state

自動收集 task state 預設是**關閉**的。必須明確加上：

```bash
hermes-handoff create \
  --repo . \
  --goal "完成 dashboard QA" \
  --auto-task-state \
  --completed "要保留的手動補充" \
  --next "執行 build 與 browser smoke test"
```

`--auto-task-state` 的邊界：

- 只掃描保守的 repo-local Markdown：
  - `PROGRESS.md`
  - `README.md`
  - 直層 `docs/*.md`
- 只擷取 Completed Work、In Progress、Blockers、Do Not Touch、Next Step 等 task-state heading 下方的 bullets；
- 跳過 generated/runtime paths，例如 `.git`、`.hermes`、`graphify-out`、`_knowledge_base`、`.pytest_cache`、`__pycache__`、`*.egg-info`；
- 限制收集的項目數與字數；
- 若掃描到 private-key block，會 fail closed；
- 不會解析完整 Hermes transcript；
- 不會從 chat history 推測隱藏狀態；
- manual list values 會附加在 auto-collected values 後面並去重；
- manual `--next` 永遠優先。

重要資訊請仍然使用手動 flags。自動收集只是方便預填，不是唯一事實來源。

## 從 handoff 繼續

<!-- Compatibility alias: ## 從 handoff JSON 恢復續工 prompt -->

使用產生的 JSON 印出給新 session 的 prompt：

```bash
hermes-handoff resume .hermes/handoffs/<timestamp>-handoff.json
```

預設情況下，`resume` 只輸出 prompt 文字，方便直接貼到新的 Hermes session 或 pipe 給其他工具。若想輸出含標題的 Markdown：

```bash
hermes-handoff resume --markdown .hermes/handoffs/<timestamp>-handoff.json
```

`resume` 會先驗證 JSON packet。它不會建立新的 handoff、不會修改 handoff file，也不會推測缺失的任務狀態。

## Hermes 外掛包裝器

<!-- Compatibility alias: ## Hermes plugin 安裝與啟用 -->

若要在 Hermes runtime/plugin 中使用，請把 `hermes-continuation` 安裝到**執行 Hermes 的同一個 Python interpreter**。實際路徑取決於你的 Hermes 安裝方式。Plugin 需要選擇啟用，不會預設載入。

範例模式：

```bash
cd /path/to/hermes-continuation
/path/to/hermes/python -m pip install -e .
```

此套件提供 entry point：

```toml
[project.entry-points."hermes_agent.plugins"]
hermes-continuation = "hermes_continuation.plugin"
```

請透過 Hermes 正常 plugin-management 流程啟用，或在 Hermes config 加入：

```yaml
plugins:
  enabled:
    - hermes-continuation
  disabled: []
```

安裝或修改 config 後，請重啟 Hermes CLI/gateway。執行中的 Hermes process 會 cache plugin discovery。

載入後，wrapper 會註冊兩個 tools：

- `hermes_handoff_create`：建立 Markdown + JSON handoff packet。
- `hermes_handoff_resume`：從 handoff JSON 取出 resume prompt。

plugin create schema 必填：

- `goal`
- `next_task`

## 斜線指令

<!-- Compatibility alias: ## `/handoff` slash command 用法 -->

在支援 plugin slash commands 的 Hermes build 上，wrapper 會註冊 `/handoff`，且不修改 Hermes core。

Help：

```text
/handoff help
```

使用 JSON 建立；這是最穩定、最建議的格式：

```text
/handoff create {"repo_path":".","goal":"完成 dashboard QA","next_task":"執行 build 與 browser smoke","auto_task_state":true}
```

使用 shell-style key/value arguments 建立：

```text
/handoff create repo_path=. goal="完成 dashboard QA" next_task="執行 build 與 browser smoke" auto_task_state=true
```

省略 `create` 的 implicit create：

```text
/handoff {"repo_path":".","goal":"完成 dashboard QA","next_task":"執行 build 與 browser smoke"}
```

Resume：

```text
/handoff resume .hermes/handoffs/<timestamp>-handoff.json
```

Resume 並加上 Markdown wrapper：

```text
/handoff resume {"handoff_json":".hermes/handoffs/<timestamp>-handoff.json","markdown":true}
```

單獨輸入 `/handoff` 或 `/handoff help` 只會顯示 help，不會建立資訊不足的 packet。Plugin `auto_task_state` 是選擇性功能，邊界與 CLI `--auto-task-state` 相同。

## 輸出與 artifacts 政策

Runtime handoff packets 預設寫入：

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

若要執行 smoke commands，建議使用 temporary repository，或用 `--output-dir` 指到 working tree 外部。

## Runtime smoke 相容性

`tests/test_hermes_runtime_plugin_smoke.py` 刻意設計為可攜：

- 若 Hermes runtime 前置條件不存在，會 clean skip；
- 預設 source fallback 路徑是 `/home/zycas/.hermes/hermes-agent`；
- 預設 interpreter fallback 路徑是 `/home/zycas/.hermes/hermes-agent/venv/bin/python3`。

你可以用環境變數覆寫：

```bash
HERMES_AGENT_SOURCE="/path/to/hermes-agent" \
HERMES_AGENT_PYTHON="/path/to/hermes-agent/venv/bin/python3" \
python -m pytest -q tests/test_hermes_runtime_plugin_smoke.py
```

## 安全與遮蔽

<!-- Compatibility alias: ## Safety 與 redaction 邊界 -->

Handoff 內容可能被貼到另一個 agent 或分享給隊友，因此必須保持 secret-safe。

規則：

- 不要在 examples 或 handoff notes 放入真實 API keys、tokens、passwords、private keys、connection strings、chat IDs、message IDs 或客戶 secrets。
- 使用明顯 placeholder，例如 `[REDACTED]`、`sk-test-[REDACTED]`、`example-token-[REDACTED]`。
- CLI/plugin 會將常見 token/API-key/password-like patterns redacted 成 `[REDACTED]`。
- Private-key blocks 會 fail closed，避免寫出 handoff。
- 此工具不會自動解析完整 Hermes transcripts。
- Auto task-state collection 必須明確 opt in，且只限保守的 repo-local Markdown。
- 對外傳送 handoff 前，請人工審查產生的 Markdown/JSON。

## 驗證指令

發布 code 或 docs 前，建議執行以下檢查。

完整測試：

```bash
python -m pytest -q
```

Hermes runtime/plugin smoke；僅在本機有相容 Hermes runtime 時適用：

```bash
python -m pytest -q tests/test_hermes_runtime_plugin_smoke.py
```

CLI help smoke：

```bash
python -m hermes_continuation.cli --help
python -m hermes_continuation.cli create --help
python -m hermes_continuation.cli resume --help
```

在 temporary repo 執行 create/resume smoke：

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

Graphify hook；若 workspace 有提供：

```bash
command -v graphify >/dev/null && graphify . || true
```

如果產生 graph/report output，除非 maintainer 明確要求，否則不要 stage `graphify-out/`。

## 疑難排解

<!-- Compatibility alias: ## Troubleshooting -->

### Plugin 要重啟或 reset 後才出現

Hermes 會在執行中的 process cache plugin discovery。安裝、啟用、停用或修改 plugin 後，請重啟 Hermes CLI/gateway。測試中若 runtime 支援，可使用 forced plugin discovery。

### Entry point 看不到

請用 Hermes interpreter 安裝，而不是只用 shell 預設 Python：

```bash
/path/to/hermes/python -m pip install -e /path/to/hermes-continuation
```

接著驗證：

```bash
/path/to/hermes/python - <<'PY'
from importlib.metadata import entry_points
print([ep.name for ep in entry_points(group='hermes_agent.plugins')])
PY
```

應該能看到 `hermes-continuation`。

### Tools 存在但 `/handoff` 不見

你的 Hermes build 可能尚未提供 plugin slash-command registration。這在較舊版本是預期情況。Wrapper 仍會註冊 `hermes_handoff_create` 與 `hermes_handoff_resume` tools。

### `git status` 出現 handoff files 或 generated artifacts

它們是 runtime artifacts。Commit 前請移除或忽略：

```bash
git status --short
```

不要 stage `.hermes/handoffs/`、`graphify-out/`、`_knowledge_base/`、caches 或 egg-info directories。

### 找不到 `hermes-handoff`

可以使用 module form：

```bash
python -m hermes_continuation.cli --help
```

或啟用安裝此 package 的 environment，並確認該 environment 的 scripts directory 在 `PATH` 中。

### 缺少 Hermes runtime

CLI 不需要 Hermes runtime imports。Plugin runtime smoke tests 可能因本機沒有 Hermes 而 skip 或 fail。請在真實 Hermes environment 安裝後，再執行 runtime smoke。

### `create` 因 private key 文字失敗

這是刻意的 fail-closed 行為。請從 inputs/docs 移除 private-key block，並以 `[REDACTED]` 取代敏感內容後再建立 handoff。

## Developer contribution checklist

開 PR 或請他人 commit 前：

- 保持 scope 清楚。Sidecar/plugin-wrapper 工作不要修改 Hermes core。
- 不要 commit runtime/generated artifacts：`.hermes/handoffs/`、`graphify-out/`、`_knowledge_base/`、caches、`*.egg-info`。
- Examples 必須 secret-safe，只使用明顯假資料或 placeholder。
- 維持目前產品事實：MVP 只 create/resume handoff packets；不自動重啟 session，也不解析完整 transcripts。
- CLI `create` 必須維持 `--goal` 與 `--next` 必填。
- Plugin `create` 必須維持 `goal` 與 `next_task` 必填。
- Auto task-state collection 必須維持 opt-in。
- 執行相關 tests，並記錄任何 skipped checks。
- 交付前執行 `git diff --check`。
- Review `git diff`，確保 commit 只包含預期檔案。

Scoped commit guidance：

```bash
git status --short
git diff -- README.md docs/USAGE.md docs/USAGE.zh-TW.md docs/USAGE.zh-CN.md
git diff --check
```

準備好時只 stage 目標文件。不要 stage unrelated progress files 或 generated directories。
