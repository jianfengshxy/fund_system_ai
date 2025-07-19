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

from src.API.定投计划管理.SmartPlan import getPlanDetailPro
from src.domain.fund_plan import ApiResponse
from src.domain.fund_plan.fund_plan_detail import FundPlanDetail  # 修改为直接从子模块导入
from src.common.constant import DEFAULT_USER

def test_get_plan_detail_pro_success():
    logger = logging.getLogger("TestGetPlanDetailPro")
    logger.info("开始测试 getPlanDetailPro 函数")
    
    # 假设的用户和计划ID（根据实际上下文替换）
    user = DEFAULT_USER  # 或从 fixture 获取
    plan_id = "ad31e43fbf1e4715a0b9989ba222d8c3"  # 示例计划ID，根据需要调整
    
    result = getPlanDetailPro(plan_id, user)
    
    logger.info(f"getPlanDetailPro 返回结果类型: {type(result)}")
    logger.info(f"返回数据: {result}")  # 假设 result 是 ApiResponse，可以进一步打印 Data 等字段
    
    # 断言验证
    assert isinstance(result, ApiResponse), "返回结果应为 ApiResponse 类型"
    assert result.Success, "API 调用应成功"
    assert isinstance(result.Data, FundPlanDetail), "Data 字段应为 FundPlanDetail 实例"
    
    logger.info("测试 getPlanDetailPro 函数成功")

if __name__ == "__main__":
    test_get_plan_detail_pro_success()