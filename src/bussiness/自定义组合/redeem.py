import logging
import os
import sys
from typing import Optional, List

# 路径注入
root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from src.domain.user.User import User

logging.basicConfig(
    stream=sys.stdout,
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def redeem(user: User, sub_account_name: str, fund_list: Optional[List[dict]] = None) -> bool:
    """
    业务层止盈薄封装：委托到服务层自定义组合止盈算法。
    - fund_list: 止盈目标列表（若不传，服务层可自行检索持仓）
    """
    if fund_list is not None and not isinstance(fund_list, list):
        logger.info("[自定义组合·业务] fund_list 格式不正确，跳过止盈")
        return False
    logger.info(f"[自定义组合·业务] 止盈：用户={getattr(user, 'customer_name', 'unknown')}, 组合={sub_account_name}, 基金数={len(fund_list) if fund_list else 0}")
    try:
        from src.service.自定义组合算法.自定义组合止盈 import redeem_funds as service_redeem_funds
        return service_redeem_funds(user, sub_account_name, fund_list)
    except Exception as e:
        logger.error(f"[自定义组合·业务] 止盈委托失败: {e}")
        return False