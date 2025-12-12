import pytest
import logging
import os
import sys

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("TestMonthlyPlan021740")

# Add project root to path
root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from src.API.定投计划管理.SmartPlan import getFundPlanList, getFundRations, getPlanDetailPro
from src.common.constant import DEFAULT_USER

def test_get_monthly_plan_021740():
    logger.info("开始测试 021740 基金 月定投计划")
    
    fund_code = "021740"
    user = DEFAULT_USER
    
    try:
        # Method: getFundRations
        # getFundRations returns ApiResponse, Data=list of plans
        
        response = getFundRations(user, page_size=200)
        if response.Success and response.Data:
            all_plans = response.Data
            logger.info(f"getFundRations 获取到 {len(all_plans)} 个总计划")
            
            target_plans = [p for p in all_plans if p.fundCode == fund_code]
            logger.info(f"其中属于 {fund_code} 的计划有 {len(target_plans)} 个")
            
            monthly_plans = [p for p in target_plans if int(p.periodType) == 3]
            logger.info(f"其中月定投计划 (periodType=3) 有 {len(monthly_plans)} 个")
            
            for plan in monthly_plans:
                logger.info(f"获取计划详情: {plan.planId}")
                detail_resp = getPlanDetailPro(plan.planId, user)
                
                if detail_resp.Success and detail_resp.Data:
                    detail = detail_resp.Data
                    ration_plan = detail.rationPlan
                    
                    execution_day = ration_plan.periodValue
                    # Prefer detail's nextDeductDate, fallback to list's nextDeductDate
                    next_date = ration_plan.nextDeductDate or plan.nextDeductDate
                    
                    # Log the detailed information
                    logger.info(f"Plan ID: {ration_plan.planId}, 定投周期: 每月 {execution_day} 号执行, 下次执行: {next_date}, 金额: {ration_plan.amount}")
                else:
                    logger.error(f"获取计划详情失败: {detail_resp.FirstError}")
                
            # Print other types if any
            for plan in target_plans:
                if int(plan.periodType) != 3:
                     logger.info(f"其他类型计划: ID={plan.planId}, Type={plan.periodType}, Value={plan.periodValue}")
        else:
            logger.error(f"getFundRations 失败: {response.FirstError}")

    except Exception as e:
        logger.error(f"测试过程中发生错误: {str(e)}", exc_info=True)
        raise

if __name__ == "__main__":
    test_get_monthly_plan_021740()
