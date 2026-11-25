"""
指数/主题快照同步任务

手动触发：
1. 同步所有宽基/行业/主题/海外指数的最新交易日快照
2. 首次运行时初始化主题静态表/动态表
3. 日常运行时仅同步主题当日最新快照
"""

from __future__ import annotations

from src.bussiness.指数数据.index_data_business import sync_latest_snapshot
from src.task.runtime import logger


def handler(event=None, context=None):
    """同步最新指数/主题快照"""
    logger.info("指数/主题快照同步任务开始")
    result = sync_latest_snapshot()
    logger.info(
        f"指数/主题快照同步完成: "
        f"日数据 {result['daily']['synced']}/{result['daily']['total']}, "
        f"日数据失败 {result['daily']['failed']}, "
        f"阶段指标 {result['stage']['synced']}/{result['stage']['total']}, "
        f"阶段指标失败 {result['stage']['failed']}, "
        f"无日数据 {result['stage']['no_daily_data']}, "
        f"主题快照 {result['theme']['daily']['synced']}/{result['theme']['daily']['total']}, "
        f"主题失败 {result['theme']['daily']['failed']}, "
        f"主题静态初始化 skipped={result['theme']['init_static'].get('skipped')}, "
        f"主题动态初始化 skipped={result['theme']['init_daily'].get('skipped')}, "
        f"耗时 {result.get('elapsed_min', '-')} 分钟"
    )
    return result
