import sys
import os
from typing import List

# 添加项目根目录到Python路径
sys.path.append(os.path.join(os.path.dirname(__file__), '../../../../'))

from src.domain.fund_plan.fund_plan_detail import FundPlanDetail
from src.API.定投计划管理.SmartPlan import getRationCreateParameters, getPlanDetailPro
from src.domain.user.User import User
from src.common.constant import (
    SERVER_VERSION, PAGE_SIZE, PASSPORT_CTOKEN, PLAN_TYPE,
    PASSPORT_UTOKEN, PHONE_TYPE, MOBILE_KEY, PAGE_INDEX,
    USER_ID, U_TOKEN, C_TOKEN, PASSPORT_ID, DEFAULT_USER
)
from src.API.定投计划管理.SmartPlan import getFundRations

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

if __name__ == '__main__':
    # 获取所有定投计划详情
    details = get_all_fund_plan_details(DEFAULT_USER)
    print(details)