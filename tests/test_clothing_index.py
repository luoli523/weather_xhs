"""Tests for clothing index (temperature-based outfit suggestions)."""

import pytest
from tests.conftest import _make_city_weather
from src.clothing.index import (
    generate_clothing_advice,
    _get_outfit_suggestion,
    _rain_tips,
    _uv_tips,
)


class TestGetOutfitSuggestion:
    """Test the 7 temperature categories."""

    def test_extreme_hot(self):
        level, outfit, tips = _get_outfit_suggestion(38)
        assert level == "极热"
        assert "短袖" in outfit or "背心" in outfit

    def test_hot(self):
        level, outfit, tips = _get_outfit_suggestion(30)
        assert level == "炎热"

    def test_warm(self):
        level, outfit, tips = _get_outfit_suggestion(25)
        assert level == "温暖"

    def test_comfortable(self):
        level, outfit, tips = _get_outfit_suggestion(18)
        assert level == "舒适"

    def test_cool(self):
        level, outfit, tips = _get_outfit_suggestion(10)
        assert level == "微凉"

    def test_cold(self):
        level, outfit, tips = _get_outfit_suggestion(3)
        assert level == "寒冷"
        assert "羽绒服" in outfit or "厚外套" in outfit

    def test_extreme_cold(self):
        level, outfit, tips = _get_outfit_suggestion(-10)
        assert level == "极寒"

    def test_boundary_35(self):
        level, _, _ = _get_outfit_suggestion(35)
        assert level == "极热"

    def test_boundary_28(self):
        level, _, _ = _get_outfit_suggestion(28)
        assert level == "炎热"

    def test_boundary_0(self):
        level, _, _ = _get_outfit_suggestion(0)
        assert level == "寒冷"


class TestRainTips:

    def test_rain_in_text(self):
        tips = _rain_tips("小雨转阴", "5")
        assert any("伞" in t for t in tips)

    def test_snow_adds_slip_warning(self):
        tips = _rain_tips("暴雪", "0")
        assert any("滑" in t for t in tips)

    def test_heavy_precip(self):
        tips = _rain_tips("大雨", "15")
        assert any("降水量较大" in t for t in tips)

    def test_no_rain(self):
        tips = _rain_tips("晴", "0")
        assert tips == []


class TestUvTips:

    def test_extreme_uv(self):
        tips = _uv_tips("9")
        assert len(tips) == 2
        assert any("防晒" in t for t in tips)

    def test_moderate_uv(self):
        tips = _uv_tips("6")
        assert len(tips) == 1

    def test_low_uv(self):
        tips = _uv_tips("2")
        assert tips == []

    def test_invalid_uv(self):
        assert _uv_tips("N/A") == []
        assert _uv_tips("") == []


class TestGenerateClothingAdvice:

    def test_basic_output(self, beijing_cold):
        advice = generate_clothing_advice(beijing_cold)
        assert advice.city_name == "北京"
        assert "℃" in advice.temp_range
        assert "℃" in advice.feels_like
        assert advice.outfit_suggestion

    def test_cold_category(self, beijing_cold):
        advice = generate_clothing_advice(beijing_cold)
        assert advice.clothing_category in ("寒冷", "极寒")

    def test_hot_category(self, shenzhen_hot):
        advice = generate_clothing_advice(shenzhen_hot)
        assert advice.clothing_category in ("极热", "炎热")

    def test_rain_tips_included(self, rainy_weather):
        advice = generate_clothing_advice(rainy_weather)
        assert any("伞" in t for t in advice.extra_tips)

    def test_uv_tips_included(self, shenzhen_hot):
        advice = generate_clothing_advice(shenzhen_hot)
        assert any("防晒" in t or "紫外线" in t for t in advice.extra_tips)

    def test_large_temp_diff_tip(self):
        w = _make_city_weather(temp_max=30, temp_min=15)
        advice = generate_clothing_advice(w)
        assert any("温差" in t for t in advice.extra_tips)
