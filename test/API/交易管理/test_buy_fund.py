import pytest
import os
import sys
import logging
import time

# 获取项目根目录路径
root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# 如果项目根目录不在Python路径中，则添加
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from src.API.交易管理.buyMrg import commit_order
from src.API.交易管理.revokMrg import revoke_order
from src.API.组合管理.SubAccountMrg import getSubAccountNoByName
from src.common.constant import DEFAULT_USER

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)8s] %(message)s (%(filename)s:%(lineno)d)')
logger = logging.getLogger(__name__)

def test_buy_fund_and_revoke():
    """测试基金购买并撤销"""
    # 打印测试开始信息
    logger.info("开始测试基金购买并撤销")
    
    # 测试参数
    name = "低风险组合"
    fund_code = "016531"
    amount = 1000.0
    
    # 获取子账户编号
    logger.info(f"尝试获取名为 '{name}' 的子账户编号")
    sub_account_no = getSubAccountNoByName(DEFAULT_USER, name)
    
    # 验证是否成功获取子账户编号
    if not sub_account_no:
        logger.error(f"未找到名为 '{name}' 的子账户")
        pytest.fail(f"未找到名为 '{name}' 的子账户")
    
    logger.info(f"成功获取子账户编号: {sub_account_no}")
    
    # 调用购买函数
    logger.info(f"调用基金购买函数: fund_code={fund_code}, amount={amount}")
    result = commit_order(DEFAULT_USER, sub_account_no, fund_code, amount)
    time.sleep(5)
    # 验证购买结果
    assert result is not None, "购买结果不应为None"
    logger.info(f"基金购买结果: {result}")
    
    # 如果购买成功，等待20秒后撤销
    if result and result.busin_serial_no:
        logger.info(f"购买成功，交易ID: {result.busin_serial_no}")
        logger.info("等待5秒后撤销交易...")
        time.sleep(5)
        
        # 调用撤销函数
        revoke_result = revoke_order(
            DEFAULT_USER,
            result.busin_serial_no,
            result.business_type,
            fund_code,
            result.amount
        )
        
        # 验证撤销结果
        assert revoke_result is not None, "撤销结果不应为None"
        logger.info(f"撤销结果: {revoke_result}")
        
        if revoke_result.get("Success", False):
            logger.info("撤销成功")
        else:
            logger.warning(f"撤销失败: {revoke_result.get('Message', '未知错误')}")
    else:
        logger.warning("购买失败或未返回交易ID，无法撤销")
    
    logger.info("测试完成")

