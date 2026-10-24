from __future__ import annotations

from types import SimpleNamespace


def _setup_common_monkeypatch(
    monkeypatch,
    *,
    asset,
    fund_info,
    estimated_change,
    nav5_gate_result=True,
):
    from src.service.黄金多利组合算法 import 黄金多利加仓 as service_module

    commit_calls = []

    class FakeMarketIndexService:
        def get_latest_snapshot(self, _index_code: str):
            return None

    monkeypatch.setattr(service_module, "MarketIndexService", FakeMarketIndexService)
    monkeypatch.setattr(service_module, "getSubAccountNoByName", lambda user, sub_account_name: "sub-001")
    monkeypatch.setattr(service_module, "get_sub_account_asset_by_name", lambda user, sub_account_name: [asset])
    monkeypatch.setattr(service_module, "has_buy_submission_on_dates", lambda *args, **kwargs: False)
    monkeypatch.setattr(service_module, "get_all_fund_info", lambda user, fund_code: fund_info)
    monkeypatch.setattr(service_module, "calc_estimated_change", lambda current_fund_info: (estimated_change, "估值测试"))
    monkeypatch.setattr(service_module, "nav5_gate", lambda *args, **kwargs: nav5_gate_result)
    monkeypatch.setattr(service_module, "check_hqb_risk_allowed", lambda user, threshold=None: True)
    monkeypatch.setattr(
        service_module,
        "commit_order",
        lambda user, sub_account_no, fund_code, amount: commit_calls.append((sub_account_no, fund_code, amount))
        or SimpleNamespace(amount=amount, busin_serial_no=f"order-{len(commit_calls):03d}"),
    )

    return service_module, commit_calls


def _build_asset(
    *,
    fund_code="000001",
    fund_name="测试基金",
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


def _build_fund_info(
    *,
    fund_name="测试基金",
    fund_type="000",
    index_code="399001",
    nav_date="2026-10-20",
    week_return=1.5,
    month_return=2.5,
    max_purchase=5000.0,
):
    return SimpleNamespace(
        fund_name=fund_name,
        fund_type=fund_type,
        index_code=index_code,
        nav_date=nav_date,
        week_return=week_return,
        month_return=month_return,
        max_purchase=max_purchase,
    )


def test_index_fund_heat_missing_allows_normal_increase(monkeypatch):
    service_module, commit_calls = _setup_common_monkeypatch(
        monkeypatch,
        asset=_build_asset(),
        fund_info=_build_fund_info(),
        estimated_change=-0.5,
    )

    user = SimpleNamespace(account="13918199137")
    result = service_module.increase_gold_funds(
        user=user,
        sub_account_name="黄金多利热度空值",
        amount=2000.0,
        fund_list=[{"fund_code": "000001", "amount": 2000.0}],
    )

    assert result is True
    assert commit_calls == [("sub-001", "000001", 2000.0)]


def test_index_fund_heat_equal_40_blocks_increase(monkeypatch):
    service_module, commit_calls = _setup_common_monkeypatch(
        monkeypatch,
        asset=_build_asset(),
        fund_info=_build_fund_info(),
        estimated_change=-0.5,
    )

    class FakeMarketIndexService:
        def get_latest_snapshot(self, _index_code: str):
            return {"heat_score": 20}

    monkeypatch.setattr(service_module, "MarketIndexService", FakeMarketIndexService)

    user = SimpleNamespace(account="13918199137")
    result = service_module.increase_gold_funds(
        user=user,
        sub_account_name="黄金多利热度40",
        amount=2000.0,
        fund_list=[{"fund_code": "000001", "amount": 2000.0}],
    )

    assert result is True
    assert commit_calls == []


def test_index_fund_heat_above_40_allows_double_increase(monkeypatch):
    service_module, commit_calls = _setup_common_monkeypatch(
        monkeypatch,
        asset=_build_asset(constant_profit_rate=-3.0),
        fund_info=_build_fund_info(),
        estimated_change=-1.5,
    )

    class FakeMarketIndexService:
        def get_latest_snapshot(self, _index_code: str):
            return {"heat_score": 41}

    monkeypatch.setattr(service_module, "MarketIndexService", FakeMarketIndexService)

    user = SimpleNamespace(account="13918199137")
    result = service_module.increase_gold_funds(
        user=user,
        sub_account_name="黄金多利热度41双倍",
        amount=2000.0,
        fund_list=[{"fund_code": "000001", "amount": 2000.0}],
    )

    assert result is True
    assert commit_calls == [("sub-001", "000001", 4000.0)]


def test_non_index_fund_ignores_heat_gate(monkeypatch):
    service_module, commit_calls = _setup_common_monkeypatch(
        monkeypatch,
        asset=_build_asset(fund_code="110001", fund_name="主动基金"),
        fund_info=_build_fund_info(fund_name="主动基金", fund_type="001", index_code="399001"),
        estimated_change=-0.5,
    )

    class FakeMarketIndexService:
        def get_latest_snapshot(self, _index_code: str):
            return {"heat_score": 1}

    monkeypatch.setattr(service_module, "MarketIndexService", FakeMarketIndexService)

    user = SimpleNamespace(account="13918199137")
    result = service_module.increase_gold_funds(
        user=user,
        sub_account_name="黄金多利非指数",
        amount=2000.0,
        fund_list=[{"fund_code": "110001", "amount": 2000.0}],
    )

    assert result is True
    assert commit_calls == [("sub-001", "110001", 2000.0)]


def test_index_fund_low_heat_blocks_deep_rebound_increase(monkeypatch):
    service_module, commit_calls = _setup_common_monkeypatch(
        monkeypatch,
        asset=_build_asset(asset_value=6000.0, constant_profit_rate=-4.5),
        fund_info=_build_fund_info(),
        estimated_change=-1.0,
        nav5_gate_result=True,
    )

    class FakeMarketIndexService:
        def get_latest_snapshot(self, _index_code: str):
            return {"heat_score": 39.9}

    monkeypatch.setattr(service_module, "MarketIndexService", FakeMarketIndexService)

    user = SimpleNamespace(account="13918199137")
    result = service_module.increase_gold_funds(
        user=user,
        sub_account_name="黄金多利深反低热度",
        amount=2000.0,
        fund_list=[{"fund_code": "000001", "amount": 2000.0}],
    )

    assert result is True
    assert commit_calls == []


def test_index_fund_high_heat_allows_deep_rebound_increase(monkeypatch):
    service_module, commit_calls = _setup_common_monkeypatch(
        monkeypatch,
        asset=_build_asset(asset_value=6000.0, constant_profit_rate=-4.5),
        fund_info=_build_fund_info(),
        estimated_change=-1.0,
        nav5_gate_result=True,
    )

    class FakeMarketIndexService:
        def get_latest_snapshot(self, _index_code: str):
            return {"heat_score": 45}

    monkeypatch.setattr(service_module, "MarketIndexService", FakeMarketIndexService)

    user = SimpleNamespace(account="13918199137")
    result = service_module.increase_gold_funds(
        user=user,
        sub_account_name="黄金多利深反高热度",
        amount=2000.0,
        fund_list=[{"fund_code": "000001", "amount": 2000.0}],
    )

    assert result is True
    assert commit_calls == [("sub-001", "000001", 3000.0)]
