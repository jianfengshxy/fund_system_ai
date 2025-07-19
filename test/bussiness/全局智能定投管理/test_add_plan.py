import sys
import os
import logging

# 添加项目根目录到 sys.path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../'))
sys.path.insert(0, project_root)

from src.common.constant import DEFAULT_USER
from src.bussiness.全局智能定投处理.add_plan import add_plan

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_add_plan():
    logger.info("开始测试 add_plan 函数")
    
    # 调用函数进行添加定投计划测试
    add_plan(DEFAULT_USER)
    
    # 验证是否正确执行
    logger.info("添加定投计划操作已执行")
    logger.info("测试完成")

def test_add_plan_with_custom_amount():
    logger.info("开始测试 add_plan 函数 - 自定义金额")
    
    # 调用函数进行添加定投计划测试，使用自定义金额
    add_plan(DEFAULT_USER, amount=3000)
    
    # 验证是否正确执行
    logger.info("添加定投计划操作已执行 - 自定义金额3000")
    logger.info("测试完成")

if __name__ == "__main__":
    test_add_plan_with_custom_amount()