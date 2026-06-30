import sqlite3
import os
import json
import re
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
            CREATE TABLE IF NOT EXISTS pick_registry (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                code TEXT,
                name TEXT,
                entry_price REAL,
                conviction_level TEXT,
                conviction_score INTEGER,
                tech_score INTEGER,
                rank_score REAL,
                source_sectors TEXT,
                action TEXT,
                signal TEXT,
                stop_loss_price REAL,
                report_date TEXT,
                status TEXT DEFAULT 'active',
                created_time TEXT DEFAULT (datetime('now','localtime'))
            );
            CREATE TABLE IF NOT EXISTS model_training_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                train_date TEXT,
                num_stocks INTEGER,
                num_samples INTEGER,
                num_features INTEGER,
                cv_mae REAL,
                cv_correlation REAL,
                cv_direction_accuracy REAL,
                classifier_accuracy REAL,
                created_time TEXT DEFAULT (datetime('now','localtime'))
            );
            CREATE TABLE IF NOT EXISTS pick_evaluations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                pick_id INTEGER,
                holding_days INTEGER,
                exit_price REAL,
                exit_date TEXT,
                return_pct REAL,
                max_drawdown REAL,
                hit_stop_loss INTEGER DEFAULT 0,
                conviction_level TEXT,
                checked_date TEXT DEFAULT (date('now','localtime')),
                FOREIGN KEY (pick_id) REFERENCES pick_registry(id)
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

    def save_pick(self, pick_data):
        """记录一条狙击推荐到 pick_registry"""
        try:
            stop_loss_price = 0.0
            sl_raw = pick_data.get("stop_loss", "")
            if sl_raw:
                try:
                    stop_loss_price = float(sl_raw.replace(",", "").replace("元", "").strip())
                except (ValueError, AttributeError):
                    stop_loss_price = 0.0
            conn = sqlite3.connect(self.db_path)
            c = conn.cursor()
            c.execute(
                """INSERT INTO pick_registry
                   (code, name, entry_price, conviction_level, conviction_score,
                    tech_score, rank_score, source_sectors, action, signal,
                    stop_loss_price, report_date)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    pick_data.get("code", ""),
                    pick_data.get("name", ""),
                    pick_data.get("price", 0) or 0,
                    pick_data.get("conviction", {}).get("level", ""),
                    pick_data.get("conviction", {}).get("score", 0) or 0,
                    pick_data.get("score", 0) or 0,
                    pick_data.get("rank_score", 0) or 0,
                    ",".join(pick_data.get("source_sectors", [])),
                    pick_data.get("action", ""),
                    pick_data.get("signal", ""),
                    stop_loss_price,
                    today_str(),
                )
            )
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"  [推荐记录失败] {pick_data.get('code','')} - {e}", flush=True)
            return False

    def save_picks_batch(self, picks):
        """批量保存推荐记录"""
        saved = 0
        for p in picks:
            if self.save_pick(p):
                saved += 1
        return saved

    def get_pending_evaluations(self, min_holding=5, max_days_old=90):
        """获取待评估的活跃推荐（已过 min_holding 天但尚未评估）"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute(
            """SELECT pr.id, pr.code, pr.name, pr.entry_price,
                      pr.report_date, pr.conviction_level,
                      pr.stop_loss_price
               FROM pick_registry pr
               WHERE pr.status = 'active'
                 AND pr.report_date <= date('now', ?)
                 AND pr.report_date >= date('now', ?)
                 AND NOT EXISTS (
                     SELECT 1 FROM pick_evaluations pe
                     WHERE pe.pick_id = pr.id AND pe.holding_days = ?
                 )
               ORDER BY pr.report_date ASC""",
            (f"-{min_holding} days", f"-{max_days_old} days", min_holding)
        )
        rows = c.fetchall()
        conn.close()
        return [
            {
                "id": r[0], "code": r[1], "name": r[2],
                "entry_price": r[3], "report_date": r[4],
                "conviction_level": r[5] or "中",
                "stop_loss_price": r[6] or 0,
            }
            for r in rows
        ]

    def save_pick_evaluation(self, pick_id, holding_days, exit_price, exit_date,
                              return_pct, max_drawdown, hit_stop_loss, conviction_level):
        """保存一条评估结果"""
        try:
            conn = sqlite3.connect(self.db_path)
            c = conn.cursor()
            c.execute(
                """INSERT INTO pick_evaluations
                   (pick_id, holding_days, exit_price, exit_date,
                    return_pct, max_drawdown, hit_stop_loss, conviction_level)
                   VALUES (?,?,?,?,?,?,?,?)""",
                (pick_id, holding_days, exit_price, exit_date,
                 return_pct, max_drawdown, 1 if hit_stop_loss else 0, conviction_level)
            )
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"  [评估记录失败] pick#{pick_id} - {e}", flush=True)
            return False

    def get_pick_summary(self, since_days=30):
        """获取指定天数内的推荐汇总统计"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute(
            """SELECT
                   COUNT(*) as total_picks,
                   COUNT(CASE WHEN pe.id IS NOT NULL THEN 1 END) as evaluated,
                   AVG(CASE WHEN pe.id IS NOT NULL THEN pe.return_pct END) as avg_return,
                   SUM(CASE WHEN pe.return_pct > 0 THEN 1 ELSE 0 END) as wins,
                   COUNT(pe.id) as total_eval,
                   AVG(CASE WHEN pe.return_pct > 0 THEN pe.return_pct END) as avg_win,
                   AVG(CASE WHEN pe.return_pct < 0 THEN pe.return_pct END) as avg_loss,
                   MAX(pe.return_pct) as best_return,
                   MIN(pe.return_pct) as worst_return
               FROM pick_registry pr
               LEFT JOIN pick_evaluations pe ON pe.pick_id = pr.id
               WHERE pr.report_date >= date('now', ?)
            """,
            (f"-{since_days} days",)
        )
        row = c.fetchone()
        conn.close()
        if not row or not row[0]:
            return None
        wins = row[4] or 0
        total = row[3] or 0
        return {
            "total_picks": row[0],
            "evaluated": row[1] or 0,
            "avg_return": round(row[2] or 0, 2),
            "win_rate": round(wins / total * 100, 1) if total > 0 else 0,
            "wins": wins,
            "total_eval": total,
            "avg_win": round(row[5] or 0, 2),
            "avg_loss": round(row[6] or 0, 2),
            "best_return": round(row[7] or 0, 2),
            "worst_return": round(row[8] or 0, 2),
        }

    def save_training_log(self, metrics):
        """保存量化模型训练日志"""
        try:
            conn = sqlite3.connect(self.db_path)
            c = conn.cursor()
            c.execute(
                """INSERT INTO model_training_log
                   (train_date, num_stocks, num_samples, num_features,
                    cv_mae, cv_correlation, cv_direction_accuracy, classifier_accuracy)
                   VALUES (date('now','localtime'),?,?,?,?,?,?,?)""",
                (
                    metrics.get("num_stocks", 0),
                    metrics.get("num_samples", 0),
                    metrics.get("num_features", 0),
                    metrics.get("cv_mae", 0),
                    metrics.get("cv_correlation", 0),
                    metrics.get("cv_direction_accuracy", 0),
                    metrics.get("classifier_accuracy") or 0,
                )
            )
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"  [训练日志保存失败] {e}", flush=True)
            return False

    def get_training_logs(self, limit=10):
        """获取最近的训练日志"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute(
            """SELECT train_date, num_stocks, num_samples, num_features,
                      cv_mae, cv_correlation, cv_direction_accuracy, classifier_accuracy
               FROM model_training_log
               ORDER BY id DESC
               LIMIT ?""",
            (limit,)
        )
        rows = c.fetchall()
        conn.close()
        return [
            {
                "date": r[0],
                "num_stocks": r[1],
                "num_samples": r[2],
                "num_features": r[3],
                "cv_mae": r[4],
                "cv_correlation": r[5],
                "cv_direction_accuracy": r[6],
                "classifier_accuracy": r[7],
            }
            for r in rows
        ]

    def get_pick_summary_by_conviction(self, since_days=30):
        """按确信度分组统计表现"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute(
            """SELECT pr.conviction_level,
                      COUNT(DISTINCT pr.id) as picks,
                      COUNT(pe.id) as evals,
                      AVG(pe.return_pct) as avg_ret,
                      SUM(CASE WHEN pe.return_pct > 0 THEN 1 ELSE 0 END) as wins,
                      COUNT(pe.id) as total
               FROM pick_registry pr
               JOIN pick_evaluations pe ON pe.pick_id = pr.id
               WHERE pr.report_date >= date('now', ?)
               GROUP BY pr.conviction_level
               ORDER BY pr.conviction_level DESC
            """,
            (f"-{since_days} days",)
        )
        rows = c.fetchall()
        conn.close()
        result = []
        for r in rows:
            level, picks, evals, avg_ret, wins, total = r
            wins = wins or 0
            total = total or 0
            result.append({
                "level": level,
                "picks": picks,
                "evaluations": evals,
                "avg_return": round(avg_ret or 0, 2),
                "win_rate": round(wins / total * 100, 1) if total > 0 else 0,
                "wins": wins,
                "total": total,
            })
        return result

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

    def get_stock_analysis_buy_signals(self, days=90):
        """从 stock_analysis 表获取技术面买入信号"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute(
            """SELECT code, name, price, score, signal, action, report_date
               FROM stock_analysis
               WHERE report_date >= date('now', ?)
                 AND (signal IN ('强烈买入', '买入') OR action IN ('买入', '加仓', '增持'))
                 AND score >= 60
               ORDER BY report_date DESC, score DESC""",
            (f"-{days} days",)
        )
        rows = c.fetchall()
        conn.close()
        signals = []
        for row in rows:
            code, name, price, score, signal, action, report_date = row
            signals.append({
                "code": code,
                "name": name,
                "price": price,
                "score": score,
                "signal": signal,
                "action": action,
                "date": report_date,
                "source": "stock_analysis",
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

    def auto_review(self, lookback_days=90, check_days=None, profit_threshold=2.0):
        """自动复盘：追踪历史预判后续走势，无需手动评价

        Args:
            lookback_days: 回溯多少天内的预判
            check_days: 发出预判后 N 个交易日复查（列表）
            profit_threshold: 涨幅超过此值视为"正确"（%）

        Returns:
            dict: { "reviewed": int, "skipped": int, "results": [str] }
        """
        if check_days is None:
            check_days = [10, 20]  # 改为较长持有期，给更多时间验证

        results = []
        reviewed = 0
        skipped = 0

        analysis_list = self._get_analysis_with_codes(days=lookback_days)
        for item in analysis_list:
            aid = item["id"]
            report_date = item["date"]
            analysis_raw = item["raw"]
            advice = item["advice"]

            already_reviewed = self._is_reviewed(aid)
            if already_reviewed:
                continue

            codes = self._extract_codes(analysis_raw)
            if not codes:
                skipped += 1
                continue

            report_dt = datetime.strptime(str(report_date)[:10], "%Y-%m-%d")
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

    def auto_review_stocks(self, lookback_days=90, check_days=None, profit_threshold=2.0):
        """自动复盘个股仪表盘预判（stock_analysis 表）— 有明确股票代码和操作建议

        Args:
            lookback_days: 回溯天数
            check_days: 持有期列表
            profit_threshold: 正确阈值（%）

        Returns:
            dict: { "reviewed": int, "skipped": int, "results": [str] }
        """
        if check_days is None:
            check_days = [10, 20]

        results = []
        reviewed = 0
        skipped = 0

        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute(
            """SELECT id, code, name, signal, action, report_date
               FROM stock_analysis
               WHERE report_date >= date('now', ?)
                 AND action IN ('买入', '卖出', '加仓', '减仓')
               ORDER BY report_date ASC""",
            (f"-{lookback_days} days",)
        )
        rows = c.fetchall()
        conn.close()

        for row in rows:
            sa_id, code, name, signal, action, report_date = row

            # 检查是否已复盘（用 sa_id + 'stock' 前缀区分新闻分析）
            conn = sqlite3.connect(self.db_path)
            c = conn.cursor()
            c.execute(
                "SELECT COUNT(*) FROM tracking WHERE analysis_id=? AND outcome_detail LIKE 'stock:%'",
                (-sa_id,)
            )
            cnt = c.fetchone()[0]
            conn.close()
            if cnt > 0:
                continue

            report_dt = datetime.strptime(str(report_date)[:10], "%Y-%m-%d")
            days_since = (datetime.now() - report_dt).days
            if days_since < min(check_days):
                skipped += 1
                continue

            result = self._check_stock_performance(code, report_date, check_days)
            if result is None:
                skipped += 1
                continue

            ret, worst = result

            if ret > profit_threshold:
                outcome = "正确"
                detail = f"stock:{code} {name} 预测{action} 涨幅{ret:+.2f}%"
            elif ret > -profit_threshold:
                outcome = "部分正确"
                detail = f"stock:{code} {name} 预测{action} 涨幅{ret:+.2f}%（阈值±{profit_threshold}%）"
            else:
                outcome = "错误"
                detail = f"stock:{code} {name} 预测{action} 跌幅{ret:+.2f}%"
            if worst is not None and worst < -profit_threshold:
                detail += f"（最深回撤{worst:.2f}%）"

            # 存入 tracking 表（用 analysis_id 负值防冲突）
            conn = sqlite3.connect(self.db_path)
            c = conn.cursor()
            c.execute(
                "INSERT INTO tracking (analysis_id, actual_outcome, outcome_detail) VALUES (?,?,?)",
                (-sa_id, outcome, detail)
            )
            conn.commit()
            conn.close()
            reviewed += 1
            results.append(f"  {report_date} #{sa_id} {name}({code}): {outcome} ({detail})")

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
        valid_codes = []
        # 从 JSON 的 stock_codes 字段提取
        try:
            raw = json.loads(raw_json)
            codes = raw.get("stock_codes", [])
            for code in codes:
                code = str(code).strip()
                if self._is_valid_code(code):
                    valid_codes.append(code)
        except (json.JSONDecodeError, TypeError, AttributeError):
            pass
        # 从全文正则提取（兜底：即使 AI 没输出 stock_codes 字段也尝试抓）
        raw_text = str(raw_json)
        found = re.findall(r'(?<![\.\d])([036]\d{5})(?![\.\d])', raw_text)
        for code in found:
            if self._is_valid_code(code) and code not in valid_codes:
                valid_codes.append(code)
        return valid_codes

    def get_reviews(self, days=90, limit=50):
        """获取自动复盘结果（同时处理新闻分析和个股仪表盘），用于 Web 仪表盘显示"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        # 新闻分析复盘（analysis_id > 0）
        c.execute(
            """SELECT t.actual_outcome, t.outcome_detail, t.reviewed_at,
                      a.report_date, m.title, a.event_type, a.market_sentiment,
                      'news' as review_type
               FROM tracking t
               JOIN analysis a ON a.id = t.analysis_id
               JOIN messages m ON m.id = a.message_id
               WHERE t.analysis_id > 0
                 AND a.report_date >= date('now', ?)
               ORDER BY t.reviewed_at DESC
               LIMIT ?""",
            (f"-{days} days", limit)
        )
        news_rows = c.fetchall()

        # 个股仪表盘复盘（analysis_id < 0，通过 outcome_detail 判断 stock: 前缀）
        c.execute(
            """SELECT t.actual_outcome, t.outcome_detail, t.reviewed_at,
                      '' as report_date, '' as title, '' as event_type, '' as sentiment,
                      'stock' as review_type
               FROM tracking t
               WHERE t.analysis_id < 0
                 AND t.outcome_detail LIKE 'stock:%'
               ORDER BY t.reviewed_at DESC
               LIMIT ?""",
            (limit,)
        )
        stock_rows = c.fetchall()
        conn.close()

        all_rows = news_rows + stock_rows
        all_rows.sort(key=lambda r: str(r[2] or ""), reverse=True)

        result = []
        seen = set()
        for row in all_rows:
            key = (row[0], str(row[1])[:50])
            if key in seen:
                continue
            seen.add(key)
            result.append({
                "outcome": row[0],
                "detail": row[1] or "",
                "reviewed_at": str(row[2] or "")[:19],
                "report_date": str(row[3] or "")[:10],
                "title": row[4] or "",
                "event_type": row[5] or "",
                "sentiment": row[6] or "",
                "review_type": row[7],
            })
            if len(result) >= limit:
                break
        return result

    @staticmethod
    def _is_valid_code(code):
        """验证A股代码合法性"""
        if not code or len(code) != 6 or not code.isdigit():
            return False
        prefix = code[:3]
        valid_prefixes = {"600", "601", "603", "605", "000", "001", "002", "003", "300", "301", "688", "689"}
        return prefix in valid_prefixes

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
