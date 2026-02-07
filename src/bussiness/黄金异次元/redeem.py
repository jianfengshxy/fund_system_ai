from src.domain.user.User import User
from src.service.黄金异次元算法.黄金异次元止盈 import redeem_gold_dimension_funds
import logging
from src.common.logger import get_logger

logger = get_logger(__name__)

def redeem(user: User, sub_account_name: str) -> bool:
    """
    黄金异次元组合止盈业务入口
    """
    logger.info(f"调用黄金异次元组合止盈业务，用户: {user.customer_name}, 组合: {sub_account_name}")
    return redeem_gold_dimension_funds(user, sub_account_name)
