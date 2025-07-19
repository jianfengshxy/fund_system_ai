import sys
import os
import logging
from time import sleep
import urllib.parse
import urllib3
import warnings
import hashlib
import requests
from urllib.parse import quote_plus
from typing import Dict, Any, Optional, Union

# 添加项目根目录到路径
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))
sys.path.insert(0, project_root)

# 然后进行其他导入
from src.domain.fund_plan import ApiResponse, FundPlanResponse, PageInfo, FundPlan
from src.domain.fund_plan.fund_plan_detail import FundPlanDetail
from src.domain.fund_plan import RationCreateParameters, DiscountRate
from src.domain.trade.share import Share
from src.domain.user.User import User
from src.API.定投计划管理.SmartPlan import getFundRations, getPlanDetailPro,getFundPlanList
from src.bussiness.最优止盈组合.increase import increase
from src.API.定投计划管理.SmartPlan import createPlanV3, operateRation
from src.API.组合管理.SubAccountMrg import getSubAccountNoByName
from src.common.constant import (
    SERVER_VERSION, PAGE_SIZE, PASSPORT_CTOKEN, PLAN_TYPE,
    PASSPORT_UTOKEN, PHONE_TYPE, MOBILE_KEY, PAGE_INDEX,
    USER_ID, U_TOKEN, C_TOKEN, PASSPORT_ID, DEFAULT_USER
)

# 配置logger
logger = logging.getLogger("SmartPlan")
logger.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
console_handler = logging.StreamHandler()
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)


def create_period_investment_by_group(user: User, sub_account_name: str, fund_code: str, amount: int, period_type: int = 4, period_value: int = 1):
    """
    为组合创建基金定投计划
    
    Args:
        user: 用户对象
        sub_account_name: 子账户名称（组合名称）
        fund_code: 基金代码
        amount: 定投金额
        period_type: 定投周期类型，默认为4（按日）
        period_value: 定投周期值，默认为1（每1周）
    
    Returns:
        API响应结果
    """
    # 检查该基金是否已有定投计划
    existing_plans = getFundPlanList(fund_code, user)
    
    # 检查是否已存在相同子账户名称的定投计划
    if existing_plans:  # 直接检查列表是否为空
        # 遍历返回的计划列表
        for plan in existing_plans:  # 直接遍历FundPlan对象列表
            if plan.subAccountName == sub_account_name:
                # 如果已存在相同子账户名称的定投计划，返回错误信息
                logger.info(f"基金 {plan.fundName} 在子账户 '{sub_account_name}' 中已存在定投计划")
                return None
    
    
    # 调用现有的createPlanV3函数，硬编码strategy_type=3（组合定投）
    return createPlanV3(
        user=user,
        fund_code=fund_code,
        amount=str(amount),  # 转换为字符串
        period_type=period_type,
        period_value=str(period_value),  # 转换为字符串
        sub_account_name=sub_account_name,
        strategy_type=3  # 硬编码为3，表示组合定投
    )

def dissolve_period_investment_by_group(user: User, sub_account_name: str, fund_code: str):
    """
    解散指定组合的基金定投计划
    
    Args:
        user: 用户对象
        sub_account_name: 子账户名称（组合名称）
        fund_code: 基金代码
    
    Returns:
        API响应结果或None（如果未找到对应的定投计划）
    """
    # 获取该基金的所有定投计划
    existing_plans = getFundPlanList(fund_code, user)
    
    # 查找指定子账户名称的定投计划
    target_plan = None
    if existing_plans:
        for plan in existing_plans:
            if plan.subAccountName == sub_account_name:
                target_plan = plan
                break
    if target_plan is None:
        logger.info(f"基金 {fund_code} 在子账户 '{sub_account_name}' 中未找到定投计划")
        return None
    plan_assets = target_plan.planAssets
    if plan_assets is not None and plan_assets != 0.0:
        logger.info(f"基金 {fund_code} 在子账户 '{sub_account_name}'资产不为空:{plan_assets}")
        return None
    logger.info(f"基金 {target_plan.fundName} 在子账户 '{sub_account_name}'解散定投")
    # 调用operateRation函数，硬编码operation="2"（解散）
    return operateRation(
        user=user,
        plan_id=target_plan.planId,
        operation="2"  # 硬编码为"2"，表示解散计划
    )

if __name__ == '__main__':
    
    response = create_period_investment_by_group(
        user=DEFAULT_USER,
        fund_code="021490",
        amount= "2000.0",  
        period_type=4,
        period_value=1,  # 修改为整数
        sub_account_name="低风险组合"
    )
    sleep(10)
    # dissolve_period_investment_by_group(
    #     user=DEFAULT_USER,
    #     sub_account_name="最优止盈", 
    #      fund_code="021490")