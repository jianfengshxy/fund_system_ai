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
from src.common.constant import DEFAULT_USER, DEFAULT_FUND_PLAN_DETAIL
from src.bussiness.全局智能定投处理.increase import increase
from src.domain.fund_plan.fund_plan_detail import FundPlanDetail
from src.domain.user.User import User
from src.API.定投计划管理.SmartPlan import getFundRations, getPlanDetailPro

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)8s] %(message)s (%(filename)s:%(lineno)d)')
logger = logging.getLogger(__name__)

def test_increase():
    """测试 increase 函数"""
    # 打印测试开始信息
    logger.info("开始测试 increase 函数")
    plan_id = '1283860a7d174e2dafff90aae1530ad8'
    
    # 调用函数进行加仓测试
    detail_response = getPlanDetailPro(plan_id, DEFAULT_USER)
    if detail_response.Success and detail_response.Data:
            plan_detail = detail_response.Data
    result = increase(DEFAULT_USER, plan_detail)
    
    # 验证返回结果是布尔值
    assert isinstance(result, bool), "返回结果应该是布尔值"
    
    # 打印测试结果
    logger.info(f"加仓测试结果: {'成功' if result else '失败'}")

if __name__ == "__main__":
    # 直接运行测试
    logger.info("直接运行加仓测试")
    test_increase()