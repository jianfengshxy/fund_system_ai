import pytest
import os
import sys
import logging
import json

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
    logger.info("getFee keys=%s", sorted(result.keys()))
    logger.info("FundCode=%s", result.get("FundCode"))
    print("getFee keys=", sorted(result.keys()))
    print("FundCode=", result.get("FundCode"))

    redemption_rates = result.get("RedemptionRates")
    fractional_details = result.get("RedemptionFractionalChargeDetailList")
    share_and_rates = result.get("RedeemShareAndRateList")

    logger.info(
        "RedemptionRates type=%s len=%s sample=%s",
        type(redemption_rates).__name__,
        len(redemption_rates) if isinstance(redemption_rates, list) else None,
        json.dumps((redemption_rates or [])[:3], ensure_ascii=False) if isinstance(redemption_rates, list) else str(redemption_rates)[:500],
    )
    print(
        "RedemptionRates",
        {"type": type(redemption_rates).__name__, "len": len(redemption_rates) if isinstance(redemption_rates, list) else None, "value": (redemption_rates or [])[:3] if isinstance(redemption_rates, list) else redemption_rates},
    )
    logger.info(
        "RedemptionFractionalChargeDetailList type=%s len=%s sample=%s",
        type(fractional_details).__name__,
        len(fractional_details) if isinstance(fractional_details, list) else None,
        json.dumps((fractional_details or [])[:3], ensure_ascii=False) if isinstance(fractional_details, list) else str(fractional_details)[:500],
    )
    print(
        "RedemptionFractionalChargeDetailList",
        {"type": type(fractional_details).__name__, "len": len(fractional_details) if isinstance(fractional_details, list) else None, "value": (fractional_details or [])[:3] if isinstance(fractional_details, list) else fractional_details},
    )
    logger.info(
        "RedeemShareAndRateList type=%s len=%s sample=%s",
        type(share_and_rates).__name__,
        len(share_and_rates) if isinstance(share_and_rates, list) else None,
        json.dumps((share_and_rates or [])[:3], ensure_ascii=False) if isinstance(share_and_rates, list) else str(share_and_rates)[:500],
    )
    print(
        "RedeemShareAndRateList",
        {"type": type(share_and_rates).__name__, "len": len(share_and_rates) if isinstance(share_and_rates, list) else None, "value": (share_and_rates or [])[:3] if isinstance(share_and_rates, list) else share_and_rates},
    )

    raw = json.dumps(result, ensure_ascii=False)
    logger.info("getFee raw=%s", raw[:5000])
    print(raw[:5000])
