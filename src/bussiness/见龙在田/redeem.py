# 顶部导入与路径注入（参考 increase.py 的风格）
import logging
import os
import sys
from typing import Optional
# 获取项目根目录路径并注入 sys.path（与其他业务层保持一致）
root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from src.domain.user.User import User

# 日志配置保持与 increase.py 一致（输出到 stdout）
logging.basicConfig(
    stream=sys.stdout,
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def redeem(user: User, sub_account_name: str, total_budget: Optional[float] = None, profit_threshold: Optional[float] = 20.0) -> bool:
    """
    业务薄封装：止盈
    - 统一参数处理（含 total_budget 的缺省处理）
    - 委托 service 层算法实现（包含：在加仓风向标中则跳过止盈）
    - profit_threshold：止盈收益率阈值，默认 20（可从上层传入）
    """
    # 预算兜底：未传入则取 user.budget；仍为空则默认 100000.0
    if total_budget is None:
        try:
            total_budget = float(getattr(user, 'budget', 0.0)) if getattr(user, 'budget', None) is not None else 0.0
        except Exception:
            total_budget = 0.0
        if not total_budget or total_budget <= 0:
            total_budget = 100000.0

    logger.info(f"[见龙在田] 业务层止盈调用：用户={getattr(user, 'customer_name', 'unknown')}, 组合={sub_account_name}, 预算={total_budget}, 止盈阈值={profit_threshold}%")
    try:
        # 委托到 service 层的见龙在田止盈算法（已包含“在加仓风向标中则跳过止盈”的逻辑）
        from src.service.见龙在田算法.见龙在田止盈 import redeem_funds as jianlong_redeem_funds
        success = jianlong_redeem_funds(user, sub_account_name, total_budget, profit_threshold)
        if success:
            logger.info(f"[见龙在田] 用户 {user.customer_name} 止盈操作成功")
        else:
            logger.error(f"[见龙在田] 用户 {user.customer_name} 止盈操作失败")
        return success
    except Exception as e:
        logger.error(f"[见龙在田] 业务层止盈委托失败: {e}")
        return False

if __name__ == "__main__":
    # 测试 total_budget 不传的情况（将走预算兜底）
    try:
        from src.common.constant import DEFAULT_USER
        success = redeem(DEFAULT_USER, "见龙在田")  # total_budget 不传，使用兜底逻辑
        if success:
            logging.info("测试成功（total_budget 未传）")
        else:
            logging.info("测试失败（total_budget 未传）")
    except Exception as e:
        logging.error(f"测试用户处理失败：{str(e)}")