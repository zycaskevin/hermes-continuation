# Hermes Continuation — 專案總覽

> **版本：** v0.2.0 | **日期：** 2026-05-12 | **作者：** Arthur Liao

---

## 一句話講這是什麼

**當你跟 Hermes Agent 進行長時間開發任務時，幫你做一份「交接包」讓下一個對話可以無縫接手繼續工作。**

---

## 為什麼需要它？

長時間的 AI 開發對話有幾個痛點：

1. **上下文爆炸** — 對話太長，AI 開始失憶或變慢
2. **進度丟失** — 你做了 10 個步驟，新對話要從頭問起
3. **不確定做到哪** — 哪些測過了？哪些還沒？改了什麼檔案？
4. **安全風險** — 手動整理交接筆記時可能不小心貼到密鑰或 token

這個專案解決的就是：**在你想要換對話的時候，自動產生一份結構化的交接資料。**

---

## 使用方式

### 1. CLI（命令列）

直接在你的終端機使用，最簡單：

```bash
pip install -e .
```

#### 基本用法

```bash
# 寫一份交接包
hermes-handoff create \
  --repo . \
  --goal "完成 Dashboard QA" \
  --next "執行 build 和 browser smoke test"

# 新對話接手
hermes-handoff resume .hermes/handoffs/<timestamp>-handoff.json
```

#### 五個命令

| 命令 | 功能 | 會寫檔案嗎？ |
|------|------|:---:|
| `doctor` | 分析現在適不適合做 handoff | ❌ 純建議 |
| `prepare` | 預覽即將產生的交接內容 | ❌ 純預覽 |
| `watch` | 一次性掃描：工具呼叫數、時間長度、檔案變更 | ❌ 純觀察 |
| `create` | 真正寫出交接包 | ✅ 唯一會寫的 |
| `resume` | 讀取之前寫好的交接包給新對話用 | ❌ 純讀取 |

**安全設計原則：只有 `create` 會寫檔案，其他四個都是 read-only。**

---

### 2. Hermes 插件（推薦）

在你的 Hermes Agent 裡面直接使用，不需要跳出到終端機：

**設定方式：**

在 `~/.hermes/config.yaml` 啟用插件：

```yaml
plugins:
  enabled:
    - hermes-continuation
```

重啟 Hermes 後，在對話中直接下指令：

```
/handoff doctor repo_path=. goal="完成 QA" next_task="跑 browser smoke"
/handoff prepare repo_path=. goal="完成 QA" next_task="跑 browser smoke"
/handoff watch repo_path=. goal="完成 QA" next_task="跑 browser smoke" tool_calls=10 elapsed_minutes=45
/handoff create repo_path=. goal="完成 QA" next_task="跑 browser smoke"
/handoff resume .hermes/handoffs/<timestamp>-handoff.json
/handoff help
```

插件同時註冊了 **5 個工具**（Hermes 可以自動調用）：

| 工具名稱 | 作用 |
|----------|------|
| `hermes_handoff_create` | 寫出交接包 |
| `hermes_handoff_resume` | 讀取交接包 |
| `hermes_handoff_prepare` | 預覽交接內容 |
| `hermes_handoff_watch` | 一次性觀察掃描 |
| `hermes_handoff_doctor` | 分析並建議是否該交接 |

---

### 3. 交接包長什麼樣子？

每份交接包包含兩個檔案：

```
.hermes/handoffs/
├── 20260512-143022-handoff.md    ← 人類可讀的 Markdown 版本
└── 20260512-143022-handoff.json  ← 機器可讀的 JSON 版本
```

內容包含：

- 🎯 **當前目標** — 你在做什麼
- 📁 **Repo 狀態** — 路徑、分支、commit、改過的檔案
- ✅ **已完成工作** / 🔄 **進行中** / ⚠️ **障礙物** / 🚫 **不要碰的區域**
- 🧪 **驗證狀態** — 哪些測試過了、哪些沒過、哪些還沒跑
- 🔒 **安全狀態** — 是否偵測到敏感內容並已遮蔽
- 📋 **接手提示** — 一段可以直接貼給新對話的 prompt

---

## 目前狀態

### 已完成（v0.2.0）

| 功能 | 狀態 |
|------|:---:|
| CLI：create / resume / doctor / prepare / watch | ✅ |
| 插件：5 個 tools + 5 個 slash commands | ✅ |
| 自動任務狀態收集（`--auto-task-state`） | ✅ |
| 安全：私鑰阻擋 + API key 遮蔽 + 紅線掃描 | ✅ |
| CI：pytest + compileall + secret scan + whitespace | ✅ |
| 多語言文件（繁中 / 簡中 / English） | ✅ |
| CHANGELOG.md + git tag v0.2.0 | ✅ |

### 測試覆蓋

- **89 tests** 全數通過
- Python 3.11 + 3.12
- GitHub Actions 自動化 gate

---

## 未來方向

### 🔜 短期（v0.2.x）

| 優先級 | 項目 | 說明 |
|:---:|------|------|
| P1 | **實機 dogfood 優化** | 在 Arthur 日常工作中實際使用，觀察 Feishu/Telegram 訊息可讀性，調整輸出格式 |
| P2 | **README 更新** | 補上 plugin watch 的範例（目前 README 說 watch 是 CLI-only，但 v0.2.0 已有 plugin 版） |
| P3 | **輸出可讀性調校** | 目前輸出偏技術化，非程式背景的人可能覺得不好讀，需要簡化 |

### 🟡 中期（v0.3.0）

| 優先級 | 項目 | 說明 |
|:---:|------|------|
| P1 | **自動觸發策略** | 讓 Hermes 在特定條件下（工具呼叫 > 5、時間 > 30 分鐘、檔案大量變更）主動提醒「要交接了」 |
| P2 | **Gateway session 整合** | 讓 `/handoff watch` 可以在 Gateway 模式中被 Hermes 自動呼叫，不需要人工下指令 |
| P3 | **Cron 定時 watch** | 用 cronjob 定期掃描開發中的 repo，自動判斷是否需要交接 |

### 🔴 長期（v0.4+）

| 優先級 | 項目 | 說明 |
|:---:|------|------|
| P1 | **Daemon 背景監控** | 常駐進程，持續監控開發狀態，自動觸發交接建議（安全邊界已定義在 policy 文件中） |
| P2 | **跨 Agent 交接** | 不只在 Hermes 對話間傳遞，也能讓其他 Agent 讀取交接包繼續工作 |
| P3 | **雲端同步** | 交接包上傳到 Supabase / 雲端，跨機器共享 |
| P4 | **Dashboard 視覺化** | Web 介面查看所有進行中的任務交接狀態 |

### 明確不在範圍內（Non-goals）

這些是故意不做的，避免專案膨脹：

- ❌ 不修改 Hermes 核心程式碼（永遠做 sidecar/plugin）
- ❌ 不自動重啟對話或啟動新 Agent
- ❌ 不解析完整的 Hermes 對話記錄
- ❌ 不做跨平台的交接標準化
- ❌ 交接包不進版控（`.gitignore` 已排除 `.hermes/handoffs/`）

---

## 安全紅線

這個專案從 Day 1 就把安全擺第一：

| 機制 | 行為 |
|------|------|
| 私鑰檢測 | 檢測到 RSA/SSH/EC 私鑰 → 拒絕寫入 |
| API key 遮蔽 | token / password / api_key → 自動換成 `[REDACTED]` |
| 紅線掃描 | CI 每次 push 自動掃描，抓到就擋 |
| 分級控制 | `block` 等級下不顯示任何 create 指令 |
| 純讀取 | doctor / prepare / watch 永遠不寫檔案 |

---

## 安裝與貢獻

```bash
# 安裝
pip install -e .

# 跑測試
python -m pytest -q

# CI 掃描
git diff --check
```

Repo：https://github.com/zycaskevin/hermes-continuation

---

> *這個專案是 Arthur 用 AI 開發出來給自己用的工具，全部程式碼由 Claude Code / Hermes 子代理撰寫，Arthur 負責方向與審查。如果你也有類似的痛點，歡迎拿去用或改。*
