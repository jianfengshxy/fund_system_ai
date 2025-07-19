import sys
import os
import logging

# 添加项目根目录到 sys.path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../'))
sys.path.insert(0, project_root)

from src.common.constant import DEFAULT_USER
from src.bussiness.全局智能定投处理.dissolve_plan import dissolve_daily_plan

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_dissolve_daily_plan():
    logger.info("开始测试 dissolve_daily_plan 函数")
    
    # 调用函数进行解散日定投计划测试
    dissolve_daily_plan(DEFAULT_USER)
    
    # 验证是否正确执行
    logger.info("解散日定投计划操作已执行")
    logger.info("测试完成")

if __name__ == "__main__":
    test_dissolve_daily_plan()