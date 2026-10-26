from __future__ import annotations

from typing import Dict, Optional

from src.API.市场指数.指数资金热度与价格走势 import get_index_price_flow


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
