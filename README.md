# weather_xhs

每日天气穿搭指南 + 二十四节气 + 唐诗宋词信息图自动生成系统。

获取天气 → GPT 动态生成穿搭/节气/诗词内容 → NotebookLM 生成信息图 → 推送 Telegram → 发布 Instagram。

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
3. 调用 GPT 动态生成穿搭 infographic prompt
4. 输出结构化 Markdown，上传到 NotebookLM 生成穿搭 infographic
5. 推送穿搭图到 Telegram（每城市一张，附天气穿搭 caption）
6. 发布穿搭相册到 Instagram（含 hashtags、节日祝福）

### 节气流程（节气日自动触发）

1. 使用 `sxtwl`（寿星天文历）检测当天是否为二十四节气
2. 调用 GPT 动态生成节气详细内容（含义、习俗、美食、养生）和 infographic prompt
3. 生成节气 Markdown，上传到 NotebookLM 生成中国风节气 infographic
4. 推送节气图到 Telegram（附节气介绍文案）
5. 发布节气帖子到 Instagram（附习俗、养生 hashtags）

### 诗词流程（每日运行）

1. 调用 GPT 判断当天是否与经典唐诗宋词有关联（节日、节气、纪念日等）
2. 如有关联，GPT 返回诗词全文、赏析、风俗科普和 infographic prompt
3. 生成诗词 Markdown，上传到 NotebookLM 生成信息图
4. 推送诗词图到 Telegram（附诗词简介文案）
5. 发布诗词帖子到 Instagram（附风俗知识 hashtags）

## 项目结构

```
weather_xhs/
├── main.py                         # 主入口
├── pyproject.toml                  # pytest 配置
├── config/
│   ├── config.yaml                 # 城市列表 + OpenAI/API 配置
│   └── special_days.yaml           # 节日祝福配置（固定日期）
├── src/
│   ├── common/                     # 共享基础功能
│   │   ├── config.py               #   统一配置读取（OpenAI 模型参数等）
│   │   ├── notebooklm.py           #   NotebookLM 基础（认证检查/重试/上传）
│   │   ├── telegram.py             #   Telegram 基础（get_config, send_photo/message）
│   │   ├── xhs.py                  #   小红书基础（get_config, publish_note）
│   │   └── instagram.py            #   Instagram 基础（get_config, publish_album）
│   ├── clothing/                   # 穿搭模块
│   │   ├── weather.py              #   OpenWeatherMap API 客户端
│   │   ├── mock_weather.py         #   模拟天气数据（测试用）
│   │   ├── index.py                #   穿衣指数生成（7 档温度区间）
│   │   ├── content.py              #   Markdown 内容生成
│   │   ├── notebooklm.py           #   穿搭 NotebookLM pipeline（GPT 动态 prompt）
│   │   ├── telegram.py             #   穿搭 Telegram 推送
│   │   ├── xhs.py                  #   穿搭小红书内容构建（含节日祝福）
│   │   └── instagram.py            #   穿搭 Instagram 发布
│   ├── solar_term/                 # 节气模块
│   │   ├── detector.py             #   节气检测（sxtwl）+ GPT 动态生成内容
│   │   ├── content.py              #   节气内容生成（MD/IG/Telegram）
│   │   └── notebooklm.py           #   节气 NotebookLM pipeline
│   └── poetry/                     # 诗词模块
│       ├── detector.py             #   GPT 诗词匹配（农历/节气/节日上下文）
│       ├── content.py              #   诗词内容生成（MD/IG/Telegram）
│       └── notebooklm.py           #   诗词 NotebookLM pipeline
├── tests/                          # 测试套件（90 个测试）
│   ├── conftest.py                 #   共享 fixtures（天气/穿搭/节气/诗词数据）
│   ├── test_clothing_index.py      #   穿衣指数单元测试（7 档温度分类）
│   ├── test_weather_helpers.py     #   风向/风速转换单元测试
│   ├── test_content.py             #   内容生成单元测试（穿搭/节气/诗词）
│   ├── test_special_days.py        #   节日检测 + 文案构建单元测试
│   ├── test_openai_integration.py  #   OpenAI 集成测试（mock GPT 响应）
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

每次运行后 `output/` 目录内容（以 3 个城市 + 雨水节气日 + 诗词匹配为例）：

| 文件 | 说明 |
|------|------|
| `clothing_guide_2026-02-18.md` | 穿搭 Markdown（NotebookLM source） |
| `北京_2026-02-18.png` | 北京穿搭 infographic |
| `上海_2026-02-18.png` | 上海穿搭 infographic |
| `深圳_2026-02-18.png` | 深圳穿搭 infographic |
| `solar_term_雨水_2026-02-18.md` | 节气 Markdown（仅节气日） |
| `雨水_2026-02-18.png` | 节气 infographic（仅节气日） |
| `poetry_雨水_2026-02-18.md` | 诗词 Markdown（仅匹配到诗词时） |
| `诗词_雨水_2026-02-18.png` | 诗词 infographic（仅匹配到诗词时） |

推送结果：

| 渠道 | 内容 |
|------|------|
| **Telegram** | 穿搭图（相册） + 节气图 + 诗词图（各附文案） |
| **Instagram** | 穿搭相册 + 节气帖子 + 诗词帖子（各独立发布） |

> 非节气日只有穿搭和诗词内容（如当天有匹配的诗词）。

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
| `OPENAI_API_KEY` | 是 | GPT 动态生成 prompt（未配置则跳过全部流程） |
| `TELEGRAM_ENABLED` + Token/ChatID | 推荐 | Telegram 推送 |
| `IG_ENABLED` + Username/Password | 可选 | Instagram 发布 |

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

# Mock 模式测试（无需天气 API Key）
python main.py --mock --no-nlm

# 跳过 Instagram 发布
python main.py --no-ig

# 跳过诗词模块
python main.py --no-poetry

# 仅发送当天已有图片
python main.py --send-telegram
python main.py --send-ig
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
| `--no-ig` | 跳过所有 Instagram 发布 |
| `--no-poetry` | 跳过诗词模块（不调用 GPT 匹配诗词） |
| `--gender female/male/neutral/random` | 穿搭图中人物性别（默认 female） |
| `--send-telegram` | 跳过生成，仅发送当天图片到 Telegram |
| `--send-xhs` | 跳过生成，仅发送当天图片到小红书 |
| `--send-ig` | 跳过生成，仅发送当天图片到 Instagram |

## 测试

项目包含 90 个自动化测试，覆盖 3 个层级：

| 层级 | 说明 | 测试数 |
|------|------|--------|
| **单元测试** | 穿衣指数、风向/风速转换、内容生成、节日检测 | 65 |
| **集成测试** | Mock OpenAI/Telegram/Instagram API 交互 | 22 |
| **冒烟测试** | 全流程 mock 运行、异常退出验证 | 3 |

```bash
# 运行全部测试
python -m pytest tests/ -v

# 运行单个测试文件
python -m pytest tests/test_clothing_index.py -v

# 运行特定测试类
python -m pytest tests/test_content.py::TestPoetryContent -v
```

GitHub Actions 会在每次 pipeline 执行前自动运行测试，测试不通过则跳过 pipeline。

## GitHub Actions 自动运行

项目已配置 GitHub Actions，每天北京时间 8:00 自动运行完整流程。

### 配置 Secrets

在仓库 Settings → Secrets and variables → Actions 中添加：

| Secret 名称 | 说明 |
|---|---|
| `OPENWEATHERMAP_API_KEY` | OpenWeatherMap API Key |
| `OPENAI_API_KEY` | OpenAI API Key（GPT 动态生成 prompt） |
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
| `openai` | OpenAI GPT API（动态生成穿搭/节气/诗词 prompt） |
| `notebooklm-py` | NotebookLM API 客户端（信息图生成） |
| `playwright` | 小红书浏览器自动化 |
| `instagrapi` | Instagram Private API 客户端 |
| `Pillow` | 图片格式转换（PNG→JPG） |
| `zhdate` | 农历日期转换（节日检测） |
| `sxtwl` | 寿星天文历（二十四节气计算） |
| `pytest` / `pytest-asyncio` | 自动化测试框架 |
