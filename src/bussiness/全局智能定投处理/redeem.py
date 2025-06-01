import logging
from random import vonmisesvariate
import re
from typing import Optional
import threading
from concurrent.futures import ThreadPoolExecutor
import os
import sys

# 获取项目根目录路径
root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# 如果项目根目录不在Python路径中，则添加
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from src.service.定投管理.定投查询.定投查询 import get_all_fund_plan_details
from src.domain.user.User import User
from src.domain.user.User import User  
from src.domain.fund_plan.fund_plan_detail import FundPlanDetail
from src.API.交易管理.sellMrg import super_transfer
from src.service.基金信息.基金信息 import get_all_fund_info
from src.API.交易管理.trade import get_trades_list
from src.API.交易管理.revokMrg import revoke_order
from src.API.交易管理.buyMrg import commit_order
from src.domain.trade.TradeResult import TradeResult
from src.common.constant import DEFAULT_USER
from src.API.资产管理.getAssetListOfSub import get_asset_list_of_sub
from src.service.资产管理.get_fund_asset_detail import get_fund_asset_detail
import datetime
from datetime import datetime
import math
from src.domain.fund_plan.fund_plan import FundPlan
from src.domain.fund_plan.fund_plan_detail import FundPlanDetail
from src.API.基金信息.FundRank import get_fund_growth_rate
from src.service.交易管理.赎回基金 import sell_0_fee_shares
from src.service.交易管理.赎回基金 import sell_low_fee_shares
from src.API.银行卡信息.CashBag import getCashBagAvailableShareV2

logger = logging.getLogger(__name__)

def default_user_redeem_all_fund_plans():
    """默认用户批量止盈"""
    # 打印测试开始信息
    logger.info("开始执行默认用户批量止盈函数")  
    # 调用函数进行批量止盈
    redeem_all_fund_plans(DEFAULT_USER)
    logger.info(f"{DEFAULT_USER.customer_name}所有定投计划止盈操作已执行")

def redeem_all_fund_plans(user: User):
    fund_plan_details = get_all_fund_plan_details(user)
    
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(redeem, user, plan_detail) 
                  for plan_detail in fund_plan_details]
        
    results = [future.result() for future in futures]
    logger.info(f"{user.customer_name}有{len(results)}个定投计划执行止盈操作.")
    

# 止盈算法实现
def redeem(user: User, plan_detail: FundPlanDetail) -> bool:
    """
    止盈算法实现

    Args:
        user: 用户对象
        plan_detail: 定投计划详情对象
    Returns:
        bool: 止盈操作是否成功
    """
    customer_name=user.customer_name
    # 获取基金信息
    fund_code = plan_detail.rationPlan.fundCode
    fund_info = get_all_fund_info(user, fund_code)
    fund_name = fund_info.fund_name
    if fund_info.can_purchase == False:
        logger.info(f"{fund_name}不可申购/赎回")
        return True
    sub_account_no = plan_detail.rationPlan.subAccountNo
    sub_account_name = plan_detail.rationPlan.subAccountName
    shares = plan_detail.shares or []
    period_type = plan_detail.rationPlan.periodType
    period_value = plan_detail.rationPlan.periodValue
    plan_assets = plan_detail.rationPlan.planAssets
    fund_amount = plan_detail.rationPlan.amount 
    stop_rate = 1.0
    asset_detail = get_fund_asset_detail(user, sub_account_no, fund_code)
    fund_type = fund_info.fund_type
    if asset_detail is not None:
        constant_profit_rate = asset_detail.constant_profit_rate * 100
    else:
        logger.info(f"{fund_name}资产为空，不要计算")
        return False
    on_way_transaction_count = asset_detail.on_way_transaction_count
    times = plan_assets // fund_amount
    volatility = fund_info.volatility * 100
    # 获取当前收益率和估值增长率
    current_profit_rate = constant_profit_rate if constant_profit_rate is not None else 0.0
    estimated_change = fund_info.estimated_change if fund_info.estimated_change is not None else 0.0
    estimated_profit_rate = current_profit_rate + estimated_change
    rank_100 = fund_info.rank_100day
   
    if shares == []:
        return False
    if estimated_profit_rate < 1.0:
        logger.info(f"组合{sub_account_no}的{fund_name}{fund_code}的收益率{estimated_profit_rate}小于1.0.")
        return True
 
    if shares is not None:
        if  fund_info.estimated_change != 0.0:
            stop_rate = min(volatility, 5.0)   
            logger.info(f"组合{sub_account_no}的{fund_name}{fund_code}波动率{volatility},取两者小值stop_rate:{stop_rate}")
        else:
             stop_rate = 5.0
        if times > 15.0:
            logger.info(f"{customer_name}计算止盈点：基金{fund_name}{fund_code}预估收益{estimated_profit_rate},times:{times},实际止盈点:5.0")
            stop_rate = 5.0
        #指数基金排名在90以上的时候，大于1%即止盈
        if fund_type == '000' and estimated_profit_rate > 1.0 and rank_100 > 90 and fund_info.estimated_change != 0.0 > 0.0:
            logger.info(f"{customer_name}的止盈操作开始：指数基金{fund_name}{fund_code}预估收益{estimated_profit_rate},100日排名:{rank_100},实际止盈点:1.0")
            sell_low_fee_shares(user,sub_account_no,fund_code,shares)
            return True
        #股票型基金
        # if fund_type == '001' and estimated_profit_rate > 1.0 and rank_100 > 90 :
        #     pass           
        # #混合型基金
        # if fund_type == '002' and estimated_profit_rate > 1.0 and rank_100 > 90 :
        #     pass
        #     return True       
        if asset_detail.fund_type == 'a' and estimated_profit_rate > 3.0:
            logger.info(f"{customer_name}的止盈操作开始：QDII基金{fund_name}{fund_code}预估收益{estimated_profit_rate},赎回0费率份额,实际止盈点:3.0")
            sell_0_fee_shares(user,sub_account_no,fund_code,shares)
            return True

        if estimated_profit_rate > stop_rate:
            logger.info(f"{customer_name}的止盈操作开始：基金{fund_name}{fund_code}预估收益{estimated_profit_rate},实际止盈点:{stop_rate}")
            sell_low_fee_shares(user,sub_account_no,fund_code,shares)
            return True    
            # 获取活期宝银行卡列表
        bank_cards = getCashBagAvailableShareV2(user)
        if not bank_cards:
            logger.error("获取银行卡信息失败：没有可用的银行卡")
            raise Exception("获取银行卡信息失败：没有可用的银行卡")   
        # 使用第一个银行卡（余额最高的）
        bank_card_info = bank_cards[0]     
        CurrentRealBalance = bank_card_info.CurrentRealBalance
        #检查银行卡余额,小于30万，且收益大于1.0，立即卖出费率为0的份额
        if estimated_profit_rate > 1.0 and CurrentRealBalance < 300000 and fund_type == '000':
            logger.info(f"{customer_name}的止盈操作开始：余额:{CurrentRealBalance},基金{fund_name}{fund_code}(类型:{fund_type})预估收益{estimated_profit_rate},实际止盈点:1.0.")
            sell_0_fee_shares(user,sub_account_no,fund_code,shares)
            return True     

    return True