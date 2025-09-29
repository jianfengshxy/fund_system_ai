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

from src.API.交易管理.trade import get_bank_shares
from src.API.交易管理.sellMrg import hqbMakeRedemption
from src.API.交易管理.revokMrg import revoke_order
from src.API.组合管理.SubAccountMrg import getSubAccountNoByName
from src.common.constant import DEFAULT_USER

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)8s] %(message)s (%(filename)s:%(lineno)d)')
logger = logging.getLogger(__name__)

def test_hqb_make_redemption_and_revoke():
    """测试货币基金赎回并撤销"""
    # 打印测试开始信息
    logger.info("开始测试货币基金赎回并撤销")
    
    # 测试参数
    name = "飞龙在天"
    fund_code = "016531"
    
    # 获取子账户编号
    logger.info(f"尝试获取名为 '{name}' 的子账户编号")
    sub_account_no = getSubAccountNoByName(DEFAULT_USER, name)
    
    # 验证是否成功获取子账户编号
    if not sub_account_no:
        logger.error(f"未找到名为 '{name}' 的子账户")
        pytest.fail(f"未找到名为 '{name}' 的子账户")
    
    logger.info(f"成功获取子账户编号: {sub_account_no}")
    
    # 调用函数获取银行份额信息
    logger.info(f"尝试获取基金代码 '{fund_code}' 的银行份额信息")
    bank_shares = get_bank_shares(DEFAULT_USER, sub_account_no, fund_code)
    
    # 验证是否获取到银行份额信息
    if not bank_shares or len(bank_shares) == 0:
        logger.error(f"未找到基金代码为 '{fund_code}' 的银行份额记录")
        pytest.fail(f"未找到基金代码为 '{fund_code}' 的银行份额记录")
    
    # 获取第一条银行份额记录
    share = bank_shares[0]
    logger.info(f"获取到银行份额记录: shareId={share.shareId}, 可用份额={share.availableVol}")
    
    # 设置赎回份额（这里设置为可用份额的10%，避免全部赎回）
    redemption_amount = round(share.availableVol * 0.1, 2)
    if redemption_amount <= 0:
        logger.error(f"计算的赎回份额为 {redemption_amount}，不能小于等于0")
        pytest.fail(f"计算的赎回份额为 {redemption_amount}，不能小于等于0")
    
    logger.info(f"准备赎回份额: {redemption_amount}")
    
    # 调用货币基金赎回函数
    logger.info(f"调用货币基金赎回函数: fund_code={fund_code}, share_id={share.shareId}, amount={redemption_amount}")
    result = hqbMakeRedemption(DEFAULT_USER, sub_account_no, fund_code, redemption_amount, share.shareId)
    
    # 验证赎回结果
    assert result is not None, "赎回结果不应为None"
    logger.info(f"货币基金赎回结果: {result}")
    
    # 如果赎回成功，等待20秒后撤销
    if result and result.busin_serial_no:
        logger.info(f"赎回成功，交易ID: {result.busin_serial_no}")
        logger.info("等待20秒后撤销交易...")
        time.sleep(20)
        
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
        logger.warning("赎回失败或未返回交易ID，无法撤销")
    
    logger.info("测试完成")

if __name__ == "__main__":
    # 直接运行测试
    logger.info("直接运行货币基金赎回测试")
    test_hqb_make_redemption_and_revoke()