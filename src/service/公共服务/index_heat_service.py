from __future__ import annotations

from typing import Any, Dict, List, Optional

from src.API.市场指数.指数资金热度与价格走势 import get_index_price_flow
from src.API.市场指数.证券日线K线行情数据 import get_security_day_flow_kline, get_security_today_flow_kline


def _guess_index_secid(index_code: str) -> str:
    """
    仅按指数语义推断 secid。
    """
    code = (index_code or "").strip().upper()
    if not code:
        return ""

    # 特殊指数需要显式映射，避免被通用前缀规则误判。
    if code == "899050":
        return "0.899050"
    if code == "950125":
        return "2.950125"

    if code.startswith("BK"):
        return ""

    if code.startswith(("H", "930", "931")):
        return f"2.{code}"

    if code.startswith("399"):
        return f"0.{code}"

    if code.startswith("000"):
        return f"1.{code}"

    if code.startswith(("97", "98")):
        return f"0.{code}"

    return code


def get_latest_realtime_index_heat(
    user,
    index_code: str,
    *,
    cache: Optional[Dict[str, Optional[float]]] = None,
    range_type: str = "w",
) -> Optional[float]:
    """
    获取指数最近一条实时资金热度。

    - 默认使用近一周区间拉取，取最后一条有效记录
    - 允许调用方传入 cache，避免同一轮策略重复访问接口
    """
    if not index_code:
        return None

    if cache is not None and index_code in cache:
        return cache[index_code]

    latest_score: Optional[float] = None
    try:
        resp = get_index_price_flow(user, index_code=index_code, range_type=range_type)
        items = getattr(resp, "items", None) or []
        if items:
            latest_item = items[-1]
            raw_score = getattr(latest_item, "XLFLOW_SCORE", None)
            if raw_score is not None:
                latest_score = float(raw_score)
    except Exception:
        latest_score = None

    if cache is not None:
        cache[index_code] = latest_score
    return latest_score


def get_latest_realtime_index_main_net_inflow(
    user,
    index_code: str,
    *,
    cache: Optional[Dict[str, Optional[float]]] = None,
) -> Optional[float]:
    """
    获取指数最近一条主力净流入金额。

    优先取当日实时资金流；若当日接口无值，则回退到最近一条日线资金流。
    返回值：
      - 正数：主力净流入
      - 负数：主力净流出
      - None：当前无法获取
    """
    if not index_code:
        return None

    if cache is not None and index_code in cache:
        return cache[index_code]

    secid = _guess_index_secid(index_code)
    if not secid:
        if cache is not None:
            cache[index_code] = None
        return None

    latest_main_net_inflow: Optional[float] = None
    try:
        today_resp = get_security_today_flow_kline(user, secid=secid, lmt=1)
        today_items = getattr(getattr(today_resp, "data", None), "items", None) or []
        if today_items:
            latest_main_net_inflow = getattr(today_items[-1], "MAIN_NET_INFLOW", None)

        if latest_main_net_inflow is None:
            day_resp = get_security_day_flow_kline(user, secid=secid, lmt=1)
            day_items = getattr(getattr(day_resp, "data", None), "items", None) or []
            if day_items:
                latest_main_net_inflow = getattr(day_items[-1], "MAIN_NET_INFLOW", None)
    except Exception:
        latest_main_net_inflow = None

    if latest_main_net_inflow is not None:
        try:
            latest_main_net_inflow = float(latest_main_net_inflow)
        except Exception:
            latest_main_net_inflow = None

    if cache is not None:
        cache[index_code] = latest_main_net_inflow
    return latest_main_net_inflow


def _extract_point_trade_date(point: Any) -> str:
    for attr in ("PDATE", "TRADE_DATE", "trade_date"):
        value = getattr(point, attr, None)
        if value:
            return str(value)
    return ""


def _merge_recent_flow_points(user, secid: str, lmt: int) -> List[Any]:
    """
    合并历史日线资金流与当日实时资金流，并按交易日升序返回。

    - 以当日实时点覆盖同日历史点，避免盘中/盘后口径不一致
    - 返回结果用于做最近 N 日净流入趋势确认
    """
    day_resp = get_security_day_flow_kline(user, secid=secid, lmt=lmt)
    day_items = getattr(getattr(day_resp, "data", None), "items", None) or []
    if not day_items:
        return []

    flow_by_date = {}
    for item in day_items:
        trade_date = _extract_point_trade_date(item)
        if trade_date:
            flow_by_date[trade_date] = item

    today_resp = get_security_today_flow_kline(user, secid=secid, lmt=1)
    today_items = getattr(getattr(today_resp, "data", None), "items", None) or []
    if today_items:
        today_item = today_items[-1]
        trade_date = _extract_point_trade_date(today_item)
        if trade_date:
            flow_by_date[trade_date] = today_item

    return [flow_by_date[d] for d in sorted(flow_by_date.keys())]


def get_index_main_net_inflow_filter_snapshot(
    user,
    index_code: str,
    *,
    cache: Optional[Dict[str, Dict[str, Any]]] = None,
    positive_days_window: int = 10,
    min_positive_days: int = 5,
    inflow_sum_window: int = 3,
) -> Optional[Dict[str, Any]]:
    """
    获取指数净流入过滤快照。

    当前策略采用三层确认：
    1. 当前交易日主力净流入 > 0
    2. 过去 10 个交易日里，至少 5 个交易日主力净流入 > 0
    3. 过去 3 个交易日主力净流入合计 > 0

    若接口无法提供足够历史点位，调用方可按兼容逻辑自行放行/降级。
    """
    if not index_code:
        return None

    if cache is not None and index_code in cache:
        return cache[index_code]

    secid = _guess_index_secid(index_code)
    if not secid:
        if cache is not None:
            cache[index_code] = None
        return None

    lookback = max(int(positive_days_window or 0), int(inflow_sum_window or 0), 1)
    points = _merge_recent_flow_points(user, secid=secid, lmt=lookback)
    if not points:
        if cache is not None:
            cache[index_code] = None
        return None

    latest_point = points[-1]
    latest_main_net_inflow = getattr(latest_point, "MAIN_NET_INFLOW", None)
    try:
        latest_main_net_inflow = float(latest_main_net_inflow) if latest_main_net_inflow is not None else None
    except Exception:
        latest_main_net_inflow = None

    positive_slice = points[-positive_days_window:] if positive_days_window > 0 else []
    positive_values = []
    for point in positive_slice:
        value = getattr(point, "MAIN_NET_INFLOW", None)
        try:
            if value is not None:
                positive_values.append(float(value))
        except Exception:
            continue

    inflow_sum_slice = points[-inflow_sum_window:] if inflow_sum_window > 0 else []
    inflow_sum_values = []
    for point in inflow_sum_slice:
        value = getattr(point, "MAIN_NET_INFLOW", None)
        try:
            if value is not None:
                inflow_sum_values.append(float(value))
        except Exception:
            continue

    snapshot = {
        "index_code": index_code,
        "secid": secid,
        "latest_date": _extract_point_trade_date(latest_point) or None,
        "latest_main_net_inflow": latest_main_net_inflow,
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
        cache[index_code] = snapshot
    return snapshot
