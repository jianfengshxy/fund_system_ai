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
    fund_name: str,
    fund_type: str = "000",
    index_code: str = "",
    theme_code: str = "",
    theme_name: str = "",
):
    theme_infos = []
    if theme_code or theme_name:
        theme_infos = [_build_theme(sec_code=theme_code, sec_name=theme_name, isshow=True)]
    return SimpleNamespace(
        fund_name=fund_name,
        fund_type=fund_type,
        index_code=index_code,
        can_purchase=True,
        max_purchase=5000.0,
        theme_infos=theme_infos,
        relate_themes=[],
        rank_100day=30,
        rank_30day=10,
        year_return=12.0,
        six_month_return=8.0,
    )


def test_custom_add_skips_same_theme_index_with_different_index_code(monkeypatch):
    service_module = importlib.import_module("src.service.自定义组合算法.自定义组合新增")
    commit_calls = []

    user = SimpleNamespace(customer_name="测试用户")
    holdings = [SimpleNamespace(fund_code="HOLD1", asset_value=5000.0)]
    fund_info_map = {
        "HOLD1": _build_fund_info(fund_name="已持有互联网指数", index_code="H30535", theme_code="BK000388", theme_name="TMT"),
        "NEW1": _build_fund_info(fund_name="科技通信指数", index_code="H30318", theme_code="BK000388", theme_name="TMT"),
        "NEW2": _build_fund_info(fund_name="新能源车指数", index_code="930997", theme_code="BK000225", theme_name="新能源车"),
    }

    monkeypatch.setattr(service_module, "check_hqb_risk_allowed", lambda *args, **kwargs: True)
    monkeypatch.setattr(service_module, "get_sub_account_asset_by_name", lambda *args, **kwargs: holdings)
    monkeypatch.setattr(service_module, "getSubAccountNoByName", lambda *args, **kwargs: "sub-001")
    monkeypatch.setattr(service_module, "get_all_fund_info", lambda _user, fund_code: fund_info_map.get(fund_code))
    monkeypatch.setattr(service_module, "nav5_gate", lambda *args, **kwargs: True)
    monkeypatch.setattr(
        service_module,
        "commit_order",
        lambda _user, sub_account_no, fund_code, amount: commit_calls.append((sub_account_no, fund_code, amount))
        or SimpleNamespace(amount=amount, busin_serial_no=f"order-{len(commit_calls):03d}"),
    )

    result = service_module.increase_funds(
        user=user,
        sub_account_name="自定义新增",
        total_budget=100000.0,
        fund_list=[
            {"fund_code": "NEW1", "amount": 2000.0},
            {"fund_code": "NEW2", "amount": 2000.0},
        ],
    )

    assert result is True
    assert commit_calls == [
        ("sub-001", "NEW2", 2000.0),
    ]
