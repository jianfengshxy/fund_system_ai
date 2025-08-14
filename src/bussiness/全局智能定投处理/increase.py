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
from src.API.交易管理.trade import get_trades_list, get_bank_shares

logging.basicConfig(
    stream=sys.stdout,
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)    

# 加仓算法实现
def increase(user: User, plan_detail: FundPlanDetail) -> bool:
    logger.info(f"========== 开始执行加仓算法 ==========")
    customer_name=user.customer_name
    logger.info(f"用户: {customer_name}")
    
    # 获取基金信息
    fund_code = plan_detail.rationPlan.fundCode
    fund_name = plan_detail.rationPlan.fundName
    logger.info(f"处理基金: {fund_name} {fund_code}")
    
    try:
        fund_info = get_all_fund_info(user, fund_code)
        fund_name = fund_info.fund_name
        logger.info(f"基金名称: {fund_name}")
        logger.info(f"基金估值增长率: {fund_info.estimated_change}")
        logger.info(f"基金100日排名: {fund_info.rank_100day}, 30日排名: {fund_info.rank_30day}")
    except Exception as e:
        logger.error(f"获取基金信息失败: {e}")
        return False
        
    sub_account_no = plan_detail.rationPlan.subAccountNo
    sub_account_name = plan_detail.rationPlan.subAccountName
    shares = get_bank_shares(user, sub_account_no, fund_code)
    period_type = plan_detail.rationPlan.periodType
    period_value = plan_detail.rationPlan.periodValue
    fund_amount = plan_detail.rationPlan.amount 
    plan_type = plan_detail.rationPlan.planType
    
    #获取当前日期
    current_date = datetime.now()
    # 提取当天的日期（即本月的第几天）
    day_of_month = current_date.day
    # 获取星期几的数字表示（0 表示周一，1 表示周二，依此类推）
    day_of_week_number = current_date.weekday()     
    logger.info(f"时间信息 - 当前日期: {current_date.strftime('%Y-%m-%d')}, 月份第{day_of_month}天, 星期{day_of_week_number + 1}")
  
    # 检查是否有可回撤的定投交易，4是定投业务类型，7是可以回撤交易状态
    try:
        trades = get_trades_list(user, sub_account_no=sub_account_no, fund_code = fund_code,bus_type="4", status="7")
        logger.info(f"查询可回撤交易 - 找到{len(trades) if trades else 0}笔可回撤的定投交易")
        if not trades or len(trades) == 0:
            logger.info(f"组合{sub_account_no}的{fund_name}{fund_code}今天没有可以回撤的定投计划交易记录。Skip ..........")
            return True
    except Exception as e:
        logger.error(f"查询可回撤交易失败: {e}")
        return False      

    
    logger.info(f"计划详情 - 组合账号: {sub_account_no}, 组合名称: {sub_account_name}")
    logger.info(f"计划详情 - 周期类型: {period_type}, 周期值: {period_value}, 定投金额: {fund_amount}, 计划类型: {plan_type}")
   
    
    try:
        asset_detail = get_fund_asset_detail(user, sub_account_no, fund_code)
        if asset_detail is not None:
            constant_profit_rate = asset_detail.constant_profit_rate  # 移除 * 100
            logger.info(f"{fund_name}资产详情获取成功 - 资产价值: {asset_detail.asset_value}, 收益率: {constant_profit_rate}%, 在途交易数: {asset_detail.on_way_transaction_count}")
        else:
            logger.info(f"组合{sub_account_no}的{fund_name}{fund_code}资产为空。Skip ..........")
            return True
    except Exception as e:
        logger.error(f"获取资产详情失败: {e}")
        return False
        
    plan_assets = asset_detail.asset_value
    constant_profit_rate = asset_detail.constant_profit_rate  # 移除 * 100
    on_way_transaction_count = asset_detail.on_way_transaction_count
    times = round(plan_assets / fund_amount, 2)
    logger.info(f"计算结果 - 资产倍数: {times}")
    
    # 获取当前收益率和估值增长率
    current_profit_rate = constant_profit_rate if constant_profit_rate is not None else 0.0
    estimated_change = fund_info.estimated_change if fund_info.estimated_change is not None else 0.0
    estimated_profit_rate = current_profit_rate + estimated_change
    
    logger.info(f"收益率计算 - 当前收益率: {current_profit_rate}%, 估值增长率: {estimated_change}%, 预估收益率: {estimated_profit_rate}%")
            
    logger.info(f"当前计划:{plan_detail.rationPlan.planId}组合{sub_account_no}的{fund_name}{fund_code}的周期类型{period_type},period_type:{period_value},当前月的值:{day_of_month},当前资产:{plan_assets},计划类型:{plan_type}")
    if times <= 1.0 and times > 0.0:
            logger.info(f"首次定投判定：资产价值为{plan_assets}，定投金额为{fund_amount}，满足首次定投条件，跳过本次操作。")
            logger.info(f"组合{sub_account_no}，基金{fund_name}({fund_code})资产{plan_assets}，首次定投已处理，跳过。")
            return True    
    #判断是否是月定投延期交易
    if period_type == 3 and  period_value != day_of_month: 
        logger.info(f"月定投延期检查 - 计划执行日期: {period_value}, 当前日期: {day_of_month}, 不匹配，执行回撤")
        #回撤所有交易   
        for i, trade in enumerate(trades):
            logger.info(f"回撤交易 {i+1}/{len(trades)} - 序列号: {trade.busin_serial_no}, 金额: {trade.amount}")
            try:
                revoke_order(user, trade.busin_serial_no, trade.business_type, plan_detail.rationPlan.fundCode, trade.amount)
                logger.info(f"交易回撤成功")
            except Exception as e:
                logger.error(f"交易回撤失败: {e}")
        logger.info(f"{customer_name}的组合{sub_account_name}{fund_name}的月延期交易{day_of_month},撤回所有交易。")
        return  True
        
    #判断是否是周定投延期交易
    if period_type == 1 and  period_value != day_of_week_number + 1:
        logger.info(f"周定投延期检查 - 计划执行星期: {period_value}, 当前星期: {day_of_week_number + 1}, 不匹配，执行回撤")
        #回撤所有交易
        for i, trade in enumerate(trades):
            logger.info(f"回撤交易 {i+1}/{len(trades)} - 序列号: {trade.busin_serial_no}, 金额: {trade.amount}")
            try:
                revoke_order(user, trade.busin_serial_no, trade.business_type, plan_detail.rationPlan.fundCode, trade.amount)
                logger.info(f"交易回撤成功")
            except Exception as e:
                logger.error(f"交易回撤失败: {e}")
        logger.info(f"{customer_name}的组合{sub_account_name}{fund_name}的周延期交易{day_of_week_number + 1},撤回所有交易。")
        return True
        

    # 检查是否有在途交易(在途交易个数大于1,要排除掉当天的定投交易)
    logger.info(f"在途交易检查 - 组合{sub_account_no}的{fund_name}{fund_code}今天有在途交易{on_way_transaction_count}个")
    if on_way_transaction_count > 1:
        logger.info(f"在途交易过多 - 组合{sub_account_no}的{fund_name}{fund_code}今天有在途交易，不进行加仓操作并回撤定投。Skip..........")
        # 撤回交易
        for i, trade in enumerate(trades):
            logger.info(f"回撤交易 {i+1}/{len(trades)} - 序列号: {trade.busin_serial_no}, 金额: {trade.amount}")
            try:
                revoke_order(user, trade.busin_serial_no, trade.business_type, plan_detail.rationPlan.fundCode, trade.amount)
                logger.info(f"交易回撤成功")
            except Exception as e:
                logger.error(f"交易回撤失败: {e}")
        return True
        
    logger.info(f"计划{plan_detail.rationPlan.planId}组合{sub_account_no}的{fund_name}{fund_code}当前收益率:{current_profit_rate},估值增长率:{estimated_change},预估收益率:{estimated_profit_rate},在途交易个数:{on_way_transaction_count}.")   
    
    if estimated_profit_rate > -1.0 :
        logger.info(f"预估收益率检查 - {customer_name}的组合{sub_account_name}{fund_name}的预估收益率{estimated_profit_rate} > -1.0,执行回撤")
        #回撤所有交易
        for i, trade in enumerate(trades):
            logger.info(f"回撤交易 {i+1}/{len(trades)} - 序列号: {trade.busin_serial_no}, 金额: {trade.amount}")
            try:
                revoke_order(user, trade.busin_serial_no, trade.business_type, plan_detail.rationPlan.fundCode, trade.amount)
                logger.info(f"交易回撤成功")
            except Exception as e:
                logger.error(f"交易回撤失败: {e}")
        return  True  
        
    #判断shares数组里面的totalVol之和等于shares数组里面的availableVol之和不相等为True和上面操作一样撤回交易  
    totalVol = 0
    availableVol = 0
    for share in shares:
        totalVol += share.totalVol
        availableVol += share.availableVol
        
    logger.info(f"份额检查 - 总份额: {totalVol}, 可用份额: {availableVol}")
    if totalVol != availableVol:
        logger.info(f"份额不匹配 - 组合{sub_account_no}的{fund_name}{fund_code}今天shares数组里面的totalVol之和不等于shares数组里面的availableVol之和，不进行加仓操作并回撤定投。Skip..........")
        # 撤回交易
        for i, trade in enumerate(trades):
            logger.info(f"回撤交易 {i+1}/{len(trades)} - 序列号: {trade.busin_serial_no}, 金额: {trade.amount}")
            try:
                revoke_order(user, trade.busin_serial_no, trade.business_type, plan_detail.rationPlan.fundCode, trade.amount)
                logger.info(f"交易回撤成功")
            except Exception as e:
                logger.error(f"交易回撤失败: {e}")
        return True
        
    #计算当前可以回撤的交易数量 
    try:
        revoke_count = len(get_trades_list(user, sub_account_no=sub_account_no, fund_code = fund_code,bus_type="", status="7"))
        logger.info(f"可回撤交易统计 - 总共{revoke_count}笔可回撤交易")
    except Exception as e:
        logger.error(f"统计可回撤交易失败: {e}")
        return False
        
    if  revoke_count == 1:
        logger.info(f"单笔交易处理 - 组合{sub_account_no}的{fund_name}{fund_code}今天只有一个可以回撤的交易进行加仓判断")
        if estimated_profit_rate < -1.0 :
            logger.info(f"预估收益率符合条件 - {customer_name}的组合{sub_account_name}{fund_name}的预估收益率{estimated_profit_rate} < -1.0")  
            
            # 100日排名检查
            if fund_info.rank_100day < 20:
                logger.info(f"100日排名过低 - {fund_name} rank_100 {fund_info.rank_100day} < 20, 执行回撤")
                #回撤所有交易
                for i, trade in enumerate(trades):
                    logger.info(f"回撤交易 {i+1}/{len(trades)} - 序列号: {trade.busin_serial_no}, 金额: {trade.amount}")
                    try:
                        revoke_order(user, trade.busin_serial_no, trade.business_type, plan_detail.rationPlan.fundCode, trade.amount)
                        logger.info(f"交易回撤成功")
                    except Exception as e:
                        logger.error(f"交易回撤失败: {e}")
                logger.info(f"{fund_name} rank_100 {fund_info.rank_100day} < 20. Skip......")
                return  True    
                
            if fund_info.rank_100day > 90:
                logger.info(f"100日排名过高 - {fund_name} rank_100 {fund_info.rank_100day} > 90, 执行回撤")
                #回撤所有交易
                for i, trade in enumerate(trades):
                    logger.info(f"回撤交易 {i+1}/{len(trades)} - 序列号: {trade.busin_serial_no}, 金额: {trade.amount}")
                    try:
                        revoke_order(user, trade.busin_serial_no, trade.business_type, plan_detail.rationPlan.fundCode, trade.amount)
                        logger.info(f"交易回撤成功")
                    except Exception as e:
                        logger.error(f"交易回撤失败: {e}")
                logger.info(f"{fund_name} rank_100 {fund_info.rank_100day} > 90. Skip......")
                return  True                 
                
            if fund_info.rank_30day < 5:
                logger.info(f"30日排名过低 - {fund_name} rank_30 {fund_info.rank_30day} < 5, 执行回撤")
                #回撤所有交易
                for i, trade in enumerate(trades):
                    logger.info(f"回撤交易 {i+1}/{len(trades)} - 序列号: {trade.busin_serial_no}, 金额: {trade.amount}")
                    try:
                        revoke_order(user, trade.busin_serial_no, trade.business_type, plan_detail.rationPlan.fundCode, trade.amount)
                        logger.info(f"交易回撤成功")
                    except Exception as e:
                        logger.error(f"交易回撤失败: {e}")
                logger.info(f"{fund_name} rank_30 {fund_info.rank_30day} < 5. Skip......")
                return  True
                
            season_growth_rate = fund_info.three_month_return
            month_growth_rate = fund_info.month_return
            week_growth_rate = fund_info.week_return
            logger.info(f"收益率数据 - {fund_name}周收益率预估:{week_growth_rate},{fund_name}月收益率预估:{month_growth_rate},季度收益率预估:{season_growth_rate}")
            
            if  week_growth_rate <  0.0 and month_growth_rate < 0.0 and season_growth_rate < 0.0:
                logger.info(f"全部收益率为负 - 周、月、季度收益率均为负数，执行回撤")
                # 回撤所有交易  
                for i, trade in enumerate(trades):
                    logger.info(f"回撤交易 {i+1}/{len(trades)} - 序列号: {trade.busin_serial_no}, 金额: {trade.amount}")
                    try:
                        revoke_order(user, trade.busin_serial_no, trade.business_type, plan_detail.rationPlan.fundCode, trade.amount)
                        logger.info(f"交易回撤成功")
                    except Exception as e:
                        logger.error(f"交易回撤失败: {e}")
                logger.info(f"{fund_name}周收益率预估:{week_growth_rate},{fund_name}月收益率预估:{month_growth_rate},季度收益率预估:{season_growth_rate}.Skip......")
                return  True    
                
            if  season_growth_rate < 0.0 and (month_growth_rate < 0.0 or week_growth_rate < 0.0 ):
                logger.info(f"季度收益率为负且月/周收益率至少一个为负 - 执行跳过")
                logger.info(f"{fund_name}周收益率预估:{week_growth_rate},{fund_name}月收益率预估:{month_growth_rate},季度收益率预估:{season_growth_rate}.Skip......")
                return  True
                
            if  season_growth_rate > 0.0 and (month_growth_rate < 0.0 and week_growth_rate < 0.0 ):
                logger.info(f"季度收益率为正但月、周收益率均为负 - 执行跳过")
                logger.info(f"{fund_name}周收益率预估:{week_growth_rate},{fund_name}月收益率预估:{month_growth_rate},季度收益率预估:{season_growth_rate}.Skip......")
                return  True

            try:
                season_growth_rate, season_item_rank, season_item_sc = get_fund_growth_rate(fund_info, '3Y')
                month_growth_rate, month_item_rank, month_item_sc = get_fund_growth_rate(fund_info, 'Y')
                logger.info(f"排名数据获取 - 季度排名: {season_item_rank}/{season_item_sc}, 月排名: {month_item_rank}/{month_item_sc}")
                
                month_rank_rate  =  month_item_rank  /  month_item_sc      
                season_rank_rate  =  season_item_rank  /  season_item_sc
                logger.info(f"排名占比计算 - 季度排名占比: {season_rank_rate:.4f}, 月排名占比: {month_rank_rate:.4f}")
                
                if  month_rank_rate  >  0.75 or season_rank_rate  >  0.75:
                    logger.info(f"排名占比过高 - {fund_name}季度排名占比:{season_rank_rate},月排名占比:{month_rank_rate}, 执行跳过")
                    return  True
            except Exception as e:
                logger.error(f"获取基金排名数据失败: {e}")
                return False

            logger.info(f"所有条件检查通过 - {customer_name}在组合{sub_account_name}中{fund_name}{fund_code}候选成功.") 
            
            # 10倍逻辑检查
            if estimated_profit_rate < -5.0 and times > 15 :
                logger.info(f"10倍加仓逻辑 - {customer_name}在组合{sub_account_name}中{fund_name}{fund_code}满足10倍逻辑条件，预估收益率: {estimated_profit_rate}, 倍数: {times}")
                try:
                    commit_order(user, sub_account_no, fund_code, fund_amount * 10.0)
                    logger.info(f"10倍加仓订单提交成功 - 金额: {fund_amount * 10.0}")
                except Exception as e:
                    logger.error(f"10倍加仓订单提交失败: {e}")
                return True 
                
            # 基础加仓
            try:
                logger.info(f"执行基础加仓 - 金额: {fund_amount}")
                commit_order(user, sub_account_no, fund_code, fund_amount )
                logger.info(f"基础加仓订单提交成功")
            except Exception as e:
                logger.error(f"基础加仓订单提交失败: {e}")
                
            # -3.0%额外加仓
            if estimated_profit_rate < -3.0 :
                try:
                    logger.info(f"执行-3.0%额外加仓 - 金额: {fund_amount}")
                    commit_order(user, sub_account_no, fund_code, fund_amount )
                    logger.info(f"-3.0%额外加仓订单提交成功")
                except Exception as e:
                    logger.error(f"-3.0%额外加仓订单提交失败: {e}")
                    
            # -5.0%额外加仓
            if estimated_profit_rate < -5.0 :
                try:
                    logger.info(f"执行-5.0%额外加仓 - 金额: {fund_amount}")
                    commit_order(user, sub_account_no, fund_code, fund_amount )
                    logger.info(f"-5.0%额外加仓订单提交成功")
                except Exception as e:
                    logger.error(f"-5.0%额外加仓订单提交失败: {e}")
                    
    logger.info(f"========== 加仓算法执行完成 ==========")
    return True

def increase_all_fund_plans(user: User):
    logger.info(f"========== 开始执行全部基金计划加仓 ==========")
    logger.info(f"用户: {user.customer_name}")
    
    try:
        fund_plan_details = get_all_fund_plan_details(user)
        logger.info(f"获取到{len(fund_plan_details)}个基金计划")
    except Exception as e:
        logger.error(f"获取基金计划详情失败: {e}")
        return
    
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(increase, user, plan_detail) 
                  for plan_detail in fund_plan_details]
        
    results = [future.result() for future in futures]
    success_count = sum(1 for result in results if result)
    logger.info(f"{user.customer_name}有{len(results)}个定投计划执行加仓操作，成功{success_count}个，失败{len(results) - success_count}个")
    logger.info(f"========== 全部基金计划加仓执行完成 ==========")
