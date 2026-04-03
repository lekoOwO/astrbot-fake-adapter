# astrbot-fake-adapter

AstrBot 虛擬平台適配器 / A fake platform adapter plugin for AstrBot plugin development & testing

## 簡介

FakeAdapter 是一個 AstrBot 平台適配器插件，專門用於支援其他插件的開發與測試。它能產生虛擬的聊天消息，讓插件開發者在不使用真實平台（如 QQ、Telegram 等）的情況下進行本地測試。

## 功能

- 📦 **標準 Platform Adapter** — 與其他適配器一樣可在 AstrBot WebUI 中啟用、命名與配置
- 🏘️ **多 UMO 支援** — 可設定多個虛擬聊天群組（UMO），每個 UMO 擁有獨立的虛擬用戶與發言頻率
- 🤖 **AI 生成消息** — 虛擬用戶透過配置的 LLM 模型自動產生自然的聊天內容
- 🐛 **Debug 前綴** — 可為每個 UMO 啟用 `[來自 {umo_id}] ` 前綴，方便識別消息來源
- 🔧 **高度可配置** — 支援自訂 Prompt 模板（String Template 格式）、發言頻率、虛擬用戶資訊等

## 配置說明

在 AstrBot WebUI 的平台配置頁中，可以看到 `fake_adapter`，其預設配置如下：

```yaml
type: fake_adapter
enable: false
id: fake_adapter
bot_name: FakeBot           # 虛擬機器人名稱

umos:                        # 虛擬聊天群組列表
  - id: fake_group_1         # UMO ID（必填）
    users:                   # 虛擬用戶 ID 列表
      - user_1
      - user_2
    frequency: 10            # 發言頻率（條/分鐘，可選，預設 10）
    debug_prefix: true       # 是否添加 [來自 {umo_id}] 前綴（可選，預設 true）

model: ""                    # 從 WebUI 下拉選擇 Provider（留空使用預設 Provider）
prompt_template: "..."       # 消息生成 Prompt 模板（支援 $user_count 佔位符）
```

### Prompt 模板變數

| 變數 | 說明 |
|------|------|
| `$user_count` | 當前 UMO 中的虛擬用戶數量 |

## 安裝

直接在 AstrBot 插件市場中搜索 `astrbot-fake-adapter` 安裝，或手動將本倉庫放入 AstrBot 插件目錄。

## 相關連結

- [AstrBot Repo](https://github.com/AstrBotDevs/AstrBot)
- [AstrBot 平台適配器開發文檔](https://github.com/AstrBotDevs/AstrBot/blob/master/docs/zh/dev/plugin-platform-adapter.md)
