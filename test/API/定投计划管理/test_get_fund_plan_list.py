import pytest
import requests
import os
import sys
import logging

# 配置 logging 以输出到控制台
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

# 获取项目根目录路径
root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# 如果项目根目录不在Python路径中，则添加
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from src.API.定投计划管理.SmartPlan import getFundPlanList
from src.domain.fund_plan import ApiResponse, FundPlanResponse, PageInfo, FundPlan
from src.common.constant import DEFAULT_USER, FUND_CODE
from src.API.登录接口.login import inference_passport_for_bind, login

def test_get_fund_plan_list_success():
    logger = logging.getLogger("TestGetFundPlanList")
    logger.info("开始测试 getFundPlanList 函数")
    
    # 假设的用户和基金代码（根据实际上下文替换）
    user = DEFAULT_USER  # 或从 fixture 获取
    fund_code = "021740"  # 示例基金代码，根据需要调整
    
    result = getFundPlanList(fund_code, user)
    
    logger.info(f"getFundPlanList 返回结果类型: {type(result)}")
    logger.info(f"返回列表长度: {len(result)}")
    
    # 详细打印每个计划的信息
    for plan in result:
        logger.info(f"Plan ID: {plan.planId}, Fund Code: {plan.fundCode}, , Fund Name: {plan.fundName} , State: {plan.planState}, Amount: {plan.amount}")
    
    # 断言验证
    assert isinstance(result, list), "返回结果应为列表类型"
    assert len(result) > 0, "返回列表不应为空（假设有数据）"
    for item in result:
        assert isinstance(item, FundPlan), "列表中每个元素应为 FundPlan 实例"
    
    logger.info("测试 getFundPlanList 函数成功")

if __name__ == "__main__":
    test_get_fund_plan_list_success()