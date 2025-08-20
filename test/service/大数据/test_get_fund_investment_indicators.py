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

def test_get_fund_investment_indicators_default():
    indicators = get_fund_investment_indicators()
    assert isinstance(indicators, List)
    assert all(isinstance(ind, FundInvestmentIndicator) for ind in indicators)
    # 添加更多断言，根据预期
    print(f"Retrieved {len(indicators)} frequent indicators with default params")

def test_get_fund_investment_indicators_custom():
    indicators = get_fund_investment_indicators(days=5, threshold=3)
    assert isinstance(indicators, List)
    assert all(isinstance(ind, FundInvestmentIndicator) for ind in indicators)
    # 添加更多断言，根据预期
    print(f"Retrieved {len(indicators)} frequent indicators with custom params")
    # 新增: 打印返回的基金详情
    for i, ind in enumerate(indicators, 1):
        print(f"Fund {i}: Code={ind.fund_code}, Name={ind.fund_name}, Type={ind.fund_type}, SubType={ind.fund_sub_type}, UpdateDate={ind.update_date}, UpdateTime={ind.update_time}, TrackingIndex={ind.tracking_index}")

if __name__ == "__main__":
    test_get_fund_investment_indicators_custom()