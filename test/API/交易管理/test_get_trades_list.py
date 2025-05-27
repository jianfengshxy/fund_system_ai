import pytest
import os
import sys
import logging

# 获取项目根目录路径
root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# 如果项目根目录不在Python路径中，则添加
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from src.API.交易管理.trade import get_trades_list
from src.common.constant import DEFAULT_USER

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_get_withdrawable_trades_success():
    """测试成功获取可撤单交易列表"""
    # 打印测试开始信息
    logger.info("开始测试获取可撤单交易列表")
    
    # 调用函数获取可撤单交易列表
    result = get_trades_list(DEFAULT_USER)
    
    # 打印结果信息
    logger.info(f"获取到 {len(result)} 条交易记录")
    
    # 打印所有交易记录的详细信息，格式美观
    for i, trade in enumerate(result):
        logger.info(f"\n{'='*50}")
        logger.info(f"交易记录 {i+1} 详细信息:")
        logger.info(f"{'-'*50}")
        logger.info(f"交易ID(busin_serial_no): {trade.busin_serial_no}")
        logger.info(f"业务类型(business_type): {trade.business_type}")
        logger.info(f"申请工作日(apply_work_day): {trade.apply_work_day}")
        logger.info(f"申请金额/份额(amount): {trade.amount}")
        logger.info(f"交易状态(status): {trade.status}")
        logger.info(f"显示属性(show_com_prop): {trade.show_com_prop}")
        logger.info(f"基金代码(fund_code): {trade.fund_code}")
        logger.info(f"{'='*50}")
    
    # 验证结果
    assert result is not None, "返回结果不应为None"
    assert isinstance(result, list), "返回结果应为列表类型"
    
    # 如果有交易记录，验证第一条记录的结构
    if len(result) > 0:
        trade = result[0]
        assert hasattr(trade, 'busin_serial_no'), "交易记录应有busin_serial_no属性"
        assert hasattr(trade, 'business_type'), "交易记录应有business_type属性"
        assert hasattr(trade, 'apply_work_day'), "交易记录应有apply_work_day属性"
        assert hasattr(trade, 'amount'), "交易记录应有amount属性"
        assert hasattr(trade, 'status'), "交易记录应有status属性"
        assert hasattr(trade, 'show_com_prop'), "交易记录应有show_com_prop属性"
        assert hasattr(trade, 'fund_code'), "交易记录应有fund_code属性"
        
        logger.info("交易记录结构验证通过")
    
    logger.info("测试完成")