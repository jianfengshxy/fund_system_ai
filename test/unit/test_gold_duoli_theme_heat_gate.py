from __future__ import annotations

from types import SimpleNamespace


def _build_asset(
    *,
    fund_code="110001",
    fund_name="主动基金",
    asset_value=3000.0,
    constant_profit_rate=-2.0,
):
    return SimpleNamespace(
        fund_code=fund_code,
        fund_name=fund_name,
        available_vol=100.0,
        asset_value=asset_value,
        constant_profit_rate=constant_profit_rate,
    )


def _build_theme(*, sec_code: str, sec_name: str, isshow: bool = True, corr_1y: float = 0.0):
    return SimpleNamespace(
        sec_code=sec_code,
        sec_name=sec_name,
        isshow=isshow,
        corr_1y=corr_1y,
    )


def _build_fund_info(
    *,
    fund_name="主动基金",
    fund_type="002",
    index_code="",
    nav_date="2026-10-20",
    week_return=1.5,
    month_return=2.5,
    max_purchase=5000.0,
    theme_infos=None,
    relate_themes=None,
):
    return SimpleNamespace(
        fund_name=fund_name,
        fund_type=fund_type,
        index_code=index_code,
        nav_date=nav_date,
        week_return=week_return,
        month_return=month_return,
        max_purchase=max_purchase,
        theme_infos=theme_infos or [],
        relate_themes=relate_themes or [],
    )


def _setup_common_monkeypatch(
    monkeypatch,
    *,
    assets,
    fund_info_map,
    estimated_change_map,
    theme_heat_map=None,
    theme_flow_map=None,
    theme_snapshot_map=None,
):
    from src.service.黄金多利组合算法 import 黄金多利加仓 as service_module

    commit_calls = []
    theme_heat_map = theme_heat_map or {}
    theme_flow_map = theme_flow_map or {}
    theme_snapshot_map = theme_snapshot_map or {}

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
        "get_latest_realtime_theme_heat",
        lambda user, theme_code, cache=None, snapshot_cache=None: theme_heat_map.get(theme_code),
    )
    monkeypatch.setattr(
        service_module,
        "get_latest_realtime_theme_flow",
        lambda user, theme_code, cache=None, snapshot_cache=None: theme_flow_map.get(theme_code),
    )
    monkeypatch.setattr(
        service_module,
        "get_theme_flow_filter_snapshot",
        lambda theme_code, cache=None, positive_days_window=10, min_positive_days=5, inflow_sum_window=3:
        theme_snapshot_map.get(theme_code),
    )
    monkeypatch.setattr(
        service_module,
        "commit_order",
        lambda user, sub_account_no, fund_code, amount: commit_calls.append((sub_account_no, fund_code, amount))
        or SimpleNamespace(amount=amount, busin_serial_no=f"order-{len(commit_calls):03d}"),
    )

    return service_module, commit_calls


def test_active_fund_theme_low_heat_blocks_increase(monkeypatch):
    service_module, commit_calls = _setup_common_monkeypatch(
        monkeypatch,
        assets=[_build_asset(fund_code="011707", fund_name="东吴配置优化混合C")],
        fund_info_map={
            "011707": _build_fund_info(
                fund_name="东吴配置优化混合C",
                theme_infos=[_build_theme(sec_code="BK000389", sec_name="新兴产业")],
            )
        },
        estimated_change_map={"东吴配置优化混合C": -0.5},
        theme_heat_map={"BK000389": 15.0},
        theme_flow_map={"BK000389": 100.0},
        theme_snapshot_map={
            "BK000389": {
                "positive_days_available": True,
                "positive_days_count": 6,
                "positive_days_window": 10,
                "min_positive_days": 5,
                "inflow_sum_available": True,
                "recent_inflow_sum": 500.0,
                "inflow_sum_window": 3,
            }
        },
    )

    user = SimpleNamespace(account="13918199137")
    result = service_module.increase_gold_funds(
        user=user,
        sub_account_name="黄金多利主动低热度",
        amount=2000.0,
        fund_list=[{"fund_code": "011707", "amount": 2000.0}],
        index_heat_filter_enabled=True,
    )

    assert result is True
    assert commit_calls == []


def test_active_fund_without_theme_ignores_heat_gate(monkeypatch):
    service_module, commit_calls = _setup_common_monkeypatch(
        monkeypatch,
        assets=[_build_asset(fund_code="011701", fund_name="南方均衡回报混合C")],
        fund_info_map={
            "011701": _build_fund_info(
                fund_name="南方均衡回报混合C",
                theme_infos=[],
                relate_themes=[],
            )
        },
        estimated_change_map={"南方均衡回报混合C": -0.5},
    )

    user = SimpleNamespace(account="13918199137")
    result = service_module.increase_gold_funds(
        user=user,
        sub_account_name="黄金多利主动无主题",
        amount=2000.0,
        fund_list=[{"fund_code": "011701", "amount": 2000.0}],
        index_heat_filter_enabled=True,
    )

    assert result is True
    assert commit_calls == [("sub-001", "011701", 2000.0)]


def test_active_fund_theme_negative_flow_blocks_increase(monkeypatch):
    service_module, commit_calls = _setup_common_monkeypatch(
        monkeypatch,
        assets=[_build_asset(fund_code="011707", fund_name="东吴配置优化混合C")],
        fund_info_map={
            "011707": _build_fund_info(
                fund_name="东吴配置优化混合C",
                theme_infos=[_build_theme(sec_code="BK000389", sec_name="新兴产业")],
            )
        },
        estimated_change_map={"东吴配置优化混合C": -0.5},
        theme_heat_map={"BK000389": 45.0},
        theme_flow_map={"BK000389": -1.0},
        theme_snapshot_map={"BK000389": None},
    )

    user = SimpleNamespace(account="13918199137")
    result = service_module.increase_gold_funds(
        user=user,
        sub_account_name="黄金多利主动负流向",
        amount=2000.0,
        fund_list=[{"fund_code": "011707", "amount": 2000.0}],
        index_heat_filter_enabled=True,
    )

    assert result is True
    assert commit_calls == []


def test_active_fund_theme_high_heat_allows_increase(monkeypatch):
    service_module, commit_calls = _setup_common_monkeypatch(
        monkeypatch,
        assets=[_build_asset(fund_code="011707", fund_name="东吴配置优化混合C")],
        fund_info_map={
            "011707": _build_fund_info(
                fund_name="东吴配置优化混合C",
                theme_infos=[_build_theme(sec_code="BK000389", sec_name="新兴产业")],
            )
        },
        estimated_change_map={"东吴配置优化混合C": -0.5},
        theme_heat_map={"BK000389": 66.0},
        theme_flow_map={"BK000389": 200.0},
        theme_snapshot_map={
            "BK000389": {
                "positive_days_available": True,
                "positive_days_count": 6,
                "positive_days_window": 10,
                "min_positive_days": 5,
                "inflow_sum_available": True,
                "recent_inflow_sum": 500.0,
                "inflow_sum_window": 3,
            }
        },
    )

    user = SimpleNamespace(account="13918199137")
    result = service_module.increase_gold_funds(
        user=user,
        sub_account_name="黄金多利主动高热度",
        amount=2000.0,
        fund_list=[{"fund_code": "011707", "amount": 2000.0}],
        index_heat_filter_enabled=True,
    )

    assert result is True
    assert commit_calls == [("sub-001", "011707", 2000.0)]


def test_active_fund_theme_insufficient_history_blocks_increase(monkeypatch):
    service_module, commit_calls = _setup_common_monkeypatch(
        monkeypatch,
        assets=[_build_asset(fund_code="011707", fund_name="东吴配置优化混合C")],
        fund_info_map={
            "011707": _build_fund_info(
                fund_name="东吴配置优化混合C",
                theme_infos=[_build_theme(sec_code="BK000389", sec_name="新兴产业")],
            )
        },
        estimated_change_map={"东吴配置优化混合C": -0.5},
        theme_heat_map={"BK000389": 66.0},
        theme_flow_map={"BK000389": 200.0},
        theme_snapshot_map={
            "BK000389": {
                "positive_days_available": False,
                "positive_days_count": 1,
                "positive_days_window": 10,
                "min_positive_days": 5,
                "inflow_sum_available": False,
                "recent_inflow_sum": 200.0,
                "inflow_sum_window": 3,
            }
        },
    )

    user = SimpleNamespace(account="13918199137")
    result = service_module.increase_gold_funds(
        user=user,
        sub_account_name="黄金多利主动历史不足",
        amount=2000.0,
        fund_list=[{"fund_code": "011707", "amount": 2000.0}],
        index_heat_filter_enabled=True,
    )

    assert result is True
    assert commit_calls == []
