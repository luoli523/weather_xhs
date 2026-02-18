"""Tests for weather utility functions."""

from src.clothing.weather import _wind_deg_to_dir, _wind_speed_to_scale


class TestWindDegToDir:

    def test_north(self):
        assert _wind_deg_to_dir(0) == "北风"
        assert _wind_deg_to_dir(360) == "北风"

    def test_east(self):
        assert _wind_deg_to_dir(90) == "东风"

    def test_south(self):
        assert _wind_deg_to_dir(180) == "南风"

    def test_west(self):
        assert _wind_deg_to_dir(270) == "西风"

    def test_northeast(self):
        assert _wind_deg_to_dir(45) == "东北风"

    def test_southeast(self):
        assert _wind_deg_to_dir(135) == "东南风"

    def test_southwest(self):
        assert _wind_deg_to_dir(225) == "西南风"

    def test_northwest(self):
        assert _wind_deg_to_dir(315) == "西北风"


class TestWindSpeedToScale:

    def test_calm(self):
        assert _wind_speed_to_scale(0.1) == "0"

    def test_light_breeze(self):
        assert _wind_speed_to_scale(2.0) == "2"

    def test_strong_wind(self):
        assert _wind_speed_to_scale(15.0) == "7"

    def test_hurricane(self):
        assert _wind_speed_to_scale(40.0) == "12+"

    def test_scale_boundary(self):
        assert _wind_speed_to_scale(0.3) == "1"
