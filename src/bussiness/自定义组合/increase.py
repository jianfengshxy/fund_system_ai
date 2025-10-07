import logging
import os
import sys
from typing import Optional, List

# 路径注入，与其他业务层保持一致
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


def increase(user: User, sub_account_name: str, fund_list: Optional[List[dict]] = None) -> bool:
    """
    业务层加仓薄封装：委托到服务层自定义组合加仓算法。
    - fund_list: 形如 [{"fund_code": "xxxxxx", "amount": 2000.0}, ...]
    """
    if not fund_list or not isinstance(fund_list, list):
        logger.info("[自定义组合·业务] 未提供 fund_list 或格式不正确，跳过加仓")
        return False
    logger.info(f"[自定义组合·业务] 加仓：用户={getattr(user, 'customer_name', 'unknown')}, 组合={sub_account_name}, 基金数={len(fund_list)}")
    try:
        from src.service.自定义组合算法.自定义组合加仓 import increase_funds as service_increase_funds
        return service_increase_funds(user, sub_account_name, fund_list)
    except Exception as e:
        logger.error(f"[自定义组合·业务] 加仓委托失败: {e}")
        return False