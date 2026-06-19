from reporter import SEP, SUB_SEP


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


def _pick_rank(stock_results, news_results):
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

        base_rank = score + volatility_penalty + volume_bonus + (trend_strength * 0.1)

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
        })

    scored.sort(key=lambda x: x["rank_score"], reverse=True)
    return scored


CAPITAL_ALLOCATION = [
    0.35,
    0.25,
    0.20,
    0.12,
    0.08,
]


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
        alloc = CAPITAL_ALLOCATION[i] if i < len(CAPITAL_ALLOCATION) else 0.05
        alloc_pct = f"{alloc * 100:.0f}%"

        lines.append(SUB_SEP)
        sector_tag = f"[{'/'.join(p['source_sectors'][:3])}]" if p.get('source_sectors') else ""
        lines.append(f"  #{i+1} {p['name']}（{p['code']}）{p['rating']}  {sector_tag}")
        lines.append(f"    当前价: {p['price']:.2f}  |  涨跌: {p['change_pct']:+.2f}%  |  评分: {p['score']}/100  优先级: {alloc_pct}仓位")
        lines.append(f"    策略: {p['action']}  |  趋势: {p['trend']}  |  量能: {p['volume_status']}")
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
    total_alloc = sum(CAPITAL_ALLOCATION[i] if i < len(CAPITAL_ALLOCATION) else 0.05 for i in range(len(picks)))
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
        alloc = CAPITAL_ALLOCATION[i] if i < len(CAPITAL_ALLOCATION) else 0.05
        sector_tag = f"[{'/'.join(p['source_sectors'][:2])}]" if p.get('source_sectors') else ""
        lines.append(f"{'🟢' if i == 0 else '🟢'}  #{i+1} {p['name']}（{p['code']}）{sector_tag}")
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
