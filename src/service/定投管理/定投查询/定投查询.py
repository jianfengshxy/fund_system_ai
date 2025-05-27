from typing import List
from src.domain.fund_plan.fund_plan_detail import FundPlanDetail
from src.API.定投计划管理.SmartPlan import getFundRations, getPlanDetailPro
from src.domain.user.User import User

def get_all_fund_plan_details(user: User) -> List[FundPlanDetail]:
    """
    查询所有的定投计划并获取所有详情
    
    Args:
        user: User对象，包含用户认证信息
        
    Returns:
        List[FundPlanDetail]: 定投计划详情列表
    """
    # 获取所有定投计划
    response = getFundRations(user, page_index=1, page_size=1000, planTypes=[1,2])
    
    if not response.Success or not response.Data:
        return []
        
    plan_details = []
    # 遍历每个计划获取详情
    for plan in response.Data:
        try:
            detail_response = getPlanDetailPro(plan.planId, user)
            if detail_response.Success and detail_response.Data:
                plan_details.append(detail_response.Data)
        except Exception as e:
            # 记录错误但继续处理其他计划
            print(f"获取计划 {plan.planId} 详情失败: {str(e)}")
            continue
            
    return plan_details
