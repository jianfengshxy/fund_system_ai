# -*- coding: utf-8 -*-
"""
指数预测器 - 使用 Ridge 回归对单个指数独立建模

工作流程:
  1. 从 market_index_daily 读取历史数据
  2. 构建特征: PE分位, PB分位, 热度, 近期涨跌幅, 均线偏离度等
  3. 训练 Ridge 回归 (numpy 实现) 预测未来 1个/3个/6个月涨跌幅
  4. 保存模型为 {index_code}_pred.pkl
  5. 预测时加载模型，输出信号 + 置信度

特征矩阵构建:
  - 当前日的 PE 分位、PB 分位、热度分位
  - 过去 5/10/20/60 日的累计涨跌幅
  - 当前价 vs 20MA/60MA 偏离度
  - PE 分位变化率（当前 vs 60日前）
  - 波动率（近20日日收益标准差）

标签:
  - 未来1个月/3个月/6个月的涨跌幅
"""

import os
import sys
import pickle
from typing import Optional, List, Dict, Tuple
from datetime import datetime

import numpy as np

root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from src.common.logger import get_logger
from src.service.市场指数.market_index_service import MarketIndexService

logger = get_logger(__name__)

# 模型保存目录
MODEL_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'models')
os.makedirs(MODEL_DIR, exist_ok=True)


class IndexPredictor:
    """
    指数预测器。

    每个指数一个独立模型，支持训练、保存、加载、预测。
    """

    def __init__(self):
        self._data_svc = MarketIndexService()
        self._models: Dict[str, object] = {}

    # ===================== 特征工程 =====================

    @staticmethod
    def _build_features(records: List[Dict]) -> Tuple[List, List, List]:
        """
        从历史记录构建特征矩阵 X 和标签 y1m/y3m/y6m。
        返回 (X, y_1m, y_3m, y_6m, dates)

        records: 按 trade_date 升序的 dict 列表，
                 至少包含: price, pe_pct, pb_pct, heat_score, change_pct
        """
        import math

        X, y1m, y3m, y6m, dates = [], [], [], [], []
        n = len(records)

        for i in range(60, n):  # 前60条用于计算特征
            # 特征构建窗口: i-60 到 i
            window = records[i - 60: i + 1]
            cur = records[i]

            # 需要 price
            prices = [
                float(w["price"]) if w.get("price") is not None else None
                for w in window
            ]
            if None in prices[-20:]:
                continue

            fv = []

            # ---- 当前估值指标 ----
            fv.append(float(cur.get("pe_pct") or 50.0))
            fv.append(float(cur.get("pb_pct") or 50.0))
            fv.append(float(cur.get("heat_score") or 0))
            fv.append(float(cur.get("pe_ttm") or 0))
            fv.append(float(cur.get("pb") or 0))

            # ---- 近期涨跌幅 ----
            cp = float(cur["price"]) if cur.get("price") is not None else None
            if cp:
                for lag in [5, 10, 20, 60]:
                    past = prices[-1 - lag] if len(prices) > lag else prices[0]
                    if past and past != 0:
                        fv.append((cp / past - 1) * 100)
                    else:
                        fv.append(0.0)

            # ---- 均线偏离度 ----
            valid_prices = [p for p in prices if p is not None]
            if cp and len(valid_prices) >= 20:
                ma20 = sum(valid_prices[-20:]) / 20
                fv.append((cp / ma20 - 1) * 100)
            else:
                fv.append(0.0)

            if cp and len(valid_prices) >= 60:
                ma60 = sum(valid_prices[-60:]) / 60
                fv.append((cp / ma60 - 1) * 100)
            else:
                fv.append(0.0)

            # ---- 日均波动率 (近20日) ----
            if len(prices) >= 21:
                segment = prices[-21:]  # 需要21个点计算20个日收益
                if None in segment:
                    fv.append(0.0)
                else:
                    rets = [(segment[j+1] - segment[j]) / segment[j]
                            for j in range(20)]
                    vol = (sum((r - sum(rets) / len(rets)) ** 2
                               for r in rets) / len(rets)) ** 0.5 * 100
                    fv.append(vol)
            else:
                fv.append(0.0)

            # ---- PE 分位变化率 ----
            if i >= 60:
                past_pe_pct = records[i - 60].get("pe_pct")
                cur_pe_pct = cur.get("pe_pct")
                if past_pe_pct and cur_pe_pct:
                    fv.append(cur_pe_pct - past_pe_pct)
                else:
                    fv.append(0.0)
            else:
                fv.append(0.0)

            X.append(fv)
            dates.append(cur["trade_date"])

            # ---- 标签: 未来 N 日收益 ----
            def _future_return(offset: int) -> Optional[float]:
                target_idx = i + offset
                if target_idx < n:
                    fp = records[target_idx].get("price")
                    if fp is not None and cp is not None:
                        return (float(fp) / cp - 1) * 100
                return None

            y1m.append(_future_return(21))   # ~1个月交易日的偏移
            y3m.append(_future_return(63))   # ~3个月
            y6m.append(_future_return(126))  # ~6个月

        return X, y1m, y3m, y6m, dates

    # ===================== 训练 =====================

    def train(self, index_code: str, force: bool = False) -> Dict:
        """
        训练指数预测模型。

        Args:
            index_code: 指数代码，如 "399971"
            force: 是否强制重训（否则已有模型则跳过）

        Returns:
            dict: 训练结果摘要 {feature_importances, metrics, model_path}
        """
        model_path = os.path.join(MODEL_DIR, f"{index_code}_pred.pkl")
        if os.path.exists(model_path) and not force:
            logger.info(f"[{index_code}] 模型已存在: {model_path}，跳过训练")
            self._load_model(index_code)
            return {"status": "cached", "model_path": model_path}

        # 从数据库读取历史数据
        records = self._data_svc.get_index_history(index_code)
        if not records or len(records) < 120:
            raise ValueError(f"[{index_code}] 历史数据不足（{len(records) if records else 0}条），至少需要120条")

        X, y1m, y3m, y6m, dates = self._build_features(records)

        # 只训练有标签的数据
        valid_1m = [(x, y) for x, y in zip(X, y1m) if y is not None]
        valid_3m = [(x, y) for x, y in zip(X, y3m) if y is not None]
        valid_6m = [(x, y) for x, y in zip(X, y6m) if y is not None]

        logger.info(f"[{index_code}] 特征样本: 1M={len(valid_1m)} 3M={len(valid_3m)} 6M={len(valid_6m)}")

        feature_names = [
            "pe_pct", "pb_pct", "heat_score", "pe_ttm", "pb",
            "ret_5d", "ret_10d", "ret_20d", "ret_60d",
            "ma20_dev", "ma60_dev", "vol_20d", "pe_pct_chg_60d",
        ]

        result = {"status": "trained", "model_path": model_path, "metrics": {}}
        models = {}

        for label, valid_data in [("1m", valid_1m), ("3m", valid_3m), ("6m", valid_6m)]:
            if len(valid_data) < 60:
                logger.warning(f"[{index_code}] {label} 样本不足({len(valid_data)}), 跳过")
                continue

            raw_X = np.array([vd[0] for vd in valid_data], dtype=np.float64)
            raw_y = np.array([vd[1] for vd in valid_data], dtype=np.float64)

            # train/test split: 最近30条作为测试
            n = len(raw_X)
            split = max(n - 30, int(n * 0.7))
            train_X, train_y = raw_X[:split], raw_y[:split]
            test_X, test_y = raw_X[split:], raw_y[split:]

            # 标准化 + Ridge (L2 alpha=1.0)
            model = _RidgeModel.fit(train_X, train_y, alpha=1.0)

            # 评估
            preds = model.predict(test_X)
            residuals = test_y - preds
            ss_res = np.sum(residuals ** 2)
            ss_tot = np.sum((test_y - np.mean(test_y)) ** 2)
            r2 = 1 - ss_res / ss_tot if ss_tot != 0 else 0

            # 保存模型质量指标
            model.r2_ = float(r2)
            model.residual_std_ = float(np.std(residuals)) if len(residuals) > 0 else 15.0
            # 近期方向准确率：预测涨跌方向与实际的吻合度
            actual_direction = np.sign(test_y)
            pred_direction = np.sign(preds)
            correct = np.sum(actual_direction == pred_direction)
            total = len(actual_direction)
            model.recent_accuracy_ = float(correct / total) if total > 0 else 0.5

            models[label] = model
            result["metrics"][label] = {
                "r2": round(float(r2), 4),
                "samples": n,
                "train_samples": split,
                "test_samples": n - split,
                "coefficients": {feature_names[i]: round(float(model.coef_[i]), 4)
                                 for i in range(len(feature_names))},
            }

        # 保存模型
        with open(model_path, "wb") as f:
            pickle.dump({
                "models": {k: v.to_dict() for k, v in models.items()},
                "feature_names": feature_names,
                "trained_at": datetime.now().isoformat(),
            }, f)

        r2_vals = [f'{k}:{v["r2"]:.3f}' for k, v in result["metrics"].items()]
        logger.info(f"[{index_code}] 训练完成 (Ridge): {list(result['metrics'].keys())}, R²={r2_vals}")
        self._models[index_code] = models
        return result

    # ===================== 预测 =====================

    def predict(self, index_code: str) -> Optional[Dict]:
        """
        预测当前指数未来走势。

        Returns:
            dict: {
                'index_code': '399971',
                'trade_date': '2026-07-23',
                'signals': {
                    '1m': {'predicted_return': 2.5, 'signal': 'buy/hold/sell'},
                    '3m': {...},
                    '6m': {...},
                },
                'overall': 'buy/hold/sell',
                'confidence': 0.75
            }
        """
        self._load_model(index_code)
        models = self._models.get(index_code)
        if not models:
            logger.error(f"[{index_code}] 未加载模型，请先 train()")
            return None

        # 获取最近 120 条数据构建当前特征
        records = self._data_svc.get_index_history(index_code)
        if len(records) < 61:
            return None

        X, _, _, _, dates = self._build_features(records)
        if not X:
            return None

        current_fv = X[-1]
        result = {
            "index_code": index_code,
            "trade_date": records[-1]["trade_date"],
            "signals": {},
            "overall": "hold",
            "confidence": 0.0,
        }

        signal_map = {0: "sell", 1: "hold", 2: "buy"}
        confidences = []

        for label, model in models.items():
            pred = float(model.predict(np.array([current_fv], dtype=np.float64))[0])

            # 信号判断阈值
            if pred > 5.0:
                signal = "buy"
            elif pred < -3.0:
                signal = "sell"
            else:
                signal = "hold"

            result["signals"][label] = {
                "predicted_return": round(pred, 2),
                "signal": signal,
            }

            # 置信度：综合 R² + 残差标准差 + 信号强度 + 方向准确率
            pred_abs = abs(pred)
            r2_w = max(0, float(model.r2_)) * 0.4          # R²（权重 0.4）
            mag_w = min(pred_abs / 15.0, 1.0) * 0.2        # 信号强度（权重 0.2）
            rs = float(model.residual_std_)
            res_w = max(0, 1.0 - rs / 30.0) * 0.3          # 残差（权重 0.3）
            acc_w = float(model.recent_accuracy_) * 0.1    # 方向准确率（权重 0.1）
            confidences.append(r2_w + mag_w + res_w + acc_w)

        result["confidence"] = round(min(sum(confidences) / len(confidences), 1.0), 2)

        # 综合信号: 多数投票
        votes = [s["signal"] for s in result["signals"].values()]
        buy_cnt = votes.count("buy")
        sell_cnt = votes.count("sell")
        if buy_cnt >= 2:
            result["overall"] = "buy"
        elif sell_cnt >= 2:
            result["overall"] = "sell"
        else:
            result["overall"] = "hold"

        return result

    # ===================== 内部方法 =====================

    def _load_model(self, index_code: str):
        """加载已保存的模型"""
        if index_code in self._models:
            return
        path = os.path.join(MODEL_DIR, f"{index_code}_pred.pkl")
        if not os.path.exists(path):
            return
        with open(path, "rb") as f:
            data = pickle.load(f)
        # 从 dict 重建 _RidgeModel 对象
        models = {}
        for label, d in data.get("models", {}).items():
            models[label] = _RidgeModel.from_dict(d)
        self._models[index_code] = models




# ===================== Ridge 回归模型 (numpy) =====================


class _RidgeModel:
    """L2-正则化线性回归，纯 numpy 实现（标准缩放 + Ridge 闭式解）。"""

    __slots__ = ("coef_", "intercept_", "x_mean_", "x_std_", "y_mean_",
                 "r2_", "residual_std_", "recent_accuracy_")

    def __init__(self):
        self.coef_: Optional[np.ndarray] = None
        self.intercept_: float = 0.0
        self.x_mean_: Optional[np.ndarray] = None
        self.x_std_: Optional[np.ndarray] = None
        self.y_mean_: float = 0.0
        self.r2_: float = 0.0        # 测试集 R²（模型拟合质量）
        self.residual_std_: float = 15.0  # 残差标准差（预测不确定性）
        self.recent_accuracy_: float = 0.5  # 近期方向准确率

    @classmethod
    def fit(cls, X: np.ndarray, y: np.ndarray, alpha: float = 1.0) -> "_RidgeModel":
        """
        训练 Ridge 回归。
        w = (XᵀX + αI)⁻¹ Xᵀy（对标准化后的 X）
        """
        model = cls()
        model.y_mean_ = float(np.mean(y))

        # 标准化特征（全部减去均值除以标准差）
        model.x_mean_ = np.mean(X, axis=0)
        model.x_std_ = np.std(X, axis=0)
        model.x_std_[model.x_std_ == 0] = 1.0  # 常数特征除 1
        X_scaled = (X - model.x_mean_) / model.x_std_

        # 标准化目标
        y_centered = y - model.y_mean_

        # Ridge 闭式解: (XᵀX + αI)⁻¹ Xᵀy
        n_features = X_scaled.shape[1]
        gram = X_scaled.T @ X_scaled
        gram.flat[:: n_features + 1] += alpha  # 对角加 α
        coef = np.linalg.solve(gram, X_scaled.T @ y_centered)

        model.coef_ = coef
        model.intercept_ = model.y_mean_ - np.dot(model.x_mean_, coef / model.x_std_)
        return model

    def predict(self, X: np.ndarray) -> np.ndarray:
        X_scaled = (X - self.x_mean_) / self.x_std_
        return X_scaled @ self.coef_ + self.y_mean_

    def to_dict(self) -> Dict:
        return {
            "coef": self.coef_.tolist(),
            "intercept": self.intercept_,
            "x_mean": self.x_mean_.tolist(),
            "x_std": self.x_std_.tolist(),
            "y_mean": self.y_mean_,
            "r2": self.r2_,
            "residual_std": self.residual_std_,
            "recent_accuracy": self.recent_accuracy_,
        }

    @classmethod
    def from_dict(cls, d: Dict) -> "_RidgeModel":
        model = cls()
        model.coef_ = np.array(d["coef"])
        model.intercept_ = d["intercept"]
        model.x_mean_ = np.array(d["x_mean"])
        model.x_std_ = np.array(d["x_std"])
        model.y_mean_ = d["y_mean"]
        model.r2_ = d.get("r2", -0.5)
        model.residual_std_ = d.get("residual_std", 15.0)
        model.recent_accuracy_ = d.get("recent_accuracy", 0.5)
        return model
