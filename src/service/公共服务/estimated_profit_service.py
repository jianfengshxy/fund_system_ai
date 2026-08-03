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


def _estimate_time_passed_close(est_time: Optional[str]) -> bool:
    """判断估值时间是否已在 A 股收盘（15:00）后 10 分钟（即 15:10）之外。

    对 QDII / 海外指数等估值时点滞后的基金，第三方估值往往带时分秒时间戳
    （如 2026-07-31 16:00:01）。即使其日期与正式净值日期相同，只要时间在
    15:10 之后，即视为当日定稿数据，仍可作为有效增量参与预估收益率计算。
    预留 10 分钟缓冲，避免 15:00 零界点的时间摩擦。
    """
    if not est_time:
        return False
    text = str(est_time).strip()
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
        try:
            dt = datetime.strptime(text, fmt)
            return (dt.hour, dt.minute, dt.second) >= (15, 10, 0)
        except ValueError:
            continue
    return False


def calc_estimated_change(fund_info: Any) -> Tuple[float, str]:
    """按净值日期 vs 估值日期的关系，返回真正的「有效估值涨跌幅」和「计算口径标签」。

    规则：
      - 当估值日期 < 最近净值日：正式净值已经发布，持有收益率已同步，返回 0.0，
        不再把估值收益率重复叠加到持有收益率上。
      - 当估值日期 == 最近净值日：若估值时间在 A 股收盘后 10 分钟（15:10）之外，
        视为当日定稿估值（如 QDII 海外指数收盘数据），仍返回估算涨跌幅；否则视为
        与正式净值重复，返回 0.0。
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
        if est_date == nav_date and _estimate_time_passed_close(est_time):
            return est_change, f"收盘后估值(nav={nav_date}, est={est_time})"
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
