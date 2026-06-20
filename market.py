import requests
import re
import pandas as pd
import numpy as np
from utils import now_str

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}


def _bypass_proxy():
    return {"http": "", "https": ""}


def _stock_sina_id(code):
    if code.startswith("6") or code.startswith("9"):
        return f"sh{code}"
    return f"sz{code}"


def get_realtime_quote(code):
    sid = _stock_sina_id(code)
    url = f"https://hq.sinajs.cn/list={sid}"
    headers = {**HEADERS, "Referer": "https://finance.sina.com.cn"}
    try:
        resp = requests.get(url, headers=headers, timeout=10, proxies=_bypass_proxy())
        text = resp.text.strip()
        if not text or "=" not in text:
            return None
        parts = text.split('"')[1].split(",")
        if len(parts) < 30:
            return None
        return {
            "code": code,
            "name": parts[0],
            "open": float(parts[1]) if parts[1] else 0,
            "prev_close": float(parts[2]) if parts[2] else 0,
            "price": float(parts[3]) if parts[3] else 0,
            "high": float(parts[4]) if parts[4] else 0,
            "low": float(parts[5]) if parts[5] else 0,
            "volume": int(parts[8]) if parts[8] else 0,
            "amount": float(parts[9]) if parts[9] else 0,
            "bid_vol": int(parts[10]) if parts[10] else 0,
            "ask_vol": int(parts[20]) if parts[20] else 0,
        }
    except Exception as e:
        print(f"  [行情获取失败] {code} - {e}", flush=True)
        return None


def get_kline(code, count=60):
    sid = _stock_sina_id(code)
    url = f"https://money.finance.sina.com.cn/quotes_service/api/json_v2.php/CN_MarketData.getKLineData?symbol={sid}&scale=240&ma=5&datalen={count}"
    headers = {**HEADERS, "Referer": "https://finance.sina.com.cn"}
    for attempt in range(2):
        try:
            resp = requests.get(url, headers=headers, timeout=30, proxies=_bypass_proxy())
            data = resp.json()
            if not data or not isinstance(data, list):
                return []
            result = []
            for item in data:
                result.append({
                    "date": item.get("day", ""),
                    "open": float(item.get("open", 0)),
                    "close": float(item.get("close", 0)),
                    "high": float(item.get("high", 0)),
                    "low": float(item.get("low", 0)),
                    "volume": int(item.get("volume", 0)),
                })
            return result
        except Exception as e:
            if attempt == 0:
                import time
                time.sleep(3)
                continue
            print(f"  [K线获取失败] {code} - {e}", flush=True)
            return []


class StockTrendAnalyzer:
    VOLUME_SHRINK_RATIO = 0.7
    VOLUME_HEAVY_RATIO = 1.5
    MA_SUPPORT_TOLERANCE = 0.02
    MACD_FAST = 12
    MACD_SLOW = 26
    MACD_SIGNAL = 9
    RSI_SHORT = 6
    RSI_MID = 12
    RSI_LONG = 24
    RSI_OVERBOUGHT = 70
    RSI_OVERSOLD = 30

    def analyze(self, kline, code):
        df = pd.DataFrame(kline)
        if df.empty or len(df) < 20:
            return None

        df = df.sort_values("date").reset_index(drop=True)
        for col in ["open", "high", "low", "close", "volume"]:
            df[col] = pd.to_numeric(df[col], errors="coerce")
        df = df.dropna(subset=["close", "volume"])

        df = self._calc_ma(df)
        df = self._calc_macd(df)
        df = self._calc_rsi(df)
        latest = df.iloc[-1]
        prev2 = df.iloc[-2] if len(df) >= 2 else latest

        price = float(latest["close"])
        ma5 = float(latest["MA5"])
        ma10 = float(latest["MA10"])
        ma20 = float(latest["MA20"])
        ma60 = float(latest.get("MA60", 0))

        trend, strength, alignment = self._analyze_trend(df, ma5, ma10, ma20)
        bias5, bias10, bias20 = self._calc_bias(price, ma5, ma10, ma20)
        vol_status, vol_ratio, vol_trend = self._analyze_volume(df, latest, prev2)
        support_list, support_ma5, support_ma10 = self._analyze_support(price, ma5, ma10, ma20)
        resistance_list = self._analyze_resistance(df, price)
        macd_info = self._analyze_macd(df, latest, prev2)
        rsi_info = self._analyze_rsi(latest)
        score, signal, reasons, risks = self._generate_signal(
            trend, strength, bias5, bias10, bias20, vol_status,
            support_ma5, support_ma10, macd_info, rsi_info
        )

        model_score = _get_quant_score(kline, code, score)
        blended_score = int(round(score * 0.5 + model_score * 0.5))

        if blended_score >= 75 and trend in ("强势多头", "多头排列"):
            final_signal = "强烈买入"
        elif blended_score >= 60 and trend in ("强势多头", "多头排列", "弱势多头"):
            final_signal = "买入"
        elif blended_score >= 45:
            final_signal = "持有"
        elif blended_score >= 30:
            final_signal = "观望"
        elif trend in ("空头排列", "强势空头"):
            final_signal = "强烈卖出"
        else:
            final_signal = "卖出"

        return {
            "code": code,
            "price": price,
            "model_score": model_score,
            "rule_score": score,
            "score": blended_score,
            "signal": final_signal,
            "ma5": ma5, "ma10": ma10, "ma20": ma20, "ma60": ma60,
            "bias_ma5": bias5, "bias_ma10": bias10, "bias_ma20": bias20,
            "ma_alignment": alignment,
            "trend": trend,
            "trend_strength": strength,
            "volume_status": vol_status,
            "volume_ratio": vol_ratio,
            "volume_trend": vol_trend,
            "support_ma5": support_ma5,
            "support_ma10": support_ma10,
            "support_levels": [round(s, 2) for s in support_list],
            "resistance_levels": [round(r, 2) for r in resistance_list],
            "macd_dif": macd_info["dif"],
            "macd_dea": macd_info["dea"],
            "macd_bar": macd_info["bar"],
            "macd_status": macd_info["status"],
            "macd_signal": macd_info["signal"],
            "rsi_6": rsi_info["rsi_6"],
            "rsi_12": rsi_info["rsi_12"],
            "rsi_24": rsi_info["rsi_24"],
            "rsi_status": rsi_info["status"],
            "rsi_signal": rsi_info["signal"],
            "score": score,
            "signal": signal,
            "signal_reasons": reasons,
            "risk_factors": risks,
        }

    def _calc_ma(self, df):
        df = df.copy()
        df["MA5"] = df["close"].rolling(5).mean()
        df["MA10"] = df["close"].rolling(10).mean()
        df["MA20"] = df["close"].rolling(20).mean()
        df["MA60"] = df["close"].rolling(60).mean() if len(df) >= 60 else df["MA20"]
        return df

    def _calc_macd(self, df):
        df = df.copy()
        ema_fast = df["close"].ewm(span=self.MACD_FAST, adjust=False).mean()
        ema_slow = df["close"].ewm(span=self.MACD_SLOW, adjust=False).mean()
        df["MACD_DIF"] = ema_fast - ema_slow
        df["MACD_DEA"] = df["MACD_DIF"].ewm(span=self.MACD_SIGNAL, adjust=False).mean()
        df["MACD_BAR"] = (df["MACD_DIF"] - df["MACD_DEA"]) * 2
        return df

    def _calc_rsi(self, df):
        df = df.copy()
        for period in [self.RSI_SHORT, self.RSI_MID, self.RSI_LONG]:
            delta = df["close"].diff()
            gain = delta.where(delta > 0, 0)
            loss = -delta.where(delta < 0, 0)
            avg_gain = gain.ewm(alpha=1 / period, adjust=False).mean()
            avg_loss = loss.ewm(alpha=1 / period, adjust=False).mean()
            rs = avg_gain / avg_loss.replace(0, np.nan)
            rsi = 100 - (100 / (1 + rs))
            df[f"RSI_{period}"] = rsi.fillna(50)
        return df

    def _analyze_trend(self, df, ma5, ma10, ma20):
        if ma5 > ma10 > ma20:
            prev = df.iloc[-5] if len(df) >= 5 else df.iloc[-1]
            prev_spread = (prev["MA5"] - prev["MA20"]) / prev["MA20"] * 100 if prev["MA20"] > 0 else 0
            curr_spread = (ma5 - ma20) / ma20 * 100 if ma20 > 0 else 0
            if curr_spread > prev_spread and curr_spread > 5:
                return "强势多头", 90, "强势多头排列，均线发散上行"
            return "多头排列", 75, "多头排列 MA5>MA10>MA20"
        if ma5 > ma10 and ma10 <= ma20:
            return "弱势多头", 55, "弱势多头，MA5>MA10 但 MA10≤MA20"
        if ma5 < ma10 < ma20:
            prev = df.iloc[-5] if len(df) >= 5 else df.iloc[-1]
            prev_spread = (prev["MA20"] - prev["MA5"]) / prev["MA5"] * 100 if prev["MA5"] > 0 else 0
            curr_spread = (ma20 - ma5) / ma5 * 100 if ma5 > 0 else 0
            if curr_spread > prev_spread and curr_spread > 5:
                return "强势空头", 10, "强势空头排列，均线发散下行"
            return "空头排列", 25, "空头排列 MA5<MA10<MA20"
        if ma5 < ma10 and ma10 >= ma20:
            return "弱势空头", 40, "弱势空头，MA5<MA10 但 MA10≥MA20"
        return "盘整", 50, "均线缠绕，趋势不明"

    def _calc_bias(self, price, ma5, ma10, ma20):
        b5 = (price - ma5) / ma5 * 100 if ma5 > 0 else 0
        b10 = (price - ma10) / ma10 * 100 if ma10 > 0 else 0
        b20 = (price - ma20) / ma20 * 100 if ma20 > 0 else 0
        return round(b5, 2), round(b10, 2), round(b20, 2)

    def _analyze_volume(self, df, latest, prev2):
        if len(df) < 5:
            return "量能正常", 1.0, ""
        vol_5d_avg = df["volume"].iloc[-6:-1].mean()
        vol_ratio = float(latest["volume"]) / vol_5d_avg if vol_5d_avg > 0 else 1.0
        price_change = (latest["close"] - prev2["close"]) / prev2["close"] * 100

        if vol_ratio >= self.VOLUME_HEAVY_RATIO:
            if price_change > 0:
                return "放量上涨", vol_ratio, "放量上涨，多头力量强劲"
            else:
                return "放量下跌", vol_ratio, "放量下跌，注意风险"
        if vol_ratio <= self.VOLUME_SHRINK_RATIO:
            if price_change > 0:
                return "缩量上涨", vol_ratio, "缩量上涨，上攻动能不足"
            else:
                return "缩量回调", vol_ratio, "缩量回调，洗盘特征明显（好）"
        return "量能正常", vol_ratio, "量能正常"

    def _analyze_support(self, price, ma5, ma10, ma20):
        levels = []
        sm5 = sm10 = False
        if ma5 > 0 and abs(price - ma5) / ma5 <= self.MA_SUPPORT_TOLERANCE and price >= ma5:
            sm5 = True
            levels.append(ma5)
        if ma10 > 0 and abs(price - ma10) / ma10 <= self.MA_SUPPORT_TOLERANCE and price >= ma10:
            sm10 = True
            if ma10 not in levels:
                levels.append(ma10)
        if ma20 > 0 and price >= ma20:
            levels.append(ma20)
        return levels, sm5, sm10

    def _analyze_resistance(self, df, price):
        if len(df) >= 20:
            recent_high = df["high"].iloc[-20:].max()
            if recent_high > price:
                return [recent_high]
        return []

    def _analyze_macd(self, df, latest, prev2):
        if len(df) < self.MACD_SLOW:
            return {"dif": 0, "dea": 0, "bar": 0, "status": "中性", "signal": "数据不足"}

        dif = float(latest["MACD_DIF"])
        dea = float(latest["MACD_DEA"])
        bar = float(latest["MACD_BAR"])
        prev_dif_dea = prev2["MACD_DIF"] - prev2["MACD_DEA"]
        curr_dif_dea = dif - dea
        is_golden = prev_dif_dea <= 0 and curr_dif_dea > 0
        is_death = prev_dif_dea >= 0 and curr_dif_dea < 0
        prev_dif = prev2["MACD_DIF"]
        cross_up = prev_dif <= 0 and dif > 0
        cross_down = prev_dif >= 0 and dif < 0

        if is_golden and dif > 0:
            return {"dif": dif, "dea": dea, "bar": bar, "status": "零轴上金叉", "signal": "⭐ 零轴上金叉，强烈买入信号"}
        if cross_up:
            return {"dif": dif, "dea": dea, "bar": bar, "status": "上穿零轴", "signal": "⚡ DIF上穿零轴，趋势转强"}
        if is_golden:
            return {"dif": dif, "dea": dea, "bar": bar, "status": "金叉", "signal": "✅ 金叉，趋势向上"}
        if is_death:
            return {"dif": dif, "dea": dea, "bar": bar, "status": "死叉", "signal": "❌ 死叉，趋势向下"}
        if cross_down:
            return {"dif": dif, "dea": dea, "bar": bar, "status": "下穿零轴", "signal": "⚠️ DIF下穿零轴，趋势转弱"}
        if dif > 0 and dea > 0:
            return {"dif": dif, "dea": dea, "bar": bar, "status": "多头", "signal": "✓ 多头排列，持续上涨"}
        if dif < 0 and dea < 0:
            return {"dif": dif, "dea": dea, "bar": bar, "status": "空头", "signal": "⚠ 空头排列，持续下跌"}
        return {"dif": dif, "dea": dea, "bar": bar, "status": "中性", "signal": "MACD中性区域"}

    def _analyze_rsi(self, latest):
        r6 = float(latest.get("RSI_6", 50))
        r12 = float(latest.get("RSI_12", 50))
        r24 = float(latest.get("RSI_24", 50))
        mid = r12
        if mid > self.RSI_OVERBOUGHT:
            return {"rsi_6": r6, "rsi_12": r12, "rsi_24": r24, "status": "超买", "signal": f"⚠️ RSI超买({mid:.1f}>70)"}
        if mid > 60:
            return {"rsi_6": r6, "rsi_12": r12, "rsi_24": r24, "status": "强势买入", "signal": f"✅ RSI强势({mid:.1f})"}
        if mid >= 40:
            return {"rsi_6": r6, "rsi_12": r12, "rsi_24": r24, "status": "中性", "signal": f"RSI中性({mid:.1f})"}
        if mid >= self.RSI_OVERSOLD:
            return {"rsi_6": r6, "rsi_12": r12, "rsi_24": r24, "status": "弱势", "signal": f"⚡ RSI弱势({mid:.1f})"}
        return {"rsi_6": r6, "rsi_12": r12, "rsi_24": r24, "status": "超卖", "signal": f"⭐ RSI超卖({mid:.1f}<30)"}

    def _generate_signal(self, trend, strength, bias5, bias10, bias20,
                         vol_status, support_ma5, support_ma10, macd_info, rsi_info):
        score = 0
        reasons = []
        risks = []

        trend_scores = {"强势多头": 30, "多头排列": 26, "弱势多头": 18,
                        "盘整": 12, "弱势空头": 8, "空头排列": 4, "强势空头": 0}
        score += trend_scores.get(trend, 12)
        if trend in ("强势多头", "多头排列"):
            reasons.append(f"✅ {trend}，顺势做多")
        elif trend in ("空头排列", "强势空头"):
            risks.append(f"⚠️ {trend}，不宜做多")

        if bias5 < 0:
            if bias5 > -3:
                score += 20
                reasons.append(f"✅ 价格略低于MA5({bias5:.1f}%)，回踩买点")
            elif bias5 > -5:
                score += 16
                reasons.append(f"✅ 价格回踩MA5({bias5:.1f}%)，观察支撑")
            else:
                score += 8
                risks.append(f"⚠️ 乖离率过大({bias5:.1f}%)，可能破位")
        elif bias5 < 2:
            score += 18
            reasons.append(f"✅ 价格贴近MA5({bias5:.1f}%)，介入好时机")
        elif bias5 < 5:
            score += 14
            reasons.append(f"⚡ 价格略高于MA5({bias5:.1f}%)，可小仓介入")
        elif bias5 > 7.5 and trend == "强势多头" and strength >= 70:
            score += 10
            reasons.append(f"⚡ 强势趋势中乖离率偏高({bias5:.1f}%)，可轻仓追踪")
        else:
            score += 4
            risks.append(f"❌ 乖离率过高({bias5:.1f}%)，严禁追高")

        vol_scores = {"缩量回调": 15, "放量上涨": 12, "量能正常": 10, "缩量上涨": 6, "放量下跌": 0}
        score += vol_scores.get(vol_status, 8)
        if vol_status == "缩量回调":
            reasons.append("✅ 缩量回调，主力洗盘")
        elif vol_status == "放量下跌":
            risks.append("⚠️ 放量下跌，注意风险")

        if support_ma5:
            score += 5
            reasons.append("✅ MA5支撑有效")
        if support_ma10:
            score += 5
            reasons.append("✅ MA10支撑有效")

        macd_scores = {"零轴上金叉": 15, "金叉": 12, "上穿零轴": 10,
                       "多头": 8, "空头": 2, "下穿零轴": 0, "死叉": 0}
        score += macd_scores.get(macd_info["status"], 5)
        if macd_info["status"] in ("零轴上金叉", "金叉"):
            reasons.append(f"✅ {macd_info['signal']}")
        elif macd_info["status"] in ("死叉", "下穿零轴"):
            risks.append(f"⚠️ {macd_info['signal']}")

        rsi_scores = {"超卖": 10, "强势买入": 8, "中性": 5, "弱势": 3, "超买": 0}
        score += rsi_scores.get(rsi_info["status"], 5)
        if rsi_info["status"] in ("超卖", "强势买入"):
            reasons.append(f"✅ {rsi_info['signal']}")
        elif rsi_info["status"] == "超买":
            risks.append(f"⚠️ {rsi_info['signal']}")

        score = max(0, min(100, score))

        if score >= 75 and trend in ("强势多头", "多头排列"):
            signal = "强烈买入"
        elif score >= 60 and trend in ("强势多头", "多头排列", "弱势多头"):
            signal = "买入"
        elif score >= 45:
            signal = "持有"
        elif score >= 30:
            signal = "观望"
        elif trend in ("空头排列", "强势空头"):
            signal = "强烈卖出"
        else:
            signal = "卖出"

        return score, signal, reasons, risks


def get_market_phase():
    from datetime import datetime, time
    now = datetime.now()
    h = now.hour
    m = now.minute
    wd = now.weekday()

    if wd >= 5:
        return "non_trading", "非交易日"

    if h < 9:
        return "premarket", "盘前"
    if h == 9 and m < 30:
        return "premarket", "盘前"
    if h == 9:
        return "intraday", "盘中"
    if h == 11 and m >= 30:
        return "lunch_break", "午间休市"
    if h == 12:
        return "lunch_break", "午间休市"
    if h == 13 and m < 30:
        return "lunch_break", "午间休市" if m < 0 else "盘中"
    if h == 14 and m >= 57:
        return "closing_auction", "临近收盘"
    if h >= 15:
        return "postmarket", "盘后"
    if h >= 11 and h < 13:
        return "lunch_break", "午间休市"
    return "intraday", "盘中"


_analyzer = StockTrendAnalyzer()


def get_scorer():
    try:
        import importlib
        qm = importlib.import_module("quant_model")
        s = qm.QuantScorer()
        if s.is_trained():
            return s
        s.train_if_needed()
        return s if s.is_trained() else None
    except Exception:
        return None


_quant_scorer = None


def _get_quant_score(kline, code, rule_score):
    global _quant_scorer
    if _quant_scorer is None:
        _quant_scorer = get_scorer()
    if _quant_scorer:
        try:
            ms = _quant_scorer.predict(kline)
            if ms is not None:
                return ms
        except Exception:
            pass
    return rule_score


def get_stock_analysis(code):
    kline = get_kline(code, count=60)
    quote = get_realtime_quote(code)
    if not kline or not quote:
        return None

    analysis = _analyzer.analyze(kline, code)
    if not analysis:
        return None

    change_pct = round((quote["price"] - quote["prev_close"]) / quote["prev_close"] * 100, 2) if quote["prev_close"] else 0
    change_amount = round(quote["price"] - quote["prev_close"], 2) if quote["prev_close"] else 0

    return {
        "code": code,
        "name": quote["name"],
        "price": quote["price"],
        "prev_close": quote["prev_close"],
        "change_pct": change_pct,
        "change_amount": change_amount,
        "volume": quote["volume"],
        "amount": quote["amount"],
        "high": quote["high"],
        "low": quote["low"],
        "open": quote["open"],
        **analysis,
        "analysis_time": now_str(),
    }
