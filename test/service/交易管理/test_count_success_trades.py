import os
import sys
import logging
import pytest
from datetime import datetime

# 获取项目根目录路径
root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# 如果项目根目录不在Python路径中，则添加
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from src.service.交易管理.交易查询 import count_success_trades_on_prev_nav_day
from src.common.constant import DEFAULT_USER

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_count_success_trades():
    """测试统计成功交易数量"""
    # 打印测试开始信息
    logger.info("开始测试统计成功交易数量")
    
    # 调用函数统计成功交易数量
    # 这里可以根据实际情况传入基金代码和子账户编号
    fund_code = "015968" # 可以填入实际的基金代码
    sub_account_no = "20891029" # 可以填入实际的子账户编号
    
    result = count_success_trades_on_prev_nav_day(DEFAULT_USER, fund_code, sub_account_no)
    
    # 打印结果
    logger.info(f"统计到的成功交易数量: {result}")
    
    # 验证结果
    assert isinstance(result, int), "返回结果应为整数类型"
    assert result >= 0, "返回结果应大于等于0"
    
    logger.info("测试完成")

if __name__ == "__main__":
    # 直接运行测试
    test_count_success_trades()