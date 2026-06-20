import requests
from bs4 import BeautifulSoup
import xml.etree.ElementTree as ET
import time
from datetime import datetime
from utils import now_str


def fetch_url(url, timeout=15, retries=2, verify=True):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    for attempt in range(retries):
        try:
            kwargs = {"headers": headers, "timeout": timeout}
            if not verify:
                kwargs["verify"] = False
            import warnings
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                resp = requests.get(url, **kwargs)
            resp.encoding = "utf-8"
            return resp.text
        except Exception as e:
            if attempt < retries - 1:
                print(f"  [重试] {url} ({attempt+1}/{retries}) - {e}", flush=True)
                time.sleep(2)
                continue
            print(f"  [失败] {url} - {e}", flush=True)
            return None


def _extract_links_generic(html, source_name, domain_filter, min_length=15, max_items=50):
    items = []
    if not html:
        return items
    soup = BeautifulSoup(html, "lxml")
    seen = set()
    exclude_keywords = ["导航", "登录", "注册", "搜索", "广告", "视频", "图片", "客户端"]
    for a in soup.select("a[href]"):
        title = a.get_text(strip=True)
        href = a.get("href", "")
        if len(title) < min_length:
            continue
        if any(k in title for k in exclude_keywords):
            continue
        if domain_filter and domain_filter not in href:
            continue
        if title in seen:
            continue
        seen.add(title)
        if href.startswith("//"):
            href = "https:" + href
        elif href.startswith("/"):
            href = "https://" + domain_filter + href
        elif not href.startswith("http"):
            continue
        items.append({
            "title": title,
            "content": title,
            "source": source_name,
            "url": href,
            "publish_time": now_str(),
            "category": "news"
        })
    return items[:max_items]


def parse_eastmoney(html):
    items = []
    if not html:
        return items
    soup = BeautifulSoup(html, "lxml")
    seen = set()
    selectors = [
        ".newsList li a",
        ".list-wrap li a",
        ".article-list li a",
        ".news-item a",
        ".title a",
        "li a"
    ]
    links = []
    for sel in selectors:
        links = soup.select(sel)
        if links:
            break
    for a in links:
        title = a.get_text(strip=True)
        if len(title) < 5 or title in seen:
            continue
        seen.add(title)
        href = a.get("href", "")
        if href and not href.startswith("http"):
            href = "https://finance.eastmoney.com" + href
        content = title
        parent = a.parent
        if parent:
            desc_el = parent.select_one(".desc, .abstract, p")
            if desc_el:
                content = desc_el.get_text(strip=True)
        items.append({
            "title": title,
            "content": content,
            "source": "东方财富",
            "url": href,
            "publish_time": now_str(),
            "category": "news"
        })
    return items


def parse_sina(html):
    return _extract_links_generic(html, "新浪财经", "sina.com.cn", min_length=15, max_items=80)


def parse_rss(content):
    items = []
    if not content:
        return items
    try:
        root = ET.fromstring(content)
        for item in root.iter("item"):
            title_el = item.find("title")
            link_el = item.find("link")
            desc_el = item.find("description")
            if title_el is None or title_el.text is None:
                continue
            title = title_el.text.strip()
            link = link_el.text.strip() if link_el is not None and link_el.text else ""
            desc = desc_el.text.strip() if desc_el is not None and desc_el.text else title
            items.append({
                "title": title,
                "content": desc,
                "source": "RSS",
                "url": link,
                "publish_time": now_str(),
                "category": "news"
            })
        return items
    except ET.ParseError:
        pass
    try:
        root = ET.fromstring(content)
        ns = "{http://www.w3.org/2005/Atom}"
        for entry in root.iter(f"{ns}entry"):
            title_el = entry.find(f"{ns}title")
            link_el = entry.find(f"{ns}link")
            if title_el is None or title_el.text is None:
                continue
            title = title_el.text.strip()
            link = link_el.get("href", "") if link_el is not None else ""
            items.append({
                "title": title,
                "content": title,
                "source": "RSS",
                "url": link,
                "publish_time": now_str(),
                "category": "news"
            })
    except Exception:
        pass
    return items


def parse_10jqka(html, fallback_url="https://www.10jqka.com.cn/"):
    items = _extract_links_generic(html, "同花顺", "10jqka", min_length=15, max_items=50)
    if items:
        return items
    print("  [同花顺] 主URL无结果，尝试备选URL...", flush=True)
    try:
        fallback_html = fetch_url(fallback_url, timeout=20, verify=False)
        if fallback_html:
            items2 = _extract_links_generic(fallback_html, "同花顺", "10jqka", min_length=15, max_items=50)
            if items2:
                return items2
    except Exception:
        pass
    print("  [同花顺] 备选URL也无数据，跳过同花顺", flush=True)
    return []


def parse_stcn(html):
    return _extract_links_generic(html, "证券时报", "stcn.com", min_length=15, max_items=50)


PARSER_MAP = {
    "eastmoney": parse_eastmoney,
    "sina": parse_sina,
    "rss": parse_rss,
    "10jqka": parse_10jqka,
    "stcn": parse_stcn,
}


def collect_from_source(source_config):
    name = source_config["name"]
    url = source_config["url"]
    parser_key = source_config.get("parser", "")
    fallback_url = source_config.get("fallback_url", "")
    print(f"  正在采集: {name} ...", flush=True)
    verify = parser_key != "10jqka"
    html = fetch_url(url, verify=verify)
    if not html and fallback_url:
        print(f"  [重试] {name} 尝试备选URL...", flush=True)
        html = fetch_url(fallback_url, timeout=20, verify=verify)
    if not html:
        print(f"  [失败] {name} 无返回", flush=True)
        return []
    if parser_key == "10jqka":
        items = parse_10jqka(html, fallback_url=fallback_url)
    else:
        parser_fn = PARSER_MAP.get(parser_key)
        if not parser_fn:
            print(f"  [跳过] {name} 未找到解析器: {parser_key}", flush=True)
            return []
        items = parser_fn(html)
    print(f"  [完成] {name} 采集到 {len(items)} 条", flush=True)
    return items


def collect_all(sources):
    all_news = []
    for src in sources:
        items = collect_from_source(src)
        all_news.extend(items)
    return all_news
