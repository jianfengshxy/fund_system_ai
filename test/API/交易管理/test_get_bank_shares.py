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
from src.API.组合管理.SubAccountMrg import getSubAccountNoByName
from src.common.constant import DEFAULT_USER

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_get_bank_shares_success():
    """测试成功获取银行份额信息"""
    # 打印测试开始信息
    logger.info("开始测试获取银行份额信息")
    
    # 测试参数
    name = "低风险组合"
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
    
    # 打印结果信息
    logger.info(f"获取到 {len(bank_shares)} 条银行份额记录")
    
    # 打印所有银行份额记录的详细信息
    for i, share in enumerate(bank_shares):
        logger.info(f"\n{'='*50}")
        logger.info(f"银行份额记录 {i+1} 详细信息:")
        logger.info(f"{'-'*50}")
        logger.info(f"银行名称: {share.bankName}")
        logger.info(f"银行代码: {share.bankCode}")
        logger.info(f"显示银行代码: {share.showBankCode}")
        logger.info(f"银行卡号: {share.bankCardNo}")
        logger.info(f"份额ID: {share.shareId}")
        logger.info(f"可用份额: {share.availableVol}")
        logger.info(f"银行账户号: {share.bankAccountNo}")
        logger.info(f"总可用量: {share.totalVol}")
        logger.info(f"{'='*50}")
    
    # 验证结果
    assert bank_shares is not None, "返回结果不应为None"
    assert isinstance(bank_shares, list), "返回结果应为列表类型"
    
    # 如果有银行份额记录，验证第一条记录的结构
    if len(bank_shares) > 0:
        share = bank_shares[0]
        assert hasattr(share, 'bankName'), "银行份额记录应有bankName属性"
        assert hasattr(share, 'bankCode'), "银行份额记录应有bankCode属性"
        assert hasattr(share, 'showBankCode'), "银行份额记录应有showBankCode属性"
        assert hasattr(share, 'bankCardNo'), "银行份额记录应有bankCardNo属性"
        assert hasattr(share, 'shareId'), "银行份额记录应有shareId属性"
        assert hasattr(share, 'availableVol'), "银行份额记录应有availableVol属性"
        assert hasattr(share, 'bankAccountNo'), "银行份额记录应有bankAccountNo属性"
        assert hasattr(share, 'totalVol'), "银行份额记录应有totalVol属性"
        
        logger.info("银行份额记录结构验证通过")
    else:
        logger.warning(f"未找到基金代码为 '{fund_code}' 的银行份额记录")
    
    logger.info("测试完成")

