import logging
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
from datetime import datetime
from src.domain.fund_plan.fund_plan import FundPlan
from src.API.基金信息.FundRank import get_fund_growth_rate
from src.API.定投计划管理.SmartPlan import getFundPlanList
from src.API.大数据.加仓风向标 import getFundInvestmentIndicators
from src.service.定投管理.智能定投.智能定投管理 import dissolve_period_smart_investment

logger = logging.getLogger(__name__)    

def dissolve_daily_plan(user: User):
    """
    解散所有不在加仓风向标中的日定投计划
    
    Args:
        user: 用户对象
    """
    logger.info("=== 开始执行dissolve_daily_plan函数 ===")
    logger.info(f"用户信息: customer_no={getattr(user, 'customer_no', 'N/A')}")
    
    try:
        # 获取所有定投计划
        logger.info("步骤1: 获取所有定投计划...")
        all_fund_plan_details = get_all_fund_plan_details(user)
        if not all_fund_plan_details:
            logger.warning("获取定投计划列表失败或为空")
            return
        
        logger.info(f"获取到 {len(all_fund_plan_details)} 个定投计划")
        
        # 打印所有计划的基本信息
        logger.info("所有定投计划概览:")
        for i, plan in enumerate(all_fund_plan_details[:10]):  # 只显示前10个
            # FundPlanDetail的结构：rationPlan包含实际的基金计划信息
            ration_plan = getattr(plan, 'rationPlan', None)
            if ration_plan:
                fund_name = getattr(ration_plan, 'fundName', 'N/A')
                fund_code = getattr(ration_plan, 'fundCode', 'N/A')
                period_type = getattr(ration_plan, 'periodType', 'N/A')
                plan_type = getattr(ration_plan, 'planType', 'N/A')
                plan_assets = getattr(ration_plan, 'planAssets', 'N/A')
                plan_id = getattr(ration_plan, 'planId', 'N/A')
            else:
                fund_name = fund_code = period_type = plan_type = plan_assets = plan_id = 'N/A'
            logger.info(f"  计划{i+1}: {fund_name}({fund_code}) - 周期类型:{period_type} - 计划类型:{plan_type} - 资产:{plan_assets} - ID:{plan_id}")
        if len(all_fund_plan_details) > 10:
            logger.info(f"  ... 还有 {len(all_fund_plan_details) - 10} 个计划未显示")
        
        # 过滤出日定投计划 (period_type = 4 and plan_type = '1')
        logger.info("步骤2: 过滤日定投计划...")
        daily_plans = [plan for plan in all_fund_plan_details if hasattr(plan, 'rationPlan') and hasattr(plan.rationPlan, 'periodType') and plan.rationPlan.periodType == 4 and hasattr(plan.rationPlan, 'planType') and plan.rationPlan.planType == '1']
        
        logger.info(f"找到 {len(daily_plans)} 个日定投计划")
        
        if daily_plans:
            logger.info("日定投计划详情:")
            for i, plan in enumerate(daily_plans):
                ration_plan = getattr(plan, 'rationPlan', None)
                if ration_plan:
                    fund_name = getattr(ration_plan, 'fundName', 'N/A')
                    fund_code = getattr(ration_plan, 'fundCode', 'N/A')
                    plan_id = getattr(ration_plan, 'planId', 'N/A')
                    plan_assets = getattr(ration_plan, 'planAssets', 'N/A')
                else:
                    fund_name = fund_code = plan_id = plan_assets = 'N/A'
                logger.info(f"  日定投{i+1}: {fund_name}({fund_code}) - 计划ID:{plan_id} - 资产:{plan_assets}")
        
        if not daily_plans:
            logger.info("没有找到日定投计划，函数结束")
            return
        
        # 获取加仓风向标中的基金代码列表
        logger.info("步骤3: 获取加仓风向标数据...")
        try:
            indicators_list = getFundInvestmentIndicators(user)
            if not indicators_list:
                logger.warning("获取加仓风向标数据失败或为空")
                return
            logger.info(f"成功获取加仓风向标数据，共{len(indicators_list)}个基金")
        except Exception as e:
            logger.error(f"调用加仓风向标API失败: {str(e)}")
            import traceback
            logger.error(f"异常堆栈: {traceback.format_exc()}")
            return

        logger.info("加仓风向标数据获取完成...")
        
        # 提取加仓风向标中的基金代码
        indicator_fund_codes = set()
        logger.info(f"获取到 {len(indicators_list)} 个加仓风向标基金")
        for i, indicator in enumerate(indicators_list):
            logger.info(f"  基金{i+1}: {indicator.fund_name}({indicator.fund_code}) - 类型:{indicator.fund_type}")
            if hasattr(indicator, 'fund_code') and indicator.fund_code:
                indicator_fund_codes.add(indicator.fund_code)
        
        logger.info(f"加仓风向标中包含 {len(indicator_fund_codes)} 个基金")
        logger.info(f"加仓风向标基金代码: {sorted(list(indicator_fund_codes))}")
        
        # 检查每个日定投计划是否在加仓风向标中
        logger.info("步骤4: 检查日定投计划并执行解散操作...")
        dissolved_count = 0
        skipped_in_indicator = 0
        skipped_has_assets = 0
        
        for i, plan in enumerate(daily_plans):
            ration_plan = getattr(plan, 'rationPlan', None)
            if ration_plan:
                fund_name = getattr(ration_plan, 'fundName', 'N/A')
                fund_code = getattr(ration_plan, 'fundCode', 'N/A')
                plan_id = getattr(ration_plan, 'planId', 'N/A')
                plan_assets = getattr(ration_plan, 'planAssets', None)
            else:
                fund_name = fund_code = plan_id = 'N/A'
                plan_assets = None
            
            logger.info(f"\n处理第{i+1}个日定投计划: {fund_name}({fund_code})")
            logger.info(f"  计划ID: {plan_id}")
            logger.info(f"  计划资产: {plan_assets}")
            
            if ration_plan and hasattr(ration_plan, 'fundCode') and ration_plan.fundCode:
                if ration_plan.fundCode not in indicator_fund_codes:
                    logger.info(f"  ✓ 基金 {fund_code} {fund_name}不在加仓风向标中")
                    
                    # 基金不在加仓风向标中，检查资产是否为空或0.0
                    if plan_assets is not None and plan_assets != 0.0:
                        logger.info(f"  ✗ 资产不为空({plan_assets})，跳过解散")
                        skipped_has_assets += 1
                        continue
                    
                    logger.info(f"  ✓ 资产为空或0.0，准备解散")
                    
                    # 资产为空或0.0，可以解散该定投计划
                    try:
                        logger.info(f"  正在解散计划 {plan_id} {fund_name}...")                    
                        result = dissolve_period_smart_investment(user, plan_id)
                        if result and hasattr(result, 'success') and result.success:
                            logger.info(f"  ✓ 成功解散基金 {fund_code} {fund_name}的日定投计划 {plan_id}（资产为空）")
                            dissolved_count += 1
                        else:
                            logger.warning(f"  ✗ 解散基金 {fund_code} {fund_name}的日定投计划 {plan_id} 失败")
                    except Exception as e:
                        logger.error(f"  ✗ 解散基金 {fund_code} {fund_name}的日定投计划 {plan_id} 时发生异常: {str(e)}")
                else:
                    logger.info(f"  ✓ 基金 {fund_code} {fund_name} 在加仓风向标中，跳过解散")
                    skipped_in_indicator += 1
            else:
                logger.warning(f"  ✗ 计划缺少基金代码信息，跳过")
            
        # 输出最终统计信息
        logger.info("\n=== 执行结果统计 ===")
        logger.info(f"{user.customer_name}总日定投计划数: {len(daily_plans)}")
        logger.info(f"{user.customer_name}成功解散计划数: {dissolved_count}")
        logger.info(f"{user.customer_name}在加仓风向标中跳过: {skipped_in_indicator}")
        logger.info(f"{user.customer_name}有资产跳过解散: {skipped_has_assets}")
        logger.info(f"{user.customer_name}处理完成率: {((dissolved_count + skipped_in_indicator + skipped_has_assets) / len(daily_plans) * 100):.1f}%")
        logger.info(f"=== {user.customer_name} dissolve_daily_plan函数执行完成 ===")
        
    except Exception as e:
        logger.error(f"dissolve_daily_plan 执行失败: {str(e)}")
        logger.error(f"异常详情: {type(e).__name__}: {str(e)}")
        import traceback
        logger.error(f"异常堆栈: {traceback.format_exc()}")

if __name__ == "__main__":
    dissolve_daily_plan(DEFAULT_USER)