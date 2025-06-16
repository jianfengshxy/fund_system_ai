import logging
from random import vonmisesvariate
import re
from typing import Optional
import threading
from concurrent.futures import ThreadPoolExecutor
import os
import sys
import math

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

logger = logging.getLogger(__name__)    

# 加仓算法实现
def increase(user: User, plan_detail: FundPlanDetail) -> bool:
    customer_name=user.customer_name
    # 获取基金信息
    fund_code = plan_detail.rationPlan.fundCode
    fund_info = get_all_fund_info(user, fund_code)
    fund_name = fund_info.fund_name
    sub_account_no = plan_detail.rationPlan.subAccountNo
    sub_account_name = plan_detail.rationPlan.subAccountName
    shares = plan_detail.rationPlan.shares
    period_type = plan_detail.rationPlan.periodType
    period_value = plan_detail.rationPlan.periodValue
    plan_assets = plan_detail.rationPlan.planAssets
    fund_amount = plan_detail.rationPlan.amount 
    asset_detail = get_fund_asset_detail(user, sub_account_no, fund_code)
    if asset_detail is not None:
        constant_profit_rate = asset_detail.constant_profit_rate * 100
    else:
        logger.info(f"组合{sub_account_no}的{fund_name}{fund_code}资产为空。Skip ..........")
        return True
    constant_profit_rate = asset_detail.constant_profit_rate * 100
    on_way_transaction_count = asset_detail.on_way_transaction_count
    times = plan_assets // fund_amount
    # 获取当前收益率和估值增长率
    current_profit_rate = constant_profit_rate if constant_profit_rate is not None else 0.0
    estimated_change = fund_info.estimated_change if fund_info.estimated_change is not None else 0.0
    estimated_profit_rate = current_profit_rate + estimated_change
    #获取当前日期
    current_date = datetime.now()
    # 提取当天的日期（即本月的第几天）
    day_of_month = current_date.day
    # 获取星期几的数字表示（0 表示周一，1 表示周二，依此类推）
    day_of_week_number = current_date.weekday() 
  
    # 检查是否有可回撤的定投交易，4是定投业务类型，7是可以回撤交易状态
    trades = get_trades_list(user, sub_account_no=sub_account_no, fund_code = fund_code,bus_type="4", status="7")
    if not trades or len(trades) == 0:
        logger.info(f"组合{sub_account_no}的{fund_name}{fund_code}今天没有可以回撤的定投计划交易记录。Skip ..........")
        return True
    logger.info(f"当前计划:{plan_detail.rationPlan.planId}组合{sub_account_no}的{fund_name}{fund_code}的周期类型{period_type},period_type:{period_value},当前月的值:{day_of_month}")
    #判断是否是月定投延期交易
    if period_type == 3 and  period_value != day_of_month: 
        #回撤所有交易   
        for trade in trades:
            revoke_order(user, trade.busin_serial_no, trade.business_type, plan_detail.rationPlan.fundCode, trade.amount)
        logger.info(f"{customer_name}的组合{sub_account_name}{fund_name}的月延期交易{day_of_month},撤回所有交易。")
        return  True
    #判断是否是周定投延期交易
    if period_type == 1 and  period_value != day_of_week_number + 1:
        #回撤所有交易
        for trade in trades:
            revoke_order(user, trade.busin_serial_no, trade.business_type, plan_detail.rationPlan.fundCode, trade.amount)
        logger.info(f"{customer_name}的组合{sub_account_name}{fund_name}的周延期交易{day_of_week_number + 1},撤回所有交易。")
        return True

    if  math.isclose(float(plan_assets),fund_amount):
        logger.info(f"组合{sub_account_no}的{fund_name}{fund_code}资产{plan_assets},属于第一次定投。Skip ..........")
        return True 

    # 检查是否有在途交易(在途交易个数大于1,要排除掉当天的定投交易)
    logger.info(f"组合{sub_account_no}的{fund_name}{fund_code}今天有在途交易{on_way_transaction_count}个")
    if on_way_transaction_count > 1:
        logger.info(f"组合{sub_account_no}的{fund_name}{fund_code}今天有在途交易，不进行加仓操作并回撤定投。Skip..........")
        # 撤回交易
        for trade in trades:
            revoke_order(user, trade.busin_serial_no, trade.business_type, plan_detail.rationPlan.fundCode, trade.amount)
        return True
    logger.info(f"计划{plan_detail.rationPlan.planId}组合{sub_account_no}的{fund_name}{fund_code}当前收益率:{current_profit_rate},估值增长率:{estimated_change},预估收益率:{estimated_profit_rate},在途交易个数:{on_way_transaction_count}.")   
    if estimated_profit_rate > -1.0 :
        logger.info(f"{customer_name}的组合{sub_account_name}{fund_name}的预估收益率{estimated_profit_rate} > 1.0,Skip......")  
        #回撤所有交易
        for trade in trades:
            revoke_order(user, trade.busin_serial_no, trade.business_type, plan_detail.rationPlan.fundCode, trade.amount)
        return  True  
    #判断shares数组里面的totalVol之和等于shares数组里面的availableVol之和不相等为True和上面操作一样撤回交易  
    totalVol = 0
    availableVol = 0
    for share in shares:
        totalVol += share.totalVol
        availableVol += share.availableVol
    if totalVol != availableVol:
        logger.info(f"组合{sub_account_no}的{fund_name}{fund_code}今天shares数组里面的totalVol之和不等于shares数组里面的availableVol之和，不进行加仓操作并回撤定投。Skip..........")
        # 撤回交易
        for trade in trades:
            revoke_order(user, trade.busin_serial_no, trade.business_type, plan_detail.rationPlan.fundCode, trade.amount)
        return True
    #计算当前可以回撤的交易数量 
    revoke_count = len(get_trades_list(user, sub_account_no=sub_account_no, fund_code = fund_code,bus_type="", status="7"))
    if  revoke_count == 1:
        logger.info(f"组合{sub_account_no}的{fund_name}{fund_code}今天只有一个可以回撤的交易进行加仓判断")
        if estimated_profit_rate < -1.0 :
            logger.info(f"{customer_name}的组合{sub_account_name}{fund_name}的预估收益率{estimated_profit_rate} < -1.0")  
            if fund_info.rank_100day < 20:
                #回撤所有交易
                for trade in trades:
                    revoke_order(user, trade.busin_serial_no, trade.business_type, plan_detail.rationPlan.fundCode, trade.amount)
                logger.info(f"{fund_name} rank_100 {fund_info.rank_100day} < 20. Skip......")
                return  True    
            if fund_info.rank_100day > 90:
                #回撤所有交易
                for trade in trades:
                    revoke_order(user, trade.busin_serial_no, trade.business_type, plan_detail.rationPlan.fundCode, trade.amount)
                logger.info(f"{fund_name} rank_100 {fund_info.rank_100day} > 90. Skip......")
                return  True                 
            if fund_info.rank_30day < 5:
                #回撤所有交易
                for trade in trades:
                    revoke_order(user, trade.busin_serial_no, trade.business_type, plan_detail.rationPlan.fundCode, trade.amount)
                logger.info(f"{fund_name} rank_30 {fund_info.rank_30day} < 5. Skip......")
                return  True
            season_growth_rate = fund_info.three_month_return
            month_growth_rate = fund_info.month_return
            week_growth_rate = fund_info.week_return
            logger.info(f"{fund_name}周收益率预估:{week_growth_rate},{fund_name}月收益率预估:{month_growth_rate},季度收益率预估:{season_growth_rate}")
            if  week_growth_rate <  0.0 and month_growth_rate < 0.0 and season_growth_rate < 0.0:
                # 回撤所有交易  
                for trade in trades:
                    revoke_order(user, trade.busin_serial_no, trade.business_type, plan_detail.rationPlan.fundCode, trade.amount)
                logger.info(f"{fund_name}周收益率预估:{week_growth_rate},{fund_name}月收益率预估:{month_growth_rate},季度收益率预估:{season_growth_rate}.Skip......")
                return  True    
            if  season_growth_rate < 0.0 and (month_growth_rate < 0.0 or week_growth_rate < 0.0 ):
                 logger.info(f"{fund_name}周收益率预估:{week_growth_rate},{fund_name}月收益率预估:{month_growth_rate},季度收益率预估:{season_growth_rate}.Skip......")
                 return  True
            if  season_growth_rate > 0.0 and (month_growth_rate < 0.0 and week_growth_rate < 0.0 ):
                 logger.info(f"{fund_name}周收益率预估:{week_growth_rate},{fund_name}月收益率预估:{month_growth_rate},季度收益率预估:{season_growth_rate}.Skip......")
                 return  True

            
            season_growth_rate, season_item_rank, season_item_sc = get_fund_growth_rate(fund_info, '3Y')
            month_growth_rate, month_item_rank, month_item_sc = get_fund_growth_rate(fund_info, 'Y')
            month_rank_rate  =  month_item_rank  /  month_item_sc      
            season_rank_rate  =  season_item_rank  /  season_item_sc
            if  month_rank_rate  >  0.75 or season_rank_rate  >  0.75:
                logger.info(f"{fund_name}季度排名占比:{season_rank_rate},月排名占比:{month_rank_rate}.Skip......")
                return  True

            logger.info(f"{customer_name}在组合{sub_account_name}中{fund_name}{fund_code}候选成功.") 
            if estimated_profit_rate < -5.0 and times > 15 :
                logger.info(f"{customer_name}在组合{sub_account_name}中{fund_name}{fund_code}10倍逻辑.") 
                commit_order(user, sub_account_no, fund_code, fund_amount * 10.0)
                return True 
            commit_order(user, sub_account_no, fund_code, fund_amount )
            if estimated_profit_rate < -3.0 :   
                commit_order(user, sub_account_no, fund_code, fund_amount )
            if estimated_profit_rate < -5.0 :   
                commit_order(user, sub_account_no, fund_code, fund_amount )           

def increase_all_fund_plans(user: User):
    fund_plan_details = get_all_fund_plan_details(user)
    
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(increase, user, plan_detail) 
                  for plan_detail in fund_plan_details]
        
    results = [future.result() for future in futures]
    logger.info(f"{user.customer_name}有{len(results)}个定投计划执行加仓操作.")
