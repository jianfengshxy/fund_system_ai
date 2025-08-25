import requests
import json
import logging
import sys
import os

# 获取项目根目录路径
root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# 如果项目根目录不在Python路径中，则添加
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from src.domain.trade.TradeResult import TradeResult
from src.domain.user.User import User
from typing import List, Optional
from src.common.constant import DEFAULT_USER, MOBILE_KEY
from src.API.交易管理.trade import get_trades_list
from typing import Optional
from src.API.交易管理.feeMrg import getFee

def get_0_fee_shares(user: User, fund_code: str) -> Optional[float]:
    """
    查询基金的0费率份额
    :param user: 用户对象
    :param fund_code: 基金代码
    :return: 0费率份额，如果不存在则返回None
    """
    result = getFee(user, fund_code)
    if result is None or "RedeemShareAndRateList" not in result:
        return 0.0

    redeem_share_and_rate_list = result["RedeemShareAndRateList"]
    for item in redeem_share_and_rate_list:
        if item["Rate"] == 0.0:
            return item["AvailableVol"]
    return 0.0

def get_low_fee_shares(user: User, fund_code: str) -> Optional[float]:
    """
    查询基金的低费率份额
    :param user: 用户对象
    :param fund_code: 基金代码
    :return: 低费率份额，item["Rate"] != 1.5只和就是低费率份额
    """
    result = getFee(user, fund_code)
    if result is None or "RedeemShareAndRateList" not in result:
        return 0.0
    redeem_share_and_rate_list = result["RedeemShareAndRateList"]
    total = 0.0
    for item in redeem_share_and_rate_list:
        if item["Rate"] != 1.5:
            total += item["AvailableVol"]
    return total

def get_usable_non_zero_fee_shares(user: User, fund_code: str) -> Optional[float]:
    """
    查询基金的可用非零费率份额
    :param user: 用户对象
    :param fund_code: 基金代码
    :return: 可用非零费率份额
    """
    result = getFee(user, fund_code)
    if result is None or "RedeemShareAndRateList" not in result:
        return 0.0

    redeem_share_and_rate_list = result["RedeemShareAndRateList"]

    # 计算总份额
    total_shares = sum(item["AvailableVol"] for item in redeem_share_and_rate_list)

    # 获取0费率份额
    zero_fee_shares = get_0_fee_shares(user, fund_code)

    # 计算非零费率份额
    non_zero_fee_shares = total_shares - zero_fee_shares

    # 获取低费率份额
    low_fee_shares = get_low_fee_shares(user, fund_code)

    # 返回最小值
    return min(non_zero_fee_shares, zero_fee_shares)
  