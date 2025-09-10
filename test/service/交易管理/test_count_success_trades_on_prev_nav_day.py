import pytest
import os
import sys
import logging

# 获取项目根目录路径
root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# 如果项目根目录不在Python路径中，则添加
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from src.common.constant import DEFAULT_USER
from src.service.交易管理.交易查询 import count_success_trades_on_prev_nav_day

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)8s] %(message)s (%(filename)s:%(lineno)d)')
logger = logging.getLogger(__name__)

def test_count_success_trades_on_prev_nav_day():
    """测试 count_success_trades_on_prev_nav_day 函数"""
    # 打印测试开始信息
    logger.info("开始测试 count_success_trades_on_prev_nav_day 函数")

    # 测试参数
    fund_code = "018123"

    # 调用函数统计上一交易日成功交易数量（排除撤回）
    count = count_success_trades_on_prev_nav_day(DEFAULT_USER, fund_code,'015968')

    # 验证返回结果类型
    assert isinstance(count, int), "返回结果应该是整数"

    # 打印测试结果
    logger.info(f"基金 {fund_code} 上一交易日成功交易数量（排除撤回）: {count}")

if __name__ == "__main__":
    # 直接运行测试
    logger.info("直接运行 count_success_trades_on_prev_nav_day 测试")
    test_count_success_trades_on_prev_nav_day()