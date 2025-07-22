import sys
import os
import logging
# 添加项目根目录到 sys.path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../'))
sys.path.insert(0, project_root)

from src.common.constant import DEFAULT_USER
from src.service.用户管理.用户信息 import get_user_all_info
from src.bussiness.组合定投.指数型组合定投管理 import create_plan_by_group_for_index_funds, dissolve_plan_by_group_for_index_funds

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_create_plan_by_group_for_index_funds():
    logger.info("开始测试 create_plan_by_group_for_index_funds 函数")
    
    # 第一步：获取用户全部信息
    # account = "13500819290"
    account = DEFAULT_USER.account
    # password = "guojing1985"
    password = DEFAULT_USER.password
    user = get_user_all_info(account, password)
    logger.info(f"获取用户: {user.customer_name if user else '获取失败'}")
    assert user is not None, "获取用户失败"
    
    # 第二步：调用创建定投计划函数
    sub_account_name = "指数基金组合"
    investment_amount = 2000.0
    budget = 500000.0
    create_plan_by_group_for_index_funds(user, sub_account_name,budget,investment_amount)
    
    # 这里可以添加更多断言，例如检查是否创建了计划，但由于函数无返回值，依赖日志验证
    logger.info("测试完成")

def test_dissolve_plan_by_group_for_index_funds():
    logger.info("开始测试 dissolve_plan_by_group_for_index_funds 函数")
    
    # 第一步：获取用户全部信息
    account = DEFAULT_USER.account
    password = DEFAULT_USER.password
    user = get_user_all_info(account, password)
    logger.info(f"获取用户: {user.customer_name if user else '获取失败'}")
    assert user is not None, "获取用户失败"
    
    # 第二步：调用解散定投计划函数
    sub_account_name = "指数基金组合"
    budget = 200000.0
    dissolve_plan_by_group_for_index_funds(user, sub_account_name, budget)
    
    # 这里可以添加更多断言，依赖日志验证
    logger.info("测试完成")

if __name__ == "__main__":
    # test_create_plan_by_group_for_index_funds()
    test_dissolve_plan_by_group_for_index_funds()