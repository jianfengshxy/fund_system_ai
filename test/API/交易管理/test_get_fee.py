import pytest
import os
import sys
import logging

# 获取项目根目录路径
root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# 如果项目根目录不在Python路径中，则添加
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from src.API.交易管理.feeMrg import getFee
from src.API.交易管理.trade import get_bank_shares
from src.domain.user.User import User   
from src.API.组合管理.SubAccountMrg import getSubAccountNoByName
from src.common.constant import DEFAULT_USER

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_get_fee_success():
    """测试成功获取费率信息"""
    # 打印测试开始信息
    logger.info("测试成功获取费率信息")    
    # 测试参数
    fund_code = "016531"
    result = getFee(DEFAULT_USER,fund_code)
    assert result is not None
    assert isinstance(result, dict), "返回结果应为字典类型"
    assert "FundCode" in result, "返回结果应包含FundCode字段"
    assert result["FundCode"] == "016531"
    logger.info(f"费率信息: {result['RedemptionRates']}")
    logger.info(f"分段费率详情: {result['RedemptionFractionalChargeDetailList']}") 
    logger.info(f"分段费率份额: {result['RedeemShareAndRateList']}")   
