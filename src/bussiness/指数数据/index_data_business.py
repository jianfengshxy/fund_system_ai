# -*- coding: utf-8 -*-
"""
指数数据业务层

两个核心业务：
  1. 全量同步  — 拉取所有指数的全部历史日数据、阶段指标、计算周期涨跌幅
  2. 最新快照  — 仅同步最新交易日的阶段指标（正收益概率/平均收益率/PE百分位/PB百分位）

底层委托给 MarketIndexService。
"""

import os
import sys

# Allow running as script
if __name__ == "__main__":
    root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    if root_dir not in sys.path:
        sys.path.insert(0, root_dir)

import time
from typing import Optional

from src.common.constant import DEFAULT_USER
from src.common.logger import get_logger
from src.API.登录接口.login import ensure_user_fresh
from src.domain.user.User import User
from src.service.市场指数.market_index_service import MarketIndexService

logger = get_logger("IndexDataBusiness")


def sync_all_full(user: Optional[User] = None) -> dict:
    """
    全量同步所有指数的全部数据。

    执行步骤：
      1. 全量日数据同步（PE-TTM / PB / 价格 / 热度历史）
      2. 全量阶段指标同步（正收益概率 / 平均收益率 / PE百分位 / PB百分位，仅宽基/行业/主题/海外）
      3. 全量周期涨跌幅计算（change_w/m/q/hy/y）

    Args:
        user: 认证用户，为 None 时自动登录

    Returns:
        {"daily": {total,synced,failed}, "stage": {total,synced,failed,no_daily_data}, "changes": int, "elapsed_min": float}
    """
    if user is None:
        user = ensure_user_fresh(DEFAULT_USER)

    svc = MarketIndexService()
    t0 = time.time()
    result = {}

    # 1. 全量日数据
    logger.info("=== 业务: 全量日数据同步 ===")
    result["daily"] = svc.sync_all_indices_daily(user)
    t1 = time.time()
    logger.info(f"日数据: 成功 {result['daily']['synced']}/{result['daily']['total']}, 耗时 {(t1-t0)/60:.1f}分")

    # 2. 全量阶段指标
    logger.info("=== 业务: 全量阶段指标 ===")
    result["stage"] = svc.sync_all_indices_stage_performance(user)
    t2 = time.time()
    logger.info(f"阶段指标: 成功 {result['stage']['synced']}/{result['stage']['total']}, 耗时 {(t2-t1)/60:.1f}分")

    # 3. 全量周期涨跌幅
    logger.info("=== 业务: 全量周期涨跌幅 ===")
    result["changes"] = svc.fill_period_changes()
    t3 = time.time()
    logger.info(f"周期涨跌幅: {result['changes']} 行, 耗时 {(t3-t2)/60:.1f}分")

    result["elapsed_min"] = round((t3 - t0) / 60, 1)
    logger.info(f"全量同步完成, 总耗时 {result['elapsed_min']} 分钟")
    return result


def sync_latest_snapshot(
    user: Optional[User] = None,
    *,
    daily_range_type: str = "y",
    daily_limit: Optional[int] = None,
    stage_limit: Optional[int] = None,
) -> dict:
    """
    同步所有宽基/行业/主题/海外指数的最新交易日阶段指标。

    该接口调用天天基金 FundIndexDiy API（指数阶段指标.py），
    仅返回当前最新快照数据，不拉取历史，速度快（约 2~3 分钟）。

    Args:
        user: 认证用户，为 None 时自动登录

    Returns:
        {"total": int, "synced": int, "failed": int, "no_daily_data": int, "elapsed_min": float}
    """
    if user is None:
        user = ensure_user_fresh(DEFAULT_USER)

    svc = MarketIndexService()
    t0 = time.time()
    logger.info("=== 业务: 最新交易日快照(日数据+阶段指标) ===")

    daily_result = svc.sync_all_indices_latest_daily_price_flow(
        user,
        range_type=daily_range_type,
        limit=daily_limit,
    )

    stage_result = svc.sync_all_indices_stage_performance(user, limit=stage_limit)

    result = {"daily": daily_result, "stage": stage_result}
    result["elapsed_min"] = round((time.time() - t0) / 60, 1)
    logger.info(
        f"最新快照完成: 日数据 {daily_result['synced']}/{daily_result['total']} "
        f"(失败 {daily_result['failed']}), "
        f"阶段指标 {stage_result['synced']}/{stage_result['total']} "
        f"(失败 {stage_result['failed']}, 无日数据 {stage_result['no_daily_data']}), "
        f"耗时 {result['elapsed_min']} 分钟"
    )
    return result


if __name__ == "__main__":
    sync_latest_snapshot()
