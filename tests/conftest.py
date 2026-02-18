"""Shared test fixtures for weather_xhs tests."""

import os
import pytest
from datetime import datetime

from src.clothing.weather import CurrentWeather, DailyForecast, CityWeather
from src.clothing.index import ClothingAdvice


@pytest.fixture(autouse=True)
def _isolate_env(monkeypatch):
    """Ensure tests don't leak env vars or trigger real API calls."""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("TELEGRAM_ENABLED", raising=False)
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.delenv("TELEGRAM_CHAT_ID", raising=False)
    monkeypatch.delenv("IG_ENABLED", raising=False)
    monkeypatch.delenv("XHS_ENABLED", raising=False)


def _make_city_weather(
    city="北京",
    temp=15,
    feels_like=13,
    temp_max=20,
    temp_min=10,
    text_day="晴",
    text_night="多云",
    humidity=50,
    uv_index="3",
    precip="0",
    wind_dir="北风",
    wind_scale="3",
) -> CityWeather:
    """Factory for CityWeather with sensible defaults."""
    today = datetime.now().strftime("%Y-%m-%d")
    return CityWeather(
        city_name=city,
        location_id="39.90,116.40",
        current=CurrentWeather(
            temp=str(temp),
            feels_like=str(feels_like),
            text=text_day,
            wind_dir=wind_dir,
            wind_scale=wind_scale,
            humidity=str(humidity),
            precip=precip,
            vis="10.0",
        ),
        forecast=DailyForecast(
            date=today,
            temp_max=str(temp_max),
            temp_min=str(temp_min),
            text_day=text_day,
            text_night=text_night,
            wind_dir_day=wind_dir,
            wind_scale_day=wind_scale,
            humidity=str(humidity),
            uv_index=uv_index,
            precip=precip,
        ),
    )


@pytest.fixture
def beijing_cold():
    return _make_city_weather(city="北京", temp=-3, feels_like=-7, temp_max=2, temp_min=-8, text_day="晴", text_night="晴")


@pytest.fixture
def shanghai_comfortable():
    return _make_city_weather(city="上海", temp=18, feels_like=17, temp_max=22, temp_min=14, text_day="多云", text_night="阴")


@pytest.fixture
def shenzhen_hot():
    return _make_city_weather(city="深圳", temp=33, feels_like=36, temp_max=36, temp_min=28, text_day="晴", text_night="晴", uv_index="8")


@pytest.fixture
def rainy_weather():
    return _make_city_weather(city="广州", temp=18, feels_like=16, temp_max=20, temp_min=15, text_day="小雨", text_night="中雨", precip="15")


@pytest.fixture
def sample_advices(beijing_cold, shanghai_comfortable, shenzhen_hot):
    from src.clothing.index import generate_clothing_advice
    return [generate_clothing_advice(w) for w in [beijing_cold, shanghai_comfortable, shenzhen_hot]]


@pytest.fixture
def sample_solar_term():
    return {
        "name": "雨水",
        "date": "2026-02-18",
        "season": "春",
        "meaning": "雨水是二十四节气之第二个节气，意味着降雨开始",
        "description": "雨水节气标志着气温回升、冰雪融化、降水增多。",
        "customs": ["接寿", "回娘屋", "拉保保", "撞拜寄"],
        "food": "春笋、荠菜、韭菜等时令蔬菜",
        "health_tip": "春季养生以养肝为主，宜清淡饮食",
        "infographic_prompt": "中国风水墨画信息图...",
    }


@pytest.fixture
def sample_poem():
    return {
        "has_poem": True,
        "title": "水调歌头·明月几时有",
        "author": "苏轼",
        "dynasty": "宋",
        "full_text": "明月几时有？把酒问青天。不知天上宫阙，今夕是何年...",
        "meaning": "这首词是苏轼在中秋之夜所作，表达了对亲人的思念。",
        "customs": ["赏月", "吃月饼", "猜灯谜"],
        "occasion": "中秋节",
        "date": "2026-10-04",
        "infographic_prompt": "中国风信息图...",
    }
