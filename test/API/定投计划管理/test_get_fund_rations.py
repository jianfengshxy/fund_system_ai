import pytest
import requests
from unittest.mock import patch, MagicMock
import os
import sys
import logging

# 获取项目根目录路径
root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# 如果项目根目录不在Python路径中，则添加
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from src.API.定投计划管理.SmartPlan import getFundRations
from src.domain.fund_plan import ApiResponse, FundPlan
from src.common.constant import DEFAULT_USER

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_get_regular_portfolio_plans_success():
    logger.info("开始测试获取普通组合定投计划列表")
    
    result = getFundRations(user=DEFAULT_USER,page_index=1, page_size=1000, planTypes=[2])
    logger.info(f"API响应结果类型: {type(result)}")
    logger.info(f"API响应成功: {result.Success}")
    logger.info(f"API响应数据列表长度: {len(result.Data) if result.Data else 0}")
    
    assert isinstance(result, ApiResponse)
    assert result.Success == True
    assert isinstance(result.Data, list)
    logger.info("基本响应数据验证通过")
    
    if len(result.Data) > 0:
        for plan in result.Data:
            assert isinstance(plan, FundPlan)
            logger.info(f"计划详情: planId={plan.planId}, fundCode={plan.fundCode}, fundName={plan.fundName}, planState={plan.planState}, planType={plan.planType}, amount={plan.amount}, nextDeductDate={plan.nextDeductDate}")
        logger.info("所有计划数据验证通过")
    else:
        logger.info("未找到任何定投计划数据")

def test_get_target_profit_plans_success():
    logger.info("开始测试获取目标止盈定投计划列表")
    
    result = getFundRations(user=DEFAULT_USER, page_index=1, page_size=1000, planTypes=[1])
    logger.info(f"API响应结果类型: {type(result)}")
    logger.info(f"API响应成功: {result.Success}")
    logger.info(f"API响应数据列表长度: {len(result.Data) if result.Data else 0}")
    
    assert isinstance(result, ApiResponse)
    assert result.Success == True
    assert isinstance(result.Data, list)
    logger.info("基本响应数据验证通过")
    
    if len(result.Data) > 0:
        for plan in result.Data:
            assert isinstance(plan, FundPlan)
            logger.info(f"计划详情: planId={plan.planId}, fundCode={plan.fundCode}, fundName={plan.fundName}, planState={plan.planState}, planType={plan.planType}, amount={plan.amount}, nextDeductDate={plan.nextDeductDate}")
        logger.info("所有计划数据验证通过")
    else:
        logger.info("未找到任何定投计划数据")


if __name__ == "__main__":
    test_get_regular_portfolio_plans_success()
    test_get_target_profit_plans_success()