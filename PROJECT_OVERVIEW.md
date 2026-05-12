# Hermes Continuation — 專案總覽

> **版本：** v0.3.0 | **日期：** 2026-05-12 | **作者：** Arthur Liao

---

## 一句話講這是什麼

**當你跟 Hermes Agent 進行長時間開發任務時，幫你做一份「交接包」讓下一個對話可以無縫接手繼續工作。從 v0.3.0 開始，它還能自動偵測開發時長、工具呼叫數、檔案變更量，在不吵到你的前提下主動提醒「該交接了」。**

---

## 為什麼需要它？

長時間的 AI 開發對話有幾個痛點：

1. **上下文爆炸** — 對話太長，AI 開始失憶或變慢
2. **進度丟失** — 你做了 10 個步驟，新對話要從頭問起
3. **不確定做到哪** — 哪些測過了？哪些還沒？改了什麼檔案？
4. **安全風險** — 手動整理交接筆記時可能不小心貼到密鑰或 token
5. **忘了交接** — 連續開發 45 分鐘、call 了 80 次工具、改了 12 個檔案，但你完全忘了要做交接

這個專案解決的就是：**在你想要換對話的時候，自動產生一份結構化的交接資料，甚至在你忘記的時候自己提醒你。**

---

## 使用方式

### 1. CLI（命令列）

直接在你的終端機使用，最簡單：

```bash
pip install -e .
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

### 2. 自動觸發（v0.3.0 新增）🆕

不用手動下指令，Hermes 會在「該交接了」的時候自動提醒你：

```
⚠️ 有一個開發中的專案建議交接
已開發約 45 分鐘，使用 80+ 次工具，12 個檔案有變更
→ 回對話中輸入 /handoff prepare 來預覽交接內容
```

**三種觸發方式：**

| 方式 | 說明 | 適合場景 |
|------|------|----------|
| **Gateway Wrapper** | Hermes 每次回覆完自動檢查，滿足條件就推送通知 | 日常對話中 |
| **Cron 定時掃描** | 每 30 分鐘掃描一次所有監控中的 repo | 你不在線上的時候 |
| **手動 `/handoff watch`** | 在對話中直接下指令 | 任何時候 |

**所有自動觸發都是 read-only**：不寫檔案、不讀對話內容、不洩漏 repo 名稱、可隨時關閉。

### 3. Hermes 插件（推薦）

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

### 4. 交接包長什麼樣子？

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

### 已完成（v0.3.0）

| 功能 | 狀態 |
|------|:---:|
| CLI：create / resume / doctor / prepare / watch | ✅ |
| Context Monitor：自動收集 git 狀態 + session metrics | ✅ 🆕 |
| Gateway 自動觸發：通知閘控 + cooldown + config 開關 | ✅ 🆕 |
| Cron 定時 watch：定期掃描 + 去重追蹤 | ✅ 🆕 |
| Watch 日誌記錄：JSONL log（零 token 成本） | ✅ 🆕 |
| 插件：5 個 tools + 5 個 slash commands | ✅ |
| 自動任務狀態收集（`--auto-task-state`） | ✅ |
| 安全：私鑰阻擋 + API key 遮蔽 + 紅線掃描 | ✅ |
| CI：pytest + compileall + secret scan + whitespace（3.11/3.12/3.13）| ✅ |
| 多語言文件（繁中 / 簡中 / English） | ✅ |
| CHANGELOG.md | ✅ |

### 測試覆蓋

- **124 tests** 全數通過 🆕（v0.2.0: 89 tests → v0.3.0: +35 tests）
- Python 3.11 + 3.12 + 3.13 🆕
- GitHub Actions 自動化 gate

### v0.3.0 架構總覽

```
觸發來源                  處理層                 通知目標
┌──────────┐          ┌──────────┐          ┌──────────┐
│ Gateway  │ ──┬───→  │          │          │ Feishu   │
│ Wrapper  │   │      │  Watch   │ ──────→  │ 報告群    │
└──────────┘   │      │  Engine  │          └──────────┘
               │      │          │
┌──────────┐   │      │ (複用     │          ┌──────────┐
│ Cron     │ ──┤      │ v0.2.0   │          │ Gateway  │
│ Jobs     │   │      │ doctor   │ ──────→  │ Session  │
└──────────┘   │      │ prepare  │          └──────────┘
               │      │ watch)   │
┌──────────┐   │      └──────────┘
│ Context  │ ──┘      ┌──────────┐
│ Monitor  │          │  Logger  │ → 本地 JSONL
└──────────┘          └──────────┘
```

---

## 未來方向

### 🔜 短期（v0.3.x）

| 優先級 | 項目 | 說明 |
|:---:|------|------|
| P1 | **兩週 dogfood + 閾值調校** | 收集 ≥50 筆日誌，根據真實使用數據調整觸發門檻 |
| P2 | **輸出可讀性調校** | 目前輸出偏技術化，非程式背景的人可能覺得不好讀 |

### 🟡 中期（v0.4+）

| 優先級 | 項目 | 說明 |
|:---:|------|------|
| P1 | **Daemon 背景監控** | 常駐進程，持續監控開發狀態（安全邊界已定義） |
| P2 | **跨 Agent 交接** | 讓其他 Agent 也能讀取交接包繼續工作 |
| P3 | **雲端同步** | 交接包上傳到 Supabase / 雲端，跨機器共享 |

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
| 通知安全 | 自動通知不含 repo 名稱、路徑、檔案內容 🆕 |
| 一鍵關閉 | `auto_watch.enabled: false` → 全部自動觸發即停 🆕 |

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
