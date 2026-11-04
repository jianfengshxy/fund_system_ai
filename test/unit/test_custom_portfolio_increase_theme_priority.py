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


def _build_asset(*, fund_code: str, fund_name: str, asset_value: float, constant_profit_rate: float):
    return SimpleNamespace(
        fund_code=fund_code,
        fund_name=fund_name,
        asset_value=asset_value,
        constant_profit_rate=constant_profit_rate,
    )


def _build_fund_info(
    *,
    fund_name: str,
    index_code: str,
    theme_code: str,
    theme_name: str,
):
    return SimpleNamespace(
        fund_name=fund_name,
        fund_type="000",
        index_code=index_code,
        can_purchase=True,
        nav_date="2026-10-24",
        theme_infos=[_build_theme(sec_code=theme_code, sec_name=theme_name, isshow=True)],
        relate_themes=[],
        rank_100day=30,
        rank_30day=10,
        week_return=1.0,
        month_return=2.0,
        three_month_return=3.0,
    )


def test_custom_increase_prefers_same_theme_representative_across_different_indices(monkeypatch):
    service_module = importlib.import_module("src.service.自定义组合算法.自定义组合加仓")
    commit_calls = []

    user = SimpleNamespace(customer_name="测试用户")
    assets = [
        _build_asset(fund_code="IDX1", fund_name="互联网指数", asset_value=6000.0, constant_profit_rate=-12.0),
        _build_asset(fund_code="IDX2", fund_name="科技通信指数", asset_value=18000.0, constant_profit_rate=-12.0),
    ]
    fund_info_map = {
        "IDX1": _build_fund_info(fund_name="互联网指数", index_code="H30535", theme_code="BK000388", theme_name="TMT"),
        "IDX2": _build_fund_info(fund_name="科技通信指数", index_code="H30318", theme_code="BK000388", theme_name="TMT"),
    }
    asset_meta = {
        "summary": {
            "TotalAssetValue": 50000.0,
            "SubAssetPreview": {
                "AssetValue": 50000.0,
                "FundCount": 5,
            },
        }
    }

    monkeypatch.setattr(service_module, "getSubAccountNoByName", lambda *args, **kwargs: "sub-001")
    monkeypatch.setattr(service_module, "ensure_user_fresh", lambda user, *args, **kwargs: user)
    monkeypatch.setattr(service_module, "get_asset_list_of_sub", lambda *args, **kwargs: (assets, asset_meta))
    monkeypatch.setattr(service_module, "get_all_fund_info", lambda _user, fund_code: fund_info_map.get(fund_code))
    monkeypatch.setattr(service_module, "calc_estimated_change", lambda fi: (0.0, "估值测试"))
    monkeypatch.setattr(service_module, "nav5_gate", lambda *args, **kwargs: True)
    monkeypatch.setattr(service_module, "is_trading_time", lambda *args, **kwargs: True)
    monkeypatch.setattr(
        "src.service.公共服务.trade_guard_service.has_buy_submission_on_dates",
        lambda *args, **kwargs: None,
    )
    monkeypatch.setattr(
        service_module,
        "commit_order",
        lambda _user, sub_account_no, fund_code, amount: commit_calls.append((sub_account_no, fund_code, amount))
        or SimpleNamespace(amount=amount, busin_serial_no=f"order-{len(commit_calls):03d}"),
    )

    result = service_module.increase_funds(
        user=user,
        sub_account_name="自定义加仓",
        fund_list=[
            {"fund_code": "IDX1", "amount": 2000.0},
            {"fund_code": "IDX2", "amount": 2000.0},
        ],
    )

    assert result is True
    assert commit_calls == [
        ("sub-001", "IDX1", 2000.0),
        ("sub-001", "IDX1", 2000.0),
    ]
