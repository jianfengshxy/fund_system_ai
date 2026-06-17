from typing import Optional, List, Dict

from src.domain.user.User import User
from src.service.黄金多利组合算法.黄金多利加仓 import increase_gold_funds
from src.common.logger import get_logger

logger = get_logger(__name__)

def increase(
    user: User,
    sub_account_name: str,
    amount: float = 2000.0,
    fund_list: Optional[List[Dict]] = None,
    total_limit: Optional[float] = None,
) -> bool:
    """
    黄金多利组合加仓业务入口
    """
    logger.info(f"调用黄金多利组合加仓业务，用户: {user.customer_name}, 组合: {sub_account_name}")
    return increase_gold_funds(
        user,
        sub_account_name,
        amount,
        fund_list=fund_list,
        total_limit=total_limit,
    )
