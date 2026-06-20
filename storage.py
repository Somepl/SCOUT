import sqlite3
import os
import json
from datetime import datetime
from utils import ensure_dir, now_str, today_str


class ScoutStorage:
    def __init__(self, data_dir):
        self.data_dir = data_dir
        ensure_dir(data_dir)
        self.db_path = os.path.join(data_dir, "scout.db")
        self._init_db()

    def _init_db(self):
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.executescript("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT,
                content TEXT,
                source TEXT,
                url TEXT,
                publish_time TEXT,
                collected_time TEXT DEFAULT (datetime('now','localtime'))
            );
            CREATE TABLE IF NOT EXISTS analysis (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                message_id INTEGER,
                event_type TEXT,
                confidence TEXT,
                affected_sectors TEXT,
                affected_concept TEXT,
                impact_level TEXT,
                time_horizon TEXT,
                market_sentiment TEXT,
                advice TEXT,
                advice_reason TEXT,
                reason TEXT,
                analysis_raw TEXT,
                report_date TEXT,
                created_time TEXT DEFAULT (datetime('now','localtime'))
            );
            CREATE TABLE IF NOT EXISTS tracking (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                analysis_id INTEGER,
                actual_outcome TEXT,
                outcome_detail TEXT,
                reviewed_at TEXT DEFAULT (datetime('now','localtime'))
            );
            CREATE TABLE IF NOT EXISTS stock_analysis (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                code TEXT,
                name TEXT,
                price REAL,
                score INTEGER,
                signal TEXT,
                action TEXT,
                entry_plan TEXT,
                stop_loss TEXT,
                take_profit TEXT,
                suggested_position TEXT,
                report_date TEXT,
                analysis_json TEXT,
                created_time TEXT DEFAULT (datetime('now','localtime'))
            );
        """)
        conn.commit()
        conn.close()

    def save_analysis_batch(self, results):
        report_date = today_str()
        saved = 0
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        for r in results:
            try:
                news = r["news"]
                a = r["analysis"]
                c.execute(
                    "INSERT INTO messages (title, content, source, url, publish_time) VALUES (?,?,?,?,?)",
                    (news["title"], news["content"], news["source"],
                     news.get("url", ""), news.get("publish_time", now_str()))
                )
                msg_id = c.lastrowid
                c.execute(
                    """INSERT INTO analysis
                       (message_id, event_type, confidence, affected_sectors, affected_concept,
                        impact_level, time_horizon, market_sentiment, advice, advice_reason,
                        reason, analysis_raw, report_date)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (msg_id,
                     a.get("event_type", ""),
                     a.get("confidence", ""),
                     json.dumps(a.get("affected_sectors", []), ensure_ascii=False),
                     json.dumps(a.get("affected_concept", []), ensure_ascii=False),
                     a.get("impact_level", ""),
                     a.get("time_horizon", ""),
                     a.get("market_sentiment", ""),
                     a.get("advice", ""),
                     a.get("advice_reason", ""),
                     a.get("reason", ""),
                     json.dumps(a, ensure_ascii=False),
                     report_date)
                )
                saved += 1
            except Exception as e:
                print(f"  [存储失败] {news.get('title','')[:30]} - {e}", flush=True)
        conn.commit()
        conn.close()
        return saved

    def get_history(self, days=7):
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute(
            """SELECT m.title, m.source, a.event_type, a.confidence,
                      a.market_sentiment, a.advice, a.report_date
               FROM messages m
               JOIN analysis a ON m.id = a.message_id
               WHERE a.report_date >= date('now', ?)
               ORDER BY a.created_time DESC""",
            (f"-{days} days",)
        )
        rows = c.fetchall()
        conn.close()
        return rows

    def get_unreviewed(self, days=30):
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute(
            """SELECT a.id, a.report_date, m.title, m.source,
                      a.event_type, a.confidence, a.market_sentiment,
                      a.advice, a.advice_reason, a.reason
               FROM analysis a
               JOIN messages m ON m.id = a.message_id
               LEFT JOIN tracking t ON t.analysis_id = a.id
               WHERE t.id IS NULL
               AND a.report_date >= date('now', ?)
               ORDER BY a.report_date DESC, a.id DESC""",
            (f"-{days} days",)
        )
        rows = c.fetchall()
        conn.close()
        return rows

    def save_review(self, analysis_id, outcome, detail=""):
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute(
            "INSERT INTO tracking (analysis_id, actual_outcome, outcome_detail) VALUES (?,?,?)",
            (analysis_id, outcome, detail)
        )
        conn.commit()
        conn.close()

    def save_stock_analysis_batch(self, stock_results):
        report_date = today_str()
        saved = 0
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        for r in stock_results:
            try:
                m = r["market"]
                d = r.get("dashboard", {})
                bp = d.get("battle_plan", {})
                ep = bp.get("entry_plan", {})
                tp = bp.get("take_profit", {})
                pos = bp.get("position", {})
                c.execute(
                    """INSERT INTO stock_analysis
                       (code, name, price, score, signal, action,
                        entry_plan, stop_loss, take_profit, suggested_position,
                        report_date, analysis_json)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (m.get("code", ""),
                     m.get("name", ""),
                     m.get("price", 0),
                     m.get("score", 0),
                     m.get("signal", ""),
                     bp.get("action", ""),
                     json.dumps(ep, ensure_ascii=False),
                     ep.get("stop_loss", ""),
                     json.dumps(tp, ensure_ascii=False),
                     pos.get("suggested_position", ""),
                     report_date,
                     json.dumps(d, ensure_ascii=False))
                )
                saved += 1
            except Exception as e:
                print(f"  [个股存储失败] {m.get('code','')} - {e}", flush=True)
        conn.commit()
        conn.close()
        return saved

    def get_buy_signals(self, days=90):
        conn = sqlite3.connect(self.db_path)
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

    def get_stock_history(self, days=30):
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute(
            """SELECT code, name, price, score, signal, action, report_date
               FROM stock_analysis
               WHERE report_date >= date('now', ?)
               ORDER BY report_date DESC, score DESC""",
            (f"-{days} days",)
        )
        rows = c.fetchall()
        conn.close()
        return rows

    def get_stats(self, days=90):
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute(
            """SELECT t.actual_outcome, COUNT(*) as cnt
               FROM tracking t
               JOIN analysis a ON a.id = t.analysis_id
               WHERE a.report_date >= date('now', ?)
               GROUP BY t.actual_outcome""",
            (f"-{days} days",)
        )
        rows = c.fetchall()
        conn.close()
        stats = {}
        for outcome, cnt in rows:
            stats[outcome] = cnt
        return stats

    def auto_review(self, lookback_days=90, check_days=None, profit_threshold=3.0):
        """自动复盘：追踪历史预判后续走势，无需手动评价

        Args:
            lookback_days: 回溯多少天内的预判
            check_days: 发出预判后 N 个交易日复查（列表）
            profit_threshold: 涨幅超过此值视为"正确"（%）

        Returns:
            dict: { "reviewed": int, "skipped": int, "results": [str] }
        """
        if check_days is None:
            check_days = [5, 10]

        results = []
        reviewed = 0
        skipped = 0

        analysis_list = self._get_analysis_with_codes(days=lookback_days)
        for item in analysis_list:
            aid, report_date, analysis_raw, advice = item
            already_reviewed = self._is_reviewed(aid)
            if already_reviewed:
                continue

            codes = self._extract_codes(analysis_raw)
            if not codes:
                skipped += 1
                continue

            report_dt = datetime.strptime(report_date, "%Y-%m-%d")
            days_since = (datetime.now() - report_dt).days
            if days_since < min(check_days):
                skipped += 1
                continue

            best_ret = None
            best_worst = None
            best_code = None
            for code in codes:
                result = self._check_stock_performance(code, report_date, check_days)
                if result is not None:
                    ret, worst = result
                    if best_ret is None or ret > best_ret:
                        best_ret = ret
                        best_worst = worst
                        best_code = code

            if best_ret is None:
                skipped += 1
                continue

            if best_ret > profit_threshold:
                outcome = "正确"
                detail = f"自动复盘: {best_code} 涨幅 {best_ret:+.2f}%"
            elif best_ret > -profit_threshold:
                outcome = "部分正确"
                detail = f"自动复盘: {best_code} 涨幅 {best_ret:+.2f}%（阈值±{profit_threshold}%）"
            else:
                outcome = "错误"
                detail = f"自动复盘: {best_code} 跌幅 {best_ret:+.2f}%"
            if best_worst is not None and best_worst < -profit_threshold:
                detail += f"（期间最深回撤{best_worst:.2f}%）"

            self.save_review(aid, outcome, detail)
            reviewed += 1
            results.append(f"  {report_date} #{aid}: {outcome} ({detail})")

        return {
            "reviewed": reviewed,
            "skipped": skipped,
            "results": results,
        }

    def _get_analysis_with_codes(self, days=90):
        """获取近期含股票代码的分析记录"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute(
            """SELECT a.id, a.report_date, a.analysis_raw, a.advice
               FROM analysis a
               WHERE a.report_date >= date('now', ?)
               ORDER BY a.report_date ASC""",
            (f"-{days} days",)
        )
        rows = c.fetchall()
        conn.close()
        result = []
        for row in rows:
            result.append({"id": row[0], "date": row[1], "raw": row[2], "advice": row[3]})
        return result

    def _is_reviewed(self, analysis_id):
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM tracking WHERE analysis_id=?", (analysis_id,))
        cnt = c.fetchone()[0]
        conn.close()
        return cnt > 0

    def _extract_codes(self, raw_json):
        if not raw_json:
            return []
        try:
            raw = json.loads(raw_json)
        except (json.JSONDecodeError, TypeError):
            return []
        codes = raw.get("stock_codes", [])
        valid = []
        for code in codes:
            code = code.strip()
            if not code:
                continue
            if not (code.startswith("6") or code.startswith("0") or code.startswith("3")):
                continue
            if len(code) != 6:
                continue
            valid.append(code)
        return valid

    def _check_stock_performance(self, code, report_date, check_days):
        """检查股票在 report_date 后的 check_days 内表现。
        返回 (best_return, worst_drawdown) — best_return 用于判定正确性。
        """
        from market import get_kline
        max_needed = max(check_days) + 10
        kline = get_kline(code, count=max_needed + 20)
        if not kline:
            return None
        kline = sorted(kline, key=lambda x: x["date"])
        start_idx = -1
        for i, k in enumerate(kline):
            if k["date"] >= report_date[:10]:
                start_idx = i
                break
        if start_idx < 0 or start_idx >= len(kline) - 1:
            return None
        entry_price = kline[start_idx + 1]["open"]
        if entry_price <= 0:
            return None

        best_ret = None
        for cd in check_days:
            idx = min(start_idx + 1 + cd, len(kline) - 1)
            price = kline[idx]["open"]
            ret = (price - entry_price) / entry_price * 100
            if best_ret is None or ret > best_ret:
                best_ret = ret

        worst_low = None
        end = min(start_idx + 1 + max(check_days), len(kline))
        for i in range(start_idx + 1, end):
            low = kline[i]["low"]
            ret = (low - entry_price) / entry_price * 100
            if worst_low is None or ret < worst_low:
                worst_low = ret

        return (best_ret, worst_low)
