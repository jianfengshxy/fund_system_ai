from __future__ import annotations

import importlib
from types import SimpleNamespace


def _build_theme(*, sec_code: str, sec_name: str, isshow: bool = True, corr_1y: float = 0.0):
    return SimpleNamespace(
        sec_code=sec_code,
        sec_name=sec_name,
        isshow=isshow,
        corr_1y=corr_1y,
    )


def _build_fund_info(
    *,
    fund_code: str,
    fund_name: str,
    fund_type: str = "001",
    theme_code: str = "",
    theme_name: str = "",
    rank_100day: float = 30.0,
    rank_30day: float = 10.0,
    estimated_change: float = 0.0,
):
    theme_infos = []
    if theme_code or theme_name:
        theme_infos = [_build_theme(sec_code=theme_code, sec_name=theme_name, isshow=True)]

    return SimpleNamespace(
        fund_code=fund_code,
        fund_name=fund_name,
        fund_type=fund_type,
        index_code="",
        rank_100day=rank_100day,
        rank_30day=rank_30day,
        theme_infos=theme_infos,
        relate_themes=[],
        estimated_change_test=estimated_change,
        nav_date="2026-10-24",
    )


def _build_asset(*, fund_code: str, fund_name: str, asset_value: float, constant_profit_rate: float):
    return SimpleNamespace(
        fund_code=fund_code,
        fund_name=fund_name,
        asset_value=asset_value,
        constant_profit_rate=constant_profit_rate,
    )


def _setup_module(monkeypatch, *, assets, wind_vane_funds, fund_info_map):
    service_module = importlib.import_module("src.service.加仓风向标组合算法.加仓风向标加仓")
    commit_calls = []

    monkeypatch.setattr(service_module, "getSubAccountNoByName", lambda *args, **kwargs: "sub-001")
    monkeypatch.setattr(service_module, "get_fund_investment_indicators", lambda *args, **kwargs: wind_vane_funds)
    monkeypatch.setattr(service_module, "get_sub_account_asset_by_name", lambda *args, **kwargs: assets)
    monkeypatch.setattr(service_module, "get_all_fund_info", lambda _user, fund_code: fund_info_map.get(fund_code))
    monkeypatch.setattr(service_module, "calc_estimated_change", lambda fi: (fi.estimated_change_test, "估值测试"))
    monkeypatch.setattr(service_module, "nav5_gate", lambda *args, **kwargs: True)
    monkeypatch.setattr(service_module, "get_fund_growth_rate", lambda fi, period: (None, 20, 100))
    monkeypatch.setattr(service_module, "has_buy_submission_on_dates", lambda *args, **kwargs: False)
    monkeypatch.setattr(
        service_module,
        "commit_order",
        lambda _user, sub_account_no, fund_code, amount: commit_calls.append((sub_account_no, fund_code, amount))
        or SimpleNamespace(amount=amount, busin_serial_no=f"order-{len(commit_calls):03d}"),
    )

    user = SimpleNamespace(customer_name="测试用户", account="13918199137")
    return service_module, user, commit_calls


def test_same_theme_prefers_smaller_position_when_loss_depth_equal(monkeypatch):
    assets = [
        _build_asset(fund_code="A1", fund_name="小仓AI", asset_value=6000.0, constant_profit_rate=-15.0),
        _build_asset(fund_code="A2", fund_name="大仓AI", asset_value=18000.0, constant_profit_rate=-15.0),
        _build_asset(fund_code="B1", fund_name="机器人基金", asset_value=8000.0, constant_profit_rate=-12.0),
        _build_asset(fund_code="ZZ", fund_name="压舱基金", asset_value=50000.0, constant_profit_rate=0.0),
    ]
    wind_vane_funds = [
        SimpleNamespace(fund_code="A1", fund_type="001"),
        SimpleNamespace(fund_code="A2", fund_type="001"),
        SimpleNamespace(fund_code="B1", fund_type="001"),
    ]
    fund_info_map = {
        "A1": _build_fund_info(fund_code="A1", fund_name="小仓AI", theme_code="BK001", theme_name="人工智能"),
        "A2": _build_fund_info(fund_code="A2", fund_name="大仓AI", theme_code="BK001", theme_name="人工智能"),
        "B1": _build_fund_info(fund_code="B1", fund_name="机器人基金", theme_code="BK002", theme_name="机器人"),
        "ZZ": _build_fund_info(fund_code="ZZ", fund_name="压舱基金", theme_code="BK999", theme_name="其他", estimated_change=0.0),
    }

    service_module, user, commit_calls = _setup_module(
        monkeypatch,
        assets=assets,
        wind_vane_funds=wind_vane_funds,
        fund_info_map=fund_info_map,
    )

    result = service_module.increase_funds(
        user=user,
        sub_account_name="风向标加仓",
        total_budget=200000.0,
        amount=2000.0,
        fund_num=5,
        fund_type="non_index",
    )

    assert result is True
    assert commit_calls == [
        ("sub-001", "A1", 4000.0),
        ("sub-001", "B1", 4000.0),
    ]


def test_same_theme_prefers_higher_post_add_profit_rate_when_position_equal(monkeypatch):
    assets = [
        _build_asset(fund_code="C1", fund_name="中亏算力", asset_value=10000.0, constant_profit_rate=-8.0),
        _build_asset(fund_code="C2", fund_name="深亏算力", asset_value=10000.0, constant_profit_rate=-16.0),
        _build_asset(fund_code="ZZ", fund_name="压舱基金", asset_value=60000.0, constant_profit_rate=0.0),
    ]
    wind_vane_funds = [
        SimpleNamespace(fund_code="C1", fund_type="001"),
        SimpleNamespace(fund_code="C2", fund_type="001"),
    ]
    fund_info_map = {
        "C1": _build_fund_info(fund_code="C1", fund_name="中亏算力", theme_code="BK003", theme_name="算力"),
        "C2": _build_fund_info(fund_code="C2", fund_name="深亏算力", theme_code="BK003", theme_name="算力"),
        "ZZ": _build_fund_info(fund_code="ZZ", fund_name="压舱基金", theme_code="BK999", theme_name="其他", estimated_change=0.0),
    }

    service_module, user, commit_calls = _setup_module(
        monkeypatch,
        assets=assets,
        wind_vane_funds=wind_vane_funds,
        fund_info_map=fund_info_map,
    )

    result = service_module.increase_funds(
        user=user,
        sub_account_name="风向标加仓",
        total_budget=200000.0,
        amount=2000.0,
        fund_num=5,
        fund_type="non_index",
    )

    assert result is True
    assert commit_calls == [
        ("sub-001", "C1", 4000.0),
    ]


def test_same_index_prefers_higher_post_add_profit_rate(monkeypatch):
    assets = [
        _build_asset(fund_code="I1", fund_name="小仓新能车", asset_value=6000.0, constant_profit_rate=-12.0),
        _build_asset(fund_code="I2", fund_name="大仓新能车", asset_value=18000.0, constant_profit_rate=-12.0),
        _build_asset(fund_code="ZZ", fund_name="压舱基金", asset_value=100000.0, constant_profit_rate=0.0),
    ]
    wind_vane_funds = [
        SimpleNamespace(fund_code="I1", fund_type="000"),
        SimpleNamespace(fund_code="I2", fund_type="000"),
    ]
    fund_info_map = {
        "I1": _build_fund_info(fund_code="I1", fund_name="小仓新能车", fund_type="000"),
        "I2": _build_fund_info(fund_code="I2", fund_name="大仓新能车", fund_type="000"),
        "ZZ": _build_fund_info(fund_code="ZZ", fund_name="压舱基金", theme_code="BK999", theme_name="其他", estimated_change=0.0),
    }
    fund_info_map["I1"].index_code = "930997"
    fund_info_map["I2"].index_code = "930997"

    service_module, user, commit_calls = _setup_module(
        monkeypatch,
        assets=assets,
        wind_vane_funds=wind_vane_funds,
        fund_info_map=fund_info_map,
    )

    result = service_module.increase_funds(
        user=user,
        sub_account_name="风向标同指数",
        total_budget=200000.0,
        amount=2000.0,
        fund_num=5,
        fund_type="index",
    )

    assert result is True
    assert commit_calls == [
        ("sub-001", "I1", 4000.0),
    ]
