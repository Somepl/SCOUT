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


def deduplicate(news_list):
    seen = set()
    result = []
    for item in news_list:
        key = md5_hash(item.get("title", "") + item.get("content", "")[:100] + item.get("url", ""))
        if key not in seen:
            seen.add(key)
            item["_id"] = key
            result.append(item)
    return result
