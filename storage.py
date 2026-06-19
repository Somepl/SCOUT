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
        """)
        conn.commit()
        conn.close()

    def save_analysis_batch(self, results):
        report_date = today_str()
        saved = 0
        for r in results:
            try:
                conn = sqlite3.connect(self.db_path)
                c = conn.cursor()
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
                conn.commit()
                saved += 1
            except Exception as e:
                print(f"  [存储失败] {news.get('title','')[:30]} - {e}", flush=True)
            finally:
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
