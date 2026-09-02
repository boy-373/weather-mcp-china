# -*- coding: utf-8 -*-
"""
天气查询 · 远程 MCP Server
------------------------
部署在 mcp.pianam.cn，任何支持 MCP 协议的 AI 客户端
(Claude Desktop / Cursor / Cline 等) 填入 URL 即可查询天气。
数据源：Open-Meteo 公开天气 API（免费、无需 API Key、无需注册），
网络异常时自动切换备用通道 wttr.in。纯只读查询，不涉及账号与付费。

Author: liufuyang  2026-09-01
"""
import json
import os
import ssl
import time
import datetime
import urllib.parse
import urllib.request
from pathlib import Path

from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings


BASE_DIR = Path(__file__).parent

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")
_SSL_CTX = ssl.create_default_context()
_SSL_CTX.check_hostname = False
_SSL_CTX.verify_mode = ssl.CERT_NONE

# WMO 天气代码 -> 中文描述（Open-Meteo 使用 WMO 标准代码）
WMO = {
    0: "晴", 1: "晴间多云", 2: "多云", 3: "阴",
    45: "雾", 48: "冻雾",
    51: "毛毛雨", 53: "毛毛雨", 55: "强毛毛雨",
    56: "冻毛毛雨", 57: "冻毛毛雨",
    61: "小雨", 63: "中雨", 65: "大雨",
    66: "冻雨", 67: "冻雨",
    71: "小雪", 73: "中雪", 75: "大雪", 77: "雪粒",
    80: "小阵雨", 81: "阵雨", 82: "强阵雨",
    85: "阵雪", 86: "强阵雪",
    95: "雷暴", 96: "雷暴伴冰雹", 99: "强雷暴伴冰雹",
}

WEEKDAYS = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]

# wttr.in 英文风向缩写 -> 中文
WTTR_WIND = {
    "N": "北风", "NNE": "东北偏北风", "NE": "东北风", "ENE": "东北偏东风",
    "E": "东风", "ESE": "东南偏东风", "SE": "东南风", "SSE": "东南偏南风",
    "S": "南风", "SSW": "西南偏南风", "SW": "西南风", "WSW": "西南偏西风",
    "W": "西风", "WNW": "西北偏西风", "NW": "西北风", "NNW": "西北偏北风",
}

_weather_cache = {}


def _http_get_json(url, timeout=15):
    req = urllib.request.Request(url)
    req.add_header("User-Agent", UA)
    req.add_header("Accept", "application/json,text/plain,*/*")
    resp = urllib.request.urlopen(req, timeout=timeout, context=_SSL_CTX)
    return json.loads(resp.read().decode("utf-8", errors="ignore"))


def wmo_text(code):
    try:
        return WMO.get(int(code), "未知")
    except (TypeError, ValueError):
        return "未知"


def wind_dir_cn(deg):
    dirs = ["北", "东北", "东", "东南", "南", "西南", "西", "西北"]
    try:
        return dirs[int((float(deg) + 22.5) // 45) % 8] + "风"
    except (TypeError, ValueError):
        return ""


def fmt_date(d):
    """2026-09-01 -> 09-01 周二（今天/明天/后天）"""
    try:
        dt = datetime.date.fromisoformat(d)
    except (TypeError, ValueError):
        return str(d)
    today = datetime.date.today()
    tag = ""
    if dt == today:
        tag = "今天"
    elif dt == today + datetime.timedelta(days=1):
        tag = "明天"
    elif dt == today + datetime.timedelta(days=2):
        tag = "后天"
    base = f"{dt.month:02d}-{dt.day:02d} {WEEKDAYS[dt.weekday()]}"
    return f"{base}（{tag}）" if tag else base


def fetch_open_meteo(city, days):
    """主通道：Open-Meteo，地理编码 + 预报。返回 None 表示城市未找到。"""
    q = urllib.parse.quote(city)
    # 取 20 条 + 只看居民点，排除机场/公园/岛屿等同名干扰
    geo = _http_get_json(
        f"https://geocoding-api.open-meteo.com/v1/search?name={q}&count=20&language=zh&format=json"
    )
    results = geo.get("results") or []
    # 中文精确匹配可能只返回同名小镇/村（如"青岛"先命中辽宁大连青岛村）。
    # 没有行政级城市时，按"XX市/XX市辖区"等变体重试，把地级市捞回来。
    has_admin = any(str(r.get("feature_code", "")).startswith(("PPLA", "PPLC"))
                    for r in results)
    if not has_admin:
        seen = {r.get("id") for r in results}
        variants = []
        raw = city.strip()
        if not raw.endswith("市"):
            variants.append(raw + "市")
        for v in variants:
            try:
                geo2 = _http_get_json(
                    f"https://geocoding-api.open-meteo.com/v1/search?name={urllib.parse.quote(v)}&count=10&language=zh&format=json"
                )
                for r in geo2.get("results") or []:
                    if r.get("id") not in seen:
                        results.append(r)
                        seen.add(r.get("id"))
            except Exception:
                pass
    results = [r for r in results if str(r.get("feature_code", "")).startswith("PPL")]
    if not results:
        return None
    # 地理编码对中文精确匹配可能返回小镇/村（"青岛"先命中辽宁大连青岛村，
    # 而"青岛市"在拼音匹配结果里）。策略：行政中心(PPLA*/PPLC)优先，
    # 同级按人口排序；没有行政中心再退回人口最多的居民点。
    ADMIN = ("PPLC", "PPLA", "PPLA1", "PPLA2", "PPLA3", "PPLA4", "PPLA5")

    def rank(r):
        fc = r.get("feature_code", "")
        tier = ADMIN.index(fc) if fc in ADMIN else len(ADMIN)
        return (tier, -int(r.get("population") or 0))

    loc = sorted(results, key=rank)[0]

    fc = _http_get_json(
        "https://api.open-meteo.com/v1/forecast"
        f"?latitude={loc['latitude']}&longitude={loc['longitude']}"
        "&current=temperature_2m,relative_humidity_2m,apparent_temperature,"
        "weather_code,wind_speed_10m,wind_direction_10m"
        "&daily=weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max"
        f"&timezone=auto&forecast_days={days}"
    )
    cur = fc.get("current", {}) or {}
    daily = fc.get("daily", {}) or {}

    region_parts = [loc.get("country"), loc.get("admin1")]
    region = " ".join(dict.fromkeys([p for p in region_parts if p]))
    title = loc.get("name", city)
    out = {
        "城市": f"{title}（{region}）" if region else title,
        "更新时间": str(cur.get("time", "")).replace("T", " "),
        "当前": {
            "天气": wmo_text(cur.get("weather_code")),
            "温度": f"{cur.get('temperature_2m')}℃",
            "体感温度": f"{cur.get('apparent_temperature')}℃",
            "湿度": f"{cur.get('relative_humidity_2m')}%",
            "风": f"{wind_dir_cn(cur.get('wind_direction_10m'))} {cur.get('wind_speed_10m')}km/h".strip(),
        },
        "预报": [],
        "数据源": "Open-Meteo",
    }
    for i, d in enumerate(daily.get("time", [])):
        out["预报"].append({
            "日期": fmt_date(d),
            "天气": wmo_text(daily["weather_code"][i]),
            "最高": f"{daily['temperature_2m_max'][i]}℃",
            "最低": f"{daily['temperature_2m_min'][i]}℃",
            "降水概率": f"{daily.get('precipitation_probability_max', [0] * 99)[i] or 0}%",
        })
    return out


def _wttr_desc(node):
    zh = node.get("lang_zh") or []
    if zh and zh[0].get("value"):
        return zh[0]["value"]
    en = node.get("weatherDesc") or []
    return en[0].get("value", "") if en else ""


def fetch_wttr(city, days):
    """备用通道：wttr.in（自带地名解析，中文描述）。"""
    q = urllib.parse.quote(city)
    d = _http_get_json(f"https://wttr.in/{q}?format=j1&lang=zh", timeout=20)
    cur = (d.get("current_condition") or [{}])[0]
    area = (d.get("nearest_area") or [{}])[0]

    def _field(obj, key):
        arr = obj.get(key) or []
        return arr[0].get("value", "") if arr else ""

    name = _field(area, "areaName") or city
    region = " ".join(p for p in [_field(area, "country"), _field(area, "region")] if p)

    out = {
        "城市": f"{name}（{region}）" if region else name,
        "更新时间": cur.get("localObsDateTime", ""),
        "当前": {
            "天气": _wttr_desc(cur),
            "温度": f"{cur.get('temp_C')}℃",
            "体感温度": f"{cur.get('FeelsLikeC')}℃",
            "湿度": f"{cur.get('humidity')}%",
            "风": f"{WTTR_WIND.get(cur.get('winddir16Point', ''), '')} {cur.get('windspeedKmph')}km/h".strip(),
        },
        "预报": [],
        "数据源": "wttr.in（备用通道）",
    }
    for w in (d.get("weather") or [])[:days]:
        hourly = w.get("hourly") or []
        mid = hourly[len(hourly) // 2] if hourly else {}
        try:
            rain = max(int(h.get("chanceofrain", 0) or 0) for h in hourly) if hourly else 0
        except (TypeError, ValueError):
            rain = 0
        out["预报"].append({
            "日期": fmt_date(w.get("date")),
            "天气": _wttr_desc(mid),
            "最高": f"{w.get('maxtempC')}℃",
            "最低": f"{w.get('mintempC')}℃",
            "降水概率": f"{rain}%",
        })
    return out


def query_weather_raw(city, days):
    city = (city or "").strip()
    if not city:
        return {"error": "请提供城市名，例如「青岛」「北京」「上海」"}
    try:
        days = int(days)
    except (TypeError, ValueError):
        days = 3
    days = max(1, min(7, days))

    cache_key = (city, days)
    cached = _weather_cache.get(cache_key)
    if cached and time.time() - cached[0] < 600:
        return cached[1]

    err1 = None
    try:
        out = fetch_open_meteo(city, days)
        if out is None:
            return {"error": f"没找到城市「{city}」，请换个更通用的名字试试，例如「青岛」「北京」「Tokyo」"}
    except Exception as e:
        err1 = f"{type(e).__name__}: {e}"
        try:
            out = fetch_wttr(city, days)
        except Exception as e2:
            return {"error": f"天气查询失败（主通道 {err1}；备用通道 {type(e2).__name__}: {e2}）"}

    out["说明"] = "数据来自公开天气接口，仅供参考；预报最长支持7天"
    _weather_cache[cache_key] = (time.time(), out)
    return out


mcp = FastMCP(
    "weather-query",
    host=os.environ.get("MCP_HOST", "127.0.0.1"),
    port=int(os.environ.get("MCP_PORT", "8004")),
    transport_security=TransportSecuritySettings(
        allowed_hosts=(os.environ.get("MCP_ALLOWED_HOSTS") or "127.0.0.1:*,localhost:*,[::1]:*,mcp.pianam.cn,mcp.pianam.cn:*").split(","),
        allowed_origins=(os.environ.get("MCP_ALLOWED_ORIGINS") or "https://mcp.pianam.cn,https://mcp.pianam.cn:*,http://127.0.0.1:*,http://localhost:*").split(","),
    ),
)


@mcp.tool()
def query_weather(city: str, days: int = 3) -> dict:
    """查询全球城市的实时天气和未来几天预报。

    参数:
        city: 城市名，中文英文均可，例如 "青岛"、"北京"、"Tokyo"
        days: 预报天数，1 到 7，默认 3 天
    返回:
        当前天气（天气状况/温度/体感温度/湿度/风向风速）
        + 每日预报（日期/天气/最高温/最低温/降水概率）。
    数据源: Open-Meteo 公开接口（免费无需 Key），网络异常时自动切换 wttr.in。
    """
    try:
        return query_weather_raw(city, days)
    except Exception as e:
        return {"error": f"查询失败: {type(e).__name__}: {e}"}


if __name__ == "__main__":
    # 挂限流中间件：必须用 uvicorn 直接跑自定义 app——mcp.run() 内部会另建 app 实例，外挂中间件会被丢弃
    import sys
    import uvicorn
    sys.path.insert(0, str(BASE_DIR))
    from rate_limit import RateLimitMiddleware
    _app = mcp.streamable_http_app()
    _app.add_middleware(RateLimitMiddleware, limit_per_minute=60)
    uvicorn.run(_app, host=mcp.settings.host, port=mcp.settings.port, log_level=mcp.settings.log_level.lower())
