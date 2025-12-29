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
from src.domain.fund_plan.fund_plan_detail import FundPlanDetail
from src.domain.user.User import User
from src.API.定投计划管理.SmartPlan import getFundRations, getPlanDetailPro
from src.bussiness.最优止盈组合.increase import increase
from src.service.用户管理.用户信息 import get_user_all_info
from index import increase as increase_handler
import json

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)8s] %(message)s (%(filename)s:%(lineno)d)')
logger = logging.getLogger(__name__)

def test_increase():
    """测试 increase 函数"""
    # 打印测试开始信息
    logger.info("开始测试最优止盈的increase函数")
   
    
    # 调用函数进行加仓测试
    user = get_user_all_info("13500819290","guojing1985")
    user.budget = 200000.0
    result = increase(DEFAULT_USER, "飞龙在天")
    
    # 验证返回结果是布尔值
    assert isinstance(result, bool), "返回结果应该是布尔值"
    
    # 打印测试结果
    logger.info(f"加仓测试结果: {'成功' if result else '失败'}")

def test_increase_event_success():
    """测试 index.increase 函数 (Event Handler)"""
    # 使用提供的 payload 制造 event
    payload = {
        "account": "13918199137",
        "password": "sWX15706",
        "sub_account_name": "飞龙在天",
        "total_budget": 1000000.0,
        "amount": 10000.0,
        "fund_type": "all"
    }
    event = {'payload': json.dumps(payload)}
    context = None  # 可以根据需要模拟 context，如果不需要则设为 None
    
    # 直接调用 increase 函数
    increase_handler(event, context)

def test_increase_missing_params():
    """测试 index.increase 函数缺少参数的情况"""
    # 测试缺少参数的情况
    payload = {
        "account": "13918199137",
        "password": "sWX15706",
        # 缺少 sub_account_name 和 total_budget
    }
    event = {'payload': json.dumps(payload)}
    context = None
    
    # 直接调用 increase 函数
    increase_handler(event, context)

if __name__ == "__main__":
    # 直接运行测试
    logger.info("直接运行止盈测试")
    test_increase()
    # test_increase_event_success()
    