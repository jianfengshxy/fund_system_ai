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
from src.common.errors import RetriableError, ValidationError
def get_all_fund_plan_details(user: User) -> List[FundPlanDetail]:
    """
    查询所有的定投计划并获取所有详情
    
    Args:
        user: User对象，包含用户认证信息
        
    Returns:
        List[FundPlanDetail]: 定投计划详情列表
    """
    # 获取所有定投计划,1是目标止盈,2是组合定投
    logger = get_logger("SmartPlanQuery")
    try:
        response = getFundRations(user, page_index=1, page_size=1000, planTypes=[1,2])
    except RetriableError as e:
        logger.warning(f"获取定投计划可重试: {e}", extra={"account": getattr(user,'mobile_phone',None) or getattr(user,'account',None), "action": "get_all_fund_plan_details"})
        return []
    except ValidationError as e:
        logger.error(f"获取定投计划解析错误: {e}", extra={"account": getattr(user,'mobile_phone',None) or getattr(user,'account',None), "action": "get_all_fund_plan_details"})
        return []
    
    if not response.Success or not response.Data:
        return []
        
    plan_details = []
    # 遍历每个计划获取详情
    for plan in response.Data:
        try:
            detail_response = getPlanDetailPro(plan.planId, user)
            if detail_response.Success and detail_response.Data:
                detail_response.Data.rationPlan.planType = plan.planType
                plan_details.append(detail_response.Data)
        except Exception as e:
            # 记录错误但继续处理其他计划
            logger.error(f"获取计划 {plan.planId} 详情失败: {str(e)}", extra={"account": getattr(user,'mobile_phone',None) or getattr(user,'account',None), "action": "get_all_fund_plan_details"})
            continue
            
    return plan_details


def get_target_profit_plan_details(user: User) -> List[FundPlanDetail]:
    """
    查询目标止盈定投计划并获取所有详情
    
    Args:
        user: User对象，包含用户认证信息
        
    Returns:
        List[FundPlanDetail]: 目标止盈定投计划详情列表
    """
    # 获取目标止盈定投计划,1是目标止盈
    logger = get_logger("SmartPlanQuery")
    try:
        response = getFundRations(user, page_index=1, page_size=1000, planTypes=[1])
    except RetriableError as e:
        logger.warning(f"获取目标止盈计划可重试: {e}", extra={"account": getattr(user,'mobile_phone',None) or getattr(user,'account',None), "action": "get_target_profit_plan_details"})
        return []
    except ValidationError as e:
        logger.error(f"获取目标止盈计划解析错误: {e}", extra={"account": getattr(user,'mobile_phone',None) or getattr(user,'account',None), "action": "get_target_profit_plan_details"})
        return []
    
    if not response.Success or not response.Data:
        return []
        
    plan_details = []
    # 遍历每个计划获取详情
    for plan in response.Data:
        try:
            detail_response = getPlanDetailPro(plan.planId, user)
            if detail_response.Success and detail_response.Data:
                detail_response.Data.rationPlan.planType = plan.planType
                plan_details.append(detail_response.Data)
        except Exception as e:
            # 记录错误但继续处理其他计划
            logger.error(f"获取目标止盈计划 {plan.planId} 详情失败: {str(e)}", extra={"account": getattr(user,'mobile_phone',None) or getattr(user,'account',None), "action": "get_target_profit_plan_details"})
            continue
            
    return plan_details


def get_portfolio_plan_details(user: User) -> List[FundPlanDetail]:
    """
    查询普通组合定投计划并获取所有详情
    
    Args:
        user: User对象，包含用户认证信息
        
    Returns:
        List[FundPlanDetail]: 普通组合定投计划详情列表
    """
    # 获取普通组合定投计划,2是组合定投
    logger = get_logger("SmartPlanQuery")
    try:
        response = getFundRations(user, page_index=1, page_size=1000, planTypes=[2])
    except RetriableError as e:
        logger.warning(f"获取组合定投计划可重试: {e}", extra={"account": getattr(user,'mobile_phone',None) or getattr(user,'account',None), "action": "get_portfolio_plan_details"})
        return []
    except ValidationError as e:
        logger.error(f"获取组合定投计划解析错误: {e}", extra={"account": getattr(user,'mobile_phone',None) or getattr(user,'account',None), "action": "get_portfolio_plan_details"})
        return []
    
    if not response.Success or not response.Data:
        return []
        
    plan_details = []
    # 遍历每个计划获取详情
    for plan in response.Data:
        try:
            detail_response = getPlanDetailPro(plan.planId, user)
            if detail_response.Success and detail_response.Data:
                detail_response.Data.rationPlan.planType = plan.planType
                plan_details.append(detail_response.Data)
        except Exception as e:
            # 记录错误但继续处理其他计划
            logger.error(f"获取组合定投计划 {plan.planId} 详情失败: {str(e)}", extra={"account": getattr(user,'mobile_phone',None) or getattr(user,'account',None), "action": "get_portfolio_plan_details"})
            continue
            
    return plan_details


if __name__ == '__main__':
    # 获取所有定投计划详情
    # details = get_all_fund_plan_details(DEFAULT_USER)
    # details = get_target_profit_plan_details(DEFAULT_USER)
    # 打印目标止盈计划详情
    # for detail in details:
    #     print(f"目标止盈计划 {detail.rationPlan.planId} 详情: {detail}")
    # print(details)
    # 打印普通组合定投计划详情
    portfolio_details = get_portfolio_plan_details(DEFAULT_USER)
    for detail in portfolio_details:
        print(f"普通组合定投计划 {detail.rationPlan.planId} 详情: {detail}")

import logging
from src.common.logger import get_logger
