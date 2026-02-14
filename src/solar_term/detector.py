"""二十四节气检测模块

使用 sxtwl（寿星天文历）判断给定日期是否为节气日，
并从 config/solar_terms.yaml 加载节气详细信息。
"""

from datetime import datetime

import yaml

try:
    import sxtwl
except ImportError:
    sxtwl = None

# sxtwl 节气名称顺序（索引 0~23）
JIEQI_NAMES = [
    "冬至", "小寒", "大寒", "立春", "雨水", "惊蛰",
    "春分", "清明", "谷雨", "立夏", "小满", "芒种",
    "夏至", "小暑", "大暑", "立秋", "处暑", "白露",
    "秋分", "寒露", "霜降", "立冬", "小雪", "大雪",
]


def _load_solar_terms_config(
    config_path: str = "config/solar_terms.yaml",
) -> dict:
    """加载节气配置（描述、风俗、饮食等）"""
    with open(config_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data.get("solar_terms", {})


def get_solar_term(date_str: str) -> dict | None:
    """判断给定日期是否为二十四节气日。

    Args:
        date_str: 日期字符串（YYYY-MM-DD）

    Returns:
        节气信息字典（含 name, season, meaning, description, customs, food,
        health_tip, date）或 None（非节气日）
    """
    if sxtwl is None:
        print("⚠ sxtwl 未安装，无法判断节气")
        return None

    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError:
        return None

    day = sxtwl.fromSolar(dt.year, dt.month, dt.day)
    if not day.hasJieQi():
        return None

    jq_index = day.getJieQi()
    jq_name = JIEQI_NAMES[jq_index]

    config = _load_solar_terms_config()
    term_info = config.get(jq_name, {})

    return {
        "name": jq_name,
        "date": date_str,
        "season": term_info.get("season", ""),
        "meaning": term_info.get("meaning", ""),
        "description": term_info.get("description", "").strip(),
        "customs": term_info.get("customs", []),
        "food": term_info.get("food", ""),
        "health_tip": term_info.get("health_tip", ""),
    }
