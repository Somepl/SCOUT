"""
SCOUT 策略回测引擎
==================
从 SQLite 读取历史 AI 分析记录，用真实行情验证"买入"建议的有效性。
"""

import sys
import os
import json
from datetime import datetime, timedelta
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import DATA_DIR
from storage import ScoutStorage
from market import get_kline


def load_buy_signals(days=90):
    """读取历史分析记录中含股票代码且建议为买入/关注的信号"""
    storage = ScoutStorage(DATA_DIR)
    conn = sqlite3_connect()
    c = conn.cursor()
    c.execute(
        """SELECT a.id, a.report_date, m.title, a.advice, a.confidence,
                  a.analysis_raw, a.market_sentiment
           FROM analysis a
           JOIN messages m ON m.id = a.message_id
           WHERE a.report_date >= date('now', ?)
           ORDER BY a.report_date DESC""",
        (f"-{days} days",)
    )
    rows = c.fetchall()
    conn.close()

    signals = []
    for row in rows:
        aid, report_date, title, advice, confidence, raw_json, sentiment = row
        if not raw_json:
            continue
        try:
            raw = json.loads(raw_json)
        except (json.JSONDecodeError, TypeError):
            continue
        codes = raw.get("stock_codes", [])
        if not codes:
            continue
        for code in codes:
            code = code.strip()
            if not (code.startswith("6") or code.startswith("0") or code.startswith("3")):
                continue
            if len(code) != 6:
                continue
            signals.append({
                "analysis_id": aid,
                "date": report_date,
                "title": title,
                "code": code,
                "advice": advice,
                "confidence": confidence,
                "sentiment": sentiment,
            })
    return signals


def sqlite3_connect():
    import sqlite3
    db_path = os.path.join(DATA_DIR, "scout.db")
    return sqlite3.connect(db_path)


def simulate_trade(code, entry_date_str, holding_days=10, stop_loss=-0.05):
    """模拟单笔交易：在 entry_date 后的第一个交易日买入，持有 holding_days 个交易日"""
    kline = get_kline(code, count=holding_days + 15)
    if not kline:
        return None

    kline = sorted(kline, key=lambda x: x["date"])
    entry_date = entry_date_str[:10]

    start_idx = -1
    for i, k in enumerate(kline):
        if k["date"] >= entry_date:
            start_idx = i
            break
    if start_idx < 0 or start_idx >= len(kline) - 1:
        return None

    entry = kline[start_idx + 1]
    entry_price = entry["open"]
    if entry_price <= 0:
        return None

    max_price = entry_price
    min_price = entry_price
    exit_idx = min(start_idx + 1 + holding_days, len(kline) - 1)
    exit_date = kline[exit_idx]["date"]
    exit_price = kline[exit_idx]["open"]

    hit_stop_loss = False
    for i in range(start_idx + 1, exit_idx + 1):
        low = kline[i]["low"]
        if low < entry_price * (1 + stop_loss):
            exit_price = entry_price * (1 + stop_loss)
            exit_date = kline[i]["date"]
            hit_stop_loss = True
            break

    ret = (exit_price - entry_price) / entry_price * 100
    peak = max(k["high"] for k in kline[start_idx + 1:exit_idx + 1]) if not hit_stop_loss else max_price
    trough = min(k["low"] for k in kline[start_idx + 1:exit_idx + 1]) if not hit_stop_loss else min_price
    max_dd = (trough - peak) / peak * 100 if peak > 0 else 0

    return {
        "code": code,
        "entry_date": entry["date"],
        "entry_price": round(entry_price, 2),
        "exit_date": exit_date,
        "exit_price": round(exit_price, 2),
        "return_pct": round(ret, 2),
        "max_drawdown": round(max_dd, 2),
        "hit_stop_loss": hit_stop_loss,
        "direction": "盈利" if ret > 0 else ("亏损" if ret < 0 else "持平"),
        "holding_days": exit_idx - start_idx,
    }


def run_backtest(days=90, holding_periods=None, stop_loss=-0.05):
    """主回测入口"""
    if holding_periods is None:
        holding_periods = [5, 10, 20, 30]

    signals = load_buy_signals(days=days)

    buy_signals = [s for s in signals if s["advice"] in ("买入", "关注")]
    if not buy_signals:
        return {"总信号数": len(signals), "买入信号": 0, "成交": 0, "结果": {}, "总结": "无买入信号可回测"}

    all_results = []
    for sig in buy_signals:
        trade = simulate_trade(sig["code"], sig["date"], holding_days=holding_periods[-1], stop_loss=stop_loss)
        if trade:
            trade["advice"] = sig["advice"]
            trade["confidence"] = sig["confidence"]
            trade["title"] = sig["title"]
            trade["date"] = sig["date"]
            all_results.append(trade)

    period_results = {}
    for hp in holding_periods:
        trades = []
        for t in all_results:
            if t["holding_days"] >= hp:
                adj_ret = t["return_pct"]
                trades.append({**t, "return_pct_adj": adj_ret})

        if not trades:
            period_results[f"{hp}d"] = {"交易次数": 0}
            continue

        returns = [t["return_pct_adj"] for t in trades]
        wins = [r for r in returns if r > 0]
        losses = [r for r in returns if r < 0]
        win_rate = len(wins) / len(returns) * 100 if returns else 0
        avg_ret = sum(returns) / len(returns)
        total_gain = sum(wins) if wins else 0
        total_loss = abs(sum(losses)) if losses else 1
        profit_factor = total_gain / total_loss if total_loss > 0 else 0
        max_loss = min(returns) if returns else 0
        max_gain = max(returns) if returns else 0

        period_results[f"{hp}d"] = {
            "交易次数": len(trades),
            "胜率": round(win_rate, 1),
            "平均收益率": round(avg_ret, 2),
            "总盈利": round(total_gain, 2),
            "总亏损": round(total_loss, 2),
            "盈亏比": round(profit_factor, 2),
            "最大单笔盈利": round(max_gain, 2),
            "最大单笔亏损": round(max_loss, 2),
            "盈利次数": len(wins),
            "亏损次数": len(losses),
        }

    summary_parts = []
    for hp, r in sorted(period_results.items()):
        if r.get("交易次数", 0) == 0:
            continue
        summary_parts.append(
            f"  持有{hp}: 交易{r['交易次数']}次 | "
            f"胜率{r['胜率']}% | "
            f"平均{r['平均收益率']:+.2f}% | "
            f"盈亏比{r['盈亏比']}"
        )

    return {
        "总信号数": len(signals),
        "买入信号": len(buy_signals),
        "成交": len(all_results),
        "结果": period_results,
        "总结": "\n".join(summary_parts),
        "trades": all_results,
    }


def print_backtest_report(result):
    """终端输出回测报告"""
    sep = "=" * 58
    sub = "-" * 58

    lines = []
    lines.append(sep)
    lines.append("   [SCOUT] 策略回测报告")
    lines.append(f"   {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    lines.append(sep)
    lines.append("")

    lines.append(f"  回测范围: 最近 {result.get('回测天数', 90)} 天")
    lines.append(f"  总信号数: {result['总信号数']}（含非买入建议）")
    lines.append(f"  买入信号: {result['买入信号']} 条")
    lines.append(f"  实际成交: {result['成交']} 笔")
    lines.append("")

    if result["成交"] == 0:
        lines.append("  ⚠️ 无足够数据完成回测")
        lines.append("  （需要历史分析记录中包含股票代码且建议为买入）")
        lines.append("")
        lines.append(sep)
        lines.append("  [!] 说明: 系统运行天数不足或AI未给出买入建议时无数据")
        lines.append(sep)
        report = "\n".join(lines)
        print("\n" + report + "\n", flush=True)
        return report

    lines.append(sub)
    lines.append("  【各持有期表现】")
    lines.append("")

    for hp_key in sorted(result["结果"].keys(), key=lambda k: int(k.replace("d", ""))):
        r = result["结果"][hp_key]
        if r.get("交易次数", 0) == 0:
            lines.append(f"  {hp_key}: 无交易数据")
            continue

        lines.append(f"  📅 持有期: {hp_key}")
        lines.append(f"     交易次数: {r['交易次数']}")
        lines.append(f"     胜率:     {r['胜率']}%  ({r['盈利次数']}/{r['交易次数']})")
        lines.append(f"     平均收益: {r['平均收益率']:+.2f}%")
        lines.append(f"     盈亏比:   {r['盈亏比']}")
        lines.append(f"     最大盈利: {r['最大单笔盈利']:+.2f}%")
        lines.append(f"     最大亏损: {r['最大单笔亏损']:+.2f}%")
        lines.append("")

    lines.append(sub)
    lines.append("  【逐笔明细（买入信号）】")
    lines.append("")

    trades = result.get("trades", [])
    for t in trades[:30]:
        conf_tag = {"高": "[H]", "中": "[M]", "低": "[L]"}.get(t.get("confidence", ""), "")
        prof_tag = "🟢" if t["return_pct"] > 0 else "🔴"
        lines.append(f"  {prof_tag} {t['code']} {t['entry_date']}→{t['exit_date']}  "
                     f"买入价{t['entry_price']}→卖出价{t['exit_price']}  "
                     f"{t['return_pct']:+.2f}% {conf_tag}")
        if t["hit_stop_loss"]:
            lines.append(f"     ⚠️ 触发止损")

    if len(trades) > 30:
        lines.append(f"  ... 还有 {len(trades) - 30} 笔未显示")

    lines.append("")
    lines.append(sep)
    lines.append("  [!] 提示: 回测基于历史数据，过去表现不代表未来收益")
    lines.append(sep)

    report = "\n".join(lines)
    print("\n" + report + "\n", flush=True)
    return report


def save_report(result, days=90):
    """保存回测报告到文件"""
    report_dir = os.path.join(DATA_DIR, "reports")
    os.makedirs(report_dir, exist_ok=True)
    report = print_backtest_report(result)
    today = datetime.now().strftime("%Y%m%d")
    fpath = os.path.join(report_dir, f"backtest_{today}.txt")
    with open(fpath, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"  回测报告已保存: {fpath}", flush=True)
    return fpath


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="SCOUT 策略回测")
    parser.add_argument("--days", type=int, default=90, help="回测天数")
    parser.add_argument("--hold", type=str, default="5,10,20,30", help="持有期（逗号分隔）")
    parser.add_argument("--stop-loss", type=float, default=-0.05, help="止损线")
    args = parser.parse_args()

    holding_periods = [int(h) for h in args.hold.split(",")]
    result = run_backtest(days=args.days, holding_periods=holding_periods, stop_loss=args.stop_loss)
    result["回测天数"] = args.days
    print_backtest_report(result)
    save_report(result, days=args.days)
