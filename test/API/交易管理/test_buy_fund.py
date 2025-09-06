import sys
import os
import logging
import time

# 添加项目根目录到 sys.path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../'))
sys.path.insert(0, project_root)

from src.common.constant import DEFAULT_USER
from src.service.用户管理.用户信息 import get_user_all_info
from src.service.交易管理.购买基金 import commit_order
from src.API.交易管理.revokMrg import revoke_order
from src.API.组合管理.SubAccountMrg import getSubAccountNoByName

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_buy_fund_and_revoke():
    logger.info("开始测试基金购买并撤销")
    
    # 第一步：获取用户全部信息
    account = "13500819290"
    password = "guojing1985"
    user = get_user_all_info(account, password)
    logger.info(f"获取用户: {user.customer_name if user else '获取失败'}")
    assert user is not None, "获取用户失败"
    
    # 测试参数
    name = "最优止盈"
    fund_code = "016531"
    amount = 1000.0
    
    # 获取子账户编号
    logger.info(f"尝试获取名为 '{name}' 的子账户编号")
    sub_account_no = getSubAccountNoByName(user, name)
    
    if not sub_account_no:
        logger.error(f"未找到名为 '{name}' 的子账户")
        return
    
    logger.info(f"成功获取子账户编号: {sub_account_no}")
    
    # 调用购买函数
    logger.info(f"调用基金购买函数: fund_code={fund_code}, amount={amount}")
    result = commit_order(user, sub_account_no, fund_code, amount)
    time.sleep(5)
    
    # 验证购买结果
    if result is None:
        logger.error("购买结果为None")
        return
    logger.info(f"基金购买结果: {result}")
    
    # 如果购买成功，等待5秒后撤销
    if result and result.busin_serial_no:
        logger.info(f"购买成功，交易ID: {result.busin_serial_no}")
        logger.info("等待5秒后撤销交易...")
        time.sleep(5)
        
        # 调用撤销函数
        revoke_result = revoke_order(
            user,
            result.busin_serial_no,
            result.business_type,
            fund_code,
            result.amount
        )
        
        # 验证撤销结果
        if revoke_result is None:
            logger.error("撤销结果为None")
            return
        logger.info(f"撤销结果: {revoke_result}")
        
        if revoke_result.get("Success", False):
            logger.info("撤销成功")
        else:
            logger.warning(f"撤销失败: {revoke_result.get('Message', '未知错误')}")
    else:
        logger.warning("购买失败或未返回交易ID，无法撤销")
    
    logger.info("测试完成")

if __name__ == "__main__":
    test_buy_fund_and_revoke()

