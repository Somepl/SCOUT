from datetime import datetime
from utils import today_str
from capital import calc_capital_light

SEP = "=" * 60
SUB_SEP = "-" * 60


def _sentiment_icon(s):
    if s == "利好": return "[+]"
    if s == "利空": return "[-]"
    return "[~]"


def _conf_icon(c):
    if c == "高": return "[H]"
    if c == "中": return "[M]"
    return "[L]"


def _score_stars(score):
    if score >= 85: return "★★★★★"
    if score >= 75: return "★★★★☆"
    if score >= 60: return "★★★☆☆"
    if score >= 45: return "★★☆☆☆"
    return "★☆☆☆☆"


def _action_emoji(action):
    m = {
        "买入": "🟢", "加仓": "🟢",
        "持有": "🔵",
        "减仓": "🟡", "观望": "⚪",
        "卖出": "🔴", "强烈卖出": "🔴",
    }
    return m.get(action, "⚪")


def calc_market_light(news_results, stock_results=None):
    bullish = sum(1 for r in news_results if r["analysis"].get("market_sentiment") == "利好")
    bearish = sum(1 for r in news_results if r["analysis"].get("market_sentiment") == "利空")
    buy_news = sum(1 for r in news_results if r["analysis"].get("advice") == "买入")
    sell_news = sum(1 for r in news_results if r["analysis"].get("advice") == "卖出")

    stock_buy = 0
    stock_score_avg = 0
    if stock_results:
        stock_buy = sum(1 for r in stock_results if r.get("dashboard", {}).get("core_conclusion", {}).get("signal") in ("强烈买入", "买入"))
        stock_scores = []
        for r in stock_results:
            s = r.get("market", {}).get("score", 0) or 0
            stock_scores.append(s)
        stock_score_avg = sum(stock_scores) / len(stock_scores) if stock_scores else 0

    total_score = 50
    reasons = []

    if bullish > bearish:
        ratio = bullish / max(bearish, 1)
        if ratio >= 3:
            total_score += 20
            reasons.append("新闻面强烈偏多")
        elif ratio >= 2:
            total_score += 15
            reasons.append("新闻面偏多")
        else:
            total_score += 8
            reasons.append("新闻面略偏多")
    elif bearish > bullish:
        ratio = bearish / max(bullish, 1)
        if ratio >= 3:
            total_score -= 20
            reasons.append("新闻面强烈偏空")
        elif ratio >= 2:
            total_score -= 15
            reasons.append("新闻面偏空")
        else:
            total_score -= 8
            reasons.append("新闻面略偏空")
    else:
        reasons.append("新闻面中性")

    if stock_score_avg > 0:
        if stock_score_avg >= 65:
            total_score += 10
            reasons.append("技术面偏多")
        elif stock_score_avg >= 50:
            total_score += 5
            reasons.append("技术面中性")
        else:
            total_score -= 8
            reasons.append("技术面偏空")

    total_score = max(0, min(100, total_score))

    if total_score >= 75:
        light = "🟢🟢🟢"
        label = "市场情绪乐观，可积极参与"
    elif total_score >= 60:
        light = "🟢🟢⚪"
        label = "市场情绪偏暖，精选个股"
    elif total_score >= 40:
        light = "🟢⚪⚪"
        label = "市场情绪中性，谨慎参与"
    elif total_score >= 25:
        light = "⚪⚪🔴"
        label = "市场情绪偏冷，控制仓位"
    else:
        light = "🔴🔴🔴"
        label = "市场情绪悲观，建议空仓"

    return {
        "score": total_score,
        "light": light,
        "label": label,
        "details": "；".join(reasons),
    }


def build_report(results, history=None):
    report_date = today_str()
    lines = []
    lines.append(SEP)
    lines.append("   [SCOUT] 每日情报简报")
    lines.append(f"   {report_date}")
    lines.append(SEP)
    lines.append("")

    high_signals = [r for r in results if r["analysis"].get("confidence") == "高"
                    and r["analysis"].get("impact_level") in ("重大", "中等")]
    mid_signals = [r for r in results if r["analysis"].get("confidence") == "中"
                   and r["analysis"].get("impact_level") in ("重大", "中等")]
    low_signals = [r for r in results if r not in high_signals and r not in mid_signals]

    if not high_signals:
        lines.append("  今日暂无重点关注信号")
        lines.append("")
    else:
        lines.append(f"  !! 优先关注信号（{len(high_signals)}条）")
        lines.append(SUB_SEP)
        for r in high_signals:
            n = r["news"]
            a = r["analysis"]
            si = _sentiment_icon(a.get("market_sentiment"))
            ci = _conf_icon(a.get("confidence"))
            lines.append(f"  {si} {n['title']}")
            lines.append(f"     来源: {n['source']}  可信度: {a.get('confidence','')} {ci}")
            sectors = a.get("affected_sectors", [])
            if sectors:
                lines.append(f"     影响板块: {'/'.join(sectors)}")
            lines.append(f"     建议: {a.get('advice','')} - {a.get('advice_reason','')}")
            lines.append("")
        lines.append("")

    if mid_signals:
        lines.append(f"  -- 值得关注信号（{len(mid_signals)}条）")
        lines.append(SUB_SEP)
        for r in mid_signals:
            n = r["news"]
            a = r["analysis"]
            si = _sentiment_icon(a.get("market_sentiment"))
            lines.append(f"  {si} {n['title'][:60]}")
            lines.append(f"     来源: {n['source']}  可信度: {a.get('confidence','')}")
            lines.append(f"     建议: {a.get('advice','')}")
            lines.append("")
        lines.append("")

    if low_signals:
        lines.append(f"  一般信息（{len(low_signals)}条）")
        lines.append(SUB_SEP)
        for r in low_signals:
            n = r["news"]
            a = r["analysis"]
            lines.append(f"  {n['title'][:60]}")
            lines.append(f"     来源: {n['source']}  可信度: {a.get('confidence','')}")
        lines.append("")

    lines.append(SEP)
    lines.append("  [*] 综合研判")
    lines.append(SUB_SEP)

    buy_count = sum(1 for r in results if r["analysis"].get("advice") == "买入")
    watch_count = sum(1 for r in results if r["analysis"].get("advice") == "关注")
    sell_count = sum(1 for r in results if r["analysis"].get("advice") == "卖出")
    wait_count = sum(1 for r in results if r["analysis"].get("advice") == "观望")

    bullish = sum(1 for r in results if r["analysis"].get("market_sentiment") == "利好")
    bearish = sum(1 for r in results if r["analysis"].get("market_sentiment") == "利空")

    lines.append(f"  利好信号: {bullish}条 | 利空信号: {bearish}条")
    lines.append(f"  买入建议: {buy_count}条 | 关注建议: {watch_count}条 | 观望: {wait_count}条 | 卖出: {sell_count}条")

    if bullish > bearish * 2:
        lines.append("  综合判断: 市场偏乐观 [+]")
    elif bearish > bullish * 2:
        lines.append("  综合判断: 市场偏谨慎 [-]")
    else:
        lines.append("  综合判断: 市场情绪中性 [~]")

    lines.append(SEP)
    lines.append("  [!] 风险提示: 以上分析仅供参考，不构成投资建议")
    lines.append("     投资有风险，入市需谨慎")
    lines.append(SEP)

    return "\n".join(lines)


def print_report(report_text):
    print("\n" + report_text + "\n", flush=True)


def build_stock_report(stock_results):
    lines = []
    lines.append(SEP)
    lines.append("   [SCOUT] 个股交易决策仪表盘")
    lines.append(f"   {today_str()}")
    lines.append(SEP)
    lines.append("")

    if not stock_results:
        lines.append("  今日未配置自选股分析")
        lines.append("")
        lines.append(SEP)
        return "\n".join(lines)

    for r in stock_results:
        m = r["market"]
        d = r.get("dashboard", {})
        cc = d.get("core_conclusion", {})
        dp = d.get("data_perspective", {})
        bp = d.get("battle_plan", {})

        signal = cc.get("signal", "观望")
        rating = cc.get("trading_advisor_rating", "★★★☆☆")
        action = bp.get("action", "观望")
        emoji = _action_emoji(action)
        score = m.get("score", 0) or 0

        # 确信度（来自 strategist._pick_rank 集成）
        conv = r.get("conviction", {})
        conv_icon = {"高": "🟢🟢🟢", "中": "🟢🟡⚪", "低": "⚪⚪🔴"}.get(conv.get("level", ""), "")
        conv_line = f"  {conv_icon} 确信度: {conv.get('level', 'N/A')}" if conv and conv.get('level') else ""

        lines.append(f"  {emoji} {m['name']}（{m['code']}）{rating}")
        if conv_line:
            lines.append(conv_line)
            sig_detail = " + ".join([s['value'] for s in conv.get('signals', [])])
            lines.append(f"    信号: {sig_detail}")
        lines.append(SUB_SEP)
        lines.append(f"    当前价: {m['price']:>8.2f}  |  涨跌: {m.get('change_pct', 0):>+7.2f}%")
        lines.append(f"    信号: {signal}  |  综合评分: {score}/100")

        trend_data = dp.get("trend", {})
        ma_align = trend_data.get("ma_alignment", m.get("ma_alignment", ""))
        lines.append(f"    均线: MA5={m.get('ma5',0):.2f} MA10={m.get('ma10',0):.2f} MA20={m.get('ma20',0):.2f}")
        lines.append(f"    均线排列: {ma_align}  |  乖离MA5: {m.get('bias_ma5',0):+.1f}%")

        vol_data = dp.get("volume", {})
        lines.append(f"    量能: {vol_data.get('judgment', m.get('volume_status',''))}  |  量比: {vol_data.get('ratio', m.get('volume_ratio',1)):.2f}")

        sr = dp.get("support_resistance", {})
        sup = sr.get("nearest_support", m.get('support_levels', [None])[0] if m.get('support_levels') else "")
        res = sr.get("nearest_resistance", m.get('resistance_levels', [None])[0] if m.get('resistance_levels') else "")
        lines.append(f"    支撑: {sup}  |  阻力: {res}")

        lines.append("")
        lines.append(f"    【狙击方案】")
        ep = bp.get("entry_plan", {})
        lines.append(f"    理想买点: {ep.get('ideal_entry', 'N/A')}")
        lines.append(f"    次优买点: {ep.get('secondary_entry', 'N/A')}")
        lines.append(f"    止损位: {ep.get('stop_loss', 'N/A')}")

        tp = bp.get("take_profit", {})
        tp_parts = []
        if tp.get("tp1") and tp["tp1"] != "N/A" and tp["tp1"] != "未设置":
            tp_parts.append(f"TP1={tp['tp1']}")
        if tp.get("tp2"):
            tp_parts.append(f"TP2={tp['tp2']}")
        if tp.get("tp3"):
            tp_parts.append(f"TP3={tp['tp3']}")
        if tp_parts:
            lines.append(f"    止盈: {'  '.join(tp_parts)}")

        pos = bp.get("position", {})
        lines.append(f"    仓位: {pos.get('suggested_position', 'N/A')}  |  {pos.get('position_management', '')}")

        rc = bp.get("risk_control", {})
        seen_warnings = set()
        if rc.get("special_risks"):
            for risk in rc["special_risks"][:3]:
                clean = risk.replace("⚠️ ", "").replace("⚠️", "").strip()
                if clean and clean not in seen_warnings:
                    seen_warnings.add(clean)
                    lines.append(f"    ⚠️ {clean}")

        if cc.get("risk_warning"):
            clean = cc["risk_warning"].replace("⚠️ ", "").replace("⚠️", "").strip()
            if clean and clean not in seen_warnings:
                seen_warnings.add(clean)
                lines.append(f"    ⚠️ {clean}")

        lines.append("")

    buy_count = sum(1 for r in stock_results
                    if r.get("dashboard", {}).get("battle_plan", {}).get("action") in ("买入", "加仓"))
    lines.append(SEP)
    lines.append(f"  共分析 {len(stock_results)} 只 | 可操作买入: {buy_count} 只")
    lines.append("  [!] 风险提示: 以上分析仅供参考，不构成投资建议")
    lines.append(SEP)
    return "\n".join(lines)


def _is_offday(nb_data):
    """判断当日是否为非交易日（所有数据都是 off_day）"""
    if not nb_data:
        return False
    off_count = sum(1 for d in nb_data[:3] if d.get("note") in ("off_day", "data_failed"))
    return off_count == len(nb_data[:3])


def _get_last_trading_note(nb_data):
    """获取最近交易日标注"""
    for d in nb_data:
        if d.get("note") == "last_trading_day":
            return d
    return None


def build_capital_report(capital_data):
    lines = []
    lines.append(SEP)
    lines.append("   [SCOUT] 资金面态势")
    lines.append(f"   {today_str()}")
    lines.append(SEP)
    lines.append("")

    if not capital_data:
        lines.append("  资金面数据暂不可用")
        lines.append("")
        lines.append(SEP)
        return "\n".join(lines)

    nb = capital_data.get("northbound", [])
    mg = capital_data.get("margin", [])

    offday = _is_offday(nb)

    if nb:
        lines.append("  【北向资金流向】")
        lines.append(SUB_SEP)
        if offday:
            last_trade = _get_last_trading_note(nb)
            if last_trade:
                net = last_trade.get("total_net", 0)
                arrow = "↑" if net > 0 else "↓"
                lines.append(f"  ⏸ 今日非交易日 | 最近({last_trade['date']}): {net/1e8:+.2f}亿 {arrow}")
            else:
                lines.append(f"  ⏸ 今日非交易日，暂无最新资金面数据")
        else:
            for day in nb[:5]:
                net = day.get("total_net", 0)
                arrow = "↑" if net > 0 else ("↓" if net < 0 else "—")
                lines.append(f"  {day['date']}  沪:{day.get('sh_net',0)/1e8:+.2f}亿  深:{day.get('sz_net',0)/1e8:+.2f}亿  合计:{net/1e8:+.2f}亿 {arrow}")
        lines.append("")

    if mg:
        lines.append("  【融资融券余额】")
        lines.append(SUB_SEP)
        all_off = all(d.get("note") in ("off_day", "data_failed") for d in mg)
        if all_off:
            lines.append(f"  ⏸ 今日非交易日，融资融券数据暂无更新")
        else:
            for day in mg[:3]:
                lines.append(f"  {day['date']}  两市合计: {day['total_yi']}亿  沪:{day['sh_yi']}亿  深:{day['sz_yi']}亿")
        lines.append("")

    cl = calc_capital_light(capital_data)
    lines.append(f"  【资金面信号】{cl['light']}  {cl['label']}")
    lines.append("")

    lines.append(SEP)
    return "\n".join(lines)


def build_wechat_summary(results, stock_results=None, capital_data=None):
    bullish = sum(1 for r in results if r["analysis"].get("market_sentiment") == "利好")
    bearish = sum(1 for r in results if r["analysis"].get("market_sentiment") == "利空")
    buy = sum(1 for r in results if r["analysis"].get("advice") == "买入")
    watch = sum(1 for r in results if r["analysis"].get("advice") == "关注")

    high_items = [r for r in results if r["analysis"].get("confidence") == "高"
                  and r["analysis"].get("impact_level") in ("重大", "中等")]

    ml = calc_market_light(results, stock_results)

    lines = [f"SCOUT每日情报 | {today_str()}"]
    lines.append("")
    lines.append(f"【市场光信号】{ml['light']}  {ml['label']}")
    lines.append(f"信号统计: 利好{bullish} / 利空{bearish} / 买入建议{buy} / 关注{watch}")
    lines.append("")

    if capital_data:
        cl = calc_capital_light(capital_data)
        lines.append(f"【资金面信号】{cl['light']}  {cl['label']}")
        nb = capital_data.get("northbound", [])
        if nb and len(nb) > 0:
            offday = all(d.get("note") in ("off_day", "data_failed") for d in nb[:3])
            if offday:
                last_trade = _get_last_trading_note(nb)
                if last_trade:
                    net = last_trade.get("total_net", 0)
                    lines.append(f"北向资金: 非交易日 | 最近({last_trade['date']}): {net/1e8:+.2f}亿")
                else:
                    lines.append("北向资金: 非交易日，数据暂缺")
            else:
                latest = nb[0]
                net = latest.get("total_net", 0)
                lines.append(f"北向资金: {net/1e8:+.2f}亿")
        mg = capital_data.get("margin", [])
        if mg and len(mg) > 0:
            all_off = all(d.get("note") in ("off_day", "data_failed") for d in mg)
            if all_off:
                lines.append("融资融券: 非交易日，数据暂缺")
            else:
                lines.append(f"融资融券: {mg[0].get('total_yi',0)}亿")
        lines.append("")

    if high_items:
        lines.append("【优先关注】")
        for r in high_items[:5]:
            n = r["news"]
            a = r["analysis"]
            si = _sentiment_icon(a.get("market_sentiment"))
            lines.append(f"{si} {n['title'][:40]}")
            lines.append(f"   建议: {a.get('advice','')} | 板块: {'/'.join(a.get('affected_sectors',[]))}")
        lines.append("")

    if stock_results:
        lines.append("【个股狙击清单】")
        actionable = [
            r for r in stock_results
            if r.get("dashboard", {}).get("battle_plan", {}).get("action") in ("买入", "加仓")
        ]
        holding = [
            r for r in stock_results
            if r.get("dashboard", {}).get("battle_plan", {}).get("action") in ("持有",)
        ]
        watching = [
            r for r in stock_results
            if r.get("dashboard", {}).get("battle_plan", {}).get("action") in ("观望", "减仓", "卖出", "强烈卖出")
        ]

        if actionable:
            lines.append(f"--- 可操作买入（{len(actionable)}只）---")
            for r in actionable[:5]:
                m = r["market"]
                d = r.get("dashboard", {})
                bp = d.get("battle_plan", {})
                ep = bp.get("entry_plan", {})
                action = bp.get("action", "")
                lines.append(f"{_action_emoji(action)} {m['name']}({m['code']}) {m['price']}元 {m.get('change_pct',0):+.2f}%")
                lines.append(f"   买点:{ep.get('ideal_entry','')} 止损:{ep.get('stop_loss','')}")
                pos = bp.get("position", {}).get("suggested_position", "")
                if pos:
                    lines.append(f"   仓位:{pos}")
            lines.append("")

        if holding and len(actionable) < 3:
            lines.append("--- 持股观察 ---")
            for r in holding[:3]:
                m = r["market"]
                action = r.get("dashboard", {}).get("battle_plan", {}).get("action", "")
                lines.append(f"{_action_emoji(action)} {m['name']}({m['code']}) {m['price']}元 {m.get('change_pct',0):+.2f}%")
            lines.append("")

        if watching:
            lines.append("--- 不宜操作 ---")
            for r in watching[:3]:
                m = r["market"]
                action = r.get("dashboard", {}).get("battle_plan", {}).get("action", "")
                sig = r.get("dashboard", {}).get("core_conclusion", {}).get("signal", "")
                lines.append(f"{_action_emoji(action)} {m['name']}({m['code']}) {sig}")
            lines.append("")

        if not actionable:
            lines.append("当前无明确买入信号，建议空仓等待")
            lines.append("")

    lines.append("---")
    lines.append("由 SCOUT 自动生成，仅供参考，不构成投资建议")
    return "\n".join(lines)
