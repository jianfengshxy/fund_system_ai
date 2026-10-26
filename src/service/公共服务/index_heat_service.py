from __future__ import annotations

from typing import Dict, Optional

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
