import json
import time
import re
from openai import OpenAI
from config import AI_API_KEY, AI_BASE_URL, AI_MODEL


SYSTEM_PROMPT = """你是一名A股分析师。分析每条新闻，按格式输出：

event_type: 政策利好/政策利空/行业利好/行业利空/公司利好/公司利空/外围市场/中性消息
confidence: 高/中/低
reason: 判断理由
sectors: 影响的行业板块（逗号分隔）
concept: 影响的概念题材（逗号分隔）
stock_codes: 新闻中明确提到的A股代码（逗号分隔，如"中信证券"对应600030,"茅台"对应600519；多个用逗号分隔；没有就填"无"）
impact_level: 重大/中等/轻微
time_horizon: 短期/中期/长期
sentiment: 利好/利空/中性
advice: 买入/观望/卖出/关注
advice_reason: 建议理由

示例：
新闻"贵州茅台2024年净利润增长15%" → stock_codes:600519
新闻"宁德时代与特斯拉签订供货协议" → stock_codes:300750
新闻"中信证券、华泰证券双双涨超3%" → stock_codes:600030,601688
新闻"美联储加息预期升温" → stock_codes:无

注意：
1. 有实质内容的新闻必须明确判断利好或利空
2. stock_codes 只填新闻中明确提到的公司对应的A股代码，不能凭空编造
3. 如果是宏观政策或行业整体新闻，没有明确提到的公司就填"无"
4. stock_codes **必须填写**（至少填"无"），每条分析都必须包含此字段"""


USER_TEMPLATE = """新闻标题：{title}
新闻来源：{source}
新闻内容：{content}"""


DASHBOARD_PROMPT = """你是一名A股资深交易员。请基于以下个股的行情数据，结合市场阶段和合规要求，输出一份完整的交易决策仪表盘。

必须以严格JSON格式输出，结构如下：
{
  "core_conclusion": {
    "signal": "强烈买入/买入/持有/观望/卖出/强烈卖出",
    "confidence": "高/中/低",
    "trading_advisor_rating": "★★★★★/★★★★☆/★★★☆☆/★★☆☆☆/★☆☆☆☆",
    "market_phase": "盘前/盘中/午间/盘后/非交易",
    "summary": "一句话核心结论",
    "risk_warning": "风险提示"
  },
  "data_perspective": {
    "trend": {
      "judgment": "多头/空头/震荡",
      "strength": 数值,
      "ma_alignment": "均线排列描述",
      "bias_ma5": 乖离率数值,
      "bias_ma10": 乖离率数值,
      "bias_ma20": 乖离率数值
    },
    "volume": {
      "judgment": "放量上涨/缩量回调/放量下跌/缩量上涨/量能正常",
      "ratio": 数值,
      "analysis": "量价分析描述"
    },
    "macd": {
      "status": "零轴上金叉/金叉/多头/死叉/空头/中性",
      "signal": "信号描述",
      "dif": 数值,
      "dea": 数值,
      "bar": 数值
    },
    "rsi": {
      "rsi_6": 数值,
      "rsi_12": 数值,
      "rsi_24": 数值,
      "status": "超买/强势买入/中性/弱势/超卖",
      "signal": "信号描述"
    },
    "support_resistance": {
      "support_levels": [支撑位列表],
      "resistance_levels": [阻力位列表],
      "nearest_support": 最近支撑位,
      "nearest_resistance": 最近阻力位
    }
  },
  "battle_plan": {
    "action": "买入/加仓/持有/减仓/卖出/观望",
    "entry_plan": {
      "ideal_entry": "理想买入价位及条件",
      "secondary_entry": "次优买入价位及条件",
      "stop_loss": "止损价位及理由"
    },
    "take_profit": {
      "tp1": "第一止盈位",
      "tp2": "第二止盈位",
      "tp3": "第三止盈位"
    },
    "position": {
      "suggested_position": "仓位建议（如：总资金x%）",
      "position_management": "分仓策略描述"
    },
    "risk_control": {
      "max_loss": "最大可接受亏损",
      "special_risks": ["风险列表明细"]
    }
  }
}

输出要求：
1. 只输出JSON，不要额外的文字
2. 数据偏向谨慎，宁可低分不可追高
3. battle_plan中的entry必须明确价格区间
4. stop_loss必须给出具体价格
5. position必须给出具体仓位百分比"""


def get_client():
    if not AI_API_KEY or AI_API_KEY in ("your-api-key-here", ""):
        return None
    return OpenAI(api_key=AI_API_KEY, base_url=AI_BASE_URL)


def _parse_kv_output(text):
    result = {
        "event_type": "中性消息",
        "confidence": "低",
        "reason": "",
        "affected_sectors": [],
        "affected_concept": [],
        "stock_codes": [],
        "impact_level": "轻微",
        "time_horizon": "短期",
        "market_sentiment": "中性",
        "advice": "观望",
        "advice_reason": "",
    }
    if not text:
        return result
    for line in text.strip().split("\n"):
        line = line.strip()
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        key = key.strip().lower().replace(" ", "_")
        value = value.strip()
        if not value:
            continue
        if key == "event_type":
            result["event_type"] = value
        elif key == "confidence":
            result["confidence"] = value
        elif key == "reason":
            result["reason"] = value
        elif key == "sectors":
            result["affected_sectors"] = [s.strip() for s in re.split(r'[,，、]', value) if s.strip()]
        elif key == "concept":
            result["affected_concept"] = [s.strip() for s in re.split(r'[,，、]', value) if s.strip()]
        elif key == "stock_codes":
            raw = [s.strip() for s in re.split(r'[,，、]', value) if s.strip()]
            result["stock_codes"] = [s for s in raw if s.replace(" ","") != "无" and s.replace(" ","") != ""]
        elif key == "impact_level":
            result["impact_level"] = value
        elif key == "time_horizon":
            result["time_horizon"] = value
        elif key == "sentiment":
            result["market_sentiment"] = value
        elif key == "advice":
            result["advice"] = value
        elif key == "advice_reason":
            result["advice_reason"] = value
    return result


def _try_json(text):
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        start = -1
        end = len(lines)
        for i, line in enumerate(lines):
            stripped = line.strip()
            if stripped.startswith("```"):
                if start == -1:
                    start = i
                else:
                    end = i
                    break
        text = "\n".join(lines[start+1:end]).strip()
    text = text.strip()
    if not (text.startswith("{") and text.endswith("}")):
        return None
    try:
        data = json.loads(text)
        if not isinstance(data, dict):
            return None
        key_map = {
            "event_type": "event_type",
            "confidence": "confidence",
            "reason": "reason",
            "sectors": "affected_sectors",
            "concept": "affected_concept",
            "stock_codes": "stock_codes",
            "impact_level": "impact_level",
            "time_horizon": "time_horizon",
            "sentiment": "market_sentiment",
            "advice": "advice",
            "advice_reason": "advice_reason",
        }
        result = _parse_kv_output("")
        for json_key, result_key in key_map.items():
            if json_key not in data:
                continue
            val = data[json_key]
            if result_key in ("affected_sectors", "affected_concept", "stock_codes"):
                if isinstance(val, list):
                    result[result_key] = [str(s).strip() for s in val if str(s).strip()]
                elif isinstance(val, str):
                    result[result_key] = [s.strip() for s in re.split(r'[,，、]', val) if s.strip()]
            elif isinstance(val, str):
                result[result_key] = val
        result["stock_codes"] = [s for s in result["stock_codes"] if s.replace(" ","") != "无" and s.replace(" ","") != ""]
        return result
    except (json.JSONDecodeError, TypeError):
        return None


def analyze_single_news(client, title, source, content, retries=2):
    for attempt in range(retries):
        try:
            resp = client.chat.completions.create(
                model=AI_MODEL,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": USER_TEMPLATE.format(
                        title=title, source=source, content=content
                    )},
                ],
                temperature=0.3,
                max_tokens=800,
            )
            text = resp.choices[0].message.content.strip()
            result = _try_json(text)
            if not result:
                result = _parse_kv_output(text)
            return result
        except Exception as e:
            if attempt < retries - 1:
                time.sleep(2)
                continue
            return {
                "event_type": "中性消息",
                "confidence": "低",
                "reason": f"AI分析失败: {str(e)}",
                "affected_sectors": [],
                "affected_concept": [],
                "stock_codes": [],
                "impact_level": "轻微",
                "time_horizon": "短期",
                "market_sentiment": "中性",
                "advice": "观望",
                "advice_reason": "AI分析异常，建议人工核实"
            }


def analyze_news_batch(news_list, max_items=30):
    client = get_client()
    if not client:
        return mark_no_api(news_list[:max_items])

    results = []
    batch = news_list[:max_items]
    total = len(batch)
    for i, item in enumerate(batch):
        print(f"  分析进度: {i+1}/{total} - {item['title'][:30]}...", flush=True)
        analysis = analyze_single_news(
            client,
            item["title"],
            item["source"],
            item["content"]
        )
        results.append({
            "news": item,
            "analysis": analysis
        })
        time.sleep(0.5)
    return results


def build_dashboard_prompt(m):
    return f"""股票：{m['name']}({m['code']})
当前价：{m['price']}  涨跌幅：{m['change_pct']}%
今开：{m['open']}  最高：{m['high']}  最低：{m['low']}  昨收：{m['prev_close']}
成交量：{m['volume']}  成交额：{m['amount']}

=== 均线系统 ===
MA5={m['ma5']:.2f}  MA10={m['ma10']:.2f}  MA20={m['ma20']:.2f}  MA60={m.get('ma60', 0):.2f}
均线排列：{m['ma_alignment']}
趋势判断：{m['trend']}  趋势强度：{m['trend_strength']}
乖离率：MA5={m['bias_ma5']:.1f}%  MA10={m['bias_ma10']:.1f}%  MA20={m['bias_ma20']:.1f}%

=== 量价分析 ===
量能状态：{m['volume_status']}  量比：{m['volume_ratio']:.2f}
量能分析：{m['volume_trend']}

=== MACD ===
DIF={m['macd_dif']:.3f}  DEA={m['macd_dea']:.3f}  BAR={m['macd_bar']:.3f}
状态：{m['macd_status']}  MACD信号：{m['macd_signal']}

=== RSI ===
RSI6={m.get('rsi_6', 50):.1f}  RSI12={m.get('rsi_12', 50):.1f}  RSI24={m.get('rsi_24', 50):.1f}
状态：{m['rsi_status']}  RSI信号：{m['rsi_signal']}

=== 支撑阻力 ===
支撑位(MA5靠不靠近)：{'是' if m.get('support_ma5') else '否'}
支撑位(MA10靠不靠近)：{'是' if m.get('support_ma10') else '否'}
支撑水平：{', '.join(str(l) for l in m.get('support_levels', [])) or '未确认'}
阻力水平：{', '.join(str(l) for l in m.get('resistance_levels', [])) or '未确认'}

=== 技术评分 ===
综合评分：{m['score']}/100
信号：{m['signal']}
信号理由：{'；'.join(m['signal_reasons'])}
风险因素：{'；'.join(m['risk_factors']) or '暂无'}

注意：评分>=75为强烈买入，60-74为买入，45-59为持有，30-44为观望，<30为卖出"""


def _parse_dashboard_json(text):
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        start = -1
        end = len(lines)
        for i, line in enumerate(lines):
            if line.strip().startswith("```"):
                if start == -1:
                    start = i
                else:
                    end = i
                    break
        text = "\n".join(lines[start+1:end])

    text = text.strip()
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1:
        text = text[start:end+1]

    try:
        return json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return None


def _stabilize_decision(dashboard):
    if not dashboard or "core_conclusion" not in dashboard:
        return dashboard
    cc = dashboard["core_conclusion"]
    action = dashboard.get("battle_plan", {}).get("action", "观望")

    rule_score = 50
    if cc.get("signal") in ("强烈买入", "买入"):
        rule_score = 80
    elif cc.get("signal") == "持有":
        rule_score = 55
    elif cc.get("signal") in ("观望",):
        rule_score = 40
    elif cc.get("signal") in ("卖出", "强烈卖出"):
        rule_score = 20

    upgrade = False
    downgrade = False

    if action in ("买入", "加仓") and cc.get("signal") in ("观望", "卖出", "强烈卖出"):
        downgrade = True
    if action in ("卖出", "减仓", "观望") and cc.get("signal") in ("强烈买入",):
        upgrade = True

    if downgrade:
        dashboard["battle_plan"]["action"] = "观望"
        cc["signal"] = "观望"
        cc["trading_advisor_rating"] = "★★★☆☆"
        cc["summary"] += " [经决策稳定化审核，下调信号级别]"
    elif upgrade:
        dashboard["battle_plan"]["action"] = "买入"
        cc["signal"] = "买入"
        cc["trading_advisor_rating"] = "★★★★☆"
        cc["summary"] += " [经决策稳定化审核，上调信号级别]"

    if action in ("买入", "加仓"):
        plan = dashboard["battle_plan"]
        if not plan.get("entry_plan", {}).get("stop_loss"):
            plan["entry_plan"]["stop_loss"] = "未设置止损，建议至少设置-3%~-5%止损"
        if not plan.get("take_profit"):
            plan["take_profit"] = {"tp1": "未设置", "tp2": "未设置", "tp3": "未设置"}
        if not plan.get("position", {}).get("suggested_position"):
            plan["position"] = {"suggested_position": "总资金10%以内", "position_management": "分两批建仓，确认支撑有效后加仓"}
        if not plan.get("risk_control", {}).get("max_loss"):
            plan["risk_control"] = {"max_loss": "单票最大亏损控制在-5%以内", "special_risks": ["市场系统性风险", "个股利空风险"]}

    return dashboard


def analyze_stock_dashboard(client, m):
    if not m:
        return None

    prompt = build_dashboard_prompt(m)
    dashboard = None

    if client:
        try:
            resp = client.chat.completions.create(
                model=AI_MODEL,
                messages=[
                    {"role": "system", "content": DASHBOARD_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.3,
                max_tokens=1200,
            )
            text = resp.choices[0].message.content.strip()
            dashboard = _parse_dashboard_json(text)
        except Exception as e:
            print(f"  [AI仪表盘失败] {m.get('code', '')} - {e}", flush=True)

    dashboard = dashboard or {}

    if "core_conclusion" not in dashboard:
        dashboard["core_conclusion"] = {
            "signal": m.get("signal", "观望"),
            "confidence": "中",
            "trading_advisor_rating": _rating_from_score(m.get("score", 50)),
            "market_phase": m.get("market_phase", "盘后"),
            "summary": "；".join(m.get("signal_reasons", [])),
            "risk_warning": "；".join(m.get("risk_factors", [])) or "无明显风险",
        }
    if "data_perspective" not in dashboard:
        dashboard["data_perspective"] = {
            "trend": {
                "judgment": "多头" if m.get("trend") in ("强势多头", "多头排列") else ("空头" if m.get("trend") in ("强势空头", "空头排列") else "震荡"),
                "strength": m.get("trend_strength", 50),
                "ma_alignment": m.get("ma_alignment", ""),
                "bias_ma5": m.get("bias_ma5", 0),
                "bias_ma10": m.get("bias_ma10", 0),
                "bias_ma20": m.get("bias_ma20", 0),
            },
            "volume": {
                "judgment": m.get("volume_status", "量能正常"),
                "ratio": m.get("volume_ratio", 1.0),
                "analysis": m.get("volume_trend", ""),
            },
            "macd": {
                "status": m.get("macd_status", "中性"),
                "signal": m.get("macd_signal", ""),
                "dif": m.get("macd_dif", 0),
                "dea": m.get("macd_dea", 0),
                "bar": m.get("macd_bar", 0),
            },
            "rsi": {
                "rsi_6": m.get("rsi_6", 50),
                "rsi_12": m.get("rsi_12", 50),
                "rsi_24": m.get("rsi_24", 50),
                "status": m.get("rsi_status", "中性"),
                "signal": m.get("rsi_signal", ""),
            },
            "support_resistance": {
                "support_levels": m.get("support_levels", []),
                "resistance_levels": m.get("resistance_levels", []),
                "nearest_support": m.get("support_levels", [None])[0] if m.get("support_levels") else m.get("ma10", 0),
                "nearest_resistance": m.get("resistance_levels", [None])[0] if m.get("resistance_levels") else m.get("ma5", 0),
            },
        }
    if "battle_plan" not in dashboard:
        dashboard["battle_plan"] = _build_fallback_plan(m)

    dashboard = _stabilize_decision(dashboard)

    return dashboard


def _rating_from_score(score):
    if score >= 85:
        return "★★★★★"
    if score >= 75:
        return "★★★★☆"
    if score >= 60:
        return "★★★☆☆"
    if score >= 45:
        return "★★☆☆☆"
    return "★☆☆☆☆"


def _build_fallback_plan(m):
    price = m.get("price", 0)
    signal = m.get("signal", "观望")
    support_levels = m.get("support_levels", [])
    resistance_levels = m.get("resistance_levels", [])

    if signal in ("强烈买入", "买入"):
        entry_base = price
        ideal_entry = f"{entry_base:.2f}附近"
        secondary = f"回踩MA10({m.get('ma10', 0):.2f})附近" if m.get("ma10", 0) and m["ma10"] < price else f"{entry_base * 0.98:.2f}以下"
        sl = f"{support_levels[0] * 0.97:.2f}" if support_levels else f"{price * 0.95:.2f}"
        tp1 = f"{resistance_levels[0]:.2f}" if resistance_levels else f"{price * 1.05:.2f}"
        tp2 = f"{float(tp1) * 1.05:.2f}" if tp1 else ""
        tp3 = f"{float(tp2) * 1.05:.2f}" if tp2 else ""
        action = "买入"
        pos = "总资金15%"
        pos_mgmt = "首次建仓10%，确认均线支撑有效后加仓5%"
    elif signal == "持有":
        ideal_entry = f"{price:.2f}（当前持仓）"
        secondary = "持仓不动"
        sl = f"{m.get('ma20', price * 0.95):.2f}"
        tp1 = f"{resistance_levels[0]:.2f}" if resistance_levels else f"{price * 1.08:.2f}"
        tp2 = ""
        tp3 = ""
        action = "持有"
        pos = "维持当前仓位"
        pos_mgmt = "持股待涨，破位止损"
    elif signal in ("观望", "卖出", "强烈卖出"):
        ideal_entry = "不建议入场"
        secondary = "等待企稳信号"
        sl = "N/A"
        tp1 = "N/A"
        tp2 = ""
        tp3 = ""
        action = "观望"
        pos = "0%"
        pos_mgmt = "空仓等待"
    else:
        ideal_entry = f"{price:.2f}附近（短线快进快出）"
        secondary = f"{price * 0.98:.2f}以下"
        sl = f"{price * 0.95:.2f}"
        tp1 = f"{price * 1.05:.2f}"
        tp2 = f"{price * 1.10:.2f}"
        tp3 = ""
        action = "关注"
        pos = "总资金5%以内"
        pos_mgmt = "小仓试探，严格止损"

    return {
        "action": action,
        "entry_plan": {
            "ideal_entry": ideal_entry,
            "secondary_entry": secondary,
            "stop_loss": sl,
        },
        "take_profit": {
            "tp1": tp1 or "未设置",
            "tp2": tp2 or "未设置",
            "tp3": tp3 or "未设置",
        },
        "position": {
            "suggested_position": pos,
            "position_management": pos_mgmt,
        },
        "risk_control": {
            "max_loss": f"单票最大亏损控制在-5%以内",
            "special_risks": m.get("risk_factors", ["市场系统性风险"]),
        },
    }


def analyze_stocks_batch(stock_data_list):
    client = get_client()
    results = []
    for data in stock_data_list:
        print(f"  生成仪表盘: {data['name']}({data['code']})...", flush=True)
        dashboard = analyze_stock_dashboard(client, data)
        results.append({"market": data, "dashboard": dashboard})
        time.sleep(0.5)
    return results


def mark_no_api(news_list):
    results = []
    for item in news_list:
        results.append({
            "news": item,
            "analysis": {
                "event_type": "中性消息",
                "confidence": "低",
                "reason": "未配置API Key，无法进行AI分析",
                "affected_sectors": [],
                "affected_concept": [],
                "stock_codes": [],
                "impact_level": "轻微",
                "time_horizon": "短期",
                "market_sentiment": "中性",
                "advice": "观望",
                "advice_reason": "请先在 config.py 中配置 AI_API_KEY"
            }
        })
    return results
