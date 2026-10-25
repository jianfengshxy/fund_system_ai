from __future__ import annotations

from types import SimpleNamespace


def _build_theme(*, sec_code: str, sec_name: str, isshow: bool = True, corr_1y: float = 0.0):
    return SimpleNamespace(
        sec_code=sec_code,
        sec_name=sec_name,
        isshow=isshow,
        corr_1y=corr_1y,
    )


def _build_asset(
    *,
    fund_code: str,
    fund_name: str,
    asset_value: float,
    constant_profit_rate: float,
):
    return SimpleNamespace(
        fund_code=fund_code,
        fund_name=fund_name,
        available_vol=100.0,
        asset_value=asset_value,
        constant_profit_rate=constant_profit_rate,
    )


def _build_fund_info(
    *,
    fund_name: str,
    fund_type: str,
    index_code: str = "",
    week_return: float = 1.5,
    month_return: float = 2.5,
    max_purchase: float = 5000.0,
    theme_infos=None,
    relate_themes=None,
):
    return SimpleNamespace(
        fund_name=fund_name,
        fund_type=fund_type,
        index_code=index_code,
        nav_date="2026-10-20",
        week_return=week_return,
        month_return=month_return,
        max_purchase=max_purchase,
        theme_infos=theme_infos or [],
        relate_themes=relate_themes or [],
    )


def _setup_module(monkeypatch, *, assets, fund_info_map, estimated_change_map):
    from src.service.黄金多利组合算法 import 黄金多利加仓 as service_module

    commit_calls = []

    monkeypatch.setattr(service_module, "getSubAccountNoByName", lambda user, sub_account_name: "sub-001")
    monkeypatch.setattr(service_module, "get_sub_account_asset_by_name", lambda user, sub_account_name: assets)
    monkeypatch.setattr(service_module, "has_buy_submission_on_dates", lambda *args, **kwargs: False)
    monkeypatch.setattr(service_module, "get_all_fund_info", lambda user, fund_code: fund_info_map.get(fund_code))
    monkeypatch.setattr(
        service_module,
        "calc_estimated_change",
        lambda current_fund_info: (estimated_change_map.get(current_fund_info.fund_name, 0.0), "估值测试"),
    )
    monkeypatch.setattr(service_module, "nav5_gate", lambda *args, **kwargs: True)
    monkeypatch.setattr(service_module, "check_hqb_risk_allowed", lambda user, threshold=None: True)
    monkeypatch.setattr(
        service_module,
        "commit_order",
        lambda user, sub_account_no, fund_code, amount: commit_calls.append((sub_account_no, fund_code, amount))
        or SimpleNamespace(amount=amount, busin_serial_no=f"order-{len(commit_calls):03d}"),
    )

    user = SimpleNamespace(account="13918199137")
    return service_module, user, commit_calls


def test_same_index_only_best_efficiency_fund_increases(monkeypatch):
    assets = [
        _build_asset(fund_code="IDX1", fund_name="指数甲", asset_value=6000.0, constant_profit_rate=-3.0),
        _build_asset(fund_code="IDX2", fund_name="指数乙", asset_value=18000.0, constant_profit_rate=-3.0),
        _build_asset(fund_code="OTH1", fund_name="独立主题", asset_value=10000.0, constant_profit_rate=-2.0),
    ]
    fund_info_map = {
        "IDX1": _build_fund_info(fund_name="指数甲", fund_type="000", index_code="399001"),
        "IDX2": _build_fund_info(fund_name="指数乙", fund_type="000", index_code="399001"),
        "OTH1": _build_fund_info(
            fund_name="独立主题",
            fund_type="001",
            theme_infos=[_build_theme(sec_code="BK100", sec_name="机器人", isshow=True)],
        ),
    }
    estimated_change_map = {
        "指数甲": -1.5,
        "指数乙": -1.5,
        "独立主题": -0.5,
    }

    service_module, user, commit_calls = _setup_module(
        monkeypatch,
        assets=assets,
        fund_info_map=fund_info_map,
        estimated_change_map=estimated_change_map,
    )

    result = service_module.increase_gold_funds(
        user=user,
        sub_account_name="黄金多利同指数",
        amount=2000.0,
        fund_list=[
            {"fund_code": "IDX1", "amount": 2000.0},
            {"fund_code": "IDX2", "amount": 2000.0},
            {"fund_code": "OTH1", "amount": 2000.0},
        ],
    )

    assert result is True
    assert commit_calls == [
        ("sub-001", "IDX1", 4000.0),
        ("sub-001", "OTH1", 2000.0),
    ]


def test_same_theme_only_best_post_add_profit_rate_fund_increases(monkeypatch):
    assets = [
        _build_asset(fund_code="ACT1", fund_name="主动甲", asset_value=12000.0, constant_profit_rate=-2.0),
        _build_asset(fund_code="ACT2", fund_name="主动乙", asset_value=12000.0, constant_profit_rate=-4.0),
        _build_asset(fund_code="IDX1", fund_name="独立指数", asset_value=15000.0, constant_profit_rate=-2.5),
    ]
    fund_info_map = {
        "ACT1": _build_fund_info(
            fund_name="主动甲",
            fund_type="001",
            theme_infos=[_build_theme(sec_code="BK001", sec_name="人工智能", isshow=True)],
        ),
        "ACT2": _build_fund_info(
            fund_name="主动乙",
            fund_type="001",
            theme_infos=[_build_theme(sec_code="BK001", sec_name="人工智能", isshow=True)],
        ),
        "IDX1": _build_fund_info(fund_name="独立指数", fund_type="000", index_code="399905"),
    }
    estimated_change_map = {
        "主动甲": -0.5,
        "主动乙": -0.5,
        "独立指数": -0.5,
    }

    service_module, user, commit_calls = _setup_module(
        monkeypatch,
        assets=assets,
        fund_info_map=fund_info_map,
        estimated_change_map=estimated_change_map,
    )

    result = service_module.increase_gold_funds(
        user=user,
        sub_account_name="黄金多利同主题",
        amount=2000.0,
        fund_list=[
            {"fund_code": "ACT1", "amount": 2000.0},
            {"fund_code": "ACT2", "amount": 2000.0},
            {"fund_code": "IDX1", "amount": 2000.0},
        ],
    )

    assert result is True
    assert commit_calls == [
        ("sub-001", "ACT1", 2000.0),
        ("sub-001", "IDX1", 2000.0),
    ]
