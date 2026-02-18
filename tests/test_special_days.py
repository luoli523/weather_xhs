"""Tests for special day detection and caption builders."""

import pytest
from src.clothing.xhs import (
    get_special_day,
    build_xhs_content,
    _lunar_special_days,
)
from src.clothing.instagram import build_ig_caption
from tests.conftest import _make_city_weather
from src.clothing.index import generate_clothing_advice


class TestSpecialDayDetection:

    def test_new_year(self):
        result = get_special_day("2026-01-01")
        assert result is not None
        assert result["name"] == "元旦"

    def test_valentines(self):
        result = get_special_day("2026-02-14")
        assert result is not None
        assert result["name"] == "情人节"

    def test_christmas(self):
        result = get_special_day("2026-12-25")
        assert result is not None
        assert result["name"] == "圣诞节"

    def test_normal_day_returns_none(self):
        result = get_special_day("2026-03-15")
        assert result is None

    def test_invalid_date_returns_none(self):
        result = get_special_day("not-a-date")
        assert result is None


class TestLunarSpecialDays:

    def test_returns_dict(self):
        result = _lunar_special_days(2026)
        assert isinstance(result, dict)

    def test_has_spring_festival(self):
        result = _lunar_special_days(2026)
        has_spring = any(v["name"] == "春节" for v in result.values())
        assert has_spring

    def test_has_mid_autumn(self):
        result = _lunar_special_days(2026)
        has_mid_autumn = any(v["name"] == "中秋节" for v in result.values())
        assert has_mid_autumn


class TestBuildXhsContent:

    def test_basic_content(self, sample_advices):
        title, content, tags = build_xhs_content(sample_advices, "2026-02-18")
        assert title
        assert len(title) <= 20
        assert "北京" in content
        assert "穿搭" in tags

    def test_special_day_in_title(self, sample_advices):
        title, content, tags = build_xhs_content(sample_advices, "2026-01-01")
        assert "元旦" in title

    def test_greeting_in_content(self, sample_advices):
        _, content, _ = build_xhs_content(sample_advices, "2026-01-01")
        assert "快乐" in content or "新年" in content

    def test_tags_include_cities(self, sample_advices):
        _, _, tags = build_xhs_content(sample_advices, "2026-02-18")
        assert "北京穿搭" in tags


class TestBuildIgCaption:

    def test_basic_caption(self, sample_advices):
        caption = build_ig_caption(sample_advices, "2026-02-18")
        assert "穿搭指南" in caption
        assert "#穿搭" in caption
        assert "#OOTD" in caption

    def test_special_day_in_caption(self, sample_advices):
        caption = build_ig_caption(sample_advices, "2026-01-01")
        assert "元旦" in caption

    def test_all_cities_present(self, sample_advices):
        caption = build_ig_caption(sample_advices, "2026-02-18")
        assert "北京" in caption
        assert "上海" in caption
        assert "深圳" in caption
