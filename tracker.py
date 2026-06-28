"""
SCOUT 推荐追踪系统
==================
记录每次 _pick_rank() 输出的狙击清单标的，定期评估实际表现，生成月度业绩报告。

工作流程:
  1. record_picks() — 每天 main.py 调用，将本次推荐录入 pick_registry 表
  2. evaluate_picks() — 每天 main.py 调用，检查已过持有期但未评估的推荐
  3. generate_report() — 按需生成月度/累计业绩报告

数据流:
  [ _pick_rank() 输出 ] ───→ [ record_picks() ] ───→ [ SQLite: pick_registry ]
                                                              │
  [ N 天后检查走势 ]  ←─── [ evaluate_picks() ]  ←─── [ 读取待评估推荐 ]
                                                              │
  [ SQLite: pick_evaluations ]  ←─── [ 保存评估结果 ]
                                                              │
  [ generate_report() ]  ←─── [ 读取汇总统计 ]  ←─── [ 输出月度报告 ]
"""

import os
import sys
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import DATA_DIR
from storage import ScoutStorage
from market import get_kline


def record_picks(picks, storage=None):
    """将本次狙击清单记录到数据库

    Args:
        picks: _pick_rank() 返回的推荐列表
        storage: ScoutStorage 实例（可选，自动创建）

    Returns:
        int: 成功记录的推荐数
    """
    if not picks:
        return 0
    if storage is None:
        storage = ScoutStorage(DATA_DIR)
    saved = storage.save_picks_batch(picks)
    print(f"  [推荐追踪] 已记录 {saved}/{len(picks)} 条推荐到数据库", flush=True)
    return saved


def _simulate_trade(code, entry_date_str, holding_days=10, stop_loss_price=0.0):
    """模拟一笔交易：在 entry_date 后第一个交易日买入，持有 holding_days 天

    Args:
        code: 股票代码
        entry_date_str: 推荐日期 (YYYY-MM-DD)
        holding_days: 持有多少个交易日
        stop_loss_price: 止损价（0 = 不止损）

    Returns:
        dict or None: {"exit_price", "exit_date", "return_pct", "max_drawdown", "hit_stop_loss"}
    """
    kline = get_kline(code, count=holding_days + 20)
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

    hit_stop_loss = False
    exit_idx = min(start_idx + 1 + holding_days, len(kline) - 1)
    exit_date = kline[exit_idx]["date"]
    exit_price = kline[exit_idx]["open"]

    # 检查持有期间是否触发止损
    if stop_loss_price > 0:
        for i in range(start_idx + 1, exit_idx + 1):
            low = kline[i]["low"]
            if low <= stop_loss_price:
                exit_price = min(kline[i]["open"], stop_loss_price)
                exit_date = kline[i]["date"]
                hit_stop_loss = True
                break

    ret = (exit_price - entry_price) / entry_price * 100

    # 计算最大回撤
    peak = entry_price
    max_dd = 0.0
    for i in range(start_idx + 1, exit_idx + 1):
        high = kline[i]["high"]
        low = kline[i]["low"]
        if high > peak:
            peak = high
        dd = (low - peak) / peak * 100 if peak > 0 else 0
        if dd < max_dd:
            max_dd = dd

    return {
        "exit_price": round(exit_price, 2),
        "exit_date": exit_date,
        "return_pct": round(ret, 2),
        "max_drawdown": round(max_dd, 2),
        "hit_stop_loss": hit_stop_loss,
    }


def evaluate_picks(storage=None, holding_periods=None, days_back=90):
    """检查所有待评估推荐的实际表现

    Args:
        storage: ScoutStorage 实例
        holding_periods: 要检查的持有期列表，默认 [5, 10, 20, 30]
        days_back: 回溯多少天内的推荐

    Returns:
        dict: { "evaluated": int, "skipped": int, "results": [str] }
    """
    if holding_periods is None:
        holding_periods = [5, 10, 20, 30]
    if storage is None:
        storage = ScoutStorage(DATA_DIR)

    results = []
    total_evaluated = 0
    total_skipped = 0

    for hp in holding_periods:
        pending = storage.get_pending_evaluations(
            min_holding=hp, max_days_old=days_back
        )
        if not pending:
            continue

        for item in pending:
            trade = _simulate_trade(
                item["code"],
                item["report_date"],
                holding_days=hp,
                stop_loss_price=item.get("stop_loss_price", 0.0),
            )
            if trade is None:
                total_skipped += 1
                continue

            storage.save_pick_evaluation(
                pick_id=item["id"],
                holding_days=hp,
                exit_price=trade["exit_price"],
                exit_date=trade["exit_date"],
                return_pct=trade["return_pct"],
                max_drawdown=trade["max_drawdown"],
                hit_stop_loss=trade["hit_stop_loss"],
                conviction_level=item.get("conviction_level", "中"),
            )

            hit_tag = " ⚠️止损" if trade["hit_stop_loss"] else ""
            results.append(
                f"  {item['report_date']} #{item['id']} {item['code']} "
                f"持有{hp}d: {trade['return_pct']:+.2f}%{hit_tag}"
            )
            total_evaluated += 1

    if total_evaluated > 0:
        print(f"  [推荐评估] 完成 {total_evaluated} 次评估, {total_skipped} 跳过", flush=True)
        for line in results[-10:]:
            print(line, flush=True)
    else:
        print(f"  [推荐评估] 暂无待评估推荐", flush=True)

    return {
        "evaluated": total_evaluated,
        "skipped": total_skipped,
        "results": results,
    }


def generate_report(storage=None, months=1):
    """生成月度/累计业绩报告

    Args:
        storage: ScoutStorage 实例
        months: 回溯几个月

    Returns:
        str: 格式化报告文本
    """
    if storage is None:
        storage = ScoutStorage(DATA_DIR)

    since_days = months * 30

    # 总体统计
    summary = storage.get_pick_summary(since_days=since_days)
    if not summary:
        return "暂无推荐记录，无法生成业绩报告"

    # 按确信度分组
    by_conviction = storage.get_pick_summary_by_conviction(since_days=since_days)

    lines = []
    sep = "=" * 58
    sub = "-" * 58

    lines.append(sep)
    lines.append("   [SCOUT] 推荐追踪业绩报告")
    lines.append(f"   统计周期: 最近 {months} 个月（{since_days} 天）")
    lines.append(f"   生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    lines.append(sep)
    lines.append("")

    # 总体概览
    lines.append("  【总体表现】")
    lines.append(sub)
    lines.append(f"  总推荐次数: {summary['total_picks']} 次")
    lines.append(f"  已评估:     {summary['evaluated']} 次")
    if summary["total_eval"] > 0:
        lines.append(f"  平均收益率: {summary['avg_return']:+.2f}%")
        lines.append(f"  胜率:       {summary['win_rate']}%  "
                     f"({summary['wins']}/{summary['total_eval']})")
        lines.append(f"  平均盈利:   {summary['avg_win']:+.2f}%")
        lines.append(f"  平均亏损:   {summary['avg_loss']:+.2f}%")
        lines.append(f"  最大盈利:   {summary['best_return']:+.2f}%")
        lines.append(f"  最大亏损:   {summary['worst_return']:+.2f}%")
    else:
        lines.append("  （尚无可评估数据，推荐后需要至少5个交易日才能评估）")
    lines.append("")

    # 按确信度分组
    if by_conviction:
        lines.append("  【按确信度分组】")
        lines.append(sub)
        icons = {"高": "[🟢🟢🟢]", "中": "[🟢🟡⚪]", "低": "[⚪⚪🔴]"}
        for g in by_conviction:
            icon = icons.get(g["level"], "")
            lines.append(f"  {icon} {g['level']}确信度 ({g['evaluations']}笔):")
            lines.append(f"     胜率 {g['win_rate']}%  |  "
                         f"平均收益 {g['avg_return']:+.2f}%")

        # 高级 vs 低级 对比验证
        high_group = [g for g in by_conviction if g["level"] == "高"]
        low_group = [g for g in by_conviction if g["level"] == "低"]
        if high_group and low_group:
            h = high_group[0]
            l = low_group[0]
            if h["evaluations"] >= 3 and l["evaluations"] >= 3:
                diff = h["win_rate"] - l["win_rate"]
                lines.append("")
                lines.append(f"  📊 确信度验证: 高确信度胜率({h['win_rate']}%) vs "
                             f"低确信度胜率({l['win_rate']}%)")
                if diff >= 10:
                    lines.append(f"     ✅ 相差 {diff:.1f}%，确信度系统有效!")
                elif diff > 0:
                    lines.append(f"     ⚡ 相差 {diff:.1f}%，确信度方向正确但需更多数据")
                else:
                    lines.append(f"     ⚠️ 确信度与胜率反向，需要调校模型")
        lines.append("")

    # 按持有期统计
    lines.append("  【按持有期统计】")
    lines.append(sub)
    try:
        conn = sqlite3.connect(os.path.join(DATA_DIR, "scout.db"))
        c = conn.cursor()
        c.execute(
            """SELECT pe.holding_days,
                      COUNT(*) as cnt,
                      AVG(pe.return_pct) as avg_ret,
                      SUM(CASE WHEN pe.return_pct > 0 THEN 1 ELSE 0 END) as wins
               FROM pick_evaluations pe
               JOIN pick_registry pr ON pr.id = pe.pick_id
               WHERE pr.report_date >= date('now', ?)
               GROUP BY pe.holding_days
               ORDER BY pe.holding_days ASC""",
            (f"-{since_days} days",)
        )
        period_rows = c.fetchall()
        conn.close()
        for pr in period_rows:
            hp, cnt, avg_ret, wins = pr
            wins = wins or 0
            wr = round(wins / cnt * 100, 1) if cnt > 0 else 0
            lines.append(f"  持有 {hp}d: {cnt}笔 | 平均 {avg_ret:+.2f}% | "
                         f"胜率 {wr}% ({wins}/{cnt})")
    except Exception:
        lines.append("  持有期统计暂不可用")
    lines.append("")

    lines.append(sep)
    lines.append("  [!] 提示: 所有模拟交易基于历史K线数据")
    lines.append("     过去表现不代表未来收益，仅供参考")
    lines.append(sep)

    return "\n".join(lines)


import sqlite3

if __name__ == "__main__":
    # 独立运行：生成并打印报告
    report = generate_report(months=1)
    print("\n" + report + "\n", flush=True)
