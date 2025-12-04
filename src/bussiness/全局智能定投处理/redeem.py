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
from src.API.交易管理.trade import get_trades_list, get_bank_shares
from src.API.交易管理.revokMrg import revoke_order
from src.service.交易管理.购买基金 import commit_order
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
from src.service.交易管理.赎回基金 import sell_usable_non_zero_fee_shares
from src.API.银行卡信息.CashBag import getCashBagAvailableShareV2
from src.service.大数据.加仓风向标服务 import get_fund_investment_indicators
from src.API.资产管理.AssetManager import GetMyAssetMainPartAsync
from src.service.公共服务.nav_gate_service import nav5_gate

logging.basicConfig(
    stream=sys.stdout,
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
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
    logger.info(f"开始执行止盈算法，用户：{customer_name}")
    
    # 获取基金信息
    fund_code = plan_detail.rationPlan.fundCode
    fund_info = get_all_fund_info(user, fund_code)
    fund_name = fund_info.fund_name
    logger.info(f"基金信息：{fund_name}({fund_code})，可申购：{fund_info.can_purchase}")
    
    if fund_info.can_purchase == False:
        logger.info(f"{fund_name}不可申购/赎回")
        return True
    sub_account_no = plan_detail.rationPlan.subAccountNo
    sub_account_name = plan_detail.rationPlan.subAccountName
    
    # 获取银行份额信息，添加异常处理
    try:
        shares = get_bank_shares(user, sub_account_no, fund_code)
    except Exception as e:
        logger.warning(f"获取银行份额信息失败，将使用空份额列表继续处理: {e}")
        shares = []  # 使用空列表继续处理，而不是失败
    
    period_type = plan_detail.rationPlan.periodType
    period_value = plan_detail.rationPlan.periodValue
    
    fund_amount = plan_detail.rationPlan.amount 
    stop_rate = 1.0
    
    try:
        asset_detail = get_fund_asset_detail(user, sub_account_no, fund_code)
        
        if asset_detail is not None:
            plan_assets = asset_detail.asset_value
            fund_type = fund_info.fund_type
            constant_profit_rate = asset_detail.constant_profit_rate  # 移除 * 100
            logger.info(f"{fund_name}资产详情获取成功 - 资产价值: {asset_detail.asset_value}, 收益率: {constant_profit_rate}%, 估值增长率: {fund_info.estimated_change}%, 在途交易数: {asset_detail.on_way_transaction_count}")
        else:
            logger.info(f"组合{sub_account_no}的{fund_name}{fund_code}资产为空。Skip ..........")
            return True
    except Exception as e:
        logger.error(f"获取资产详情失败: {e}")
        return False
        
    on_way_transaction_count = asset_detail.on_way_transaction_count
    times = plan_assets // fund_amount
    volatility = fund_info.volatility 
    
    # 获取当前收益率和估值增长率
    current_profit_rate = constant_profit_rate if constant_profit_rate is not None else 0.0
    estimated_change = fund_info.estimated_change if fund_info.estimated_change is not None else 0.0
    estimated_profit_rate = current_profit_rate + estimated_change
    rank_100 = fund_info.rank_100day
    
    logger.info(f"收益率计算：当前收益率{current_profit_rate}%，估值变化{estimated_change}%，预估收益率{estimated_profit_rate}%")
    logger.info(f"其他指标：波动率{volatility}%，100日排名{rank_100}，投资次数{times}")
   
    if shares == []:
        logger.info("份额为空，返回False")
        return False
        
    if estimated_profit_rate < 1.0:
        logger.info(f"组合{sub_account_no}的{fund_name}{fund_code}的收益率{estimated_profit_rate}小于1.0.")
        return True
 
    if shares is not None:
        logger.info("开始检查止盈条件...")
        
        # 趋势门槛：只有净值低于5日均值时才允许止盈
        est_nav = getattr(fund_info, 'estimated_value', None)
        prev_nav = getattr(fund_info, 'nav', None)
        nav5 = getattr(fund_info, 'nav_5day_avg', None)
        try:
            est_val = float(est_nav) if est_nav is not None else (float(prev_nav) if prev_nav is not None else None)
            nav5_val = float(nav5) if nav5 is not None else None
        except Exception:
            est_val = None
            nav5_val = None

        if est_val is None or nav5_val is None:
            logger.info(f"止盈趋势门槛检查：缺少用于对比的净值（estimated_value={est_nav}, prev_nav={prev_nav}, nav_5day_avg={nav5}），跳过止盈")
            return True

        # 更新：止盈点 = 波动率，但不低于 3.0（移除此前的 5% 上限与估值分支）
        stop_rate = max(float(volatility), 3.0)
        logger.info(f"组合{sub_account_no}的{fund_name}{fund_code}波动率={volatility:.2f}，设置止盈点={stop_rate:.2f}（不低于3.0）")
 
        if asset_detail.fund_type == 'a' and estimated_profit_rate > 3.0:
            logger.info(f"{customer_name}的止盈操作开始：QDII基金{fund_name}{fund_code}预估收益{estimated_profit_rate},赎回0费率份额,实际止盈点:3.0")
            sell_0_fee_shares(user,sub_account_no,fund_code,shares)

        if estimated_profit_rate > stop_rate:
            logger.info(f"{customer_name}的止盈操作开始：基金{fund_name}{fund_code}预估收益{estimated_profit_rate},实际止盈点:{stop_rate}")
            sell_low_fee_shares(user,sub_account_no,fund_code,shares)
            return True
        else:
            logger.info(f"基本止盈条件检查：预估收益{estimated_profit_rate} <= 止盈点{stop_rate}，不满足条件")
            
        # 获取活期宝银行卡列表
        logger.info("开始检查银行卡余额相关条件...")
        try:
            asset_response = GetMyAssetMainPartAsync(user)
            if asset_response.Success and asset_response.Data:
                CurrentRealBalance = asset_response.Data.get('HqbValue', 0.0)
                logger.info(f"从资产API获取HqbValue: {CurrentRealBalance}")
            else:
                raise Exception("资产API调用失败")
        except Exception as e:
            logger.warning(f"获取HqbValue失败，回退到原银行卡信息: {str(e)}")
            bank_card_info = user.max_hqb_bank    
            CurrentRealBalance = bank_card_info.CurrentRealBalance
            logger.info(f"银行卡余额：{CurrentRealBalance}")
        
        #检查银行卡余额,小于30万，且收益大于1.0，立即卖出费率为0的份额
        if estimated_profit_rate > 1.0 and CurrentRealBalance < BANK_BALANCE_THRESHOLD and fund_type == '000' and "QDII" not in fund_name:
            logger.info(f"{customer_name}的止盈操作开始：余额:{CurrentRealBalance},基金{fund_name}{fund_code}(类型:{fund_type})预估收益{estimated_profit_rate},实际止盈点:1.0.")
            sell_usable_non_zero_fee_shares(user,sub_account_no,fund_code,shares)
            return True
        else:
            logger.info(f"指数基金余额条件检查：预估收益{estimated_profit_rate}，余额{CurrentRealBalance}，基金类型{fund_type}，估值变化{fund_info.estimated_change}")
            
        #检查银行卡余额,小于50万，且收益大于3.0，立即卖出费率为0的份额
        if estimated_profit_rate > 3.0 and CurrentRealBalance < BANK_BALANCE_THRESHOLD and fund_type in ['001','002']:
            logger.info(f"{customer_name}的止盈操作开始：余额:{CurrentRealBalance},基金{fund_name}{fund_code}(类型:{fund_type})预估收益{estimated_profit_rate},实际止盈点:3.0.")
            sell_usable_non_zero_fee_shares(user,sub_account_no,fund_code,shares)
            return True
    logger.info("所有止盈条件都不满足，返回True")
    return True


if __name__ == "__main__":
    # 直接运行测试
    redeem_all_fund_plans(DEFAULT_USER)

# 新增：银行卡余额阈值（环境变量 BANK_BALANCE_THRESHOLD），默认 300000
BANK_BALANCE_THRESHOLD = float(os.environ.get("BANK_BALANCE_THRESHOLD", "300000"))
    