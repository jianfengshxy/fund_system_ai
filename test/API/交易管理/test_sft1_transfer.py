import pytest
import os
import sys
import logging

# 获取项目根目录路径
root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# 如果项目根目录不在Python路径中，则添加
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from src.API.交易管理.trade import get_bank_shares
from src.API.交易管理.sellMrg import SFT1Transfer
from src.API.组合管理.SubAccountMrg import getSubAccountNoByName
from src.common.constant import DEFAULT_USER

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)8s] %(message)s (%(filename)s:%(lineno)d)')
logger = logging.getLogger(__name__)

def test_sft1_transfer():
    """测试SFT1转换L2"""
    # 打印测试开始信息
    logger.info("开始测试SFT1转换L2")
    
    # 测试参数
    name = "海外基金组合"
    fund_code = "019449"
    
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
    
    # 设置转换份额（这里设置为可用份额的10%，避免全部转出）
    transfer_amount = round(share.availableVol * 0.1, 2)

    if transfer_amount <= 0:
        logger.error(f"计算的转换份额为 {transfer_amount}，不能小于等于0")
        pytest.fail(f"计算的转换份额为 {transfer_amount}，不能小于等于0")
    
    logger.info(f"准备转换份额: {transfer_amount}")
    
    # 测试用的secu_id参数（根据接口信息设置）
    secu_id = "test_secu_id_123"
    
    # 调用SFT1转换L2函数
    logger.info(f"调用SFT1转换L2函数: fund_code={fund_code}, share_id={share.shareId}, amount={transfer_amount}, secu_id={secu_id}")
    result = SFT1Transfer(DEFAULT_USER, sub_account_no, fund_code, transfer_amount, share.shareId)
    
    # 验证转换结果
    assert result is not None, "转换结果不应为None"
    logger.info(f"SFT1转换L2结果: {result}")
    
    # 验证结果的基本属性
    if result:
        logger.info(f"转换成功，交易ID: {result.busin_serial_no}")
        logger.info(f"业务类型: {result.business_type}")
        logger.info(f"申请金额: {result.amount}")
        logger.info(f"状态: {result.status}")
        logger.info(f"基金代码: {result.fund_code}")
    else:
        logger.warning("SFT1转换L2失败")
    
    logger.info("测试完成")

if __name__ == "__main__":
    # 直接运行测试
    logger.info("直接运行SFT1转换L2测试")
    test_sft1_transfer()