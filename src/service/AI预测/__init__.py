# -*- coding: utf-8 -*-
"""
AI 预测模块 - 基于 LightGBM 的指数涨跌预测

目录结构:
  src/service/AI预测/
  ├── __init__.py               # 模块入口
  ├── index_predictor.py        # LightGBM 训练器 + 预测器
  └── strategies/               # 各指数个性化策略 (后续扩展)

用法:
  from src.service.AI预测.index_predictor import IndexPredictor

  pred = IndexPredictor()
  pred.train('399971')                     # 训练模型
  signals = pred.predict('399971')         # 获取当前买卖信号
  # 返回: {'buy_signal': True, 'confidence': 0.85, 'expected_1m': 5.2, ...}
"""

from .index_predictor import IndexPredictor

__all__ = ['IndexPredictor']
