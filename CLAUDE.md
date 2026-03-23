# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

weather_xhs is an automated daily weather outfit recommendation infographic generator. It fetches weather data, generates clothing advice via LLM, creates infographics through NotebookLM, and publishes to Telegram/Instagram/Xiaohongshu.

**Pipeline:** Fetch Weather → LLM Clothing Advice → Markdown → NotebookLM Infographic → Publish (Telegram/Instagram/XHS)

## Basic Rule

Every time before you do any adjustment, tell me what exactly you are going to do first, do it after approval.

## Common Commands

```bash
# Run full pipeline
python main.py

# Test mode (mock weather, skip NotebookLM)
python main.py --mock --no-nlm

# Skip specific channels
python main.py --no-ig --no-xhs

# Resend today's images
python main.py --send-telegram
python main.py --send-xhs
python main.py --send-ig

# Gender option (default: random)
python main.py --gender female|male|neutral|random

# Run all tests
python -m pytest tests/ -v

# Run a single test file
python -m pytest tests/test_clothing_index.py -v

# Setup
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium  # needed for XHS browser automation
```

## Architecture

### Entry Point
`main.py` — CLI argument parsing, config loading, orchestrates the full pipeline using async/await throughout.

### Module Structure
- **`src/common/`** — Shared utilities: LLM config (`config.py`), NotebookLM wrapper (`notebooklm.py`), publishing clients (`telegram.py`, `instagram.py`, `xhs.py`)
- **`src/clothing/`** — Core feature module: weather fetching (`weather.py`), 7-tier temperature classification (`index.py`), markdown generation (`content.py`), NotebookLM pipeline orchestration (`notebooklm.py`), per-channel publishing (`telegram.py`, `instagram.py`, `xhs.py`)
- **`src/solar_term/`**, **`src/poetry/`** — Archived/empty modules

### Key Design Patterns
- **All API calls are async** — weather, LLM, NotebookLM, Telegram all use `async/await` with `httpx`. Weather fetching uses `asyncio.gather()` for parallelism.
- **Multi-LLM support** — 7 providers (openai/deepseek/moonshot/qwen/grok/gemini/claude) all accessed via OpenAI-compatible API. Provider selected by `LLM_PROVIDER` env var, model by `LLM_MODEL` env var. Config in `src/common/config.py`.
- **NotebookLM rate limiting** — 20s gap between requests, 3 retries with exponential backoff (10s/20s/30s).
- **Graceful degradation** — Missing auth or disabled channels are skipped without crashing.

### Configuration
- **`config/config.yaml`** — Cities list (12 cities, 2 randomly selected per run), LLM settings, output directory
- **`config/special_days.yaml`** — Fixed-date holiday greetings
- **`.env`** — API keys and service toggles (see `.env.example`)
- Lunar holidays computed dynamically via `zhdate` library

### Output
Generated artifacts go to `output/` — markdown files (`clothing_guide_YYYY-MM-DD.md`) and PNG infographics.

## Testing

90 tests configured with `asyncio_mode = "auto"` in `pyproject.toml`. Key fixtures in `tests/conftest.py`:
- `_isolate_env` — Cleans environment per test
- `_make_city_weather()` — Factory for weather test data
- Pre-built fixtures: `beijing_cold`, `shanghai_comfortable`, `shenzhen_hot`, `rainy_weather`

## CI/CD

GitHub Actions (`.github/workflows/daily-run.yml`): runs daily at UTC 0:00 (Beijing 8:00 AM). Runs tests first, then the full pipeline with secrets injected as env vars.
