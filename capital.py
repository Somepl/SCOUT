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


def _extract_klines(data_result):
    """从API返回中提取合并的北向资金数据行，兼容新旧两种格式。
    
    旧格式: data_result["klines"] — 每行 "date,sh_val,sz_val,sh_val2,sz_val2"
    新格式: data_result["hk2sh"] + data_result["hk2sz"] — 各市场独立数组
    """
    if not data_result:
        return []
    if "klines" in data_result:
        return data_result.get("klines", [])
    # 新格式：将 hk2sh 和 hk2sz 按日期合并为旧格式行
    hk2sh = data_result.get("hk2sh", [])
    hk2sz = data_result.get("hk2sz", [])
    merged = []
    max_len = max(len(hk2sh), len(hk2sz))
    for i in range(max_len):
        sh_parts = hk2sh[i].split(",") if i < len(hk2sh) else []
        sz_parts = hk2sz[i].split(",") if i < len(hk2sz) else []
        date = sh_parts[0] if len(sh_parts) > 0 else (sz_parts[0] if len(sz_parts) > 0 else "")
        sh_val = sh_parts[1] if len(sh_parts) > 1 else "0"
        sz_val = sz_parts[1] if len(sz_parts) > 1 else "0"
        merged.append(f"{date},{sh_val},{sz_val},0,0")
    return merged


def _is_non_trading_day(data_result):
    """检查API返回的数据是否全零（非交易日特征）"""
    klines = _extract_klines(data_result)
    if not klines:
        return False
    all_zero = True
    for line in klines[:3]:
        parts = line.split(",")
        if len(parts) >= 3:
            if parts[1] or parts[2]:
                all_zero = False
                break
    return all_zero


def _find_last_valid_entry(entries):
    """从数据列表末尾向前找第一条 note='ok' 的记录"""
    for item in reversed(entries):
        if item.get("note") == "ok":
            return item
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

    klines = _extract_klines(data["data"])
    if not klines:
        return _northbound_fallback(days)

    # 检测非交易日（全零数据）
    is_off_day = _is_non_trading_day(data["data"])

    result = []
    for line in klines:
        parts = line.split(",")
        if len(parts) < 3:
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
            "direction": "净流入" if total_net > 0 else ("净流出" if total_net < 0 else ""),
            "note": "ok" if (sh_net or sz_net) else "off_day",
        })

    # 若非交易日且无有效数据，用最近交易日数据填充
    if is_off_day:
        from datetime import timedelta
        # 再往前拉取更多天找有效数据
        for extra in [20, 30]:
            more_data = _fetch_json(url, {**params, "lmt": str(days + extra)})
            if not more_data or more_data.get("data") is None:
                continue
            more_klines = _extract_klines(more_data["data"])
            for line in more_klines:
                parts = line.split(",")
                if len(parts) >= 3 and parts[1]:
                    found_date = parts[0]
                    found_sh = float(parts[1]) if parts[1] else 0
                    found_sz = float(parts[2]) if parts[2] else 0
                    total = found_sh + found_sz
                    if total != 0:
                        # 在结果头部插入最近有效交易日数据
                        result.insert(0, {
                            "date": found_date,
                            "sh_net": found_sh,
                            "sz_net": found_sz,
                            "total_net": total,
                            "direction": "净流入" if total > 0 else "净流出",
                            "note": "last_trading_day",
                        })
                        break
            if len(result) > 0 and result[0].get("note") != "off_day":
                break

    return result


def _northbound_fallback(days=10):
    rows = []
    for i in range(min(days, 5)):
        d = (datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d")
        rows.append({"date": d, "sh_net": 0, "sz_net": 0,
                    "total_net": 0, "direction": "",
                    "note": "data_failed"})
    return rows


def get_margin_balance():
    url = "https://datacenter.eastmoney.com/api/data/v1/get"

    # 尝试多种参数组合（API 格式可能变化）
    param_sets = [
        {
            "reportName": "RPTA_WEB_RZRQ_JJZ",
            "columns": "TRADE_DATE,SZ_RZRQYE,SH_RZRQYE,RZRQYE",
            "pageNumber": 1, "pageSize": 3,
            "sortTypes": "-1", "sortColumns": "TRADE_DATE",
        },
        {
            "reportName": "RPTA_WEB_RZRQ_JJZ",
            "columns": "ALL",
            "pageNumber": 1, "pageSize": 3,
            "sortTypes": "-1", "sortColumns": "TRADE_DATE",
        },
    ]

    for params in param_sets:
        data = _fetch_json(url, params)
        if data and data.get("result") is not None:
            items = data.get("result", {}).get("data", [])
            if items:
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
                        "note": "ok" if total else "off_day",
                    })
                return result

    return _margin_fallback()


def _margin_fallback():
    return [
        {"date": today_str(), "total": 0, "sh": 0, "sz": 0,
         "total_yi": 0, "sh_yi": 0, "sz_yi": 0, "note": "data_failed"},
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

    klines = _extract_klines(data.get("data", {}))
    if not klines:
        return []

    parts = klines[0].split(",")
    if len(parts) < 3:
        return []

    sh_val = float(parts[1]) if parts[1] else 0
    sz_val = float(parts[2]) if parts[2] else 0

    return [
        {"date": parts[0], "沪股通(亿)": round(sh_val / 1e8, 2),
         "深股通(亿)": round(sz_val / 1e8, 2),
         "合计(亿)": round((sh_val + sz_val) / 1e8, 2)}
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
    top10 = get_northbound_top10()
    for item in top10:
        item.setdefault("note", "ok")
    result["top10"] = top10

    return result


def _has_real_data(items):
    for item in items:
        note = item.get("note", "")
        if note not in ("data_failed", "off_day"):
            return True
    return False


def _has_off_day_data(items):
    """检查是否只有非交易日数据但存在最近交易日记录"""
    for item in items:
        if item.get("note") == "last_trading_day":
            return True
    return False


def calc_capital_light(capital_data):
    nb = capital_data.get("northbound", [])
    if not nb or not _has_real_data(nb):
        return {"score": 50, "light": "⚪", "label": "资金面数据暂缺", "signal": "中性"}

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
