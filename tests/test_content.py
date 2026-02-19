"""Tests for content generation."""

import pytest
from src.clothing.content import generate_markdown as clothing_markdown


class TestClothingMarkdown:

    def test_contains_date(self, sample_advices):
        md = clothing_markdown(sample_advices, date="2026-02-18")
        assert "2026-02-18" in md
        assert "星期三" in md

    def test_contains_all_cities(self, sample_advices):
        md = clothing_markdown(sample_advices)
        assert "北京" in md
        assert "上海" in md
        assert "深圳" in md

    def test_has_table(self, sample_advices):
        md = clothing_markdown(sample_advices)
        assert "|------|" in md
        assert "温度范围" in md

    def test_has_city_sections(self, sample_advices):
        md = clothing_markdown(sample_advices)
        assert "### 北京" in md
        assert "### 上海" in md

    def test_empty_advices(self):
        md = clothing_markdown([])
        assert "0 个城市" in md


