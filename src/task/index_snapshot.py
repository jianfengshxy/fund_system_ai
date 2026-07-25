"""
指数阶段指标快照同步任务

手动触发，同步所有宽基/行业/主题/海外指数的最新交易日阶段指标
（正收益概率/平均收益率/PE百分位/PB百分位）。
"""

from __future__ import annotations

from src.bussiness.指数数据.index_data_business import sync_latest_snapshot
from src.task.runtime import logger


def handler(event=None, context=None):
    """同步最新交易日阶段指标快照"""
    logger.info("指数阶段指标快照同步任务开始")
    result = sync_latest_snapshot()
    logger.info(
        f"指数阶段指标快照同步完成: "
        f"成功 {result['synced']}/{result['total']}, "
        f"失败 {result['failed']}, "
        f"无日数据 {result['no_daily_data']}, "
        f"耗时 {result.get('elapsed_min', '-')} 分钟"
    )
    return result
