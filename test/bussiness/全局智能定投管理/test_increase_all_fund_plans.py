import sys
import os
import logging

# 添加项目根目录到 sys.path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../'))
sys.path.insert(0, project_root)

from src.common.constant import DEFAULT_USER
from src.bussiness.全局智能定投处理.increase import increase_all_fund_plans

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_increase_all_fund_plans():
    logger.info("开始测试 increase_all_fund_plans 函数")
    
    # 调用函数进行加仓测试
    increase_all_fund_plans(DEFAULT_USER)
    
    # 验证是否正确执行
    logger.info("所有定投计划加仓操作已执行")
    logger.info("测试完成")

if __name__ == "__main__":
    test_increase_all_fund_plans()