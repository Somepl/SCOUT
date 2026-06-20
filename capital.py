import requests
import json
import re
from datetime import datetime, timedelta
from utils import today_str, now_str

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://data.eastmoney.com/",
}


def _bypass_proxy():
    return {"http": None, "https": None}


def _fetch_json(url, params=None):
    try:
        resp = requests.get(url, params=params, headers=HEADERS,
                            timeout=15, proxies=_bypass_proxy())
        return resp.json()
    except Exception as e:
        print(f"  [资金面API失败] {e}", flush=True)
        return None


def get_northbound_flow(days=10):
    url = "https://push2.eastmoney.com/api/qt/kamt.kline/get"
    params = {
        "fields1": "f1,f2,f3,f4,f5,f6",
        "fields2": "f51,f52,f53,f54,f55",
        "klt": "101",
        "lmt": str(days),
    }
    data = _fetch_json(url, params)
    if not data or data.get("data") is None:
        return _northbound_fallback(days)

    klines = data["data"].get("klines", [])
    if not klines:
        return _northbound_fallback(days)

    result = []
    for line in klines:
        parts = line.split(",")
        if len(parts) < 5:
            continue
        date = parts[0]
        sh_net = float(parts[1]) if parts[1] else 0
        sz_net = float(parts[2]) if parts[2] else 0
        total_net = sh_net + sz_net
        result.append({
            "date": date,
            "sh_net": sh_net,
            "sz_net": sz_net,
            "total_net": total_net,
            "direction": "净流入" if total_net > 0 else "净流出",
        })

    return result


def _northbound_fallback(days=10):
    rows = []
    for i in range(min(days, 5)):
        d = (datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d")
        if i == 0:
            rows.append({"date": d, "sh_net": 0, "sz_net": 0,
                        "total_net": 0, "direction": "数据延迟"})
        else:
            rows.append({"date": d, "sh_net": 0, "sz_net": 0,
                        "total_net": 0, "direction": "暂无数据"})
    return rows


def get_margin_balance():
    url = "https://datacenter.eastmoney.com/api/data/v1/get"
    params = {
        "reportName": "RPTA_WEB_RZRQ_JJZ",
        "columns": "TRADE_DATE,SZ_RZRQYE,SH_RZRQYE,RZRQYE",
        "pageNumber": 1,
        "pageSize": 3,
        "sortTypes": "-1",
        "sortColumns": "TRADE_DATE",
        "source": "WEB",
        "client": "WEB",
    }
    data = _fetch_json(url, params)
    if not data or data.get("result") is None:
        return _margin_fallback()

    items = data.get("result", {}).get("data", [])
    if not items:
        return _margin_fallback()

    result = []
    for item in items:
        date = item.get("TRADE_DATE", "")
        total = float(item.get("RZRQYE", 0) or 0)
        sz = float(item.get("SZ_RZRQYE", 0) or 0)
        sh = float(item.get("SH_RZRQYE", 0) or 0)
        result.append({
            "date": date[:10] if len(date) > 10 else date,
            "total": total,
            "sh": sh,
            "sz": sz,
            "total_yi": round(total / 1e8, 2),
            "sh_yi": round(sh / 1e8, 2),
            "sz_yi": round(sz / 1e8, 2),
        })

    return result


def _margin_fallback():
    return [
        {"date": today_str(), "total": 0, "sh": 0, "sz": 0,
         "total_yi": 0, "sh_yi": 0, "sz_yi": 0, "note": "数据获取失败"},
    ]


def get_northbound_top10():
    url = "https://push2.eastmoney.com/api/qt/kamt.kline/get"
    params = {
        "fields1": "f1,f2,f3,f4,f5,f6,f7,f8",
        "fields2": "f51,f52,f53,f54,f55,f56,f57,f58",
        "klt": "101",
        "lmt": "1",
    }
    data = _fetch_json(url, params)
    if not data:
        return []

    klines = data.get("data", {}).get("klines", [])
    if not klines:
        return []

    parts = klines[0].split(",")
    if len(parts) < 6:
        return []

    return [
        {"date": parts[0], "沪股通(亿)": round(float(parts[1]) / 1e8, 2) if parts[1] else 0,
         "深股通(亿)": round(float(parts[2]) / 1e8, 2) if parts[2] else 0,
         "合计(亿)": round((float(parts[1]) + float(parts[2])) / 1e8, 2) if parts[1] and parts[2] else 0}
    ]


def get_capital_summary():
    result = {"time": now_str(), "northbound": [], "margin": [], "top10": []}

    print("  [资金面] 获取北向资金流向...", flush=True)
    nb = get_northbound_flow(days=5)
    result["northbound"] = nb
    if nb:
        latest = nb[0]
        print(f"    北向资金: {latest['total_net']/1e8:.2f}亿 {latest['direction']}", flush=True)

    print("  [资金面] 获取融资融券余额...", flush=True)
    mg = get_margin_balance()
    result["margin"] = mg
    if mg:
        print(f"    融资融券余额: {mg[0]['total_yi']}亿", flush=True)

    print("  [资金面] 获取沪深港通十大成交...", flush=True)
    result["top10"] = get_northbound_top10()

    return result


def calc_capital_light(capital_data):
    nb = capital_data.get("northbound", [])
    if not nb:
        return {"score": 50, "light": "⚪", "label": "资金面数据不足", "signal": "中性"}

    recent = nb[:3]
    total_net = sum(abs(r["total_net"]) for r in recent if r["total_net"])
    inflow_days = sum(1 for r in recent if r.get("total_net", 0) > 0)

    if total_net == 0:
        return {"score": 50, "light": "⚪", "label": "北向资金无明显动向", "signal": "中性"}

    ratio = inflow_days / len(recent)
    avg_net = sum(r["total_net"] for r in recent) / len(recent)

    score = 50
    if ratio >= 0.66 and avg_net > 0:
        score = 80
        label = "北向资金持续净流入，外资看多"
        signal = "利好"
    elif ratio >= 0.5 and avg_net > 0:
        score = 65
        label = "北向资金小幅净流入，偏积极"
        signal = "利好"
    elif ratio <= 0.33 and avg_net < 0:
        score = 20
        label = "北向资金持续净流出，外资看空"
        signal = "利空"
    elif ratio < 0.5 and avg_net < 0:
        score = 35
        label = "北向资金小幅净流出，偏谨慎"
        signal = "利空"
    else:
        label = "北向资金流向分歧，方向不明"
        signal = "中性"

    light = "🟢🟢🟢" if score >= 75 else \
            "🟢🟢⚪" if score >= 60 else \
            "🟢⚪⚪" if score >= 40 else \
            "⚪⚪🔴" if score >= 25 else \
            "🔴🔴🔴"

    return {"score": score, "light": light, "label": label, "signal": signal}
