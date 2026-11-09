from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional

from src.API.市场指数.基金主题详情 import get_fund_theme_detail
from src.db.database_connection import DatabaseConnection


def _normalize_date(raw) -> Optional[str]:
    if raw is None:
        return None
    if isinstance(raw, datetime):
        return raw.date().isoformat()
    text = str(raw).strip()
    if not text:
        return None
    return text[:10] if len(text) >= 10 else text


def _safe_float(raw) -> Optional[float]:
    if raw in (None, "", "--"):
        return None
    try:
        return float(raw)
    except Exception:
        return None


def get_latest_realtime_theme_snapshot(
    user,
    theme_code: str,
    *,
    cache: Optional[Dict[str, Optional[Dict[str, Any]]]] = None,
) -> Optional[Dict[str, Any]]:
    """
    获取主题当前资金面快照。

    说明：
      - heat_score 来自评分口径（SCOREDATE）
      - flow 来自实时行情口径（DEALTIME）
    """
    if not theme_code:
        return None

    if cache is not None and theme_code in cache:
        return cache[theme_code]

    snapshot: Optional[Dict[str, Any]] = None
    try:
        detail = get_fund_theme_detail(user, theme_code)
        if detail.success and detail.data:
            rt = detail.data.realTimeList[0] if detail.data.realTimeList else None
            bi = detail.data.themeBaseInfo[0] if detail.data.themeBaseInfo else None
            snapshot = {
                "theme_code": theme_code,
                "theme_name": getattr(rt, "INDEXNAME", None) if rt else None,
                "score_date": _normalize_date(
                    (getattr(rt, "SCOREDATE", None) if rt else None)
                    or (getattr(bi, "SCOREDATE", None) if bi else None)
                ),
                "deal_date": _normalize_date(getattr(rt, "DEALTIME", None) if rt else None),
                "latest_heat_score": _safe_float(
                    (getattr(rt, "CHANCE_ZJRD", None) if rt else None)
                    or (getattr(bi, "CHANCE_ZJRD", None) if bi else None)
                ),
                "latest_flow": _safe_float(getattr(rt, "FLOW", None) if rt else None),
                "latest_main_net_inflow": _safe_float(getattr(bi, "RM_NETFLOWXL", None) if bi else None),
            }
    except Exception:
        snapshot = None

    if cache is not None:
        cache[theme_code] = snapshot
    return snapshot


def get_latest_realtime_theme_heat(
    user,
    theme_code: str,
    *,
    cache: Optional[Dict[str, Optional[float]]] = None,
    snapshot_cache: Optional[Dict[str, Optional[Dict[str, Any]]]] = None,
) -> Optional[float]:
    """获取主题最近一条资金热度评分。"""
    if not theme_code:
        return None

    if cache is not None and theme_code in cache:
        return cache[theme_code]

    snapshot = get_latest_realtime_theme_snapshot(user, theme_code, cache=snapshot_cache)
    latest_heat_score = snapshot.get("latest_heat_score") if snapshot else None
    if cache is not None:
        cache[theme_code] = latest_heat_score
    return latest_heat_score


def get_latest_realtime_theme_flow(
    user,
    theme_code: str,
    *,
    cache: Optional[Dict[str, Optional[float]]] = None,
    snapshot_cache: Optional[Dict[str, Optional[Dict[str, Any]]]] = None,
) -> Optional[float]:
    """获取主题最近一条实时净流入金额。"""
    if not theme_code:
        return None

    if cache is not None and theme_code in cache:
        return cache[theme_code]

    snapshot = get_latest_realtime_theme_snapshot(user, theme_code, cache=snapshot_cache)
    latest_flow = snapshot.get("latest_flow") if snapshot else None
    if cache is not None:
        cache[theme_code] = latest_flow
    return latest_flow


def get_theme_flow_filter_snapshot(
    theme_code: str,
    *,
    user=None,
    cache: Optional[Dict[str, Optional[Dict[str, Any]]]] = None,
    snapshot_cache: Optional[Dict[str, Optional[Dict[str, Any]]]] = None,
    positive_days_window: int = 10,
    min_positive_days: int = 5,
    inflow_sum_window: int = 3,
) -> Optional[Dict[str, Any]]:
    """
    获取主题净流入过滤快照。

    历史数据来自 market_theme_daily.flow，当前交易日优先用实时 FLOW 覆盖：
      1. 当前交易日净流入 > 0
      2. 过去 10 个交易日里，至少 5 个交易日净流入 > 0
      3. 过去 3 个交易日净流入合计 > 0
    """
    if not theme_code:
        return None

    if cache is not None and theme_code in cache:
        return cache[theme_code]

    lookback = max(int(positive_days_window or 0), int(inflow_sum_window or 0), 1)
    db = DatabaseConnection()
    rows = db.execute_query(
        "SELECT trade_date, flow "
        "FROM market_theme_daily "
        "WHERE theme_code = %s AND flow IS NOT NULL "
        "ORDER BY trade_date DESC "
        "LIMIT %s",
        (theme_code, lookback),
    )
    points_by_date = {}
    for row in rows or []:
        trade_date = _normalize_date(row.get("trade_date"))
        flow = _safe_float(row.get("flow"))
        if trade_date and flow is not None:
            points_by_date[trade_date] = {
                "trade_date": trade_date,
                "flow": flow,
                "flow_source": "database",
            }

    if user is not None:
        realtime_snapshot = get_latest_realtime_theme_snapshot(user, theme_code, cache=snapshot_cache)
        realtime_trade_date = _normalize_date(realtime_snapshot.get("deal_date")) if realtime_snapshot else None
        realtime_flow = _safe_float(realtime_snapshot.get("latest_flow")) if realtime_snapshot else None
        if realtime_trade_date and realtime_flow is not None:
            points_by_date[realtime_trade_date] = {
                "trade_date": realtime_trade_date,
                "flow": realtime_flow,
                "flow_source": "realtime",
            }

    if not points_by_date:
        if cache is not None:
            cache[theme_code] = None
        return None

    points = [points_by_date[trade_date] for trade_date in sorted(points_by_date.keys())]
    points = points[-lookback:]
    latest_row = points[-1]
    latest_flow = _safe_float(latest_row.get("flow"))

    positive_slice = points[-positive_days_window:] if positive_days_window > 0 else []
    positive_values = [_safe_float(row.get("flow")) for row in positive_slice]
    positive_values = [value for value in positive_values if value is not None]

    inflow_sum_slice = points[-inflow_sum_window:] if inflow_sum_window > 0 else []
    inflow_sum_values = [_safe_float(row.get("flow")) for row in inflow_sum_slice]
    inflow_sum_values = [value for value in inflow_sum_values if value is not None]

    snapshot = {
        "theme_code": theme_code,
        "latest_date": latest_row.get("trade_date"),
        "latest_flow": latest_flow,
        "latest_flow_source": latest_row.get("flow_source"),
        "positive_days_window": positive_days_window,
        "min_positive_days": min_positive_days,
        "positive_days_available": len(positive_values) >= positive_days_window,
        "positive_days_count": sum(1 for value in positive_values if value > 0),
        "inflow_sum_window": inflow_sum_window,
        "inflow_sum_available": len(inflow_sum_values) >= inflow_sum_window,
        "recent_inflow_sum": sum(inflow_sum_values) if inflow_sum_values else None,
        "trade_days": len(points),
    }

    if cache is not None:
        cache[theme_code] = snapshot
    return snapshot
