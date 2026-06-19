import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import NEWS_SOURCES, MAX_NEWS, DATA_DIR, MAX_SCREENED_STOCKS
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


def main():
    print(flush=True)
    print("=" * 58, flush=True)
    print("   [SCOUT] 情报系统启动", flush=True)
    print(f"   {now_str()}", flush=True)
    print("=" * 58, flush=True)
    print(flush=True)

    stock_results = None
    report_parts = []

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

            stock_report = build_stock_report(stock_results)
            report_parts.append(stock_report)
            print_report(stock_report)

    print("【第8步】资金面数据采集...", flush=True)
    capital_data = get_capital_summary()
    capital_report = build_capital_report(capital_data)
    report_parts.append(capital_report)
    print_report(capital_report)

    picks = _pick_rank(stock_results or [], results)
    picks_report = build_picks_report(picks, results)
    report_parts.append(picks_report)
    print_report(picks_report)

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

    print("【第9步】推送通知...", flush=True)
    wechat_summary = build_wechat_summary(results, stock_results, capital_data)
    wechat_picks = build_wechat_picks(picks, results)
    push_wechat(
        title=f"SCOUT每日情报 {now_str()[:10]}",
        content=wechat_summary + "\n" + wechat_picks
    )
    print(flush=True)

    print("=" * 58, flush=True)
    print("   [OK] SCOUT 本次运行完成", flush=True)
    print("=" * 58, flush=True)
    print(flush=True)


if __name__ == "__main__":
    main()
