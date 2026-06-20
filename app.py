import os
import sys
import json
import re
from datetime import datetime, timedelta
from flask import Flask, render_template, request, jsonify

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import DATA_DIR, NEWS_SOURCES, MAX_NEWS, MAX_SCREENED_STOCKS
from storage import ScoutStorage
from reporter import calc_market_light
from capital import get_capital_summary, calc_capital_light as calc_cl

app = Flask(__name__)
app.config["DATA_DIR"] = DATA_DIR


def _get_storage():
    return ScoutStorage(app.config["DATA_DIR"])


def _load_report_files(days=14):
    report_dir = os.path.join(app.config["DATA_DIR"], "reports")
    if not os.path.isdir(report_dir):
        return []
    files = []
    for f in sorted(os.listdir(report_dir), reverse=True):
        if f.startswith("report_") and f.endswith(".txt"):
            fpath = os.path.join(report_dir, f)
            stat = os.stat(fpath)
            date_str = f.replace("report_", "").replace(".txt", "")
            if date_str.isdigit() and len(date_str) == 8:
                display = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:]}"
            else:
                display = date_str
            files.append({
                "filename": f,
                "date": display,
                "path": fpath,
                "size": stat.st_size,
                "mtime": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M"),
            })
    return files


def _parse_report_sections(text):
    sections = re.split(r'={5,}', text)
    result = {}
    for sec in sections:
        sec = sec.strip()
        if not sec:
            continue
        first_line = sec.split("\n")[0].strip()
        if "资金面" in first_line:
            result["capital"] = sec
        elif "狙击清单" in first_line or "今日狙击" in first_line:
            result["picks"] = sec
        elif "决策仪表盘" in first_line or "仪表盘" in first_line:
            result["stocks"] = sec
        elif "情报简报" in first_line or "每日情报" in first_line:
            result["news"] = sec
        else:
            result.setdefault("other", []).append(sec)
    return result


def _read_report(filename):
    fpath = os.path.join(app.config["DATA_DIR"], "reports", filename)
    if not os.path.isfile(fpath):
        return None
    with open(fpath, "r", encoding="utf-8") as f:
        return f.read()


def _get_db_stats(storage):
    history = storage.get_history(days=7)
    total = len(history)
    bullish = sum(1 for h in history if h[4] == "利好")
    bearish = sum(1 for h in history if h[4] == "利空")
    buy = sum(1 for h in history if h[5] == "买入")
    return {
        "total": total,
        "bullish": bullish,
        "bearish": bearish,
        "buy": buy,
    }


def _get_last_run_time():
    report_dir = os.path.join(app.config["DATA_DIR"], "reports")
    if not os.path.isdir(report_dir):
        return None
    files = [f for f in os.listdir(report_dir) if f.startswith("report_") and f.endswith(".txt")]
    if not files:
        return None
    latest = max(files, key=lambda f: os.path.getmtime(os.path.join(report_dir, f)))
    return datetime.fromtimestamp(os.path.getmtime(os.path.join(report_dir, latest))).strftime("%Y-%m-%d %H:%M")


def _get_market_light_from_reports():
    reports = _load_report_files(days=1)
    if not reports:
        return None
    text = _read_report(reports[0]["filename"])
    if not text:
        return None
    m = re.search(r'市场光信号: (🟢🟢🟢|🟢🟢⚪|🟢⚪⚪|⚪⚪🔴|🔴🔴🔴)\s+(.*?)[（(]评分(\d+)', text)
    if m:
        return {
            "light": m.group(1),
            "label": m.group(2).strip(),
            "score": int(m.group(3)),
        }
    m2 = re.search(r'市场光信号.*?(🟢🟢🟢|🟢🟢⚪|🟢⚪⚪|⚪⚪🔴|🔴🔴🔴).*?(评分[：:]?\d+)', text)
    if m2:
        score_m = re.search(r'\d+', m2.group(2))
        score = int(score_m.group()) if score_m else 50
        return {"light": m2.group(1), "label": "", "score": score}
    return None


# ─── Routes ────────────────────────────────────────────────────────────

@app.route("/")
def index():
    storage = _get_storage()
    stats = _get_db_stats(storage)
    reports = _load_report_files(days=14)
    last_run = _get_last_run_time()
    ml = _get_market_light_from_reports()

    cl = None
    try:
        cd = get_capital_summary()
        cl = calc_cl(cd)
    except Exception:
        pass

    today = datetime.now().strftime("%Y-%m-%d %H:%M")
    return render_template("index.html",
                           stats=stats,
                           reports=reports,
                           last_run=last_run,
                           ml=ml,
                           cl=cl,
                           today=today)


@app.route("/news")
def news_view():
    storage = _get_storage()
    history = storage.get_history(days=7)
    sentiment_filter = request.args.get("sentiment", "")
    advice_filter = request.args.get("advice", "")

    items = []
    for h in history:
        item = {
            "title": h[0],
            "source": h[1],
            "event_type": h[2],
            "confidence": h[3],
            "sentiment": h[4],
            "advice": h[5],
            "report_date": h[6],
        }
        if sentiment_filter and item["sentiment"] != sentiment_filter:
            continue
        if advice_filter and item["advice"] != advice_filter:
            continue
        items.append(item)

    return render_template("news.html", items=items,
                           sentiment_filter=sentiment_filter,
                           advice_filter=advice_filter)


@app.route("/stocks")
def stocks_view():
    reports = _load_report_files(days=14)
    stock_sections = []
    for r in reports:
        text = _read_report(r["filename"])
        if not text:
            continue
        sections = _parse_report_sections(text)
        content = sections.get("stocks") or sections.get("picks", "")
        if content:
            stock_sections.append({
                "date": r["date"],
                "filename": r["filename"],
                "content": content,
            })
    return render_template("stocks.html", stock_sections=stock_sections)


@app.route("/capital")
def capital_view():
    cd = None
    try:
        cd = get_capital_summary()
    except Exception as e:
        print(f"  [资本页面获取失败] {e}", flush=True)

    cl = None
    if cd:
        cl = calc_cl(cd)

    return render_template("capital.html",
                           capital_data=cd,
                           capital_light=cl)


@app.route("/history")
def history_view():
    filename = request.args.get("file", "")
    reports = _load_report_files(days=60)

    if filename:
        content = _read_report(filename)
        if content is None:
            content = "文件不存在或无法读取"
        return render_template("history.html",
                               reports=reports,
                               current_file=filename,
                               current_content=content)
    return render_template("history.html",
                           reports=reports,
                           current_file="",
                           current_content="")


_scout_status = {"status": "idle", "step": "", "message": "", "progress": ""}

def _run_scout_with_status():
    global _scout_status
    _scout_status = {"status": "running", "step": "", "message": "", "progress": ""}
    original_print = __builtins__.print if isinstance(__builtins__, dict) else __builtins__.print
    def capture_print(*args, **kwargs):
        msg = " ".join(str(a) for a in args)
        if "【" in msg:
            _scout_status["step"] = msg.strip()[:60]
        _scout_status["message"] = msg.strip()[-200:]
        if _scout_status["progress"]:
            parts = _scout_status["progress"].split("\n")
            parts.append(msg.strip()[-100:])
            _scout_status["progress"] = "\n".join(parts[-10:])
        else:
            _scout_status["progress"] = msg.strip()[-100:]
        original_print(*args, **kwargs)
    try:
        import builtins
        builtins.print = capture_print
        from main import main
        main()
        _scout_status["status"] = "done"
    except Exception as e:
        _scout_status["status"] = "error"
        _scout_status["message"] = str(e)
    finally:
        import builtins
        builtins.print = original_print


@app.route("/api/run", methods=["POST"])
def api_run_scout():
    global _scout_status
    if _scout_status["status"] == "running":
        return jsonify({"status": "busy", "message": "已有分析任务正在运行"}), 409
    try:
        import threading
        thread = threading.Thread(target=_run_scout_with_status, daemon=True)
        thread.start()
        return jsonify({"status": "started", "message": "SCOUT 分析已启动"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route("/api/status")
def api_scout_status():
    return jsonify(_scout_status)


@app.route("/api/stats")
def api_stats():
    storage = _get_storage()
    history = storage.get_history(days=30)
    stats = {"total": len(history)}
    for h in history:
        sent = h[4]
        stats[sent] = stats.get(sent, 0) + 1
    return jsonify(stats)


if __name__ == "__main__":
    print(f"  SCOUT Web Dashboard 启动")
    print(f"  访问地址: http://127.0.0.1:5000")
    print(f"  按 Ctrl+C 停止")
    app.run(debug=True, host="127.0.0.1", port=5000, use_reloader=False)
