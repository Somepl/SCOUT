SEP = "=" * 60
SUB_SEP = "-" * 60

# ── 多信号确信度系统 ──

def _sector_news_sentiment(stock_sectors, news_results):
    """计算该股票所在板块的新闻情绪得分
    返回: 1=偏多, 0=中性, -1=偏空, None=无相关新闻
    """
    if not stock_sectors or not news_results:
        return None
    
    total_score = 0
    match_count = 0
    for r in news_results:
        analysis = r.get("analysis", {})
        sectors = analysis.get("affected_sectors", [])
        # 检查是否有交集
        if not any(s in stock_sectors for s in sectors):
            continue
        sentiment = analysis.get("market_sentiment", "中性")
        confidence = analysis.get("confidence", "中")
        # 置信度权重
        conf_w = {"高": 3, "中": 2, "低": 1}.get(confidence, 1)
        # 情绪分
        sent_w = {"利好": 1, "利空": -1, "中性": 0}.get(sentiment, 0)
        total_score += sent_w * conf_w
        match_count += conf_w
    
    if match_count == 0:
        return None
    avg = total_score / match_count
    if avg > 0.3:
        return 1   # 偏多
    elif avg < -0.3:
        return -1  # 偏空
    return 0         # 中性


def calc_conviction(stock_market_data, news_results, capital_data):
    """多信号确信度评估
    结合技术面、板块新闻情绪、资金面三个独立信号源
    
    Args:
        stock_market_data: dict from market.py StockTrendAnalyzer.analyze()
        news_results: list of news analysis results
        capital_data: dict from capital.get_capital_summary()
    
    Returns:
        dict with:
            level: str 高/中/低
            score: int 0-100 确信度分数
            signals: list of individual signal dicts
            label: str 简要说明
    """
    signals = []
    
    # 1. 技术面信号
    tech_score = stock_market_data.get('score', 50) or 50
    if tech_score >= 60:
        signals.append({"name": "技术面", "value": "看多", "detail": f"评分{tech_score}", "score": 1})
    elif tech_score >= 45:
        signals.append({"name": "技术面", "value": "中性", "detail": f"评分{tech_score}", "score": 0})
    else:
        signals.append({"name": "技术面", "value": "看空", "detail": f"评分{tech_score}", "score": -1})
    
    # 2. 板块新闻情绪
    stock_sectors = stock_market_data.get('source_sectors', [])
    news_sent = _sector_news_sentiment(stock_sectors, news_results)
    if news_sent == 1:
        signals.append({"name": "新闻面(板块)", "value": "偏多", "detail": "板块利好新闻居多", "score": 1})
    elif news_sent == -1:
        signals.append({"name": "新闻面(板块)", "value": "偏空", "detail": "板块利空新闻居多", "score": -1})
    else:
        signals.append({"name": "新闻面(板块)", "value": "中性", "detail": "板块新闻情绪中性或无直接相关", "score": 0})
    
    # 3. 资金面信号
    if capital_data:
        try:
            from capital import calc_capital_light
            cap_light = calc_capital_light(capital_data)
            cap_score = cap_light.get('score', 50) if isinstance(cap_light, dict) else 50
        except Exception:
            cap_score = 50
        if cap_score >= 65:
            signals.append({"name": "资金面", "value": "偏多", "detail": f"北向资金净流入", "score": 1})
        elif cap_score <= 35:
            signals.append({"name": "资金面", "value": "偏空", "detail": f"北向资金净流出", "score": -1})
        else:
            signals.append({"name": "资金面", "value": "中性", "detail": "资金面无明显方向", "score": 0})
    else:
        signals.append({"name": "资金面", "value": "未知", "detail": "数据暂不可用", "score": 0})
    
    # 综合确信度
    positive = sum(1 for s in signals if s['score'] > 0)
    negative = sum(1 for s in signals if s['score'] < 0)
    total_active = sum(1 for s in signals if s['score'] != 0)
    
    # 确信度评分 (0-100)
    net = positive - negative
    total = len(signals)
    conv_score = int(50 + (net / total) * 50)
    conv_score = max(0, min(100, conv_score))
    
    # 确信度等级
    if positive >= 2 and negative == 0:
        level = "高"
        label = "多信号一致看多"
    elif positive >= 2 and negative > 0:
        level = "中"
        label = "多数偏多但有分歧"
    elif negative >= 2:
        level = "低"
        label = "多数信号偏空"
    elif positive == 0 and negative == 0:
        level = "低"
        label = "信号不明朗"
    else:
        level = "中"
        label = "信号存在分歧"
    
    return {
        "level": level,
        "score": conv_score,
        "signals": signals,
        "positive_count": positive,
        "negative_count": negative,
        "label": label,
    }


def _normalize_alloc(n):
    allocs = [0.35, 0.25, 0.20, 0.12, 0.08]
    while len(allocs) < n:
        allocs.append(0.05)
    total = sum(allocs)
    return [a / total for a in allocs]


def _extract_sectors(news_results):
    sectors = set()
    for r in news_results:
        for s in r.get("analysis", {}).get("affected_sectors", []):
            if s:
                sectors.add(s)
    return sectors


def _sentiment_score(news_results):
    bullish = sum(1 for r in news_results if r["analysis"].get("market_sentiment") == "利好")
    bearish = sum(1 for r in news_results if r["analysis"].get("market_sentiment") == "利空")
    if bullish + bearish == 0:
        return 0
    return (bullish - bearish) / (bullish + bearish) * 100


def _safety_overrides(m, action):
    """安全强制检查：某些技术形态下无论AI说什么都不可买入
    返回 (new_action, reasons)
    """
    reasons = []
    new_action = action

    # 1. RSI超买（>70）→ 至少降级为持有
    rsi6 = m.get("rsi6", 70)
    if rsi6 and rsi6 > 70 and action in ("买入", "加仓"):
        new_action = "持有"
        reasons.append(f"RSI({rsi6:.0f})超买>70")

    # 2. 放量下跌 → 不可买入
    vol_status = m.get("volume_status", "")
    if vol_status == "放量下跌" and action in ("买入", "加仓"):
        new_action = "观望"
        reasons.append("放量下跌")
    # 缩量下跌也不建议买入
    if vol_status == "缩量下跌" and action in ("买入", "加仓"):
        new_action = "观望"
        reasons.append("缩量下跌")

    # 3. 乖离过大（已离均线太远）
    bias_ma5 = m.get("bias_ma5", 0)
    if bias_ma5 and bias_ma5 > 8 and action in ("买入", "加仓"):
        new_action = "持有"
        reasons.append(f"乖离MA5+{bias_ma5:.1f}%偏离过大")

    return new_action, reasons


def _pick_rank(stock_results, news_results, capital_data=None):
    scored = []
    for r in stock_results:
        m = r.get("market", {})
        d = r.get("dashboard", {})
        cc = d.get("core_conclusion", {})
        bp = d.get("battle_plan", {})

        action = bp.get("action", "观望")
        signal = cc.get("signal", "观望")
        score = m.get("score", 0) or 0
        trend_strength = m.get("trend_strength", 0) or 0
        vol_status = m.get("volume_status", "")

        # 安全强制检查（AI可能忽略的技术风险）
        safe_action, safety_reasons = _safety_overrides(m, action)
        if safe_action != action:
            # 如果被安全规则降级了，但rank_score仍可用于排序
            action = safe_action

        if action not in ("买入", "加仓") and signal not in ("强烈买入", "买入"):
            continue
        if score < 60:
            continue

        volatility_penalty = 0
        if m.get("bias_ma5", 0) and abs(m["bias_ma5"]) > 7:
            volatility_penalty -= 10
        if m.get("bias_ma20", 0) and abs(m["bias_ma20"]) > 10:
            volatility_penalty -= 10

        volume_bonus = 0
        if vol_status in ("缩量回调", "放量上涨"):
            volume_bonus = 5

        # 确信度加成
        conviction = calc_conviction(m, news_results, capital_data)
        conv_bonus = 0
        if conviction["level"] == "高":
            conv_bonus = 10
        elif conviction["level"] == "中" and conviction["positive_count"] > conviction["negative_count"]:
            conv_bonus = 5
        elif conviction["negative_count"] >= 2:
            conv_bonus = -15  # 多数信号看空，强烈不推荐

        base_rank = score + volatility_penalty + volume_bonus + (trend_strength * 0.1) + conv_bonus

        final_score = max(0, min(100, base_rank))

        ep = bp.get("entry_plan", {})
        tp = bp.get("take_profit", {})
        pos = bp.get("position", {})
        rc = bp.get("risk_control", {})

        sectors = m.get("source_sectors", [])
        if not sectors:
            from screener import match_sectors
            for s in _extract_sectors(news_results):
                if match_sectors(s):
                    sectors.append(s)
                    break

        scored.append({
            "name": m.get("name", ""),
            "code": m.get("code", ""),
            "price": m.get("price", 0),
            "change_pct": m.get("change_pct", 0),
            "score": score,
            "rank_score": round(final_score, 1),
            "action": action,
            "signal": signal,
            "rating": cc.get("trading_advisor_rating", "★★★☆☆"),
            "summary": cc.get("summary", ""),
            "risk_warning": cc.get("risk_warning", ""),
            "source_sectors": sectors,
            "ideal_entry": ep.get("ideal_entry", ""),
            "secondary_entry": ep.get("secondary_entry", ""),
            "stop_loss": ep.get("stop_loss", ""),
            "tp1": tp.get("tp1", ""),
            "tp2": tp.get("tp2", ""),
            "tp3": tp.get("tp3", ""),
            "suggested_position": pos.get("suggested_position", ""),
            "position_management": pos.get("position_management", ""),
            "special_risks": rc.get("special_risks", []),
            "trend": m.get("trend", ""),
            "volume_status": vol_status,
            "ma_alignment": m.get("ma_alignment", ""),
            "conviction": conviction,
            "safety_overrides": safety_reasons,
        })

    scored.sort(key=lambda x: x["rank_score"], reverse=True)
    return scored


def _conviction_icon(level):
    icons = {"高": "🟢🟢🟢", "中": "🟢🟡⚪", "低": "⚪⚪🔴"}
    return icons.get(level, "⚪⚪⚪")


CAPITAL_ALLOCATION = _normalize_alloc(5)


def build_picks_report(picks, news_results):
    lines = []
    lines.append(SEP)
    lines.append("   [SCOUT] 今日狙击清单 — 可直接执行")
    lines.append(SEP)
    lines.append("")

    if not picks:
        lines.append("  ⚠️ 当前无符合条件的买入标的")
        lines.append("")
        lines.append("  可能原因：")
        lines.append("    · 市场整体偏弱，无个股达到买入标准（评分≥60且信号为买入）")
        lines.append("    · 今日新闻热点板块对应的个股技术面尚未走好")
        lines.append("    · 建议：保持空仓观望，等待市场企稳")
        lines.append("")
        lines.append(SEP)
        return "\n".join(lines)

    sent = _sentiment_score(news_results)
    if sent > 20:
        lines.append(f"  市场情绪: 偏多（{sent:+.0f}）  ✅ 环境配合")
    elif sent > -20:
        lines.append(f"  市场情绪: 中性（{sent:+.0f}）  ⚡ 精选个股")
    else:
        lines.append(f"  市场情绪: 偏空（{sent:+.0f}）  ⚠️ 仅限高手操作")
    lines.append(f"  今日可操作: {len(picks)} 只")
    lines.append("")

    for i, p in enumerate(picks):
        alloc = CAPITAL_ALLOCATION[i] if i < len(CAPITAL_ALLOCATION) else 0.0
        alloc_pct = f"{alloc * 100:.0f}%"

        lines.append(SUB_SEP)
        sector_tag = f"[{'/'.join(p['source_sectors'][:3])}]" if p.get('source_sectors') else ""
        conv = p.get('conviction', {})
        conv_label = f"{_conviction_icon(conv.get('level', ''))} 确信度: {conv.get('level', 'N/A')}" if conv else ""
        lines.append(f"  #{i+1} {p['name']}（{p['code']}）{p['rating']}  {sector_tag}")
        if conv_label:
            lines.append(f"    {conv_label}")
            sig_detail = " + ".join([s['value'] for s in conv.get('signals', [])])
            lines.append(f"    信号: {sig_detail}")
        lines.append(f"    当前价: {p['price']:.2f}  |  涨跌: {p['change_pct']:+.2f}%  |  评分: {p['score']}/100  优先级: {alloc_pct}仓位")
        lines.append(f"    策略: {p['action']}  |  趋势: {p['trend']}  |  量能: {p['volume_status']}")
        if p.get('safety_overrides'):
            for r in p['safety_overrides']:
                lines.append(f"    ⛔ 安全规则: {r}")
        lines.append("")
        lines.append(f"    【交易计划】")
        lines.append(f"    理想买点: {p['ideal_entry']}")
        lines.append(f"    次优买点: {p['secondary_entry']}")
        lines.append(f"    止损位:   {p['stop_loss']}")

        tp_parts = []
        if p['tp1'] and p['tp1'] not in ("N/A", "未设置", ""):
            tp_parts.append(f"TP1={p['tp1']}")
        if p['tp2'] and p['tp2'] not in ("N/A", "未设置", ""):
            tp_parts.append(f"TP2={p['tp2']}")
        if p['tp3'] and p['tp3'] not in ("N/A", "未设置", ""):
            tp_parts.append(f"TP3={p['tp3']}")
        if tp_parts:
            lines.append(f"    止盈目标: {'  '.join(tp_parts)}")
        lines.append(f"    仓位: {p['suggested_position']}  |  {p['position_management']}")
        lines.append("")
        lines.append(f"    【核心理由】")
        lines.append(f"    {p['summary']}")
        lines.append("")
        if p['special_risks'] or p['risk_warning']:
            lines.append(f"    【风险清单】")
            seen_risks = set()
            for risk in p['special_risks']:
                clean = risk.replace("⚠️ ", "").replace("⚠️", "").strip()
                if clean and clean not in seen_risks:
                    seen_risks.add(clean)
                    lines.append(f"    ⚠️ {clean}")
                    if len(seen_risks) >= 3:
                        break
            if p['risk_warning']:
                clean = p['risk_warning'].replace("⚠️ ", "").replace("⚠️", "").strip()
                if clean and clean not in seen_risks:
                    seen_risks.add(clean)
                    lines.append(f"    ⚠️ {clean}")
        lines.append("")

    lines.append(SEP)
    total_alloc = sum(CAPITAL_ALLOCATION[i] if i < len(CAPITAL_ALLOCATION) else 0.0 for i in range(len(picks)))
    lines.append(f"  建议总仓位: {total_alloc * 100:.0f}%（{len(picks)}只分散）")
    lines.append(f"  剩余资金: {(1 - total_alloc) * 100:.0f}%（留足现金应对风险）")
    lines.append("")
    lines.append("  【操作纪律】")
    lines.append("  · 严格按止损位执行，触及即走")
    lines.append("  · 分批建仓，不追高")
    lines.append("  · 单票最大亏损控制在-5%以内")
    lines.append("  · 以上分析仅供参考，不构成投资建议")
    lines.append(SEP)

    return "\n".join(lines)


def build_wechat_picks(picks, news_results):
    lines = []

    if not picks:
        lines.append("【今日狙击清单】")
        lines.append("当前无符合买入条件的标的，建议空仓观望")
        lines.append("")
        return "\n".join(lines)

    sent = _sentiment_score(news_results)
    if sent > 20:
        lines.append("【今日狙击清单】市场偏多 ✅")
    elif sent > -20:
        lines.append("【今日狙击清单】市场中，精选个股 ⚡")
    else:
        lines.append("【今日狙击清单】市场偏空，谨慎 ⚠️")

    lines.append(f"可操作: {len(picks)}只")
    lines.append("")

    for i, p in enumerate(picks):
        alloc = CAPITAL_ALLOCATION[i] if i < len(CAPITAL_ALLOCATION) else 0.0
        sector_tag = f"[{'/'.join(p['source_sectors'][:2])}]" if p.get('source_sectors') else ""
        conv = p.get('conviction', {})
        conv_tag = f" 确信度:{conv.get('level','?')}" if conv else ""
        lines.append(f"{'🟢' if i == 0 else '🟢'}  #{i+1} {p['name']}（{p['code']}）{sector_tag}{conv_tag}")
        lines.append(f"  买入区间: {p['ideal_entry']}")
        lines.append(f"  止损: {p['stop_loss']}")
        tp_parts = []
        if p['tp1'] and p['tp1'] not in ("N/A", "未设置", ""):
            tp_parts.append(f"TP1={p['tp1']}")
        if p['tp2'] and p['tp2'] not in ("N/A", "未设置", ""):
            tp_parts.append(f"TP2={p['tp2']}")
        if tp_parts:
            lines.append(f"  止盈: {' '.join(tp_parts)}")
        lines.append(f"  仓位: {p['suggested_position']}")
        lines.append("")

    lines.append("---")
    lines.append("严格止损，分批建仓")

    return "\n".join(lines)
