from types import SimpleNamespace

from src.service.公共服务.estimated_profit_service import (
    calc_estimated_profit_rate,
    compound_profit_rate,
)


def _build_fund_info(
    *,
    nav_date="2026-11-26",
    estimated_time="2026-11-27 14:46:00",
    estimated_change=0.0,
    fund_type="000",
    fund_name="测试基金",
):
    return SimpleNamespace(
        nav_date=nav_date,
        estimated_time=estimated_time,
        estimated_change=estimated_change,
        fund_type=fund_type,
        fund_name=fund_name,
    )


def test_compound_profit_rate_avoids_false_take_profit_on_deep_loss_rebound():
    result = compound_profit_rate(-13.36, 14.88)

    assert round(result, 2) == -0.47


def test_compound_profit_rate_handles_extreme_loss_rebound():
    result = compound_profit_rate(-30.0, 20.0)

    assert round(result, 2) == -16.00


def test_calc_estimated_profit_rate_uses_effective_intraday_change():
    fund_info = _build_fund_info(estimated_change=14.88)

    estimated_profit_rate, estimated_change, label = calc_estimated_profit_rate(-13.36, fund_info)

    assert round(estimated_profit_rate, 2) == -0.47
    assert estimated_change == 14.88
    assert "盘中估值" in label


def test_calc_estimated_profit_rate_zeroes_change_after_nav_published():
    fund_info = _build_fund_info(
        nav_date="2026-11-27",
        estimated_time="2026-11-27 14:46:00",
        estimated_change=14.88,
    )

    estimated_profit_rate, estimated_change, label = calc_estimated_profit_rate(-13.36, fund_info)

    assert round(estimated_profit_rate, 2) == -13.36
    assert estimated_change == 0.0
    assert "净值已发布" in label


def test_calc_estimated_profit_rate_keeps_qdii_change_even_same_day():
    fund_info = _build_fund_info(
        nav_date="2026-11-27",
        estimated_time="2026-11-27 16:00:01",
        estimated_change=1.20,
        fund_type="a",
        fund_name="全球QDII测试基金",
    )

    estimated_profit_rate, estimated_change, label = calc_estimated_profit_rate(2.0, fund_info)

    assert round(estimated_profit_rate, 2) == 3.22
    assert estimated_change == 1.20
    assert "QDII估值" in label
