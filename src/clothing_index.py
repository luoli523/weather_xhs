"""穿衣指数生成模块

基于 OpenWeatherMap 天气数据，根据温度区间生成穿搭建议。
包含 7 档温度区间的具体穿搭方案，以及降水、紫外线、温差等附加提示。
"""

from dataclasses import dataclass
from .weather import CityWeather


@dataclass
class ClothingAdvice:
    """穿搭建议"""
    city_name: str
    date: str
    temp_range: str         # 温度范围
    feels_like: str         # 体感温度
    weather_desc: str       # 天气描述
    clothing_level: str     # 穿衣等级
    clothing_category: str  # 穿衣级别名称
    api_advice: str         # API 原始建议
    outfit_suggestion: str  # 具体穿搭建议
    extra_tips: list[str]   # 额外提示


# 根据温度区间给出穿搭建议
_OUTFIT_BY_TEMP = [
    (35, None, "极热", "短袖/背心 + 短裤/短裙，选择透气轻薄的棉麻面料", ["注意防晒，涂抹SPF50+防晒霜", "随身携带遮阳伞或戴遮阳帽", "浅色衣物更凉爽"]),
    (28, 35, "炎热", "短袖T恤/衬衫 + 薄长裤/短裤，材质选冰丝或速干面料", ["注意防晒", "可穿浅色宽松衣物", "女生可选连衣裙"]),
    (22, 28, "温暖", "薄长袖/短袖 + 长裤/半裙，可搭配薄外套早晚穿", ["早晚温差可能较大，带件薄外套", "适合穿针织衫或薄卫衣"]),
    (15, 22, "舒适", "长袖衬衫/薄毛衣 + 长裤/裙装，外搭薄夹克或风衣", ["适合穿卫衣、薄毛衣", "建议叠穿，方便增减"]),
    (8, 15, "微凉", "毛衣/卫衣 + 外套（夹克/风衣/薄羽绒）+ 长裤", ["建议穿保暖内衣", "围巾可以提升保暖和造型"]),
    (0, 8, "寒冷", "厚毛衣/抓绒 + 羽绒服/厚外套 + 加绒裤/毛呢裤", ["戴帽子、手套、围巾", "注意脚部保暖，穿厚袜+保暖鞋"]),
    (None, 0, "极寒", "保暖内衣 + 厚毛衣 + 长款羽绒服/棉服 + 加厚裤装", ["全副武装：帽子、围巾、手套必备", "尽量减少户外活动时间", "贴暖宝宝防寒"]),
]


def _get_outfit_suggestion(temp: float) -> tuple[str, str, list[str]]:
    """根据温度获取穿搭建议"""
    for low, high, _level, outfit, tips in _OUTFIT_BY_TEMP:
        low_ok = low is None or temp >= low
        high_ok = high is None or temp < high
        if low_ok and high_ok:
            return _level, outfit, tips
    # fallback
    return "舒适", "长袖 + 长裤，适当搭配外套", ["注意查看实时天气变化"]


def _rain_tips(weather_text: str, precip: str) -> list[str]:
    """降水相关提示"""
    tips = []
    rain_keywords = ["雨", "雪", "冰", "雹"]
    if any(k in weather_text for k in rain_keywords):
        tips.append("记得带伞！穿防水鞋或靴子")
    if "雪" in weather_text:
        tips.append("路面可能湿滑，穿防滑鞋底的鞋子")
    try:
        if float(precip) > 10:
            tips.append("降水量较大，建议穿雨衣或带长柄伞")
    except (ValueError, TypeError):
        pass
    return tips


def _uv_tips(uv_index: str) -> list[str]:
    """紫外线提示"""
    try:
        uv = int(uv_index)
    except (ValueError, TypeError):
        return []
    if uv >= 7:
        return ["紫外线极强，务必做好防晒", "戴墨镜保护眼睛"]
    elif uv >= 5:
        return ["紫外线较强，建议涂防晒霜"]
    return []


def generate_clothing_advice(city_weather: CityWeather) -> ClothingAdvice:
    """根据城市天气数据生成穿搭建议"""
    w = city_weather
    try:
        avg_temp = (float(w.forecast.temp_max) + float(w.forecast.temp_min)) / 2
    except (ValueError, TypeError):
        avg_temp = float(w.current.temp)

    _level, outfit, base_tips = _get_outfit_suggestion(avg_temp)
    extra_tips = list(base_tips)
    extra_tips.extend(_rain_tips(w.forecast.text_day, w.forecast.precip))
    extra_tips.extend(_uv_tips(w.forecast.uv_index))

    # 温差提示
    try:
        temp_diff = float(w.forecast.temp_max) - float(w.forecast.temp_min)
        if temp_diff >= 10:
            extra_tips.append(f"昼夜温差达{temp_diff:.0f}℃，注意叠穿方便增减")
    except (ValueError, TypeError):
        pass

    # 如果 API 提供了穿衣指数，优先使用其等级和类别
    clothing_level = w.clothing.level if w.clothing else str(int(avg_temp // 5))
    clothing_category = w.clothing.category if w.clothing else _level
    api_advice = w.clothing.text if w.clothing else ""

    return ClothingAdvice(
        city_name=w.city_name,
        date=w.forecast.date,
        temp_range=f"{w.forecast.temp_min}℃ ~ {w.forecast.temp_max}℃",
        feels_like=f"{w.current.feels_like}℃",
        weather_desc=f"白天{w.forecast.text_day}，夜间{w.forecast.text_night}",
        clothing_level=clothing_level,
        clothing_category=clothing_category,
        api_advice=api_advice,
        outfit_suggestion=outfit,
        extra_tips=extra_tips,
    )
