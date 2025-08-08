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

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)8s] %(message)s (%(filename)s:%(lineno)d)')
logger = logging.getLogger(__name__)

user_list = [
    ("13918797997","Zj951103","Zj951103","仇晓钰","最优止盈",100000.0)
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
            result = add_new_funds(user, "最优止盈", user.budget)
            
            assert isinstance(result, bool), "返回结果应该是布尔值"
            logger.info(f"用户 {customer_name} 新增基金测试结果: {'成功' if result else '失败'}")
        except Exception as e:
            logger.error(f"处理用户 {customer_name} 失败，错误信息：{str(e)}")
            continue

if __name__ == "__main__":
    test_add_new_funds()