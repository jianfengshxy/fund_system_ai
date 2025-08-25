import sys
import os
import logging

# 添加项目根目录到 sys.path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../'))
sys.path.insert(0, project_root)

from src.common.constant import DEFAULT_USER
from src.bussiness.全局智能定投处理.increase import increase
from src.API.定投计划管理.SmartPlan import getPlanDetailPro

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_increase():
    logger.info("开始测试 increase 函数")
    
    plan_id = '9e734772aa664c52b1564647bed84b5b'
    
    # 调用函数进行加仓测试
    detail_response = getPlanDetailPro(plan_id, DEFAULT_USER)
    if detail_response.Success and detail_response.Data:
        plan_detail = detail_response.Data
        result = increase(DEFAULT_USER, plan_detail)
        
        # 验证返回结果是布尔值
        if not isinstance(result, bool):
            logger.error("返回结果不是布尔值")
            return
        
        # 打印测试结果
        logger.info(f"加仓测试结果: {'成功' if result else '失败'}")
    else:
        logger.error("获取计划详情失败")

if __name__ == "__main__":
    test_increase()