import logging
from src.common.logger import get_logger
import os
import sys
from typing import List

# 获取项目根目录路径
root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# 如果项目根目录不在Python路径中，则添加
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from src.domain.user.User import User
from src.service.交易管理.交易查询 import get_withdrawable_trades
from src.API.交易管理.revokMrg import revoke_order
from src.API.组合管理.SubAccountMrg import getSubAccountNoByName

logger = get_logger(__name__)

def revoke_funds(user: User, sub_account_name: str = "最优止盈") -> bool:
    """
    撤回基金交易算法实现：
    1. 获取组合账号
    2. 查询可撤回交易
    3. 遍历每个可撤回交易并执行撤回
    
    Args:
        user: 用户对象
        sub_account_name: 组合名称，默认为"最优止盈"
    
    Returns:
        bool: 操作是否成功
    """
    customer_name = user.customer_name
    logger.info(f"开始为用户 {customer_name} 执行撤回操作，组合: {sub_account_name}")
    
    # 获取组合账号
    sub_account_no = getSubAccountNoByName(user, sub_account_name)
    if not sub_account_no:
        logger.error(f"未找到组合 {sub_account_name} 的账号")
        return False
    
    # 查询可撤回交易
    trades = get_withdrawable_trades(user, sub_account_no=sub_account_no)
    if not trades:
        logger.info(f"{customer_name} 在组合 {sub_account_name} 中没有可撤回交易")
        return True
    
    logger.info(f"找到 {len(trades)} 个可撤回交易")
    success_count = 0
    
    for trade in trades:
        try:
            result = revoke_order(
                user,
                trade.busin_serial_no,
                trade.business_type,
                trade.fund_code,
                trade.amount,
                sub_account_no=sub_account_no
            )
            if result and result.get('Success', False):
                logger.info(f"成功撤回交易: {trade.busin_serial_no} (基金: {trade.fund_code})")
                success_count += 1
            else:
                logger.error(f"撤回交易 {trade.busin_serial_no} 失败: {result.get('Message', '未知错误')}")
        except Exception as e:
            logger.error(f"撤回交易 {trade.busin_serial_no} 时发生异常: {e}")
    
    logger.info(f"撤回操作完成: {success_count}/{len(trades)} 个交易成功")
    return success_count == len(trades)


if __name__ == "__main__":
    # 测试代码，例如使用 DEFAULT_USER
    from src.common.constant import DEFAULT_USER
    revoke_funds(DEFAULT_USER, '飞龙在天')
