# weather_xhs

天气穿搭指南生成工具：获取天气、生成穿搭建议、输出 Markdown，并可选调用 NotebookLM 生成信息图。

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
