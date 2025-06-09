import sys
import os
import logging
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
from src.API.定投计划管理.SmartPlan import createPlanV3,operateRation
from src.API.组合管理.SubAccountMrg import getSubAccountNoByName
from src.common.constant import (
    SERVER_VERSION, PAGE_SIZE, PASSPORT_CTOKEN, PLAN_TYPE,
    PASSPORT_UTOKEN, PHONE_TYPE, MOBILE_KEY, PAGE_INDEX,
    USER_ID, U_TOKEN, C_TOKEN, PASSPORT_ID, DEFAULT_USER
)


def create_period_smart_investment(user: User,fund_code: str, amount: int, period_type: int = 4, period_value: int = 1):
    """
    为组合创建基金定投计划
    
    Args:
        user: 用户对象
        fund_code: 基金代码
        amount: 定投金额
        period_type: 定投周期类型，默认为4（按日）
        period_value: 定投周期值，默认为1（每1周）
    
    Returns:
        API响应结果
    """
    # 获取该基金的所有定投计划
    existing_plans = getFundPlanList(fund_code, user)
    # 查找指定子账户名称的定投计划
    target_plan = None
    if existing_plans:
        for plan in existing_plans:
            try:
                detail_response = getPlanDetailPro(plan.planId, user)
            except Exception as e:
                 # 记录错误但继续处理其他计划
                print(f"获取计划 {plan.planId} 详情失败: {str(e)}")
            if  plan.planType == '1' and detail_response.Data.rationPlan.periodType == 4:
                # 如果计划类型为1（目标定投）且周期类型为4（按日）
                logger.info(f"基金 {plan.fundName}已存在智能定投每日定投计划")
                return None           
    # 调用现有的createPlanV3函数，硬编码strategy_type=3（组合定投）
    return createPlanV3(
        user=user,
        fund_code=fund_code,
        amount=str(amount),  # 转换为字符串
        period_type=period_type,
        period_value=str(period_value),
        sub_account_name= None,
        strategy_type= 0 # 硬编码为0，表示目标定投
    )


if __name__ == '__main__':
    # 配置logger
    logger = logging.getLogger("SmartPlan")
    logger.setLevel(logging.DEBUG)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    response = create_period_smart_investment(
        user=DEFAULT_USER,
        fund_code="021490",
        amount = "2000.0",  
        period_type = 4,
        period_value = 1
    )