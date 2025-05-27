import pytest
import os
import sys
from src.service.基金信息.基金信息 import get_all_fund_info
from src.API.基金信息.FundRank import get_fund_growth_rate
from src.domain.fund.fund_info import FundInfo
from src.common.constant import DEFAULT_USER

def test_get_fund_growth_rate_real():
    """集成测试：真实调用 get_fund_growth_rate"""
    # 构造真实基金信息对象（可根据实际情况调整参数）
    fund_info = get_all_fund_info(DEFAULT_USER, "014674")
    # 测试不同周期类型
    for period_type in ["3Y", "Z", "Y"]:
        growth_rate, rank, total = get_fund_growth_rate(fund_info, period_type)
        print(f"周期: {period_type}，增长率: {growth_rate}%，排名: {rank}/{total}")
        # 只要接口返回即可，基本断言增长率为 float，排名和总数为 int
        assert isinstance(growth_rate, float)
        assert isinstance(rank, int)
        assert isinstance(total, int)