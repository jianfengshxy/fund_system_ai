import pytest
import os
import sys
import logging

# 获取项目根目录路径
root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# 如果项目根目录不在Python路径中，则添加
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from src.API.交易管理.revokMrg import revoke_order
from src.serice.交易管理.交易查询 import get_withdrawable_trades
from src.common.constant import DEFAULT_USER

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_revoke_order_success():
    """测试成功撤回交易订单"""
    # 打印测试开始信息
    logger.info("开始测试撤回交易订单")
    
    # 获取可撤单交易列表
    logger.info("获取可撤单交易列表")
    trades = get_withdrawable_trades(DEFAULT_USER)
    
    # 验证是否有可撤单交易
    if not trades:
        logger.warning("没有可撤单的交易，跳过测试")
        pytest.skip("没有可撤单的交易")
    
    # 选择第一笔交易进行撤单测试
    trade = trades[0]
    logger.info(f"准备撤单: ID={trade.busin_serial_no}, 业务类型={trade.business_type}, 基金代码={trade.fund_code}, 金额/份额={trade.amount}")
    
    # 调用撤单接口
    result = revoke_order(
        DEFAULT_USER,
        trade.busin_serial_no,
        trade.business_type,
        trade.fund_code,
        trade.amount
    )
    
    # 打印结果
    logger.info(f"撤单结果: {result}")
    
    # 验证结果
    assert result is not None, "返回结果不应为None"
    assert isinstance(result, dict), "返回结果应为字典类型"
    assert "Success" in result, "返回结果应包含Success字段"
    assert "Message" in result, "返回结果应包含Message字段"
    
    # 如果撤单成功，验证Success字段为True
    if result["Success"]:
        assert result["Success"] is True, "撤单成功时Success字段应为True"
        logger.info("撤单成功")
    else:
        logger.warning(f"撤单失败: {result['Message']}")
    
    logger.info("测试完成")

def test_revoke_order_invalid_params():
    """测试使用无效参数撤回交易订单"""
    # 打印测试开始信息
    logger.info("开始测试使用无效参数撤回交易订单")
    
    # 使用无效参数调用撤单接口
    result = revoke_order(
        DEFAULT_USER,
        "invalid_busin_serial_no",
        "invalid_business_type",
        "invalid_fund_code",
        "0"
    )
    
    # 打印结果
    logger.info(f"撤单结果: {result}")
    
    # 验证结果
    assert result is not None, "返回结果不应为None"
    assert isinstance(result, dict), "返回结果应为字典类型"
    assert "Success" in result, "返回结果应包含Success字段"
    assert "Message" in result, "返回结果应包含Message字段"
    
    # 预期撤单失败
    assert result["Success"] is False, "使用无效参数时撤单应失败"
    logger.info(f"预期的撤单失败: {result['Message']}")
    
    logger.info("测试完成")

if __name__ == "__main__":
    # 直接运行测试
    logger.info("直接运行撤单测试")
    test_revoke_order_success()
    test_revoke_order_invalid_params()