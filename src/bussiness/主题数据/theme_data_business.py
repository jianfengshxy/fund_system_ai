# -*- coding: utf-8 -*-
"""
主题数据业务层

两个核心业务：
  1. 初始化同步  — 建立主题静态表，并为动态表回补可获取的历史数据
  2. 最新快照    — 每日仅刷新当天最新 BK 快照与主题详情补充字段
"""

from __future__ import annotations

import os
import sys
import time
from typing import Optional


if __name__ == "__main__":
    root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    if root_dir not in sys.path:
        sys.path.insert(0, root_dir)

from src.common.constant import DEFAULT_USER
from src.common.logger import get_logger
from src.API.登录接口.login import ensure_user_fresh
from src.domain.user.User import User
from src.service.市场主题.market_theme_service import MarketThemeService


logger = get_logger("ThemeDataBusiness")


def sync_latest_snapshot(
    user: Optional[User] = None,
    *,
    init_range_type: str = "3n",
) -> dict:
    """
    同步主题数据。

    执行规则：
      1. 若静态表为空，先初始化全部主题静态属性
      2. 若动态表为空，先做动态历史全量初始化
      3. 无论是否初始化，最后都补一次当日最新快照
    """
    if user is None:
        user = ensure_user_fresh(DEFAULT_USER)

    svc = MarketThemeService()
    t0 = time.time()

    static_count = svc.get_theme_count()
    daily_count = svc.get_daily_count()
    theme_total = static_count

    init_static = {"total": static_count, "synced": 0, "failed": 0, "skipped": static_count > 0}
    init_daily = {"total": theme_total, "synced": 0, "failed": 0, "rows": 0, "period_changes": 0, "skipped": daily_count > 0}

    if static_count == 0:
        logger.info("=== 业务: 主题静态表初始化 ===")
        init_static = svc.sync_all_themes(user, enrich_detail=True)
        init_static["skipped"] = False
        theme_total = init_static["total"]
        init_daily["total"] = theme_total

    if daily_count == 0:
        logger.info("=== 业务: 主题动态表全量初始化 ===")
        init_daily = svc.sync_all_themes_full_daily(user, range_type=init_range_type)
        init_daily["skipped"] = False

    logger.info("=== 业务: 主题最新快照同步 ===")
    latest = svc.sync_all_themes_latest_snapshot(user)

    result = {
        "init_static": init_static,
        "init_daily": init_daily,
        "daily": latest,
        "elapsed_min": round((time.time() - t0) / 60, 1),
    }
    logger.info(
        f"主题数据同步完成: "
        f"静态初始化 {init_static['synced']}/{init_static['total']} "
        f"(失败 {init_static['failed']}, skipped={init_static.get('skipped')}), "
        f"动态初始化 {init_daily['synced']}/{init_daily['total']} "
        f"(失败 {init_daily['failed']}, skipped={init_daily.get('skipped')}), "
        f"最新快照 {latest['synced']}/{latest['total']} "
        f"(失败 {latest['failed']}), "
        f"耗时 {result['elapsed_min']} 分钟"
    )
    return result


if __name__ == "__main__":
    sync_latest_snapshot()
