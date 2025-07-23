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

def test_add_new_funds():
    """测试 add_new_funds 函数"""
    # 打印测试开始信息
    logger.info("开始测试最优止盈的add_new_funds函数")
    
    # 调用函数进行新增基金测试
    user = get_user_all_info("13500819290", "guojing1985")
    user.budget = 200000.0
    result = add_new_funds(user, "最优止盈", 10000.0)
    
    # 验证返回结果是布尔值
    assert isinstance(result, bool), "返回结果应该是布尔值"
    
    # 打印测试结果
    logger.info(f"新增基金测试结果: {'成功' if result else '失败'}")

if __name__ == "__main__":
    # 直接运行测试
    logger.info("直接运行新增基金测试")
    test_add_new_funds()