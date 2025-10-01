import logging
import sys
import os
from typing import Optional

# 获取项目根目录路径
root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
# 如果项目根目录不在Python路径中，则添加
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from src.domain.user.User import User
from src.service.见龙在田算法.见龙在田新增 import add_new_funds as service_add_new_funds

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def add_new_funds(
    user: User,
    sub_account_name: str,
    total_budget: float,
    amount: Optional[float] = None,
    fund_type: str = 'non_index',
    fund_num: int = 1,
    spread_days: int = 5,
    selector_days: int = 50,
    selector_min_appear: int = 15,
    selector_weak_ratio: float = 0.75,
    selector_max_rank_100day: int = 20,
    selector_fallback_all_if_insufficient: bool = True
) -> bool:
    """
    见龙在田：业务层新增基金薄封装
    - 透传参数到服务层实现（src/service/见龙在田算法/见龙在田新增.py）
    """
    logger.info(f"[见龙在田·业务] 用户 {user.customer_name} 新增基金，组合：{sub_account_name}，预算：{total_budget}，类型：{fund_type}，fund_num={fund_num}，spread_days={spread_days}")
    success = service_add_new_funds(
        user,
        sub_account_name,
        total_budget,
        amount,
        fund_type,
        fund_num,
        spread_days,
        selector_days,
        selector_min_appear,
        selector_weak_ratio,
        selector_max_rank_100day,
        selector_fallback_all_if_insufficient
    )
    if success:
        logger.info(f"[见龙在田·业务] 用户 {user.customer_name} 新增基金成功")
    else:
        logger.error(f"[见龙在田·业务] 用户 {user.customer_name} 新增基金失败")
    return success