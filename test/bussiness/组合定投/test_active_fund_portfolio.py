import sys
import os
import logging

# 添加项目根目录到 sys.path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../'))
sys.path.insert(0, project_root)

from src.common.constant import DEFAULT_USER
from src.service.用户管理.用户信息 import get_user_all_info
from src.bussiness.组合定投.主动型组合定投管理 import create_plan_by_group, dissolve_plan_by_group

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_create_plan_by_group():
    logger.info("开始测试 create_plan_by_group 函数")
    
    # 第一步：获取用户全部信息
    account = DEFAULT_USER.account
    password = DEFAULT_USER.password
    user = get_user_all_info(account, password)
    logger.info(f"获取用户: {user.customer_name if user else '获取失败'}")
    assert user is not None, "获取用户失败"
    
    # 第二步：调用创建定投计划函数
    sub_account_name = "低风险组合"  # 根据主动型示例调整
    budget = 1000000.0
    investment_amount = 10000.0  # 根据函数参数调整
    create_plan_by_group(user, sub_account_name, budget, investment_amount)
    
    # 这里可以添加更多断言，依赖日志验证
    logger.info("测试完成")

def test_dissolve_plan_by_group():
    logger.info("开始测试 dissolve_plan_by_group 函数")
    
    # 第一步：获取用户全部信息
    account = DEFAULT_USER.account
    password = DEFAULT_USER.password
    user = get_user_all_info(account, password)
    logger.info(f"获取用户: {user.customer_name if user else '获取失败'}")
    assert user is not None, "获取用户失败"
    
    # 第二步：调用解散定投计划函数
    sub_account_name = "低风险组合"
    budget = 1000000.0
    dissolve_plan_by_group(user, sub_account_name, budget)
    
    # 这里可以添加更多断言，依赖日志验证
    logger.info("测试完成")

if __name__ == "__main__":
    # test_create_plan_by_group()
    test_dissolve_plan_by_group()