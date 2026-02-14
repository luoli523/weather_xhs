"""OpenWeatherMap API 调用模块

使用免费版 API：
- /data/2.5/weather  实时天气
- /data/2.5/forecast 5天/3小时预报（从中聚合当日数据）
"""

import httpx
from dataclasses import dataclass
from datetime import datetime, timezone


@dataclass
class CurrentWeather:
    """实时天气数据"""
    temp: str           # 温度 ℃
    feels_like: str     # 体感温度 ℃
    text: str           # 天气状况（晴、多云等）
    wind_dir: str       # 风向
    wind_scale: str     # 风力等级
    humidity: str       # 相对湿度 %
    precip: str         # 降水量 mm（过去1h/3h）
    vis: str            # 能见度 km


@dataclass
class DailyForecast:
    """当日预报数据（从3小时预报聚合）"""
    date: str
    temp_max: str
    temp_min: str
    text_day: str
    text_night: str
    wind_dir_day: str
    wind_scale_day: str
    humidity: str
    uv_index: str
    precip: str


@dataclass
class CityWeather:
    """单个城市的完整天气信息"""
    city_name: str
    location_id: str
    current: CurrentWeather
    forecast: DailyForecast
    clothing: None = None  # OpenWeatherMap 无穿衣指数，由 clothing.index 模块生成


def _wind_deg_to_dir(deg: float) -> str:
    """将风向角度转为中文方向"""
    dirs = ["北风", "东北风", "东风", "东南风", "南风", "西南风", "西风", "西北风"]
    idx = round(deg / 45) % 8
    return dirs[idx]


def _wind_speed_to_scale(speed_ms: float) -> str:
    """将风速(m/s)转为风力等级"""
    thresholds = [0.3, 1.6, 3.4, 5.5, 8.0, 10.8, 13.9, 17.2, 20.8, 24.5, 28.5, 32.7]
    for i, t in enumerate(thresholds):
        if speed_ms < t:
            return str(i)
    return "12+"


class OpenWeatherClient:
    """OpenWeatherMap API 客户端"""

    BASE_URL = "https://api.openweathermap.org/data/2.5"

    def __init__(self, api_key: str):
        self.api_key = api_key

    async def _request(self, path: str, params: dict) -> dict:
        params["appid"] = self.api_key
        params["units"] = "metric"
        params["lang"] = "zh_cn"
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(f"{self.BASE_URL}{path}", params=params)
            resp.raise_for_status()
            data = resp.json()
            if "cod" in data and str(data["cod"]) not in ("200", "200"):
                raise RuntimeError(f"OpenWeatherMap error: {data.get('message', data)}")
            return data

    async def get_current_weather(self, lat: str, lon: str) -> CurrentWeather:
        data = await self._request("/weather", {"lat": lat, "lon": lon})
        rain_1h = data.get("rain", {}).get("1h", 0)
        snow_1h = data.get("snow", {}).get("1h", 0)
        precip = rain_1h + snow_1h
        vis_km = data.get("visibility", 10000) / 1000

        return CurrentWeather(
            temp=str(round(data["main"]["temp"])),
            feels_like=str(round(data["main"]["feels_like"])),
            text=data["weather"][0]["description"],
            wind_dir=_wind_deg_to_dir(data["wind"].get("deg", 0)),
            wind_scale=_wind_speed_to_scale(data["wind"].get("speed", 0)),
            humidity=str(data["main"]["humidity"]),
            precip=str(round(precip, 1)),
            vis=str(round(vis_km, 1)),
        )

    async def get_daily_forecast(self, lat: str, lon: str) -> DailyForecast:
        """从5天/3小时预报中聚合当天数据"""
        data = await self._request("/forecast", {"lat": lat, "lon": lon})
        today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        today_items = [
            item for item in data["list"]
            if item["dt_txt"].startswith(today_str)
        ]
        if not today_items:
            today_items = data["list"][:8]

        temps = [item["main"]["temp"] for item in today_items]
        humidities = [item["main"]["humidity"] for item in today_items]
        precips = [
            item.get("rain", {}).get("3h", 0) + item.get("snow", {}).get("3h", 0)
            for item in today_items
        ]

        day_texts = []
        night_texts = []
        for item in today_items:
            hour = int(item["dt_txt"].split(" ")[1].split(":")[0])
            desc = item["weather"][0]["description"]
            if 6 <= hour < 18:
                day_texts.append(desc)
            else:
                night_texts.append(desc)

        def most_common(texts: list[str], fallback: str) -> str:
            if not texts:
                return fallback
            return max(set(texts), key=texts.count)

        text_day = most_common(day_texts, today_items[0]["weather"][0]["description"])
        text_night = most_common(night_texts, text_day)

        wind_deg = today_items[0]["wind"].get("deg", 0)
        wind_speed = max(item["wind"].get("speed", 0) for item in today_items)

        return DailyForecast(
            date=today_str,
            temp_max=str(round(max(temps))),
            temp_min=str(round(min(temps))),
            text_day=text_day,
            text_night=text_night,
            wind_dir_day=_wind_deg_to_dir(wind_deg),
            wind_scale_day=_wind_speed_to_scale(wind_speed),
            humidity=str(round(sum(humidities) / len(humidities))),
            uv_index="0",
            precip=str(round(sum(precips), 1)),
        )

    async def get_city_weather(self, city_name: str, location_id: str) -> CityWeather:
        """获取一个城市的完整天气信息。location_id 格式为 'lat,lon'"""
        lat, lon = location_id.split(",")
        current = await self.get_current_weather(lat, lon)
        forecast = await self.get_daily_forecast(lat, lon)
        return CityWeather(
            city_name=city_name,
            location_id=location_id,
            current=current,
            forecast=forecast,
        )
