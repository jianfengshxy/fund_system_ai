import sys
import os
from typing import List


# 添加项目根目录到Python路径
sys.path.append(os.path.join(os.path.dirname(__file__), '../../../../'))

from src.API.定投计划管理.SmartPlan import getFundPlanList, updatePlanStatus
from src.domain.user.User import User
from src.domain.fund_plan.fund_plan import FundPlan
import logging
from src.common.constant import DEFAULT_USER

logger = logging.getLogger(__name__)

def batch_update_fund_plan_status(user: User, fund_code: str, buy_strategy_switch: bool) -> List[dict]:
    """
    批量更改某个基金的定投计划状态
    
    Args:
        user: User对象，包含用户认证信息
        fund_code: 基金代码
        buy_strategy_switch: true 代表恢复买入，false代表暂停买入
        
    Returns:
        List[dict]: 更新结果列表，包含每个计划的更新状态
    """
    try:
        # 获取指定基金的定投计划列表
        logger.info(f"开始获取基金 {fund_code} 的定投计划列表")
        existing_plans = getFundPlanList(fund_code, user)
        
        if not existing_plans:
            logger.info(f"基金 {fund_code} 没有找到任何定投计划")
            return []
        
        logger.info(f"找到 {len(existing_plans)} 个定投计划，开始批量更新状态")
        
        # 存储更新结果
        update_results = []
        
        # 循环调用updatePlanStatus更新每个计划的状态
        for plan in existing_plans:
            try:
                logger.info(f"正在更新计划ID: {plan.planId}, 基金: {plan.fundName}")
                
                # 调用updatePlanStatus更新计划状态
                result = updatePlanStatus(user, plan.planId, buy_strategy_switch)
                
                update_results.append({
                    'planId': plan.planId,
                    'fundCode': plan.fundCode,
                    'fundName': plan.fundName,
                    'subAccountName': plan.subAccountName,
                    'success': result.Success if hasattr(result, 'Success') else True,
                    'message': '状态更新成功' if (hasattr(result, 'Success') and result.Success) else '状态更新失败',
                    'buyStrategySwitch': buy_strategy_switch
                })
                
                logger.info(f"计划ID {plan.planId} 状态更新完成")
                
            except Exception as e:
                logger.error(f"更新计划ID {plan.planId} 状态时发生错误: {str(e)}")
                update_results.append({
                    'planId': plan.planId,
                    'fundCode': plan.fundCode,
                    'fundName': plan.fundName,
                    'subAccountName': plan.subAccountName,
                    'success': False,
                    'message': f'更新失败: {str(e)}',
                    'buyStrategySwitch': buy_strategy_switch
                })
        
        # 统计更新结果
        success_count = sum(1 for result in update_results if result['success'])
        total_count = len(update_results)
        
        logger.info(f"批量更新完成，成功: {success_count}/{total_count}")
        
        return update_results
        
    except Exception as e:
        logger.error(f"批量更新基金 {fund_code} 定投计划状态时发生错误: {str(e)}")
        raise Exception(f"批量更新失败: {str(e)}")

def pause_all_fund_plans(user: User, fund_code: str) -> List[dict]:
    """
    暂停指定基金的所有定投计划
    
    Args:
        user: User对象，包含用户认证信息
        fund_code: 基金代码
        
    Returns:
        List[dict]: 更新结果列表
    """
    return batch_update_fund_plan_status(user, fund_code, False)

def resume_all_fund_plans(user: User, fund_code: str) -> List[dict]:
    """
    恢复指定基金的所有定投计划
    
    Args:
        user: User对象，包含用户认证信息
        fund_code: 基金代码
        
    Returns:
        List[dict]: 更新结果列表
    """
    return batch_update_fund_plan_status(user, fund_code, True)

# 测试函数
if __name__ == "__main__":
  
    
    # 示例用法
    user = DEFAULT_USER
    fund_code = "001595"  # 示例基金代码
    
    # # 暂停所有定投计划
    # print("暂停所有定投计划:")
    # pause_results = pause_all_fund_plans(user, fund_code)
    # for result in pause_results:
    #     print(f"计划ID: {result['planId']}, 基金: {result['fundName']}, 结果: {result['message']}")
    
    # 恢复所有定投计划
    print("\n恢复所有定投计划:")
    resume_results = resume_all_fund_plans(user, fund_code)
    for result in resume_results:
        print(f"计划ID: {result['planId']}, 基金: {result['fundName']}, 结果: {result['message']}")