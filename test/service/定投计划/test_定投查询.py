import pytest
import os
import sys
import logging

# 获取项目根目录路径
root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# 如果项目根目录不在Python路径中，则添加
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

# 修改导入路径，使用正确的导入路径
from src.common.constant import DEFAULT_USER
from src.service.定投管理.定投查询.定投查询 import get_all_fund_plan_details
# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)8s] %(message)s (%(filename)s:%(lineno)d)')
logger = logging.getLogger(__name__)

def test_get_all_fund_plan_details():
    """测试获取所有定投计划详情"""
    # 打印测试开始信息
    logger.info("开始测试获取所有定投计划详情")
    
    # 调用函数获取所有定投计划详情
    plan_details = get_all_fund_plan_details(DEFAULT_USER)
    
    # 验证返回结果不为None
    assert plan_details is not None, "返回结果不应为None"
    
    # 验证返回结果是列表
    assert isinstance(plan_details, list), "返回结果应该是列表"
    
    # 如果有定投计划，验证每个计划的基本信息
    for detail in plan_details:
        # 验证计划对象存在
        assert detail is not None, "计划详情对象不应为None"
        
        # 验证计划基本属性
        plan = detail.rationPlan
        assert hasattr(plan, 'planId'), "计划应该有planId属性"
        assert hasattr(plan, 'fundCode'), "计划应该有fundCode属性"
        assert hasattr(plan, 'fundName'), "计划应该有fundName属性"
        
        # 打印计划详细信息
        logger.info("-" * 50)
        logger.info("基金基本信息:")
        logger.info(f"计划ID: {plan.planId}")
        logger.info(f"基金代码: {plan.fundCode}")
        logger.info(f"基金名称: {plan.fundName}")
        logger.info(f"基金类型: {plan.fundType}")
        
        logger.info("\n定投配置信息:")
        logger.info(f"定投周期类型: {plan.periodType}")
        logger.info(f"定投周期值: {plan.periodValue}")
        logger.info(f"定投金额: {plan.amount}")
        logger.info(f"定投状态: {plan.planState}")
        logger.info(f"定投扩展状态: {plan.planExtendStatus}")
  
        logger.info("\n收益信息:")
        logger.info(f"定投收益: {plan.rationProfit}")
        logger.info(f"总收益: {plan.totalProfit}")
        logger.info(f"定投收益率: {plan.rationProfitRate}")
        logger.info(f"总收益率: {plan.totalProfitRate}")
        logger.info(f"单位净值: {plan.unitPrice}")
        
        if hasattr(plan, 'targetRate') and plan.targetRate:
            logger.info(f"目标收益率: {plan.targetRate}")
        # 打印分隔线
        logger.info("-" * 50)
        logger.info("\n")
        
        # 如果有止盈目标，打印止盈信息
        if hasattr(plan, 'targetProfit'):
            logger.info(f"止盈目标: {plan.targetProfit}%")
            logger.info(f"当前收益率: {plan.currentProfit}%")

        
        logger.info("-" * 50)
    
    # 打印测试结果摘要
    logger.info(f"测试完成，共获取到 {len(plan_details)} 个定投计划")

if __name__ == "__main__":
    # 直接运行测试
    logger.info("直接运行定投计划查询测试")
    test_get_all_fund_plan_details()