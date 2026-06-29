import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import NEWS_SOURCES, MAX_NEWS, DATA_DIR, MAX_SCREENED_STOCKS
from config import USE_ML_SCORING, TRAIN_INTERVAL_DAYS, AUTO_REVIEW_ENABLED, AUTO_REVIEW_LOOKBACK_DAYS
from config import AUTO_REVIEW_CHECK_DAYS, AUTO_REVIEW_PROFIT_THRESHOLD
from collector import collect_all
from analyzer import analyze_news_batch, analyze_stocks_batch
from market import get_stock_analysis
from screener import discover_stocks
from storage import ScoutStorage
from reporter import build_report, print_report, build_wechat_summary, build_stock_report, calc_market_light, build_capital_report
from strategist import build_picks_report, build_wechat_picks, _pick_rank
from capital import get_capital_summary, calc_capital_light
from utils import deduplicate, now_str
from notifier import push_wechat
from backtest import run_backtest, print_backtest_report
from tracker import record_picks, evaluate_picks, generate_report


def main():
    print(flush=True)
    print("=" * 58, flush=True)
    print("   [SCOUT] 情报系统启动", flush=True)
    print(f"   {now_str()}", flush=True)
    print("=" * 58, flush=True)
    print(flush=True)

    stock_results = None
    report_parts = []

    if USE_ML_SCORING:
        print("【第0步】检查量化模型是否需要重新训练...", flush=True)
        try:
            from quant_model import QuantScorer
            scorer = QuantScorer()
            trained = False
            if not scorer.is_trained():
                print("  [量化模型] 模型不存在，开始训练...", flush=True)
                trained = scorer.train()
            else:
                trained = scorer.train_if_expired(interval_days=TRAIN_INTERVAL_DAYS)
            # 记录训练日志
            if trained:
                metrics = scorer.get_last_train_metrics()
                if metrics:
                    try:
                        storage = ScoutStorage(DATA_DIR)
                        storage.save_training_log(metrics)
                    except Exception:
                        pass
        except Exception as e:
            print(f"  [量化模型] 检查失败: {e}", flush=True)
        print(flush=True)

    print("【第1步】采集信息...", flush=True)
    raw_news = collect_all(NEWS_SOURCES)
    print(f"\n  共采集到 {len(raw_news)} 条原始消息", flush=True)
    print(flush=True)

    print("【第2步】去重处理...", flush=True)
    news_list = deduplicate(raw_news)
    print(f"  去重后剩余 {len(news_list)} 条", flush=True)
    print(flush=True)

    print("【第3步】AI分析...", flush=True)
    results = analyze_news_batch(news_list, max_items=MAX_NEWS)
    print(f"\n  完成 {len(results)} 条消息分析", flush=True)
    print(flush=True)

    print("【第4步】存储结果...", flush=True)
    storage = ScoutStorage(DATA_DIR)
    saved = storage.save_analysis_batch(results)
    print(f"  已保存 {saved} 条记录到数据库", flush=True)
    print(flush=True)

    print("【第5步】生成简报...", flush=True)
    report = build_report(results)
    report_parts.append(report)
    print_report(report)

    print("【第6步】热点筛选→发现候选股票...", flush=True)
    candidates, hot_sectors = discover_stocks(results, max_stocks=MAX_SCREENED_STOCKS)
    print(flush=True)

    if candidates:
        print("【第7步】个股行情+技术分析...", flush=True)
        stock_data_list = []
        for c in candidates:
            code = c["code"]
            print(f"  获取行情: {code}...", flush=True)
            data = get_stock_analysis(code)
            if data:
                data["source_sectors"] = c.get("source_sectors", [])
                stock_data_list.append(data)
                print(f"     {data['name']} {data['price']} ({data['change_pct']:+.2f}%)", flush=True)

        if stock_data_list:
            print(f"\n  行情获取完成，共 {len(stock_data_list)} 只", flush=True)
            print("  AI生成决策仪表盘...", flush=True)
            stock_results = analyze_stocks_batch(stock_data_list)

    print("【第8步】资金面数据采集...", flush=True)
    capital_data = get_capital_summary()
    capital_report = build_capital_report(capital_data)
    report_parts.append(capital_report)
    print_report(capital_report)

    # 在资金面数据到位后，为每只个股注入多信号确信度
    if stock_results:
        from strategist import calc_conviction
        for sr in stock_results:
            m = sr.get("market", {})
            conv = calc_conviction(m, results, capital_data)
            sr["conviction"] = conv
        stock_report = build_stock_report(stock_results)
        report_parts.append(stock_report)
        print_report(stock_report)

    picks = _pick_rank(stock_results or [], results, capital_data=capital_data)
    picks_report = build_picks_report(picks, results)
    report_parts.append(picks_report)
    print_report(picks_report)

    # 记录本次推荐到追踪数据库
    record_picks(picks, storage=storage)

    ml = calc_market_light(results, stock_results)
    cl = calc_capital_light(capital_data)
    print(f"\n【市场光信号】{ml['light']}  {ml['label']}", flush=True)
    print(f"【资金面信号】{cl['light']}  {cl['label']}", flush=True)
    ml_line = f"市场光信号: {ml['light']}  {ml['label']}（评分{ml['score']}）"
    cl_line = f"资金面信号: {cl['light']}  {cl['label']}（评分{cl['score']}）"

    report_parts.insert(0, cl_line)
    report_parts.insert(0, ml_line)
    report_file = os.path.join(DATA_DIR, "reports", f"report_{now_str()[:10].replace('-','')}.txt")
    os.makedirs(os.path.dirname(report_file), exist_ok=True)
    with open(report_file, "w", encoding="utf-8") as f:
        f.write("\n\n".join(report_parts))
    print(f"  简报已保存: {report_file}", flush=True)
    print(flush=True)

    print("【第9步】存储个股分析结果...", flush=True)
    if stock_results:
        storage.save_stock_analysis_batch(stock_results)
        print(f"  已保存 {len(stock_results)} 只个股分析到数据库", flush=True)
    print(flush=True)

    print("【第10步】策略回测验证...", flush=True)
    bt_result = run_backtest(days=90, holding_periods=[5, 10, 20], stop_loss=-0.05)
    bt_result["回测天数"] = 90
    bt_report = print_backtest_report(bt_result)
    report_parts.append(bt_report)
    print(flush=True)

    print("【第10.1步】推荐追踪评估...", flush=True)
    evaluate_picks(storage=storage, holding_periods=[5, 10, 20, 30], days_back=90)
    print(flush=True)

    if AUTO_REVIEW_ENABLED:
        print("【第10.5步】自动复盘追踪...", flush=True)
        try:
            ar_result = storage.auto_review(
                lookback_days=AUTO_REVIEW_LOOKBACK_DAYS,
                check_days=AUTO_REVIEW_CHECK_DAYS,
                profit_threshold=AUTO_REVIEW_PROFIT_THRESHOLD,
            )
            print(f"  自动复盘完成: 新增 {ar_result['reviewed']} 条, 跳过 {ar_result['skipped']} 条", flush=True)
            if ar_result["results"]:
                for line in ar_result["results"][-5:]:
                    print(line, flush=True)
            print(flush=True)
        except Exception as e:
            print(f"  [自动复盘失败] {e}", flush=True)
            print(flush=True)

    if AUTO_REVIEW_ENABLED:
        print("【第10.6步】个股仪表盘复盘...", flush=True)
        try:
            ars_result = storage.auto_review_stocks(
                lookback_days=AUTO_REVIEW_LOOKBACK_DAYS,
                check_days=AUTO_REVIEW_CHECK_DAYS,
                profit_threshold=AUTO_REVIEW_PROFIT_THRESHOLD,
            )
            print(f"  个股仪表盘复盘: 新增 {ars_result['reviewed']} 条, 跳过 {ars_result['skipped']} 条", flush=True)
            if ars_result["results"]:
                for line in ars_result["results"][-5:]:
                    print(line, flush=True)
            print(flush=True)
        except Exception as e:
            print(f"  [个股仪表盘复盘失败] {e}", flush=True)
            print(flush=True)

    # 每日推荐追踪摘要
    try:
        summary = storage.get_pick_summary(since_days=90)
        if summary and summary["total_eval"] > 0:
            print(f"  [推荐追踪] 累计{summary['total_eval']}次评估 | "
                  f"胜率{summary['win_rate']}% | "
                  f"平均收益{summary['avg_return']:+.2f}%", flush=True)
            # 每月1号和15号输出完整报告
            day_of_month = int(now_str()[8:10])
            if day_of_month in (1, 15):
                print("\n  [月度业绩报告]", flush=True)
                monthly_report = generate_report(storage=storage, months=1)
                for line in monthly_report.split("\n"):
                    print(f"  {line}", flush=True)
    except Exception as e:
        print(f"  [追踪摘要失败] {e}", flush=True)
    print(flush=True)

    print("【第11步】推送通知...", flush=True)
    # 获取复盘统计用于推送
    review_stats_for_push = None
    try:
        ar_data = storage.get_reviews(days=90, limit=200)
        ar_total = len(ar_data)
        ar_correct = sum(1 for r in ar_data if r["outcome"] == "正确")
        if ar_total > 0:
            review_stats_for_push = {
                "total": ar_total,
                "correct": ar_correct,
                "win_rate": round(ar_correct / ar_total * 100, 1),
            }
    except Exception:
        pass
    wechat_summary = build_wechat_summary(results, stock_results, capital_data, review_stats=review_stats_for_push)
    wechat_picks = build_wechat_picks(picks, results)
    push_wechat(
        title=f"SCOUT每日情报 {now_str()[:10]}",
        content=wechat_summary + "\n" + wechat_picks
    )
    print(flush=True)

    print("=" * 58, flush=True)
    print("   [SCOUT] 全链路运行完成", flush=True)
    print("=" * 58, flush=True)
    print(flush=True)


if __name__ == "__main__":
    main()
