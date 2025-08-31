import logging
from typing import Optional

from src.common.constant import DEFAULT_USER
from src.API.工具.utils import get_fund_system_time_trade


def is_trading_time(user: Optional[object] = None) -> bool:
    """
    判断当前是否处于交易时间。

    - 直接调用 src/API/工具/utils.py 中的 get_fund_system_time_trade
    - 返回其中 Data['IsTrade'] 的布尔值（失败或缺失字段时返回 False）

    Args:
        user: 用户对象；不传则使用 DEFAULT_USER

    Returns:
        bool: True 表示交易时间，False 表示非交易时间或调用失败
    """
    logger = logging.getLogger("TradeTimeService")
    if user is None:
        user = DEFAULT_USER

    try:
        resp = get_fund_system_time_trade(user)
        if not resp.Success or not isinstance(resp.Data, dict):
            logger.warning(f"FundSystemTimeTrade 调用失败或返回数据异常: Success={resp.Success}, FirstError={resp.FirstError}")
            return False

        is_trade = resp.Data.get("IsTrade", False)
        # 部分接口可能返回字符串/数字，做一次布尔归一化
        return bool(is_trade)
    except Exception as e:
        logger.error(f"is_trading_time 调用异常: {e}")
        return False