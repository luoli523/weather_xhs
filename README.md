# weather_xhs

每日天气穿搭指南 + 二十四节气信息图自动生成系统。

获取天气 → 生成穿搭建议 → NotebookLM 生成信息图 → 推送 Telegram → 发布小红书 / Instagram。节气日额外生成节气文化信息图。

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

## 功能概览

### 穿搭流程（每日运行）

1. 调用 OpenWeatherMap API 获取各城市实时天气 + 当日预报
2. 根据温度生成 7 档穿衣指数和穿搭建议（极热/炎热/温暖/舒适/微凉/寒冷/极寒）
3. 输出结构化 Markdown，上传到 NotebookLM 生成穿搭 infographic
4. 推送穿搭图到 Telegram（每城市一张，附天气穿搭 caption）
5. 发布穿搭多图笔记到小红书（含节日祝福、天气穿衣指数）
6. 发布穿搭相册到 Instagram（含 hashtags、节日祝福）

### 节气流程（节气日自动触发）

1. 使用 `sxtwl`（寿星天文历）检测当天是否为二十四节气
2. 从 `config/solar_terms.yaml` 加载节气含义、传统习俗、美食、养生提示
3. 生成节气 Markdown，上传到 NotebookLM 生成中国风节气 infographic
4. 推送节气图到 Telegram（附节气介绍文案）
5. 发布独立节气笔记到小红书（附习俗、美食、养生内容）
6. 发布节气帖子到 Instagram（附习俗、养生 hashtags）

## 项目结构

```
weather_xhs/
├── main.py                         # 主入口
├── config/
│   ├── config.yaml                 # 城市列表 + API 配置
│   ├── prompts.yaml                # NotebookLM prompt 模板（穿搭 + 节气）
│   ├── style_options.yaml          # 穿搭图风格变量（配色/人物/氛围）
│   ├── special_days.yaml           # 节日祝福配置（固定日期）
│   └── solar_terms.yaml            # 二十四节气信息（含义/习俗/美食/养生）
├── src/
│   ├── common/                     # 共享基础功能
│   │   ├── notebooklm.py           #   NotebookLM 基础（find notebook, upload source）
│   │   ├── telegram.py             #   Telegram 基础（get_config, send_photo）
│   │   ├── xhs.py                  #   小红书基础（get_config, publish_note）
│   │   └── instagram.py            #   Instagram 基础（get_config, publish_album）
│   ├── clothing/                   # 穿搭模块
│   │   ├── weather.py              #   OpenWeatherMap API 客户端
│   │   ├── mock_weather.py         #   模拟天气数据（测试用）
│   │   ├── index.py                #   穿衣指数生成
│   │   ├── content.py              #   Markdown 内容生成
│   │   ├── notebooklm.py           #   穿搭 NotebookLM pipeline
│   │   ├── telegram.py             #   穿搭 Telegram 推送
│   │   ├── xhs.py                  #   穿搭小红书发布（含节日祝福）
│   │   └── instagram.py            #   穿搭 Instagram 发布
│   └── solar_term/                 # 节气模块
│       ├── detector.py             #   节气检测（sxtwl）
│       ├── content.py              #   节气内容生成（MD/Prompt/XHS/Telegram）
│       └── notebooklm.py           #   节气 NotebookLM pipeline
├── scripts/
│   ├── xhs_login.py                # 小红书登录辅助脚本
│   └── ig_login.py                 # Instagram 登录辅助脚本
├── output/                         # 生成产物目录
└── .github/workflows/
    └── daily-run.yml               # 每日定时运行
```

## 输出产物

每次运行后 `output/` 目录内容（以 3 个城市 + 雨水节气日为例）：

| 文件 | 说明 |
|------|------|
| `clothing_guide_2026-02-18.md` | 穿搭 Markdown（NotebookLM source） |
| `北京_2026-02-18.png` | 北京穿搭 infographic |
| `上海_2026-02-18.png` | 上海穿搭 infographic |
| `深圳_2026-02-18.png` | 深圳穿搭 infographic |
| `solar_term_雨水_2026-02-18.md` | 节气 Markdown（仅节气日） |
| `雨水_2026-02-18.png` | 节气 infographic（仅节气日） |

推送结果：

| 渠道 | 内容 |
|------|------|
| **Telegram** | 3 张穿搭图（各附天气穿搭 caption）+ 1 张节气图（附节气介绍） |
| **小红书** | 1 条穿搭多图笔记 + 1 条节气笔记（独立发布） |
| **Instagram** | 1 条穿搭相册 + 1 条节气帖子（独立发布） |

> 非节气日只有穿搭内容，节气相关的文件和推送不会产生。

## 快速开始

### 1. 环境准备

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. 配置环境变量

```bash
cp .env.example .env
```

编辑 `.env`，填入 `OPENWEATHERMAP_API_KEY`。

### 3. 运行

```bash
# Mock 模式测试（无需 API Key，仅生成 Markdown）
python main.py --mock --no-nlm

# 完整流程（天气 + NotebookLM 生成图 + Telegram + 小红书）
python main.py

# 跳过 NotebookLM（仅生成 Markdown）
python main.py --no-nlm

# 跳过小红书发布
python main.py --no-xhs

# 跳过 Instagram 发布
python main.py --no-ig

# 仅发送当天已有图片到 Telegram
python main.py --send-telegram

# 仅发送当天已有图片到小红书
python main.py --send-xhs

# 仅发送当天已有图片到 Instagram
python main.py --send-ig
```

### 命令行参数

| 参数 | 说明 |
|------|------|
| `--mock` | 使用模拟天气数据，不调用 API |
| `--no-nlm` | 跳过 NotebookLM 生成流程 |
| `--no-xhs` | 跳过所有小红书发布（穿搭和节气） |
| `--no-ig` | 跳过所有 Instagram 发布（穿搭和节气） |
| `--gender female/male/neutral/random` | 穿搭图中人物性别（默认 female） |
| `--send-telegram` | 跳过生成，仅发送当天图片到 Telegram |
| `--send-xhs` | 跳过生成，仅发送当天图片到小红书 |
| `--send-ig` | 跳过生成，仅发送当天图片到 Instagram |

## 可选功能配置

### Telegram 推送

1. 在 Telegram 中与 [@BotFather](https://t.me/BotFather) 对话，发送 `/newbot` 创建 Bot，获取 Token
2. 向你的 Bot 发送一条消息，然后访问 `https://api.telegram.org/bot<TOKEN>/getUpdates` 获取 `chat_id`
3. 在 `.env` 中设置：

```
TELEGRAM_ENABLED=true
TELEGRAM_BOT_TOKEN=你的token
TELEGRAM_CHAT_ID=你的chat_id
```

### 小红书自动发布

1. 安装 Playwright 浏览器：

```bash
playwright install chromium
```

2. 运行登录脚本，在弹出的浏览器中登录小红书：

```bash
python scripts/xhs_login.py
```

3. 在 `.env` 中设置 `XHS_ENABLED=true`

> 小红书的 cookie 会过期，过期后重新运行登录脚本即可。

### Instagram 自动发布

1. 运行登录脚本（首次需要完成 Challenge 安全验证）：

```bash
python scripts/ig_login.py
```

脚本会提示输入账密（或自动读取 `.env`）。如果 Instagram 发送验证码到邮箱/手机，在终端输入即可。登录成功后 session 保存到 `~/.instagram/session.json`。

2. 在 `.env` 中设置：

```
IG_ENABLED=true
IG_USERNAME=你的用户名
IG_PASSWORD=你的密码
```

> Instagram 使用 `instagrapi` 库（Instagram Private API），无需浏览器。Session 文件包含设备指纹，后续登录不会再触发 Challenge 验证。如果 session 过期，重新运行登录脚本即可。

## GitHub Actions 自动运行

项目已配置 GitHub Actions，每天北京时间 8:00 自动运行完整流程。

### 配置 Secrets

在仓库 Settings → Secrets and variables → Actions 中添加：

| Secret 名称 | 说明 |
|---|---|
| `OPENWEATHERMAP_API_KEY` | OpenWeatherMap API Key |
| `TELEGRAM_BOT_TOKEN` | Telegram Bot Token |
| `TELEGRAM_CHAT_ID` | 接收消息的 chat_id |
| `NOTEBOOKLM_STORAGE_STATE` | NotebookLM 认证文件（base64 编码） |
| `XHS_STORAGE_STATE` | 小红书认证文件（base64 编码，可选） |
| `IG_SESSION` | Instagram session 文件（base64 编码，可选） |
| `IG_USERNAME` | Instagram 用户名（配合 session 使用，可选） |
| `IG_PASSWORD` | Instagram 密码（配合 session 使用，可选） |

### 导出 NotebookLM 认证

```bash
# 本地先登录（仅需一次）
notebooklm login

# 生成 base64 字符串，复制粘贴到 GitHub Secret
base64 < ~/.notebooklm/storage_state.json
```

> NotebookLM 的 cookie 会过期，过期后需重新 `notebooklm login` 并更新 Secret。

### 导出小红书认证（可选）

```bash
# 本地先登录（仅需一次）
python scripts/xhs_login.py

# 生成 base64 字符串，复制粘贴到 GitHub Secret
base64 < ~/.xhs/storage_state.json
```

> 配置了 `XHS_STORAGE_STATE` Secret 后，GitHub Actions 会自动启用小红书发布。

### 导出 Instagram 认证（可选）

```bash
# 本地先登录（仅需一次，需完成 Challenge 验证）
python scripts/ig_login.py

# 生成 base64 字符串，复制粘贴到 GitHub Secret
base64 < ~/.instagram/session.json
```

> Session 包含设备指纹，CI 中加载后 Instagram 不会再触发 Challenge。
> 同时配置 `IG_USERNAME` 和 `IG_PASSWORD` Secret 可在 session 过期时自动重新登录。

### 手动触发

在仓库 Actions 页面选择 "每日穿搭指南生成" → Run workflow 即可手动运行。

## 依赖

| 库 | 用途 |
|---|---|
| `httpx` | HTTP 客户端（天气 API + Telegram） |
| `pyyaml` | YAML 配置文件解析 |
| `python-dotenv` | 环境变量管理 |
| `notebooklm-py` | NotebookLM API 客户端 |
| `playwright` | 小红书浏览器自动化 |
| `instagrapi` | Instagram Private API 客户端 |
| `zhdate` | 农历日期转换（节日祝福） |
| `sxtwl` | 寿星天文历（二十四节气计算） |
