# weather_xhs

每日天气穿搭指南信息图自动生成系统。

获取天气 → LLM 动态生成穿搭 prompt → NotebookLM 生成信息图 → 推送 Telegram → 发布 Instagram。

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

每日运行流程：

1. 从 12 个候选城市中随机选取生成信息图的城市（默认 4 个，`infographic_count` 可配置）
2. 并发调用 OpenWeatherMap API 获取各城市实时天气 + 当日预报
3. 根据温度生成 7 档穿衣指数和穿搭建议（极热/炎热/温暖/舒适/微凉/寒冷/极寒）
4. 调用 LLM 动态生成穿搭 infographic prompt（每张图随机选取一种视觉风格）
5. 输出结构化 Markdown，上传到 NotebookLM 生成穿搭 infographic
6. 推送穿搭图到 Telegram（每城市一张，附天气穿搭 caption）
7. 发布穿搭相册到 Instagram（含 hashtags、节日祝福）

## 视觉风格

每张穿搭图随机选取一种风格，当前 active 共 6 种：

- 日系少女漫画风
- 极简素描时装风
- 中国风水墨插画
- 半写实动漫时装风
- 可爱卡通动漫风
- 吉卜力手绘动画风

风格定义见 `src/clothing/notebooklm.py` 的 `VISUAL_STYLES`。

## 项目结构

```
weather_xhs/
├── main.py                         # 主入口
├── pyproject.toml                  # pytest 配置
├── config/
│   ├── config.yaml                 # 城市列表（12 个）+ infographic_count + LLM 配置
│   └── special_days.yaml           # 节日祝福配置（固定日期）
├── src/
│   ├── common/                     # 共享基础功能
│   │   ├── config.py               #   LLM 配置（7 厂商统一 OpenAI 兼容接口）
│   │   ├── notebooklm.py           #   NotebookLM 基础（认证检查/重试/上传）
│   │   ├── telegram.py             #   Telegram 基础（get_config, send_photo/message）
│   │   ├── xhs.py                  #   小红书基础（get_config, publish_note）
│   │   └── instagram.py            #   Instagram 基础（get_config, publish_album）
│   └── clothing/                   # 穿搭模块
│       ├── weather.py              #   OpenWeatherMap API 客户端
│       ├── mock_weather.py         #   模拟天气数据（测试用）
│       ├── index.py                #   穿衣指数生成（7 档温度区间）
│       ├── content.py              #   Markdown 内容生成
│       ├── notebooklm.py           #   穿搭 NotebookLM pipeline（含 6 种视觉风格）
│       ├── telegram.py             #   穿搭 Telegram 推送
│       ├── xhs.py                  #   穿搭小红书内容构建（含节日祝福）
│       └── instagram.py            #   穿搭 Instagram 发布
├── tests/                          # 测试套件
│   ├── conftest.py                 #   共享 fixtures（天气/穿搭数据）
│   ├── test_clothing_index.py      #   穿衣指数单元测试（7 档温度分类）
│   ├── test_weather_helpers.py     #   风向/风速转换单元测试
│   ├── test_content.py             #   Markdown 内容生成测试
│   ├── test_special_days.py        #   节日检测 + 文案构建测试
│   ├── test_telegram.py            #   Telegram/Instagram 配置与发送测试
│   └── test_smoke.py               #   端到端冒烟测试（mock 全流程）
├── scripts/
│   ├── xhs_login.py                # 小红书登录辅助脚本
│   ├── ig_login.py                 # Instagram 登录辅助脚本
│   └── experiment_grok_video.py    # Grok Imagine 视频生成实验脚本
├── output/                         # 生成产物目录
└── .github/workflows/
    └── daily-run.yml               # 每日定时运行（含测试）
```

## 输出产物

每次运行后 `output/` 目录内容（以 `infographic_count=4` 为例）：

| 文件 | 说明 |
|------|------|
| `clothing_guide_2026-04-22.md` | 穿搭 Markdown（NotebookLM source） |
| `<城市>_2026-04-22.png` × 4 | 随机选中的 4 个城市各生成 1 张 infographic |

推送结果：

| 渠道 | 内容 |
|------|------|
| **Telegram** | 穿搭图相册（附每城市天气穿搭 caption） |
| **Instagram** | 穿搭相册（含 hashtags、节日祝福） |
| **小红书** | 仅手动 `--send-xhs` 触发，不在主流程中 |

## 快速开始

### 1. 环境准备

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium  # 小红书发布需要
```

### 2. 配置环境变量

```bash
cp .env.example .env
```

编辑 `.env`，填入必要的 API Key：

| 变量 | 必填 | 说明 |
|------|------|------|
| `OPENWEATHERMAP_API_KEY` | 是 | 天气 API Key |
| `LLM_PROVIDER` | 是 | LLM 厂商：`openai`/`deepseek`/`moonshot`/`qwen`/`grok`/`gemini`/`claude` |
| `<PROVIDER>_API_KEY` | 是 | 对应厂商的 API Key（如 `OPENAI_API_KEY` / `DEEPSEEK_API_KEY` 等） |
| `LLM_MODEL` | 否 | 覆盖厂商默认模型（不设置则使用厂商默认） |
| `TELEGRAM_ENABLED` + Bot Token/Chat ID | 推荐 | Telegram 推送 |
| `IG_ENABLED` + 用户名/密码 | 可选 | Instagram 发布 |
| `XHS_ENABLED` + Storage State | 可选 | 小红书手动发送（`--send-xhs`） |

未配置 LLM API Key 时主流程会跳过（并通过 Telegram 发送通知，若已配置）。

### 3. 登录认证（一次性）

```bash
# NotebookLM（必须）
notebooklm login

# Instagram（可选）
python scripts/ig_login.py

# 小红书（可选，手动发送时需要）
python scripts/xhs_login.py
```

### 4. 运行

```bash
# 完整流程
python main.py

# Mock 模式测试（无需天气 API Key、不生成 infographic）
python main.py --mock --no-nlm

# 跳过 Instagram 发布
python main.py --no-ig

# 仅发送当天已有图片
python main.py --send-telegram
python main.py --send-ig
python main.py --send-xhs
```

### 5. 运行测试

```bash
python -m pytest tests/ -v
```

### 命令行参数

| 参数 | 说明 |
|------|------|
| `--mock` | 使用模拟天气数据，不调用 API |
| `--no-nlm` | 跳过 NotebookLM 生成流程 |
| `--no-ig` | 跳过 Instagram 发布 |
| `--gender female/male/neutral/random` | 穿搭图中人物性别（默认 `random`） |
| `--send-telegram` | 跳过生成，仅发送当天图片到 Telegram |
| `--send-ig` | 跳过生成，仅发送当天图片到 Instagram |
| `--send-xhs` | 跳过生成，仅发送当天图片到小红书 |

## 测试

项目包含 70 个自动化测试，覆盖：

- 穿衣指数分类（7 档温度区间）
- 风向/风速转换工具
- Markdown 内容生成
- 节日检测（固定日期 + 农历）
- Telegram / Instagram 配置与发送
- 端到端冒烟测试（全流程 mock）

```bash
# 运行全部测试
python -m pytest tests/ -v

# 运行单个测试文件
python -m pytest tests/test_clothing_index.py -v
```

GitHub Actions 会在每次 pipeline 执行前自动运行测试，测试不通过则跳过 pipeline。

## GitHub Actions 自动运行

项目已配置 GitHub Actions，每天北京时间 8:00 自动运行完整流程。

### 配置 Secrets

在仓库 Settings → Secrets and variables → Actions 中添加：

| Secret 名称 | 说明 |
|---|---|
| `OPENWEATHERMAP_API_KEY` | OpenWeatherMap API Key |
| `LLM_PROVIDER` | LLM 厂商（`openai`/`deepseek`/`moonshot`/... 其一） |
| `<PROVIDER>_API_KEY` | 对应厂商的 API Key |
| `LLM_MODEL` | 可选，覆盖厂商默认模型 |
| `TELEGRAM_BOT_TOKEN` | Telegram Bot Token |
| `TELEGRAM_CHAT_ID` | 接收消息的 chat_id |
| `NOTEBOOKLM_STORAGE_STATE` | NotebookLM 认证文件（base64 编码） |
| `IG_SESSION` | Instagram session 文件（base64 编码，可选） |
| `IG_USERNAME` | Instagram 用户名（可选） |
| `IG_PASSWORD` | Instagram 密码（可选） |

### 导出认证文件

```bash
# NotebookLM
notebooklm login
base64 < ~/.notebooklm/storage_state.json

# Instagram
python scripts/ig_login.py
base64 < ~/.instagram/session.json
```

> NotebookLM 的 cookie 会过期，过期后需重新登录并更新 Secret。
> 如果 NotebookLM 认证失效，pipeline 会自动通过 Telegram 发送通知提醒重新登录。

### 手动触发

在仓库 Actions 页面选择 "每日穿搭指南生成" → Run workflow 即可手动运行。

## 依赖

| 库 | 用途 |
|---|---|
| `httpx` | HTTP 客户端（天气 API + Telegram） |
| `pyyaml` | YAML 配置文件解析 |
| `python-dotenv` | 环境变量管理 |
| `openai` | OpenAI 兼容 API 客户端（7 厂商统一通过该 SDK 调用） |
| `notebooklm-py` | NotebookLM API 客户端（信息图生成） |
| `playwright` | 小红书浏览器自动化 |
| `instagrapi` | Instagram Private API 客户端 |
| `Pillow` | 图片格式转换（PNG→JPG） |
| `zhdate` | 农历日期转换（节日检测） |
| `pytest` / `pytest-asyncio` | 自动化测试框架 |
