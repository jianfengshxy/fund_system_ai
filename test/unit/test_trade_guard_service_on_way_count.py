from __future__ import annotations

import datetime
from types import SimpleNamespace


def _build_trade(
    *,
    fund_code: str = "021031",
    app_state_text: str = "已受理(无需支付)",
    business_type: str = "转入投资账户",
    strike_start_date: str = "2026-11-06 20:58:39",
):
    return SimpleNamespace(
        fund_code=fund_code,
        app_state_text=app_state_text,
        status=app_state_text,
        business_type=business_type,
        display_business_code=None,
        strike_start_date=strike_start_date,
        apply_work_day=strike_start_date,
        cash_bag_app_time=strike_start_date,
        raw={},
    )


def test_has_buy_submission_on_dates_falls_back_to_asset_on_way_count(monkeypatch):
    from src.service.公共服务 import trade_guard_service as service_module

    late_trade = _build_trade()
    asset = SimpleNamespace(
        fund_code="021031",
        fund_name="汇添富国证港股通创新药ETF发起式联接C",
        on_way_transaction_count=1,
        available_vol=0.0,
        asset_value=0.0,
    )

    monkeypatch.setattr(
        service_module,
        "get_trades_list",
        lambda *args, **kwargs: [late_trade],
    )
    monkeypatch.setattr(
        service_module,
        "get_asset_list_of_sub",
        lambda user, sub_account_no: [asset],
    )

    result = service_module.has_buy_submission_on_dates(
        user=SimpleNamespace(account="13918199137"),
        sub_account_no="10005780",
        fund_code="021031",
        trans_date=datetime.date(2026, 11, 6),
    )

    assert result is asset
