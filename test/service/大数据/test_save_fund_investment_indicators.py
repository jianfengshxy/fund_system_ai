import pytest
import os
import sys
import logging

# 获取项目根目录路径
root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# 如果项目根目录不在Python路径中，则添加
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from src.service.大数据.加仓风向标服务 import save_fund_investment_indicators, process_fund_investment_indicators
from src.common.constant import DEFAULT_USER
from src.db.database_connection import DatabaseConnection
from datetime import datetime

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)8s] %(message)s (%(filename)s:%(lineno)d)')
logger = logging.getLogger(__name__)

def test_save_fund_investment_indicators_success():
    """测试 save_fund_investment_indicators 函数 - 成功案例，直接调用并验证数据库插入"""
    db = DatabaseConnection()
    # 先获取数据以提取 update_date
    indicators = process_fund_investment_indicators(DEFAULT_USER)
    if not indicators:
        assert False, "无数据返回"
    update_time = indicators[0].update_time
    update_date = datetime.strptime(update_time, '%Y-%m-%d %H:%M:%S').strftime('%Y-%m-%d')
    # 清理指定日期的数据
    db.execute_query("DELETE FROM fund_investment_indicators WHERE update_date = %s", (update_date,))
    # 调用函数
    save_fund_investment_indicators(DEFAULT_USER)
    # 验证
    results = db.execute_query("SELECT COUNT(*) FROM fund_investment_indicators WHERE update_date = %s", (update_date,))
    count = results[0]['COUNT(*)'] if results else 0
    assert count == len(indicators), f"预期插入 {len(indicators)} 条，但实际 {count} 条"
    logger.info(f"成功插入 {count} 条数据")
    db.disconnect()

def test_save_fund_investment_indicators_no_data():
    """测试无数据情况（如果适用，根据实际函数行为调整）"""
    # 此测试可能需要修改函数或环境以模拟无数据
    pass  # 如果函数总是返回数据，则跳过或调整

if __name__ == "__main__":
    test_save_fund_investment_indicators_success()