import pytest
import os
import sys
import logging

# 获取项目根目录路径
root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# 如果项目根目录不在Python路径中，则添加
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from src.service.用户管理.用户信息 import get_user_all_info
from src.bussiness.最优止盈组合.add_new import add_new_funds
from src.common.constant import DEFAULT_USER
from index import add_new
import json

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)8s] %(message)s (%(filename)s:%(lineno)d)')
logger = logging.getLogger(__name__)

user_list = [
    ("13918199137","sWX15706","sWX15706","施小雨","飞龙在天",1000000.0)
]

def test_add_new_funds():
    """测试 add_new_funds 函数"""
    logger.info("开始测试最优止盈的add_new_funds函数")
    
    # 遍历user_list中的用户数据
    for user_info in user_list:
        account = user_info[0]
        password = user_info[1]
        customer_name = user_info[3]
        budget = user_info[5]
        
        try:
            user = get_user_all_info(account, password)
            user.budget = budget
            result = add_new_funds(user, "指数基金组合", user.budget,20000,fund_type='index')
            
            assert isinstance(result, bool), "返回结果应该是布尔值"
            logger.info(f"用户 {customer_name} 新增基金测试结果: {'成功' if result else '失败'}")
        except Exception as e:
            logger.error(f"处理用户 {customer_name} 失败，错误信息：{str(e)}")
            continue

if __name__ == "__main__":
    test_add_new_funds()

def test_add_new_event_success():
    """测试 index.add_new 函数 (Event Handler)"""
    logger.info("开始测试 index.add_new (Event Handler)")
    # 使用提供的 payload 制造 event
    payload = {
        "account": "13918199137",
        "password": "sWX15706",
        "sub_account_name": "飞龙在天",
        "total_budget": 1000000.0,
        "amount": 50000.0,
        "fund_type": "non_index"
    }
    event = {'payload': json.dumps(payload)}
    context = None  # 可以根据需要模拟 context，如果不需要则设为 None
    
    # 直接调用 add_new 函数
    add_new(event, context)