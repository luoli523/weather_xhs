"""Mock 天气数据模块

提供模拟天气数据，用于在 API Key 不可用时测试完整流程。
用法：python3 main.py --mock
"""

import random
from datetime import datetime
from .weather import CurrentWeather, DailyForecast, CityWeather

# 各城市的模拟天气数据（按2月冬季设定）
_MOCK_DATA = {
    "北京": {"temp": -2, "high": 3, "low": -6, "text": "晴", "night": "晴", "humidity": 25, "wind": "西北风"},
    "上海": {"temp": 7, "high": 10, "low": 4, "text": "多云", "night": "阴", "humidity": 65, "wind": "东风"},
    "广州": {"temp": 18, "high": 22, "low": 15, "text": "多云", "night": "多云", "humidity": 72, "wind": "东南风"},
    "深圳": {"temp": 19, "high": 23, "low": 16, "text": "阴", "night": "小雨", "humidity": 78, "wind": "南风"},
    "成都": {"temp": 10, "high": 13, "low": 6, "text": "阴", "night": "阴", "humidity": 80, "wind": "北风"},
}

_DEFAULT = {"temp": 12, "high": 16, "low": 8, "text": "多云", "night": "晴", "humidity": 55, "wind": "东风"}


class MockWeatherClient:
    """模拟天气客户端，返回预设数据"""

    async def get_city_weather(self, city_name: str, location_id: str) -> CityWeather:
        d = _MOCK_DATA.get(city_name, _DEFAULT)
        temp_offset = random.randint(-1, 1)

        today_str = datetime.now().strftime("%Y-%m-%d")

        current = CurrentWeather(
            temp=str(d["temp"] + temp_offset),
            feels_like=str(d["temp"] + temp_offset - 2),
            text=d["text"],
            wind_dir=d["wind"],
            wind_scale="3",
            humidity=str(d["humidity"]),
            precip="0" if "雨" not in d["text"] else "2.5",
            vis="10.0",
        )

        forecast = DailyForecast(
            date=today_str,
            temp_max=str(d["high"] + temp_offset),
            temp_min=str(d["low"] + temp_offset),
            text_day=d["text"],
            text_night=d["night"],
            wind_dir_day=d["wind"],
            wind_scale_day="3",
            humidity=str(d["humidity"]),
            uv_index="3",
            precip="0" if "雨" not in d["night"] else "5.0",
        )

        return CityWeather(
            city_name=city_name,
            location_id=location_id,
            current=current,
            forecast=forecast,
        )
