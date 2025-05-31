import pytest
import os
import sys
import logging
import threading

# 获取项目根目录路径
root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# 将 code 目录添加到 Python 路径中
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

# 修改导入路径，使用正确的导入路径
from src.common.constant import DEFAULT_USER
from src.domain.user.User import User
from src.bussiness.最优止盈组合.increase import increase_all_users

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)8s] %(message)s (%(filename)s:%(lineno)d)')
logger = logging.getLogger(__name__)

def test_increase_all_users():
    """测试 increase_all_users 函数"""
    # 打印测试开始信息
    logger.info("开始测试 increase_all_users 函数")
    
    # 调用函数进行批量止盈测试
    increase_all_users()
    
    # 验证是否正确执行
    logger.info("所有定投计划止盈操作已执行")

if __name__ == "__main__":
    # 直接运行测试
    logger.info("直接运行施小雨所有定投计划止盈测试")
    test_increase_all_users()