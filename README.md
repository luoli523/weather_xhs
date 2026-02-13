# weather_xhs

天气穿搭指南生成工具：获取天气、生成穿搭建议、输出 Markdown，并可选调用 NotebookLM 生成信息图。

## 效果展示

以下是 2026-02-13 自动生成的穿搭信息图示例：

<p align="center">
  <img src="examples/北京_2026-02-13.png" width="30%" />
  <img src="examples/上海_2026-02-13.png" width="30%" />
  <img src="examples/深圳_2026-02-13.png" width="30%" />
</p>

<p align="center">
  <sub>北京 5~13℃ 微凉 &nbsp;|&nbsp; 上海 12~18℃ 舒适 &nbsp;|&nbsp; 深圳 18~23℃ 舒适</sub>
</p>

## Python 与兼容性

- 核心流程（天气 + Markdown）兼容 Python 3.9+
- NotebookLM 流程依赖 `notebooklm-py`（按其发布版本要求安装，建议使用 Python 3.10+）

## 使用 venv 运行

1. 创建并激活虚拟环境

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
```

2. 安装依赖

```bash
pip install -r requirements.txt
```

3. 配置环境变量

```bash
cp .env.example .env
```

编辑 `.env`，填入 `OPENWEATHERMAP_API_KEY`。

（可选）配置 Telegram 推送：填入 `TELEGRAM_BOT_TOKEN` 和 `TELEGRAM_CHAT_ID`，生成图片后会自动发送到你的 Telegram。获取方式：

1. 在 Telegram 中与 [@BotFather](https://t.me/BotFather) 对话，发送 `/newbot` 创建 Bot，获取 Token
2. 向你的 Bot 发送一条消息，然后访问 `https://api.telegram.org/bot<TOKEN>/getUpdates` 获取 `chat_id`

4. 运行

- 使用真实天气（仅输出 Markdown）：

```bash
python main.py --no-nlm
```

- 使用 mock 数据（无需 API Key）：

```bash
python main.py --mock --no-nlm
```

- 完整流程（含 NotebookLM 生成图片）：

```bash
python main.py
```

## 输出

- Markdown：`output/clothing_guide_YYYY-MM-DD.md`
- 图片（启用 NotebookLM 时）：`output/*.png`

## GitHub Actions 自动运行

项目已配置 GitHub Actions，每天北京时间 8:00 自动运行全流程并推送到 Telegram。

### 配置 Secrets

在仓库 Settings → Secrets and variables → Actions 中添加以下 Secrets：

| Secret 名称 | 说明 |
|---|---|
| `OPENWEATHERMAP_API_KEY` | OpenWeatherMap API Key |
| `TELEGRAM_BOT_TOKEN` | Telegram Bot Token |
| `TELEGRAM_CHAT_ID` | 接收消息的 chat_id |
| `NOTEBOOKLM_STORAGE_STATE` | NotebookLM 认证文件（base64 编码） |

### 导出 NotebookLM 认证

本地登录后，将 `storage_state.json` 编码为 base64 并存入 Secret：

```bash
# 本地先登录（仅需一次）
notebooklm login

# 生成 base64 字符串，复制粘贴到 GitHub Secret
base64 < ~/.notebooklm/storage_state.json
```

> 注意：NotebookLM 的 cookie 会过期，过期后需重新 `notebooklm login` 并更新 Secret。

### 手动触发

在仓库 Actions 页面选择 "每日穿搭指南生成" → Run workflow 即可手动运行。
