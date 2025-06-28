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
from src.API.大数据.加仓风向标 import getFundInvestmentIndicators
from src.domain.fund.fund_investment_indicator import FundInvestmentIndicator
# 修改第39行的导入语句
from src.service.定投管理.智能定投.智能定投管理 import create_period_smart_investment
from src.service.基金信息.基金信息 import get_all_fund_info
logger = logging.getLogger(__name__)    

def add_plan(user: User, amount: int = 2000):
    """
    全局智能定投处理 - 为加仓风向标中的基金创建日智能定投计划
    :param user: 用户对象
    :param amount: 定投金额，默认2000
    :return: None
    """
    logger.info("=== 开始执行add_plan函数 ===")
    logger.info(f"用户信息: customer_name={getattr(user, 'customer_name', 'N/A')}")
    
    try:
        # 步骤1: 获取加仓风向标基金信息
        logger.info("步骤1: 获取加仓风向标数据...")
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
        
        # 步骤2: 获取所有的定投计划详情
        logger.info("步骤2: 获取所有定投计划...")
        fund_plan_details = get_all_fund_plan_details(user)
        if not fund_plan_details:
            logger.warning("获取定投计划列表失败或为空")
            return
        
        logger.info(f"获取到 {len(fund_plan_details)} 个定投计划")
        
        # 提取所有定投计划中指数基金的跟踪指数（用于避免重复）
        all_existing_index_codes = set()
        
        for plan in fund_plan_details:
            if (hasattr(plan, 'rationPlan') and 
                hasattr(plan.rationPlan, 'fundCode') and 
                plan.rationPlan.fundCode):
                try:
                    fund_info = get_all_fund_info(user, plan.rationPlan.fundCode)
                    if fund_info and hasattr(fund_info, 'fund_type') and fund_info.fund_type == "000":
                        if hasattr(fund_info, 'index_code') and fund_info.index_code:
                            all_existing_index_codes.add(fund_info.index_code)
                            logger.info(f"  所有定投计划中的指数基金: {plan.rationPlan.fundName}({plan.rationPlan.fundCode}) 跟踪指数: {fund_info.index_code}")
                except Exception as e:
                    logger.warning(f"获取定投计划基金 {plan.rationPlan.fundCode} 详细信息失败: {e}")
        
        logger.info(f"所有定投计划中跟踪的指数: {sorted(list(all_existing_index_codes))}")
        
        # 步骤3: 过滤出periodType == 4 且 planType == '1' 的日智能定投计划集合
        logger.info("步骤3: 过滤日智能定投计划...")
        filtered_fund_plan_details = [
            fund_plan_detail for fund_plan_detail in fund_plan_details
            if (hasattr(fund_plan_detail, 'rationPlan') and 
                hasattr(fund_plan_detail.rationPlan, 'periodType') and 
                fund_plan_detail.rationPlan.periodType == 4 and 
                hasattr(fund_plan_detail.rationPlan, 'planType') and 
                fund_plan_detail.rationPlan.planType == '1')
        ]
        
        logger.info(f"找到 {len(filtered_fund_plan_details)} 个日智能定投计划")
        
        # 提取现有日智能定投计划的基金代码
        existing_fund_codes = set()
        
        for plan in filtered_fund_plan_details:
            if (hasattr(plan, 'rationPlan') and 
                hasattr(plan.rationPlan, 'fundCode') and 
                plan.rationPlan.fundCode):
                existing_fund_codes.add(plan.rationPlan.fundCode)
                logger.info(f"  现有日智能定投: {plan.rationPlan.fundName}({plan.rationPlan.fundCode})")
        
        logger.info(f"现有日智能定投计划基金代码: {sorted(list(existing_fund_codes))}")
        
        # 步骤4: 遍历加仓风向标基金信息集合，检查并创建计划
        logger.info("步骤4: 检查加仓风向标基金并创建计划...")
        created_count = 0
        skipped_count = 0
        
        for i, indicator in enumerate(indicators_list):
            logger.info(f"\n处理第{i+1}个加仓风向标基金: {indicator.fund_name}({indicator.fund_code})")
            
            # 判断indicator的基金fund_code在现有日智能定投计划中是否存在
            if indicator.fund_code in existing_fund_codes:
                logger.info(f"  ✓ {indicator.fund_name}({indicator.fund_code})的日智能定投计划已经存在，跳过")
                print(f"{indicator.fund_name}的日智能定投计划已经有了，跳过")
                skipped_count += 1
                continue
            
            # 如果是指数基金，检查跟踪指数是否重复
            should_create = True
            skip_reason = ""
            
            if hasattr(indicator, 'fund_type') and indicator.fund_type == "000":
                try:
                    fund_info = get_all_fund_info(user, indicator.fund_code)
                    if fund_info and hasattr(fund_info, 'index_code') and fund_info.index_code:
                        if fund_info.index_code in all_existing_index_codes:
                            should_create = False
                            skip_reason = f"已有跟踪相同指数({fund_info.index_code})的定投计划"
                            logger.info(f"  ✓ 跳过指数基金 {indicator.fund_name}({indicator.fund_code}): {skip_reason}")
                            print(f"跳过{indicator.fund_name}，{skip_reason}")
                            skipped_count += 1
                        else:
                            logger.info(f"  ✓ 指数基金 {indicator.fund_name}({indicator.fund_code}) 跟踪指数 {fund_info.index_code}，未重复")
                    else:
                        logger.info(f"  ✓ 指数基金 {indicator.fund_name}({indicator.fund_code}) 无法获取跟踪指数信息，继续创建")
                except Exception as e:
                    logger.warning(f"获取指数基金 {indicator.fund_code} 详细信息失败: {e}，继续创建")
            
            if should_create:
                logger.info(f"  ✓ {indicator.fund_name}({indicator.fund_code})没有日智能定投计划，准备创建")
                print(f"要为{indicator.fund_name}添加日智能定投计划")
                
                try:
                    # 调用创建日智能定投计划函数
                    result = create_period_smart_investment(
                        user=user, 
                        fund_code=indicator.fund_code, 
                        amount=amount, 
                        period_type=4, 
                        period_value=1
                    )
                    
                    # 修正判断逻辑：使用大写的Success属性
                    if result and hasattr(result, 'Success') and result.Success:
                        logger.info(f"  ✓ 成功为{indicator.fund_name}({indicator.fund_code})创建日智能定投计划")
                        created_count += 1
                    else:
                        logger.warning(f"  ✗ 为{indicator.fund_name}({indicator.fund_code})创建日智能定投计划失败")
                        if result:
                            logger.warning(f"    失败原因: ErrorCode={getattr(result, 'ErrorCode', 'N/A')}, FirstError={getattr(result, 'FirstError', 'N/A')}")
                        
                except Exception as e:
                    logger.error(f"  ✗ 为{indicator.fund_name}({indicator.fund_code})创建日智能定投计划时发生异常: {str(e)}")
        
        # 输出最终统计信息
        logger.info("\n=== 执行结果统计 ===")
        logger.info(f"加仓风向标基金总数: {len(indicators_list)}")
        logger.info(f"成功创建计划数: {created_count}")
        logger.info(f"已存在跳过数: {skipped_count}")
        logger.info(f"处理完成率: {((created_count + skipped_count) / len(indicators_list) * 100):.1f}%")
        logger.info("=== add_plan函数执行完成 ===")
        
    except Exception as e:
        logger.error(f"add_plan 执行失败: {str(e)}")
        logger.error(f"异常详情: {type(e).__name__}: {str(e)}")
        import traceback
        logger.error(f"异常堆栈: {traceback.format_exc()}")

