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
    t = re.sub(r"[^\w\u4e00-\u9fff\s]", "", t)
    # 去常见前缀
    prefixes = ["快讯", "午盘", "收评", "早评", "收盘", "开盘", "盘中",
                "最新", "突发", "重磅", "紧急", "独家",
                "刚刚", "晚间", "早间", "午间"]
    for p in prefixes:
        if t.startswith(p) and len(t) > len(p) + 4:
            t = t[len(p):]
            break
    # 去常见的"来源"后缀
    for suffix in ["-东方财富", "-新浪财经", "-同花顺", "-证券时报",
                    "|每经网", "|财联社", "|证券时报", "|第一财经"]:
        if t.endswith(suffix):
            t = t[:-len(suffix)]
            break
    return t[:60]


def _title_char_overlap(norm1, norm2):
    """计算两个归一化标题的字符重叠率（Jaccard相似度）"""
    if not norm1 or not norm2:
        return 0.0
    s1, s2 = set(norm1), set(norm2)
    inter = s1 & s2
    union = s1 | s2
    return len(inter) / len(union) if union else 0.0


def _title_contains_ratio(short, long):
    """short 中的字符有多少比例出现在 long 中"""
    if not short or not long:
        return 0.0
    short_set = set(short)
    if len(short_set) < 3:
        return 0.0
    matched = sum(1 for c in short_set if c in long)
    return matched / len(short_set)


def deduplicate(news_list):
    """去重：先用精确MD5，再用归一化标题字符重叠兜底"""
    exact_seen = set()
    norm_seen = []  # 保留顺序，存储 (norm, raw_title)
    result = []
    for item in news_list:
        title = item.get("title", "") or ""
        content = item.get("content", "") or ""
        url = item.get("url", "") or ""

        # 精确去重（标题+内容片段+url）
        exact_key = md5_hash(title + content[:100] + url)
        if exact_key in exact_seen:
            continue
        exact_seen.add(exact_key)

        # 归一化模糊去重
        norm = _normalize_title(title)
        if norm and len(norm) >= 4:
            is_dup = False
            for seen_norm, seen_raw in norm_seen:
                # 策略1: 互相包含 → 重复
                if norm in seen_norm or seen_norm in norm:
                    is_dup = True
                    break
                # 策略2: 字符重叠率 > 85% → 同一事件
                if _title_char_overlap(norm, seen_norm) >= 0.85:
                    is_dup = True
                    break
                # 策略3: 较短标题中 >90% 字符出现在较长标题中
                short, long = (norm, seen_norm) if len(norm) <= len(seen_norm) else (seen_norm, norm)
                if len(short) >= 6 and _title_contains_ratio(short, long) >= 0.90:
                    is_dup = True
                    break
            if is_dup:
                continue  # 模糊重复，跳过
            norm_seen.append((norm, title))

        item["_id"] = exact_key
        result.append(item)
    return result
