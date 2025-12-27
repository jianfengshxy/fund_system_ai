
from math import log
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

from src.service.基金信息.基金信息 import get_all_fund_info
from src.domain.trade.TradeResult import TradeResult
from src.domain.user.User import User
from typing import List, Optional
from src.common.constant import DEFAULT_USER, MOBILE_KEY
from src.API.交易管理.trade import get_trades_list
from typing import Optional
from src.API.交易管理.feeMrg import getFee
from src.domain.trade.share import Share
from decimal import Decimal, ROUND_HALF_UP
from src.service.交易管理.费率查询 import get_0_fee_shares
from src.service.交易管理.费率查询 import get_low_fee_shares
from src.API.交易管理.sellMrg import super_transfer
from src.API.交易管理.sellMrg import hqbMakeRedemption,SFT1Transfer
from src.domain.trade.share import Share
from decimal import Decimal, ROUND_HALF_UP
from src.service.交易管理.费率查询 import get_usable_non_zero_fee_shares
from src.common.logger import get_logger
from src.common.errors import RetriableError, ValidationError
logger = get_logger(__name__)

# 新增：交易时间判断函数导入
from src.service.公共服务.trade_time_service import is_trading_time

def sell_0_fee_shares(user:User, sub_account_no:str, fund_code:str, shares:List[Share]):
    """
    赎回0费率份额
    :param user: 用户对象
    :param sub_account_no: 子账户号
    :param fund_code: 基金代码
    :param fund_type: 基金类型
    :param fund_name: 基金名称
    """
    # 新增：非交易时间直接跳出
    if not is_trading_time(user):
        logger.info(f"{user.customer_name} 当前非交易时间，跳过赎回0费率份额操作", extra={"account": (getattr(user, 'mobile_phone', None) or getattr(user, 'account', None)), "action": "sell_0_fee", "fund_code": fund_code, "sub_account_no": sub_account_no})
        return None
    
    # 检查是否可赎回
    fund_info = get_all_fund_info(user, fund_code)
    if fund_info and not fund_info.can_redeem:
        logger.info(f"{user.customer_name}基金{fund_code}({fund_info.fund_name})不可赎回，跳过赎回操作", extra={"account": (getattr(user, 'mobile_phone', None) or getattr(user, 'account', None)), "action": "sell_0_fee", "fund_code": fund_code, "sub_account_no": sub_account_no})
        return None

   #遍历shares
    for share in shares:
        fund_info = get_all_fund_info(user,fund_code)
        fund_name = fund_info.fund_name
        zero_fee_shares = get_0_fee_shares(user,fund_code)
        if share.availableVol > zero_fee_shares:
            amount = zero_fee_shares
        else:
            amount = share.availableVol

        # 检查剩余份额是否小于10
        remaining_shares = share.availableVol - amount
        if 0 < remaining_shares < 10:
             # 如果剩余不足10份，则少卖出一点，凑够10份剩余
             amount = share.availableVol - 10.0
             if amount < 0:
                 amount = 0.0


        if amount == 0.0:
            logger.info(f"{user.customer_name}基金{fund_code}({fund_name})的份额为0，跳过赎回操作", extra={"account": (getattr(user, 'mobile_phone', None) or getattr(user, 'account', None)), "action": "sell_0_fee", "fund_code": fund_code, "sub_account_no": sub_account_no})
            return None

        try:
            result1 = super_transfer(user, sub_account_no, fund_code, amount, share.shareId)
        except RetriableError as e:
            logger.warning(f"super_transfer 可重试: {e}", extra={"account": (getattr(user, 'mobile_phone', None) or getattr(user, 'account', None)), "action": "sell_0_fee", "fund_code": fund_code, "sub_account_no": sub_account_no})
            result1 = None
        except ValidationError as e:
            logger.error(f"super_transfer 参数错误: {e}", extra={"account": (getattr(user, 'mobile_phone', None) or getattr(user, 'account', None)), "action": "sell_0_fee", "fund_code": fund_code, "sub_account_no": sub_account_no})
            result1 = None
        if result1 is not None and getattr(result1, "status", 0) == 1:
            logger.info(f"{user.customer_name}超级转换基金{fund_code}({fund_name})的银行卡份额{amount}成功", extra={"account": (getattr(user, 'mobile_phone', None) or getattr(user, 'account', None)), "action": "sell_0_fee", "fund_code": fund_code, "sub_account_no": sub_account_no})
            return result1
        else:
            logger.error(f"{user.customer_name}超级转换基金{fund_code}({fund_name})的银行卡份额{amount}失败切换成普通赎回", extra={"account": (getattr(user, 'mobile_phone', None) or getattr(user, 'account', None)), "action": "sell_0_fee", "fund_code": fund_code, "sub_account_no": sub_account_no})
            try:
                result2 = SFT1Transfer(user, sub_account_no, fund_code, amount, share.shareId)
            except RetriableError as e:
                logger.warning(f"SFT1Transfer 可重试: {e}", extra={"account": (getattr(user, 'mobile_phone', None) or getattr(user, 'account', None)), "action": "sell_0_fee", "fund_code": fund_code, "sub_account_no": sub_account_no})
                result2 = None
            except ValidationError as e:
                logger.error(f"SFT1Transfer 参数错误: {e}", extra={"account": (getattr(user, 'mobile_phone', None) or getattr(user, 'account', None)), "action": "sell_0_fee", "fund_code": fund_code, "sub_account_no": sub_account_no})
                result2 = None
            if result2 is not None and getattr(result2, "status", 0) == 1:
                logger.info(f"{user.customer_name}普通赎回基金{fund_code}({fund_name})的银行卡份额成功", extra={"account": (getattr(user, 'mobile_phone', None) or getattr(user, 'account', None)), "action": "sell_0_fee", "fund_code": fund_code, "sub_account_no": sub_account_no})
                return result2
            else:
                logger.error(f"{user.customer_name}普通赎回基金{fund_code}({fund_name})的银行卡份额失败", extra={"account": (getattr(user, 'mobile_phone', None) or getattr(user, 'account', None)), "action": "sell_0_fee", "fund_code": fund_code, "sub_account_no": sub_account_no})
                return None

def sell_low_fee_shares(user:User, sub_account_no:str, fund_code:str, shares:List[Share]):
    """
    赎回低费率份额
    :param user: 用户对象
    :param sub_account_no: 子账户号
    :param fund_code: 基金代码
    :param fund_type: 基金类型
    :param fund_name: 基金名称
    """
    # 新增：非交易时间直接跳出
    if not is_trading_time(user):
        logger.info(f"{user.customer_name} 当前非交易时间，跳过赎回低费率份额操作", extra={"account": (getattr(user, 'mobile_phone', None) or getattr(user, 'account', None)), "action": "sell_low_fee", "fund_code": fund_code, "sub_account_no": sub_account_no})
        return None
    
    # 检查是否可赎回
    fund_info = get_all_fund_info(user, fund_code)
    if fund_info and not fund_info.can_redeem:
        logger.info(f"{user.customer_name}基金{fund_code}({fund_info.fund_name})不可赎回，跳过赎回操作", extra={"account": (getattr(user, 'mobile_phone', None) or getattr(user, 'account', None)), "action": "sell_low_fee", "fund_code": fund_code, "sub_account_no": sub_account_no})
        return None

   #遍历shares
    for share in shares:        
        low_fee_shares = round(float(get_low_fee_shares(user,fund_code)), 2)
        fund_info = get_all_fund_info(user,fund_code)
        fund_name = fund_info.fund_name
        amount = share.availableVol 
        logger.info(f"{user.customer_name}的基金{fund_code}({fund_name})低费率份额的{low_fee_shares}，当前账户有效份额{share.availableVol}", extra={"account": (getattr(user, 'mobile_phone', None) or getattr(user, 'account', None)), "action": "sell_low_fee", "fund_code": fund_code, "sub_account_no": sub_account_no})
        if share.availableVol > low_fee_shares:
            amount = low_fee_shares
        else:
            amount = share.availableVol 

        # 检查剩余份额是否小于10
        remaining_shares = share.availableVol - amount
        if 0 < remaining_shares < 10:
             # 如果剩余不足10份，则少卖出一点，凑够10份剩余
             amount = share.availableVol - 10.0
             if amount < 0:
                 amount = 0.0
 

        # 检查份额是否为0
        if amount == 0.0:
            logger.info(f"{user.customer_name}基金{fund_code}({fund_name})的份额为0，跳过赎回操作", extra={"account": (getattr(user, 'mobile_phone', None) or getattr(user, 'account', None)), "action": "sell_low_fee", "fund_code": fund_code, "sub_account_no": sub_account_no})
            return None

        try:
            result1 = super_transfer(user, sub_account_no, fund_code, amount, share.shareId)
        except RetriableError as e:
            logger.warning(f"super_transfer 可重试: {e}", extra={"account": (getattr(user, 'mobile_phone', None) or getattr(user, 'account', None)), "action": "sell_low_fee", "fund_code": fund_code, "sub_account_no": sub_account_no})
            result1 = None
        except ValidationError as e:
            logger.error(f"super_transfer 参数错误: {e}", extra={"account": (getattr(user, 'mobile_phone', None) or getattr(user, 'account', None)), "action": "sell_low_fee", "fund_code": fund_code, "sub_account_no": sub_account_no})
            result1 = None
        if result1 is not None and getattr(result1, "status", 0) == 1:
            logger.info(f"{user.customer_name}超级转换基金{fund_code}({fund_name})的银行卡份额{amount}成功", extra={"account": (getattr(user, 'mobile_phone', None) or getattr(user, 'account', None)), "action": "sell_low_fee", "fund_code": fund_code, "sub_account_no": sub_account_no})
            return result1
        else:
            logger.error(f"{user.customer_name}超级转换基金{fund_code}({fund_name})的银行卡份额{amount}失败切换成普通赎回", extra={"account": (getattr(user, 'mobile_phone', None) or getattr(user, 'account', None)), "action": "sell_low_fee", "fund_code": fund_code, "sub_account_no": sub_account_no})
            try:
                result2 = SFT1Transfer(user, sub_account_no, fund_code, amount, share.shareId)
            except RetriableError as e:
                logger.warning(f"SFT1Transfer 可重试: {e}", extra={"account": (getattr(user, 'mobile_phone', None) or getattr(user, 'account', None)), "action": "sell_low_fee", "fund_code": fund_code, "sub_account_no": sub_account_no})
                result2 = None
            except ValidationError as e:
                logger.error(f"SFT1Transfer 参数错误: {e}", extra={"account": (getattr(user, 'mobile_phone', None) or getattr(user, 'account', None)), "action": "sell_low_fee", "fund_code": fund_code, "sub_account_no": sub_account_no})
                result2 = None
            if result2 is not None and getattr(result2, "status", 0) == 1:
                logger.info(f"{user.customer_name}普通赎回基金{fund_code}({fund_name})的银行卡份额成功", extra={"account": (getattr(user, 'mobile_phone', None) or getattr(user, 'account', None)), "action": "sell_low_fee", "fund_code": fund_code, "sub_account_no": sub_account_no})
                return result2
            else:
                logger.error(f"{user.customer_name}普通赎回基金{fund_code}({fund_name})的银行卡份额失败", extra={"account": (getattr(user, 'mobile_phone', None) or getattr(user, 'account', None)), "action": "sell_low_fee", "fund_code": fund_code, "sub_account_no": sub_account_no})
                try:
                    result3 = hqbMakeRedemption(user, sub_account_no, fund_code, amount, share.shareId)
                except RetriableError as e:
                    logger.warning(f"hqbMakeRedemption 可重试: {e}", extra={"account": (getattr(user, 'mobile_phone', None) or getattr(user, 'account', None)), "action": "sell_low_fee", "fund_code": fund_code, "sub_account_no": sub_account_no})
                    result3 = None
                except ValidationError as e:
                    logger.error(f"hqbMakeRedemption 参数错误: {e}", extra={"account": (getattr(user, 'mobile_phone', None) or getattr(user, 'account', None)), "action": "sell_low_fee", "fund_code": fund_code, "sub_account_no": sub_account_no})
                    result3 = None
                if result3 is not None and getattr(result3, "status", 0) == 1:
                    logger.info(f"{user.customer_name}普通赎回银行{fund_code}({fund_name})的银行卡份额成功", extra={"account": (getattr(user, 'mobile_phone', None) or getattr(user, 'account', None)), "action": "sell_low_fee", "fund_code": fund_code, "sub_account_no": sub_account_no})
                    return result3
                else:
                    logger.error(f"{user.customer_name}普通赎回银行{fund_code}({fund_name})的银行卡份额失败", extra={"account": (getattr(user, 'mobile_phone', None) or getattr(user, 'account', None)), "action": "sell_low_fee", "fund_code": fund_code, "sub_account_no": sub_account_no})
                    return None

def sell_usable_non_zero_fee_shares(user: User, sub_account_no: str, fund_code: str, shares: List[Share]):
    """
    赎回可用非零费率份额
    :param user: 用户对象
    :param sub_account_no: 子账户号
    :param fund_code: 基金代码
    :param shares: 份额列表
    """
    # 新增：非交易时间直接跳出
    if not is_trading_time(user):
        logger.info(f"{user.customer_name} 当前非交易时间，跳过赎回可用非零费率份额操作", extra={"account": (getattr(user, 'mobile_phone', None) or getattr(user, 'account', None)), "action": "sell_non_zero_fee", "fund_code": fund_code, "sub_account_no": sub_account_no})
        return None
    
    # 检查是否可赎回
    fund_info = get_all_fund_info(user, fund_code)
    if fund_info and not fund_info.can_redeem:
        logger.info(f"{user.customer_name}基金{fund_code}({fund_info.fund_name})不可赎回，跳过赎回操作", extra={"account": (getattr(user, 'mobile_phone', None) or getattr(user, 'account', None)), "action": "sell_non_zero_fee", "fund_code": fund_code, "sub_account_no": sub_account_no})
        return None

    for share in shares:
        fund_info = get_all_fund_info(user,fund_code)
        fund_name = fund_info.fund_name
        usable_shares = get_usable_non_zero_fee_shares(user, fund_code)
        amount = min(share.availableVol, usable_shares)

        # 检查份额是否为0
        if amount == 0.0:
            logger.info(f"{user.customer_name}基金{fund_code}({fund_name})的份额为0，跳过赎回操作", extra={"account": (getattr(user, 'mobile_phone', None) or getattr(user, 'account', None)), "action": "sell_non_zero_fee", "fund_code": fund_code, "sub_account_no": sub_account_no})
            return None

        try:
            result1 = super_transfer(user, sub_account_no, fund_code, amount, share.shareId)
        except RetriableError as e:
            logger.warning(f"super_transfer 可重试: {e}", extra={"account": (getattr(user, 'mobile_phone', None) or getattr(user, 'account', None)), "action": "sell_non_zero_fee", "fund_code": fund_code, "sub_account_no": sub_account_no})
            result1 = None
        except ValidationError as e:
            logger.error(f"super_transfer 参数错误: {e}", extra={"account": (getattr(user, 'mobile_phone', None) or getattr(user, 'account', None)), "action": "sell_non_zero_fee", "fund_code": fund_code, "sub_account_no": sub_account_no})
            result1 = None
        if result1 is not None and result1.status == 1:
            logger.info(f"{user.customer_name}超级转换基金{fund_code}({fund_name})的银行卡份额{amount}成功", extra={"account": (getattr(user, 'mobile_phone', None) or getattr(user, 'account', None)), "action": "sell_non_zero_fee", "fund_code": fund_code, "sub_account_no": sub_account_no})
            return result1
        else:
            logger.error(f"{user.customer_name}超级转换基金{fund_code}({fund_name})的银行卡份额{amount}失败切换成普通赎回", extra={"account": (getattr(user, 'mobile_phone', None) or getattr(user, 'account', None)), "action": "sell_non_zero_fee", "fund_code": fund_code, "sub_account_no": sub_account_no})
            try:
                result2 = SFT1Transfer(user, sub_account_no, fund_code, amount, share.shareId)
            except RetriableError as e:
                logger.warning(f"SFT1Transfer 可重试: {e}", extra={"account": (getattr(user, 'mobile_phone', None) or getattr(user, 'account', None)), "action": "sell_non_zero_fee", "fund_code": fund_code, "sub_account_no": sub_account_no})
                result2 = None
            except ValidationError as e:
                logger.error(f"SFT1Transfer 参数错误: {e}", extra={"account": (getattr(user, 'mobile_phone', None) or getattr(user, 'account', None)), "action": "sell_non_zero_fee", "fund_code": fund_code, "sub_account_no": sub_account_no})
                result2 = None
            if result2 is not None and result2.status == 1:
                logger.info(f"{user.customer_name}普通赎回基金{fund_code}({fund_name})的银行卡份额成功", extra={"account": (getattr(user, 'mobile_phone', None) or getattr(user, 'account', None)), "action": "sell_non_zero_fee", "fund_code": fund_code, "sub_account_no": sub_account_no})
                return result2
            else:
                logger.error(f"{user.customer_name}普通赎回基金{fund_code}({fund_name})的银行卡份额失败", extra={"account": (getattr(user, 'mobile_phone', None) or getattr(user, 'account', None)), "action": "sell_non_zero_fee", "fund_code": fund_code, "sub_account_no": sub_account_no})
                try:
                    result3 = hqbMakeRedemption(user, sub_account_no, fund_code, amount, share.shareId)
                except RetriableError as e:
                    logger.warning(f"hqbMakeRedemption 可重试: {e}", extra={"account": (getattr(user, 'mobile_phone', None) or getattr(user, 'account', None)), "action": "sell_non_zero_fee", "fund_code": fund_code, "sub_account_no": sub_account_no})
                    result3 = None
                    logger.error(f"hqbMakeRedemption 参数错误: {e}", extra={"account": (getattr(user, 'mobile_phone', None) or getattr(user, 'account', None)), "action": "sell_non_zero_fee", "fund_code": fund_code, "sub_account_no": sub_account_no})
                    result3 = None
                if result3 is not None and result3.status == 1:
                    logger.info(f"{user.customer_name}普通赎回银行{fund_code}({fund_name})的银行卡份额成功", extra={"account": (getattr(user, 'mobile_phone', None) or getattr(user, 'account', None)), "action": "sell_non_zero_fee", "fund_code": fund_code, "sub_account_no": sub_account_no})
                    return result3
                else:
                    logger.error(f"{user.customer_name}普通赎回银行{fund_code}({fund_name})的银行卡份额失败", extra={"account": (getattr(user, 'mobile_phone', None) or getattr(user, 'account', None)), "action": "sell_non_zero_fee", "fund_code": fund_code, "sub_account_no": sub_account_no})
                    return result3
