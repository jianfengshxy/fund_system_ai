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
from src.service.交易管理.交易查询 import get_withdrawable_trades

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)8s] %(message)s (%(filename)s:%(lineno)d)')
logger = logging.getLogger(__name__)

def test_get_withdrawable_trades():
    """测试 get_withdrawable_trades 函数"""
    # 打印测试开始信息
    logger.info("开始测试 get_withdrawable_trades 函数")
    
    # 调用函数获取可撤单交易列表
    trades = get_withdrawable_trades(DEFAULT_USER, sub_account_no='20891029', fund_code='018125')
    
    # 验证返回结果是列表
    assert isinstance(trades, list), "返回结果应该是列表"
    
    # 打印测试结果
    logger.info(f"获取到 {len(trades)} 条可撤单交易记录")

if __name__ == "__main__":
    # 直接运行测试
    logger.info("直接运行可撤单交易测试")
    test_get_withdrawable_trades()