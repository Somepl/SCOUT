import hashlib
import os
import json
from datetime import datetime


def md5_hash(text):
    return hashlib.md5(text.encode("utf-8")).hexdigest()


def ensure_dir(path):
    os.makedirs(path, exist_ok=True)


def now_str():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def today_str():
    return datetime.now().strftime("%Y-%m-%d")


def load_json(filepath):
    if not os.path.exists(filepath):
        return []
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(filepath, data):
    ensure_dir(os.path.dirname(filepath))
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


import re


def _normalize_title(title):
    """归一化标题：去空格/标点/特殊字符/来源前缀，用于模糊去重"""
    if not title:
        return ""
    # 去空格
    t = re.sub(r"\s+", "", title)
    # 去常见标点
    # 去除非中文字符、字母、数字、空格以外的杂项
    t = re.sub(r"[^\w\u4e00-\u9fff\s]", "", t)
    # 去常见前缀
    prefixes = ["快讯", "午盘", "收评", "早评", "收盘", "开盘", "盘中",
                "最新", "突发", "重磅", "紧急", "独家",
                "刚刚", "晚间", "早间", "午间"]
    for p in prefixes:
        if t.startswith(p) and len(t) > len(p) + 4:
            t = t[len(p):]
            break
    return t[:60]


def deduplicate(news_list):
    """去重：先用精确MD5，再用归一化标题比较兜底"""
    exact_seen = set()
    norm_seen = set()
    result = []
    for item in news_list:
        # 精确去重（标题+内容+url）
        exact_key = md5_hash(
            (item.get("title", "") or "") +
            (item.get("content", "") or "")[:100] +
            (item.get("url", "") or "")
        )
        if exact_key not in exact_seen:
            exact_seen.add(exact_key)
            # 归一化模糊去重
            norm = _normalize_title(item.get("title", ""))
            if norm and len(norm) >= 4:
                # 检查前40字符是否有近似的
                is_dup = False
                for seen_norm in norm_seen:
                    # 如果归一化后标题互相包含，视为重复
                    if norm[:40] in seen_norm or seen_norm in norm[:40]:
                        is_dup = True
                        break
                if not is_dup:
                    norm_seen.add(norm)
                else:
                    continue  # 模糊重复，跳过
            item["_id"] = exact_key
            result.append(item)
    return result
