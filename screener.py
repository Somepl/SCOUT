import re
import time
from openai import OpenAI
from config import AI_API_KEY, AI_BASE_URL, AI_MODEL

SECTOR_STOCKS = {
    "白酒": ["600519", "000858", "000568", "600809", "002304"],
    "银行": ["601398", "601939", "601288", "600036", "000001"],
    "保险": ["601318", "601628", "601601", "601336"],
    "证券": ["600030", "601688", "600837", "601066", "002736"],
    "新能源汽车": ["002594", "300750", "002460", "002466", "300014"],
    "新能源汽车产业链": ["002594", "300750", "002460", "002466", "300014"],
    "锂电池": ["300750", "002460", "002466", "300014", "300457"],
    "光伏": ["601012", "600438", "688599", "688223", "600089"],
    "半导体": ["688981", "002371", "603501", "688012", "600703"],
    "芯片": ["688981", "002371", "603501", "688012", "600703"],
    "人工智能": ["688111", "002230", "300624", "603019", "688256"],
    "AI": ["688111", "002230", "300624", "603019", "688256"],
    "医药": ["600276", "300760", "000538", "300015", "603259"],
    "医疗器械": ["300760", "688271", "300529", "300896"],
    "创新药": ["600276", "603259", "300122", "002821"],
    "房地产": ["000002", "001979", "600048", "600383", "600325"],
    "煤炭": ["601088", "600188", "601225", "600985", "601898"],
    "电力": ["600900", "600011", "601985", "600886", "600025"],
    "军工": ["600760", "002179", "600893", "600862", "600765"],
    "消费电子": ["002475", "601138", "000725", "002241", "300433"],
    "食品饮料": ["600887", "002714", "300498", "000895", "603288"],
    "家电": ["000333", "000651", "600690", "002032", "000100"],
    "通信": ["600941", "601728", "600050", "603236", "300308"],
    "基建": ["601668", "601390", "601186", "601800", "600585"],
    "旅游": ["601888", "000888", "002707", "300144"],
    "电商": ["002024", "601113", "600859", "601933"],
    "物流": ["002352", "600233", "601006", "002120"],
    "钢铁": ["600019", "000708", "600010", "000932"],
    "有色金属": ["601899", "600547", "603993", "000630", "600362"],
    "化工": ["601857", "600028", "600309", "000830", "002601"],
    "互联网": ["300059", "002555", "600570", "300033", "300418"],
    "计算机": ["688111", "603019", "000977", "600588", "002415"],
    "软件": ["688111", "600570", "300033", "002230", "603019"],
    "传媒": ["300413", "002027", "300251", "603000", "600637"],
    "教育": ["002607", "300192", "300688", "600661"],
    "游戏": ["002602", "300315", "603444", "002624", "300052"],
    "数字货币": ["002152", "300579", "300468", "600570"],
    "机器人": ["300124", "002747", "300276", "688017", "603960"],
    "氢能源": ["600989", "300471", "002274", "600860"],
    "储能": ["300274", "300763", "002518", "688063"],
    "智能电网": ["600406", "601222", "002028", "603556"],
    "风电": ["300443", "601615", "002202", "600875"],
    "核能核电": ["601985", "601611", "601899", "000777"],
    "免税": ["601888", "000888", "603069"],
    "信创": ["688111", "600536", "000977", "603019", "300624"],
    "国产替代": ["002371", "688981", "603501", "000977", "600536"],
    "中特估": ["601398", "601939", "601088", "600900", "601668"],
    "一带一路": ["601668", "601390", "601186", "600970", "601618"],
    "碳中和": ["300750", "601012", "600438", "002459", "300274"],
    "数字经济": ["688111", "600570", "300059", "002230", "300033"],
    "新质生产力": ["300124", "002230", "688981", "688111", "603019"],
    "低空经济": ["002151", "300696", "002389", "300123"],
    "飞行汽车": ["002151", "300696", "002389", "300123"],
    "银发经济": ["300015", "000538", "600276", "300896"],
    "消费复苏": ["601888", "000858", "600519", "000333", "600887"],
    "出口出海": ["002475", "601138", "000333", "600690", "300750"],
    "沪深300": ["600519", "300750", "000333", "600036", "601318"],
    "中证500": [],
}

ALL_SECTOR_KEYS = list(SECTOR_STOCKS.keys())

SECTOR_ALIASES = {}
for key in ALL_SECTOR_KEYS:
    SECTOR_ALIASES[key] = [key]
    for word in key.replace(" ", "").split():
        if len(word) >= 2 and word != key:
            SECTOR_ALIASES[key].append(word)

SECTOR_CACHE = {}


def match_sectors(free_text):
    matched = set()
    text = free_text.strip()
    if not text:
        return []
    text_lower = text.lower()
    for sector in ALL_SECTOR_KEYS:
        if sector.lower() in text_lower:
            matched.add(sector)
            continue
        for alias in SECTOR_ALIASES.get(sector, []):
            if alias.lower() in text_lower:
                matched.add(sector)
                break
    return list(matched)


def collect_hot_sectors(news_results):
    sector_mentions = {}
    sector_sentiment = {}

    for r in news_results:
        a = r.get("analysis", {})
        sectors = a.get("affected_sectors", [])
        sentiment = a.get("market_sentiment", "中性")
        confidence = a.get("confidence", "低")
        impact = a.get("impact_level", "轻微")

        weight = {"高": 3, "中": 2, "低": 1}.get(confidence, 1)
        impact_w = {"重大": 3, "中等": 2, "轻微": 1}.get(impact, 1)
        w = weight * impact_w

        for s in sectors:
            matched = match_sectors(s)
            for m in matched:
                sector_mentions[m] = sector_mentions.get(m, 0) + 1
                current = sector_sentiment.get(m, 0)
                if sentiment == "利好":
                    sector_sentiment[m] = current + w
                elif sentiment == "利空":
                    sector_sentiment[m] = current - w

    hot = []
    for sector, mentions in sorted(sector_mentions.items(), key=lambda x: x[1], reverse=True):
        sentiment_score = sector_sentiment.get(sector, 0)
        hot.append({
            "sector": sector,
            "mentions": mentions,
            "sentiment_score": sentiment_score,
            "sentiment": "利好" if sentiment_score > 0 else ("利空" if sentiment_score < 0 else "中性"),
        })

    return hot


def screen_by_sector(hot_sectors, max_stocks=15):
    candidates = []
    seen_codes = set()
    priority = 0

    for hs in hot_sectors:
        if hs["sentiment"] == "利空":
            continue
        stocks = SECTOR_STOCKS.get(hs["sector"], [])
        for code in stocks:
            if code not in seen_codes:
                seen_codes.add(code)
                candidates.append({
                    "code": code,
                    "source_sectors": [hs["sector"]],
                    "priority": priority,
                })
            else:
                for c in candidates:
                    if c["code"] == code:
                        c["source_sectors"].append(hs["sector"])

        if len(candidates) >= max_stocks:
            break

        priority += 1

    return candidates[:max_stocks]


AI_SUGGEST_PROMPT = """你是一名A股分析师。基于今日财经新闻中提到的热点行业，推荐最相关的A股股票。

今日新闻热点摘要：
{news_summary}

以严格JSON格式返回：
{{
  "stocks": [
    {{"code": "600519", "name": "贵州茅台", "reason": "新闻中提到XX政策利好白酒行业，茅台作为龙头受益"}},
    ...
  ]
}}

要求：
1. 必须是真实存在的A股代码（沪市6开头、深市0/3开头，非ST）
2. 关联到新闻内容，说明推荐理由与新闻的关联
3. 总共不超过{max_stocks}只
4. 只输出JSON，不输出额外文字"""


def _extract_stock_codes_from_analysis(news_results):
    seen = set()
    candidates = []
    for r in news_results:
        codes = r.get("analysis", {}).get("stock_codes", [])
        if not codes:
            continue
        for code in codes:
            code = code.strip()
            if not code:
                continue
            if not (code.startswith("6") or code.startswith("0") or code.startswith("3")):
                continue
            if len(code) != 6:
                continue
            if code not in seen:
                seen.add(code)
                candidates.append({
                    "code": code,
                    "source_sectors": r.get("analysis", {}).get("affected_sectors", [])[:2],
                    "priority": 0,
                })
    return candidates


def ai_suggest_stocks(client, news_results, max_stocks=15, retries=2):
    if not client:
        return []

    summary_parts = []
    for r in news_results[:10]:
        a = r.get("analysis", {})
        title = r.get("news", {}).get("title", "")
        sectors = a.get("affected_sectors", [])
        sentiment = a.get("market_sentiment", "")
        summary_parts.append(f"- {title} [板块:{'/'.join(sectors)} 情绪:{sentiment}]")

    news_summary = "\n".join(summary_parts)
    if not news_summary:
        return []

    prompt = AI_SUGGEST_PROMPT.format(
        news_summary=news_summary,
        max_stocks=max_stocks,
    )

    for attempt in range(retries):
        try:
            resp = client.chat.completions.create(
                model=AI_MODEL,
                messages=[
                    {"role": "system", "content": "你是一个A股分析助手。"},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.3,
                max_tokens=800,
                timeout=30,
            )
            text = resp.choices[0].message.content.strip()
            if text.startswith("```"):
                start = text.find("{")
                end = text.rfind("}")
                if start != -1 and end != -1:
                    text = text[start:end + 1]
            import json
            try:
                data = json.loads(text)
                stocks = data.get("stocks", [])
                result = []
                for s in stocks:
                    code = str(s.get("code", "")).strip()
                    if code and (code.startswith("6") or code.startswith("0") or code.startswith("3")):
                        if code not in [r["code"] for r in result]:
                            result.append({
                                "code": code,
                                "source_sectors": ["AI推荐"],
                                "priority": 0,
                            })
                return result[:max_stocks]
            except (json.JSONDecodeError, TypeError):
                if attempt < retries - 1:
                    time.sleep(2)
                    continue
                return []
        except Exception as e:
            print(f"  [AI荐股失败] 第{attempt+1}次: {e}", flush=True)
            if attempt < retries - 1:
                time.sleep(3)
                continue
            return []


def discover_stocks(news_results, max_stocks=15):
    seen = set()
    candidates = []

    print("  [筛选] 从新闻分析中提取相关股票代码...", flush=True)
    direct = _extract_stock_codes_from_analysis(news_results)
    for c in direct:
        if c["code"] not in seen:
            seen.add(c["code"])
            candidates.append(c)
    if direct:
        print(f"    新闻直接提到: {', '.join(c['code'] for c in direct)}", flush=True)

    hot = collect_hot_sectors(news_results)
    top_sectors = [hs for hs in hot if hs["sentiment_score"] > 0] or hot[:5]

    if top_sectors:
        parts = []
        for h in top_sectors[:8]:
            parts.append(f"{h['sector']}({h['sentiment']})")
        print(f"  [筛选] 热点板块: {', '.join(parts)}", flush=True)

    client = None
    if AI_API_KEY and AI_API_KEY not in ("your-api-key-here", ""):
        client = OpenAI(api_key=AI_API_KEY, base_url=AI_BASE_URL)

    if client:
        print("  [筛选] AI根据新闻推荐相关股票...", flush=True)
        ai_stocks = ai_suggest_stocks(client, news_results, max_stocks)
        for s in ai_stocks:
            if s["code"] not in seen:
                seen.add(s["code"])
                candidates.append(s)
        if ai_stocks:
            print(f"    AI推荐: {', '.join(s['code'] for s in ai_stocks[:8])}", flush=True)

    if not candidates and top_sectors:
        print("  [筛选] 使用板块映射补充候选股...", flush=True)
        for hs in top_sectors[:5]:
            if hs["sentiment"] == "利空":
                continue
            stocks = SECTOR_STOCKS.get(hs["sector"], [])
            for code in stocks:
                if code not in seen:
                    seen.add(code)
                    candidates.append({
                        "code": code,
                        "source_sectors": [hs["sector"]],
                        "priority": 0,
                    })
            if len(candidates) >= max_stocks:
                break

    print(f"  [筛选] 共发现 {len(candidates)} 只相关股票: {', '.join(c['code'] for c in candidates[:8])}", flush=True)

    return candidates[:max_stocks], hot
