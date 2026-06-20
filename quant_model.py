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
        ema12 = _ema(closes, 12)[-1]
        ema26 = _ema(closes, 26)[-1]
        dif = ema12 - ema26
        feats["macd_dif"] = dif
        feats["macd_hist"] = dif - _ema(np.array([ema12 - ema26]), 9)[-1]
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


def compute_features_vectorized(kline):
    """为训练准备: 返回每日特征矩阵和对应未来收益"""
    if not kline or len(kline) < 30:
        return None, None

    df = sorted(kline, key=lambda x: x["date"])
    closes = np.array([float(k["close"]) for k in df])
    highs = np.array([float(k["high"]) for k in df])
    lows = np.array([float(k["low"]) for k in df])
    opens = np.array([float(k["open"]) for k in df])
    volumes = np.array([float(k["volume"]) for k in df])
    n = len(df)

    rows = []
    targets = []
    # 从第 30 天开始，往前看 20 天算特征，往后看 5 天算收益
    for i in range(30, n - 5):
        sub = df[:i + 1]
        feats = compute_features(sub)
        if feats is None:
            continue
        fwd_ret = (closes[i + 5] - closes[i]) / closes[i] * 100
        rows.append(feats)
        targets.append(fwd_ret)

    if not rows:
        return None, None
    return rows, targets


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

    def train(self, codes=None, max_codes=50):
        """在多个股票的历史数据上训练模型"""
        if not HAS_LGB:
            print("  [量化模型] LightGBM 未安装，跳过训练", flush=True)
            return False

        if not codes:
            codes = ["600519", "000858", "300750", "601318",
                     "600036", "000333", "002594", "600887",
                     "601012", "600438", "002371", "688981"]

        all_features = []
        all_targets = []

        print(f"  [量化模型] 开始训练，加载 {len(codes)} 只股票...", flush=True)
        from market import get_kline as _get_kline
        for code in codes[:max_codes]:
            kline = _get_kline(code, count=180)
            if not kline:
                continue
            rows, targets = compute_features_vectorized(kline)
            if rows and targets:
                all_features.extend(rows)
                all_targets.extend(targets)
                print(f"    {code}: {len(rows)} 条样本", flush=True)

        if len(all_features) < 50:
            print(f"  [量化模型] 样本不足 ({len(all_features)}), 训练跳过", flush=True)
            return False

        X, keys = feature_dicts_to_matrix(all_features)
        y = np.array(all_targets)
        self.feature_keys = keys

        print(f"  [量化模型] 训练样本: {X.shape[0]} 条, 特征: {X.shape[1]} 个", flush=True)

        split = int(len(y) * 0.8)
        X_train, X_val = X[:split], X[split:]
        y_train, y_val = y[:split], y[split:]

        train_data = lgb.Dataset(X_train, label=y_train)
        val_data = lgb.Dataset(X_val, label=y_val, reference=train_data)

        params = {
            "objective": "regression",
            "metric": "mae",
            "boosting_type": "gbdt",
            "num_leaves": 32,
            "learning_rate": 0.05,
            "feature_fraction": 0.8,
            "bagging_fraction": 0.8,
            "bagging_freq": 5,
            "verbose": -1,
            "seed": 42,
        }

        self.model = lgb.train(
            params,
            train_data,
            valid_sets=[val_data],
            num_boost_round=500,
            callbacks=[lgb.early_stopping(20), lgb.log_evaluation(0)],
        )

        val_pred = self.model.predict(X_val)
        val_mae = np.mean(np.abs(val_pred - y_val))
        val_corr = np.corrcoef(val_pred, y_val)[0, 1] if len(y_val) > 2 else 0
        print(f"  [量化模型] 验证集 MAE: {val_mae:.2f}%, 相关系数: {val_corr:.3f}", flush=True)

        self._save()
        print(f"  [量化模型] 模型已保存: {self.model_path}", flush=True)

        # 打印特征重要性
        imp = pd.DataFrame({"feature": self.feature_keys, "importance": self.model.feature_importance()})
        imp = imp.sort_values("importance", ascending=False).head(10)
        print(f"  [量化模型] 最重要特征:\n{imp.to_string(index=False)}", flush=True)

        return True

    def predict(self, kline_data):
        """对单只股票的当前状态评分，返回 0-100 分"""
        if not self.model or not self.feature_keys:
            return None

        feats = compute_features(kline_data)
        if feats is None:
            return None

        row = np.array([[feats.get(k, 0) for k in self.feature_keys]])
        pred = self.model.predict(row)[0]

        score = 50 + pred * 3
        score = max(0, min(100, score))
        return round(score, 1)

    def train_if_needed(self, codes=None):
        """如果模型不存在则训练"""
        if not self.is_trained():
            return self.train(codes=codes)
        return True


import pandas as pd
