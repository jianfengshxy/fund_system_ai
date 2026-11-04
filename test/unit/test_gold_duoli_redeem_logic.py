from __future__ import annotations

import datetime
from types import SimpleNamespace


def _build_asset(
    *,
    fund_code="000001",
    fund_name="测试基金",
    constant_profit_rate=2.0,
):
    return SimpleNamespace(
        fund_code=fund_code,
        fund_name=fund_name,
        constant_profit_rate=constant_profit_rate,
    )


def _build_fund_info(
    *,
    fund_name="测试基金",
    fund_type="000",
    volatility=6.0,
    nav_date="2026-10-20",
):
    return SimpleNamespace(
        fund_name=fund_name,
        fund_type=fund_type,
        volatility=volatility,
        nav_date=nav_date,
    )


def _setup_common_monkeypatch(
    monkeypatch,
    *,
    assets,
    fund_info_map,
    estimated_change_map,
    bank_shares=None,
    prev_trade_record=False,
    today_trade_record=False,
    sell_zero_fee_result=True,
    sell_low_fee_result=True,
):
    from src.service.黄金多利组合算法 import 黄金多利止盈 as service_module

    zero_fee_calls = []
    low_fee_calls = []

    monkeypatch.setattr(service_module, "getSubAccountNoByName", lambda user, sub_account_name: "sub-001")
    monkeypatch.setattr(service_module, "get_sub_account_asset_by_name", lambda user, sub_account_name: assets)
    monkeypatch.setattr(service_module, "get_all_fund_info", lambda user, fund_code: fund_info_map[fund_code])
    monkeypatch.setattr(
        service_module,
        "calc_estimated_change",
        lambda current_fund_info: (estimated_change_map[current_fund_info.fund_name], "估值测试"),
    )
    monkeypatch.setattr(
        service_module,
        "get_bank_shares",
        lambda user, sub_account_no, fund_code: bank_shares if bank_shares is not None else [{"share": 100.0}],
    )

    def _fake_has_buy_submission_on_dates(user, sub_account_no, fund_code, target_date):
        if target_date == datetime.date.today():
            return today_trade_record
        return prev_trade_record

    monkeypatch.setattr(service_module, "has_buy_submission_on_dates", _fake_has_buy_submission_on_dates)
    monkeypatch.setattr(
        service_module,
        "sell_0_fee_shares",
        lambda user, sub_account_no, fund_code, shares: zero_fee_calls.append((sub_account_no, fund_code, shares))
        or sell_zero_fee_result,
    )
    monkeypatch.setattr(
        service_module,
        "sell_low_fee_shares",
        lambda user, sub_account_no, fund_code, shares: low_fee_calls.append((sub_account_no, fund_code, shares))
        or sell_low_fee_result,
    )

    return service_module, zero_fee_calls, low_fee_calls


def test_redeem_uses_fund_level_stop_rate_and_sells_zero_fee(monkeypatch):
    service_module, zero_fee_calls, low_fee_calls = _setup_common_monkeypatch(
        monkeypatch,
        assets=[_build_asset(constant_profit_rate=2.0)],
        fund_info_map={"000001": _build_fund_info()},
        estimated_change_map={"测试基金": 1.0},
    )

    user = SimpleNamespace(account="13918199137")
    result = service_module.redeem_gold_funds(
        user=user,
        sub_account_name="黄金多利止盈",
        fund_list=[{"fund_code": "000001", "stop_rate": 2.5}],
        stop_rate=5.0,
    )

    assert result is True
    assert len(zero_fee_calls) == 1
    assert low_fee_calls == []


def test_redeem_skips_when_estimated_profit_rate_below_stop_rate(monkeypatch):
    service_module, zero_fee_calls, low_fee_calls = _setup_common_monkeypatch(
        monkeypatch,
        assets=[_build_asset(constant_profit_rate=2.0)],
        fund_info_map={"000001": _build_fund_info()},
        estimated_change_map={"测试基金": 0.2},
    )

    user = SimpleNamespace(account="13918199137")
    result = service_module.redeem_gold_funds(
        user=user,
        sub_account_name="黄金多利未止盈",
        stop_rate=3.0,
    )

    assert result is True
    assert zero_fee_calls == []
    assert low_fee_calls == []


def test_redeem_skips_when_previous_trade_pending(monkeypatch):
    pending_record = SimpleNamespace(app_state_text="受理中")
    service_module, zero_fee_calls, low_fee_calls = _setup_common_monkeypatch(
        monkeypatch,
        assets=[_build_asset(constant_profit_rate=4.0)],
        fund_info_map={"000001": _build_fund_info()},
        estimated_change_map={"测试基金": 2.0},
        prev_trade_record=pending_record,
    )

    user = SimpleNamespace(account="13918199137")
    result = service_module.redeem_gold_funds(
        user=user,
        sub_account_name="黄金多利在途止盈",
        stop_rate=3.0,
    )

    assert result is True
    assert zero_fee_calls == []
    assert low_fee_calls == []


def test_redeem_falls_back_to_low_fee_when_profit_above_ten(monkeypatch):
    service_module, zero_fee_calls, low_fee_calls = _setup_common_monkeypatch(
        monkeypatch,
        assets=[_build_asset(constant_profit_rate=9.0)],
        fund_info_map={"000001": _build_fund_info(volatility=12.0)},
        estimated_change_map={"测试基金": 2.0},
        sell_zero_fee_result=False,
        sell_low_fee_result=True,
    )

    user = SimpleNamespace(account="13918199137")
    result = service_module.redeem_gold_funds(
        user=user,
        sub_account_name="黄金多利高收益兜底",
        stop_rate=8.0,
    )

    assert result is True
    assert len(zero_fee_calls) == 1
    assert len(low_fee_calls) == 1
