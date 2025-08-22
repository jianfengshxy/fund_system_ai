import pytest
import os
import sys
from typing import List

# 获取项目根目录路径
root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# 如果项目根目录不在Python路径中，则添加
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from src.service.大数据.加仓风向标服务 import get_fund_investment_indicators
from src.domain.fund.fund_investment_indicator import FundInvestmentIndicator
from src.db.database_connection import DatabaseConnection  # 新增导入
from datetime import datetime  # 新增导入，如果需要格式化日期

def test_get_fund_investment_indicators_default():
    indicators = get_fund_investment_indicators()
    assert isinstance(indicators, List)
    assert all(isinstance(ind, FundInvestmentIndicator) for ind in indicators)
    # 添加更多断言，根据预期
    print(f"Retrieved {len(indicators)} frequent indicators with default params")

def test_get_fund_investment_indicators_custom():
    indicators = get_fund_investment_indicators(days=10, threshold=3)
    assert isinstance(indicators, List)
    assert all(isinstance(ind, FundInvestmentIndicator) for ind in indicators)
    # 添加更多断言，根据预期
    print(f"Retrieved {len(indicators)} frequent indicators with custom params")
    # 新增: 打印返回的基金详情，包括出现次数和日期
    db = DatabaseConnection()  # 初始化数据库连接
    for i, ind in enumerate(indicators, 1):
        # 查询出现次数
        count_query = "SELECT COUNT(*) as count FROM fund_investment_indicators WHERE fund_code = %s AND update_date >= DATE_SUB(CURDATE(), INTERVAL 10 DAY)"
        count_result = db.execute_query(count_query, (ind.fund_code,))
        appearance_count = count_result[0]['count'] if count_result else 0
        
        # 查询具体日期
        dates_query = "SELECT DISTINCT update_date FROM fund_investment_indicators WHERE fund_code = %s AND update_date >= DATE_SUB(CURDATE(), INTERVAL 10 DAY) ORDER BY update_date"
        dates_result = db.execute_query(dates_query, (ind.fund_code,))
        appearance_dates = [row['update_date'] for row in dates_result]
        
        print(f"Fund {i}: Code={ind.fund_code}, Name={ind.fund_name}, Type={ind.fund_type}, SubType={ind.fund_sub_type}, UpdateDate={ind.update_date}, UpdateTime={ind.update_time}, TrackingIndex={ind.tracking_index}")
        print(f"   Appearance Count (last 10 days): {appearance_count}")
        print(f"   Appearance Dates: {', '.join(str(date) for date in appearance_dates)}")  # 修改：将日期转换为字符串
    # db.disconnect()  # 可选：关闭连接

if __name__ == "__main__":
    test_get_fund_investment_indicators_custom()