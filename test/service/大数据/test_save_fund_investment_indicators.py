import pytest
import os
import sys
import logging


# 获取项目根目录路径
root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# 如果项目根目录不在Python路径中，则添加
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from src.service.大数据.加仓风向标服务 import save_fund_investment_indicators
from src.common.constant import DEFAULT_USER
from src.db.database_connection import DatabaseConnection
from datetime import datetime
from src.service.大数据.加仓风向标服务 import get_fund_investment_indicators
from src.service.大数据.加仓风向标服务 import process_fund_investment_indicators  # 确保导入
from src.db.fund_investment_indicator_repository_impl import FundInvestmentIndicatorRepositoryImpl  # 新增导入

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)8s] %(message)s (%(filename)s:%(lineno)d)')
logger = logging.getLogger(__name__)

def test_save_fund_investment_indicators_success():
    """测试 save_fund_investment_indicators 函数 - 成功案例，直接调用并验证数据库插入"""
    db = DatabaseConnection()
    # 先调用 process 获取预期数据
    indicators = process_fund_investment_indicators(DEFAULT_USER)
    if not indicators:
        assert False, "无数据返回"
    update_time = indicators[0].update_time
    update_date = datetime.strptime(update_time, '%Y-%m-%d %H:%M:%S').strftime('%Y-%m-%d')
    db.execute_query("DELETE FROM fund_investment_indicators WHERE update_date = %s", (update_date,))
    # 调用服务方法（会先补齐新增字段，再入库）
    save_fund_investment_indicators(DEFAULT_USER)
    # 验证数量
    results = db.execute_query("SELECT COUNT(*) AS cnt FROM fund_investment_indicators WHERE update_date = %s", (update_date,))
    count = results[0]['cnt'] if results else 0
    assert count == len(indicators), f"预期插入 {len(indicators)} 条，但实际 {count} 条"
    # 额外验证：抽样检查新增列是否已赋值（至少有一条非NULL）
    sample = db.execute_query("""
        SELECT fund_code, rank_100day, rank_30day, volatility, nav_5day_avg,
               season_item_rank, season_item_sc, month_item_rank, month_item_sc
        FROM fund_investment_indicators
        WHERE update_date = %s
        ORDER BY product_rank ASC
        LIMIT 5
    """, (update_date,))
    assert any(
        (row.get('rank_100day') is not None) or
        (row.get('rank_30day') is not None) or
        (row.get('volatility') is not None) or
        (row.get('nav_5day_avg') is not None) or
        (row.get('season_item_rank') is not None and row.get('season_item_sc') is not None) or
        (row.get('month_item_rank') is not None and row.get('month_item_sc') is not None)
        for row in (sample or [])
    ), "新增列均为NULL，请检查API赋值是否成功"
    # 直接使用仓库保存，以确保使用相同的 indicators
    repo = FundInvestmentIndicatorRepositoryImpl()
    repo.save_investment_indicators(indicators, update_date)
    # 验证
    results = db.execute_query("SELECT COUNT(*) FROM fund_investment_indicators WHERE update_date = %s", (update_date,))
    count = results[0]['COUNT(*)'] if results else 0
    assert count == len(indicators), f"预期插入 {len(indicators)} 条，但实际 {count} 条"
    logger.info(f"成功插入 {count} 条数据")
    # db.disconnect()


if __name__ == "__main__":
    test_save_fund_investment_indicators_success()