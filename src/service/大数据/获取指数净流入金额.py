import os
import sys
from typing import Any, Dict, List, Optional


if __name__ == "__main__":
    root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    if root_dir not in sys.path:
        sys.path.insert(0, root_dir)

from src.common.logger import get_logger
from src.domain.user.User import User
from src.API.市场指数.证券日线K线行情数据 import (
    get_security_day_flow_kline,
    get_security_today_flow_kline,
)


logger = get_logger("IndexNetInflowService")


def guess_index_secid_from_code(index_code: str) -> str:
    """
    仅按“指数”语义推断 secid。

    注意：
    - 通用的 guess_secid_from_code 需要同时兼容股票/指数，像 000001 这类代码会有歧义。
    - 这里专门服务指数场景，因此优先按指数规则映射。
    - BK 主题代码不走本接口，因东财 fflow 对 BK 板块口径不稳定。
    - 399/97/98 开头的指数按深市/国证口径走 0.code，例如 987018 -> 0.987018。
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


def _merge_recent_flow_points(user: User, secid: str, lmt: int) -> List[Any]:
    """
    合并历史日线资金流与当日资金流。

    返回值按日期升序排列，元素兼容 SecurityDayFlowKlinePoint /
    SecurityTodayFlowKlinePoint，两者都包含 MAIN_NET_INFLOW 与 PDATE。
    """
    day_resp = get_security_day_flow_kline(user, secid=secid, lmt=lmt)
    if not day_resp.success or not day_resp.data or not day_resp.data.items:
        logger.warning(f"历史资金流获取失败: secid={secid}, err={day_resp.first_error}")
        return []

    flow_by_date = {item.PDATE: item for item in day_resp.data.items if getattr(item, "PDATE", None)}

    today_resp = get_security_today_flow_kline(user, secid=secid, lmt=1)
    if today_resp.success and today_resp.data and today_resp.data.items:
        today_item = today_resp.data.items[-1]
        if today_item.PDATE:
            # 以实时口径覆盖同日历史点，避免盘中/盘后口径不一致。
            flow_by_date[today_item.PDATE] = today_item

    return [flow_by_date[d] for d in sorted(flow_by_date.keys())]


def _sum_recent_main_net_inflow(points: List[Any], days: int) -> Dict[str, Any]:
    if len(points) < days:
        return {
            "days": days,
            "available": False,
            "trade_days": len(points),
            "start_date": points[0].PDATE if points else None,
            "end_date": points[-1].PDATE if points else None,
            "main_net_inflow": None,
        }

    selected = points[-days:]
    return {
        "days": days,
        "available": True,
        "trade_days": len(selected),
        "start_date": selected[0].PDATE,
        "end_date": selected[-1].PDATE,
        "main_net_inflow": sum((getattr(p, "MAIN_NET_INFLOW", None) or 0.0) for p in selected),
    }


def get_index_recent_main_net_inflow(
    user: User,
    index_code: str,
    windows: Optional[List[int]] = None,
) -> Dict[str, Any]:
    """
    获取指数近 N 日主力净流入金额。

    说明：
    - 天天基金 FundIndexPrice 仅返回热度分，不返回净流入金额。
    - 这里改用东财 fflow/daykline/get + fflow/kline/get。
    - “指数净流入金额”在当前接口里统一解释为“主力净流入金额”。
    - 返回值中的 main_net_inflow / latest_main_net_inflow:
      正数表示主力净流入，负数表示主力净流出。
    - 这与成交额(trade_amount)不是一个概念：
      trade_amount 反映交易活跃度，main_net_inflow 反映资金方向。
    """
    windows = sorted(set(windows or [3, 5]))
    max_window = max(windows) if windows else 5

    secid = guess_index_secid_from_code(index_code)
    if not secid:
        return {
            "success": False,
            "index_code": index_code,
            "secid": None,
            "message": "该指数代码无法映射到可用 secid，BK 主题代码暂不支持按 3/5 日口径计算净流入。",
            "windows": [],
        }

    points = _merge_recent_flow_points(user, secid=secid, lmt=max_window)
    if not points:
        return {
            "success": False,
            "index_code": index_code,
            "secid": secid,
            "message": "未获取到指数资金流数据。",
            "windows": [],
        }

    results = [_sum_recent_main_net_inflow(points, days) for days in windows]
    latest = points[-1]

    return {
        "success": True,
        "index_code": index_code,
        "secid": secid,
        "latest_date": latest.PDATE,
        "latest_main_net_inflow": getattr(latest, "MAIN_NET_INFLOW", None),
        "windows": results,
    }


if __name__ == "__main__":
    from src.common.constant import DEFAULT_USER
    from src.API.登录接口.login import ensure_user_fresh

    user = ensure_user_fresh(DEFAULT_USER)
    for code in ["399998", "930901", "000001"]:
        print(f"\n=== {code} ===")
        print(get_index_recent_main_net_inflow(user, code))
