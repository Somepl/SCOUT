"""
SCOUT 量化评分模型
==================
用 LightGBM 替代固定规则评分，从历史数据中学习什么特征组合能预测涨跌。

工作流程:
  1. 从 K 线数据计算 ~40 个量化特征
  2. 训练 LightGBM 模型预测未来 5 日收益
  3. 模型输出分映射到 0-100 分，替换/补充规则评分

使用方法:
  from quant_model import QuantScorer
  scorer = QuantScorer()
  scorer.train(codes=['000001', '600519', ...])  # 训练一次
  score = scorer.predict(kline_data)               # 每日评分
"""

import sys
import os
import json
import pickle
import numpy as np
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import DATA_DIR

MODEL_PATH = os.path.join(DATA_DIR, "quant_model.pkl")
LAST_TRAIN_PATH = os.path.join(DATA_DIR, "quant_last_train.txt")

SAFE_DIV = 1e-10


def compute_features(kline):
    """从 K 线数据计算 ~40 个量化特征，返回 dict"""
    if not kline or len(kline) < 20:
        return None

    df = sorted(kline, key=lambda x: x["date"])
    closes = np.array([float(k["close"]) for k in df])
    highs = np.array([float(k["high"]) for k in df])
    lows = np.array([float(k["low"]) for k in df])
    opens = np.array([float(k["open"]) for k in df])
    volumes = np.array([float(k["volume"]) for k in df])
    n = len(closes)

    feats = {}

    # ── 收益率特征 ──
    for d in [1, 3, 5, 10, 20]:
        if n > d:
            feats[f"ret_{d}d"] = (closes[-1] - closes[-1 - d]) / (closes[-1 - d] + SAFE_DIV) * 100
            feats[f"ret_std_{d}d"] = float(np.std([(closes[i] - closes[i - 1]) / (closes[i - 1] + SAFE_DIV) for i in range(-d, 0)])) * 100
        else:
            feats[f"ret_{d}d"] = 0
            feats[f"ret_std_{d}d"] = 0

    # ── 价格位置特征 ──
    for d in [5, 10, 20, 60]:
        if n > d:
            window = closes[-d:]
            hh = np.max(highs[-d:])
            ll = np.min(lows[-d:])
            feats[f"pos_in_{d}d"] = (closes[-1] - ll) / (hh - ll + SAFE_DIV) * 100
            feats[f"pct_off_high_{d}d"] = (closes[-1] - hh) / (hh + SAFE_DIV) * 100
            feats[f"pct_off_low_{d}d"] = (closes[-1] - ll) / (ll + SAFE_DIV) * 100
        else:
            feats[f"pos_in_{d}d"] = 50
            feats[f"pct_off_high_{d}d"] = 0
            feats[f"pct_off_low_{d}d"] = 0

    # ── 均线特征 ──
    for period in [5, 10, 20, 60]:
        if n >= period:
            ma = np.mean(closes[-period:])
            feats[f"ma_{period}"] = ma
            feats[f"dist_ma_{period}"] = (closes[-1] - ma) / (ma + SAFE_DIV) * 100
            ma_prev = np.mean(closes[-period - 1:-1]) if n > period else ma
            feats[f"ma_slope_{period}"] = (ma - ma_prev) / (ma_prev + SAFE_DIV) * 100
        else:
            feats[f"ma_{period}"] = closes[-1]
            feats[f"dist_ma_{period}"] = 0
            feats[f"ma_slope_{period}"] = 0

    # ── 均线交叉特征 ──
    if n >= 10:
        ma5 = np.mean(closes[-5:])
        ma10 = np.mean(closes[-10:])
        ma20 = np.mean(closes[-20:]) if n >= 20 else ma10
        feats["ma5_gt_ma10"] = 1 if ma5 > ma10 else 0
        feats["ma5_gt_ma20"] = 1 if ma5 > ma20 else 0
        feats["ma10_gt_ma20"] = 1 if ma10 > ma20 else 0
        feats["ma5_minus_ma10"] = (ma5 - ma10) / (ma10 + SAFE_DIV) * 100
        feats["ma5_minus_ma20"] = (ma5 - ma20) / (ma20 + SAFE_DIV) * 100
    else:
        for k in ["ma5_gt_ma10", "ma5_gt_ma20", "ma10_gt_ma20"]:
            feats[k] = 0
        for k in ["ma5_minus_ma10", "ma5_minus_ma20"]:
            feats[k] = 0

    # ── 波动率特征 ──
    for d in [5, 10, 20]:
        if n > d:
            feats[f"hl_range_{d}d"] = np.mean(highs[-d:] - lows[-d:]) / (closes[-1] + SAFE_DIV) * 100
            feats[f"volatility_{d}d"] = float(np.std(closes[-d:])) / (closes[-1] + SAFE_DIV) * 100
        else:
            feats[f"hl_range_{d}d"] = 0
            feats[f"volatility_{d}d"] = 0

    # ── 成交量特征 ──
    for d in [5, 10, 20]:
        if n > d:
            avg_vol = np.mean(volumes[-d:-1]) if d > 1 else volumes[-2]
            feats[f"vol_ratio_{d}d"] = volumes[-1] / (avg_vol + SAFE_DIV)
            vol_trend = (np.mean(volumes[-d:]) - np.mean(volumes[-2 * d:-d])) / (np.mean(volumes[-2 * d:-d]) + SAFE_DIV) if n > 2 * d else 0
            feats[f"vol_trend_{d}d"] = vol_trend * 100
        else:
            feats[f"vol_ratio_{d}d"] = 1.0
            feats[f"vol_trend_{d}d"] = 0

    # ── RSI ──
    for period in [6, 12, 24]:
        if n > period:
            deltas = np.diff(closes[-(period + 1):])
            gains = deltas[deltas > 0].sum()
            losses = abs(deltas[deltas < 0].sum())
            avg_gain = gains / period
            avg_loss = losses / period
            rs = avg_gain / (avg_loss + SAFE_DIV)
            feats[f"rsi_{period}"] = 100 - 100 / (1 + rs)
        else:
            feats[f"rsi_{period}"] = 50

    # ── MACD ──
    if n > 26:
        ema12_arr = _ema(closes, 12)
        ema26_arr = _ema(closes, 26)
        dif_arr = ema12_arr - ema26_arr
        dif = dif_arr[-1]
        dea_arr = _ema(dif_arr, 9)
        dea = dea_arr[-1]
        feats["macd_dif"] = dif
        feats["macd_hist"] = dif - dea
        feats["macd_positive"] = 1 if dif > 0 else 0
    else:
        feats["macd_dif"] = 0
        feats["macd_hist"] = 0
        feats["macd_positive"] = 0

    # ── 价格形态 ──
    feats["close_gt_open"] = 1 if closes[-1] > opens[-1] else 0
    feats["upper_shadow"] = (highs[-1] - max(closes[-1], opens[-1])) / (closes[-1] + SAFE_DIV) * 100
    feats["lower_shadow"] = (min(closes[-1], opens[-1]) - lows[-1]) / (closes[-1] + SAFE_DIV) * 100
    feats["body_pct"] = abs(closes[-1] - opens[-1]) / (opens[-1] + SAFE_DIV) * 100

    return feats


def _ema(data, period):
    alpha = 2 / (period + 1)
    result = np.zeros_like(data)
    result[0] = data[0]
    for i in range(1, len(data)):
        result[i] = alpha * data[i] + (1 - alpha) * result[i - 1]
    return result


def _add_calendar_features(feats, date_str):
    """添加日历特征：周几、月份、是否月底/季末"""
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        feats["day_of_week"] = dt.weekday()
        feats["month"] = dt.month
        feats["day_of_month"] = dt.day
        feats["is_month_end"] = 1 if dt.day >= 25 else 0
        feats["is_quarter_end"] = 1 if dt.month in (3, 6, 9, 12) and dt.day >= 25 else 0
    except Exception:
        feats["day_of_week"] = 0
        feats["month"] = 0
        feats["day_of_month"] = 15
        feats["is_month_end"] = 0
        feats["is_quarter_end"] = 0
    return feats


def compute_features_vectorized(kline, stride=3, market_closes=None):
    """为训练准备: 返回每日特征矩阵和对应未来收益。
    使用 stride 间隔采样减少重叠。
    支持添加日历特征和市场相对收益特征。
    """
    if not kline or len(kline) < 30:
        return None, None

    df = sorted(kline, key=lambda x: x["date"])
    closes = np.array([float(k["close"]) for k in df])
    highs = np.array([float(k["high"]) for k in df])
    lows = np.array([float(k["low"]) for k in df])
    opens = np.array([float(k["open"]) for k in df])
    volumes = np.array([float(k["volume"]) for k in df])
    dates = [k["date"] for k in df]
    n = len(df)

    rows = []
    targets = []
    target_classes = []
    for i in range(30, n - 5, stride):
        sub = df[:i + 1]
        feats = compute_features(sub)
        if feats is None:
            continue
        # 日历特征
        feats = _add_calendar_features(feats, dates[i])
        # 市场相对收益（如果提供）
        if market_closes is not None and i < len(market_closes) and i + 5 < len(market_closes):
            mkt_ret = (market_closes[i + 5] - market_closes[i]) / market_closes[i] * 100
            stock_ret = (closes[i + 5] - closes[i]) / closes[i] * 100
            feats["excess_ret_5d"] = stock_ret - mkt_ret
        fwd_ret = (closes[i + 5] - closes[i]) / closes[i] * 100
        rows.append(feats)
        targets.append(fwd_ret)
        # 分类标签: 1=涨(>2%), 0=平(±2%), -1=跌(<-2%)
        if fwd_ret > 2:
            target_classes.append(1)
        elif fwd_ret < -2:
            target_classes.append(-1)
        else:
            target_classes.append(0)

    if not rows:
        return None, None
    return rows, targets, target_classes


def feature_dicts_to_matrix(feature_list):
    """将特征 dict 列表转为 numpy 矩阵"""
    if not feature_list:
        return None
    keys = sorted(feature_list[0].keys())
    matrix = np.zeros((len(feature_list), len(keys)))
    for i, fd in enumerate(feature_list):
        for j, k in enumerate(keys):
            matrix[i, j] = fd.get(k, 0)
    return matrix, keys


try:
    import lightgbm as lgb
    HAS_LGB = True
except ImportError:
    HAS_LGB = False


class QuantScorer:
    """量化评分器: 训练 LightGBM 模型替代固定规则评分"""

    def __init__(self, model_path=None):
        self.model_path = model_path or MODEL_PATH
        self.model = None
        self.feature_keys = None
        self._load()

    def _load(self):
        if os.path.isfile(self.model_path):
            try:
                with open(self.model_path, "rb") as f:
                    data = pickle.load(f)
                self.model = data["model"]
                self.feature_keys = data["feature_keys"]
                return True
            except Exception:
                pass
        return False

    def _save(self):
        os.makedirs(os.path.dirname(self.model_path), exist_ok=True)
        with open(self.model_path, "wb") as f:
            pickle.dump({
                "model": self.model,
                "feature_keys": self.feature_keys,
            }, f)

    def is_trained(self):
        return self.model is not None

    @staticmethod
    def get_diverse_stocks(count=50):
        """从板块映射表中获取多样化的股票列表"""
        try:
            from screener import SECTOR_STOCKS
            seen = set()
            result = []
            for sector, codes in SECTOR_STOCKS.items():
                for code in codes:
                    if code not in seen:
                        seen.add(code)
                        result.append((sector, code))
            if len(result) < count:
                return [c for _, c in result]
            seen_sectors = set()
            diverse = []
            for sector, code in result:
                if sector not in seen_sectors:
                    seen_sectors.add(sector)
                    diverse.append(code)
                if len(diverse) >= count:
                    break
            if len(diverse) < count:
                for _, code in result:
                    if code not in diverse:
                        diverse.append(code)
                    if len(diverse) >= count:
                        break
            return diverse[:count]
        except Exception:
            return ["600519", "000858", "300750", "601318",
                    "600036", "000333", "002594", "600887",
                    "601012", "600438", "002371", "688981",
                    "000568", "601398", "601628", "600030",
                    "002460", "002466", "688599", "603501",
                    "300760", "000002", "601088", "600900",
                    "002475", "000333", "600941", "601668",
                    "002352", "600019", "601899", "300059",
                    "300124", "002230", "601888", "600276"]

    def get_last_train_days_ago(self):
        """返回距离上次训练的天数，若从未训练返回 None"""
        if not os.path.isfile(LAST_TRAIN_PATH):
            return None
        try:
            with open(LAST_TRAIN_PATH, "r") as f:
                dt = datetime.strptime(f.read().strip(), "%Y-%m-%d")
                return (datetime.now() - dt).days
        except Exception:
            return None

    def _write_last_train(self):
        os.makedirs(os.path.dirname(LAST_TRAIN_PATH), exist_ok=True)
        with open(LAST_TRAIN_PATH, "w") as f:
            f.write(datetime.now().strftime("%Y-%m-%d"))

    def train(self, codes=None, max_codes=None):
        """在多个股票的历史数据上训练模型。
        使用多任务学习: 回归(预测收益) + 分类(预测方向)
        """
        if not HAS_LGB:
            print("  [量化模型] LightGBM 未安装，跳过训练", flush=True)
            return False

        from config import TRAIN_MIN_STOCKS
        if max_codes is None:
            max_codes = TRAIN_MIN_STOCKS

        if not codes:
            codes = self.get_diverse_stocks(count=max_codes)

        all_features = []
        all_targets_reg = []  # 回归目标: 5日收益%
        all_targets_cls = []  # 分类目标: 1(涨)/0(平)/-1(跌)

        print(f"  [量化模型] 开始训练，加载 {len(codes)} 只股票（各250日K线）...", flush=True)
        from market import get_kline as _get_kline
        success_count = 0
        for idx, code in enumerate(codes[:max_codes]):
            if idx > 0 and idx % 5 == 0:
                import time
                print(f"  [量化模型] 进度: {idx}/{min(len(codes), max_codes)}，已成功 {success_count} 只", flush=True)
                time.sleep(2)
            kline = _get_kline(code, count=250)
            if not kline or len(kline) < 60:
                continue
            rows, targets_reg, targets_cls = compute_features_vectorized(kline)
            if rows and targets_reg:
                all_features.extend(rows)
                all_targets_reg.extend(targets_reg)
                all_targets_cls.extend(targets_cls)
                success_count += 1
                print(f"    {code}: {len(rows)} 条样本", flush=True)

        if len(all_features) < 50:
            print(f"  [量化模型] 样本不足 ({len(all_features)}), 训练跳过", flush=True)
            return False

        X, keys = feature_dicts_to_matrix(all_features)
        y_reg = np.array(all_targets_reg)
        y_cls = np.array(all_targets_cls)
        self.feature_keys = keys

        print(f"  [量化模型] 训练样本: {X.shape[0]} 条, 特征: {X.shape[1]} 个", flush=True)

        # 5折交叉验证
        from sklearn.model_selection import KFold
        kf = KFold(n_splits=5, shuffle=True, random_state=42)
        cv_maes = []
        cv_corrs = []
        cv_accs = []
        best_model = None
        best_val_score = float("inf")

        for fold, (train_idx, val_idx) in enumerate(kf.split(X)):
            X_train, X_val = X[train_idx], X[val_idx]
            y_train_reg, y_val_reg = y_reg[train_idx], y_reg[val_idx]
            y_train_cls, y_val_cls = y_cls[train_idx], y_cls[val_idx]

            train_data = lgb.Dataset(X_train, label=y_train_reg)
            val_data = lgb.Dataset(X_val, label=y_val_reg, reference=train_data)

            params = {
                "objective": "regression",
                "metric": "mae",
                "boosting_type": "gbdt",
                "num_leaves": 31,
                "learning_rate": 0.03,
                "feature_fraction": 0.8,
                "bagging_fraction": 0.8,
                "bagging_freq": 5,
                "min_data_in_leaf": 10,
                "verbose": -1,
                "seed": 42 + fold,
            }

            model = lgb.train(
                params,
                train_data,
                valid_sets=[val_data],
                num_boost_round=300,
                callbacks=[lgb.early_stopping(15), lgb.log_evaluation(0)],
            )

            val_pred = model.predict(X_val)
            mae = float(np.mean(np.abs(val_pred - y_val_reg)))
            corr = float(np.corrcoef(val_pred, y_val_reg)[0, 1]) if len(y_val_reg) > 2 else 0

            # 方向准确率
            pred_dir = np.sign(val_pred)
            true_dir = np.sign(y_val_reg)
            acc = float(np.mean(pred_dir == true_dir)) * 100

            cv_maes.append(mae)
            cv_corrs.append(corr)
            cv_accs.append(acc)

            if mae < best_val_score:
                best_val_score = mae
                best_model = model

        avg_mae = np.mean(cv_maes)
        avg_corr = np.mean(cv_corrs)
        avg_acc = np.mean(cv_accs)
        print(f"  [量化模型] 5折CV | MAE: {avg_mae:.2f}% | 相关系数: {avg_corr:.3f} | 方向准确率: {avg_acc:.1f}%", flush=True)

        self.model = best_model
        self._save()
        self._write_last_train()
        print(f"  [量化模型] 模型已保存: {self.model_path}", flush=True)

        # 打印特征重要性
        try:
            import pandas as pd
            imp = pd.DataFrame({"feature": self.feature_keys, "importance": self.model.feature_importance()})
            imp = imp.sort_values("importance", ascending=False).head(10)
            print(f"  [量化模型] 最重要特征:\n{imp.to_string(index=False)}", flush=True)
        except Exception:
            pass

        # 分类辅助模型（可选）
        self._train_classifier(X, y_cls, keys)

        return True

    def _train_classifier(self, X, y_cls, keys):
        """训练方向分类辅助模型"""
        try:
            # 过滤掉标签为0的样本（涨跌不明显）
            mask = y_cls != 0
            X_filt = X[mask]
            y_filt = y_cls[mask]
            if len(X_filt) < 50:
                return

            from sklearn.model_selection import KFold
            params = {
                "objective": "binary",
                "metric": "binary_logloss",
                "boosting_type": "gbdt",
                "num_leaves": 24,
                "learning_rate": 0.03,
                "feature_fraction": 0.8,
                "verbose": -1,
            }
            # 转为二分类：涨(1) vs 跌(0)
            y_bin = (y_filt == 1).astype(int)
            accs = []
            final_clf = None
            kf = KFold(n_splits=5, shuffle=True, random_state=42)
            for train_idx, val_idx in kf.split(X_filt):
                X_tr, X_va = X_filt[train_idx], X_filt[val_idx]
                y_tr, y_va = y_bin[train_idx], y_bin[val_idx]
                tr_data = lgb.Dataset(X_tr, label=y_tr)
                va_data = lgb.Dataset(X_va, label=y_va, reference=tr_data)
                clf = lgb.train(
                    {**params},
                    tr_data,
                    valid_sets=[va_data],
                    num_boost_round=200,
                    callbacks=[lgb.early_stopping(10), lgb.log_evaluation(0)],
                )
                pred = (clf.predict(X_va) > 0.5).astype(int)
                acc = float(np.mean(pred == y_va)) * 100
                accs.append(acc)
                final_clf = clf
            print(f"  [量化模型] 分类模型(涨/跌) 5折CV准确率: {np.mean(accs):.1f}%", flush=True)
            self.classifier = final_clf
        except Exception as e:
            print(f"  [量化模型] 分类模型训练跳过: {e}", flush=True)

    def predict(self, kline_data):
        """对单只股票的当前状态评分，返回 0-100 分
        融合回归预测 + 分类预测
        """
        if not self.model or not self.feature_keys:
            return None

        feats = compute_features(kline_data)
        if feats is None:
            return None

        feat_array = np.array([[feats.get(k, 0) for k in self.feature_keys]])

        # 回归预测
        pred_ret = self.model.predict(feat_array)[0]
        reg_score = 50 + pred_ret * 3

        # 分类预测（方向信号）
        cls_score = 50
        try:
            if hasattr(self, 'classifier') and self.classifier is not None:
                cls_prob = self.classifier.predict(feat_array)[0]
                # prob > 0.5 → 看涨, < 0.5 → 看跌
                cls_score = 40 + cls_prob * 60  # 30~100
        except Exception:
            pass

        # 融合：回归70% + 分类30%
        score = reg_score * 0.7 + cls_score * 0.3
        score = max(0, min(100, score))
        return round(score, 1)

    def train_if_needed(self, codes=None):
        """如果模型不存在则训练"""
        if not self.is_trained():
            return self.train(codes=codes)
        return True

    def train_if_expired(self, interval_days=7, codes=None):
        """如果距离上次训练超过 interval_days 则重新训练"""
        days_ago = self.get_last_train_days_ago()
        if days_ago is None or days_ago >= interval_days:
            print(f"  [量化模型] 上次训练距今 {days_ago or 'N/A'} 天 >= {interval_days} 天，开始重新训练", flush=True)
            return self.train(codes=codes)
        print(f"  [量化模型] 上次训练距今 {days_ago} 天 < {interval_days} 天，无需重新训练", flush=True)
        return True


import pandas as pd
