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
from src.service.交易管理.费率查询 import get_0_fee_shares

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)8s] %(message)s (%(filename)s:%(lineno)d)')
logger = logging.getLogger(__name__)

def test_get_0_fee_shares():
    """测试 get_0_fee_shares 函数"""
    # 打印测试开始信息
    logger.info("开始测试 get_0_fee_shares 函数")
    
    # 测试参数
    fund_code = "004855"
    
    # 调用函数获取0费率份额
    zero_fee_shares = get_0_fee_shares(DEFAULT_USER, fund_code)
    
    # 验证返回结果
    assert zero_fee_shares is not None, "返回结果不应为None"
    assert isinstance(zero_fee_shares, float), "返回结果应为浮点数类型"
    
    # 打印测试结果
    logger.info(f"获取到的0费率份额: {zero_fee_shares}")

if __name__ == "__main__":
    # 直接运行测试
    logger.info("直接运行0费率份额测试")
    test_get_0_fee_shares()