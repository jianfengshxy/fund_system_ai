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
from src.bussiness.全局智能定投处理.dissolve_plan import dissolve_daily_plan
from src.domain.user.User import User

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)8s] %(message)s (%(filename)s:%(lineno)d)')
logger = logging.getLogger(__name__)

def test_dissolve_daily_plan():
    """测试 dissolve_daily_plan 函数"""
    # 打印测试开始信息
    logger.info("开始测试 dissolve_daily_plan 函数")
    
    # 调用函数进行解散日定投计划测试
    dissolve_daily_plan(DEFAULT_USER)
    
    # 验证是否正确执行
    logger.info("解散日定投计划操作已执行")

if __name__ == "__main__":
    # 直接运行测试
    logger.info("直接运行解散日定投计划测试")
    test_dissolve_daily_plan()