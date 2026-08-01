import logging
import sys
import os
from datetime import datetime
from typing import Any, Optional, Tuple


root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)


def _extract_date_part(date_text: Optional[str]) -> Optional[str]:
    if not date_text:
        return None
    candidate = str(date_text).strip()[:10]
    try:
        return datetime.strptime(candidate, "%Y-%m-%d").strftime("%Y-%m-%d")
    except ValueError:
        return None


def calc_estimated_change(fund_info: Any) -> Tuple[float, str]:
    """按净值日期 vs 估值日期的关系，返回真正的「有效估值涨跌幅」和「计算口径标签」。

    规则：
      - 当估值日期 <= 最近净值日（正式净值已经发布，持有收益率已同步）：返回 0.0，
        不再把估值收益率重复叠加到持有收益率上。
      - 其他情况（估值日期晚于净值日）：返回 fund_info.estimated_change。
    """
    nav_date = _extract_date_part(getattr(fund_info, "nav_date", None))
    est_time = getattr(fund_info, "estimated_time", None)
    est_date = _extract_date_part(est_time)

    try:
        est_change = float(getattr(fund_info, "estimated_change", None) or 0.0)
    except (ValueError, TypeError):
        est_change = 0.0

    if est_date and nav_date and est_date <= nav_date:
        return 0.0, f"净值已发布(nav={nav_date}, est={est_date})"
    return est_change, (f"盘中估值(nav={nav_date}, est={est_date})" if est_date else "估值日期缺失")


def calc_estimated_profit_rate(current_profit_rate: float, fund_info: Any) -> Tuple[float, float, str]:
    """按口径规则统一计算预估持有收益率。

    返回 (estimated_profit_rate, effective_estimated_change, label)。
    """
    if current_profit_rate is None:
        current_profit_rate = 0.0
    try:
        cur = float(current_profit_rate)
    except (ValueError, TypeError):
        cur = 0.0
    eff_change, label = calc_estimated_change(fund_info)
    return cur + eff_change, eff_change, label
