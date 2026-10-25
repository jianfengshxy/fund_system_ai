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
    fund_type: str = "001",
    index_code: str = "",
    can_purchase: bool = True,
    theme_infos=None,
    relate_themes=None,
):
    return SimpleNamespace(
        fund_name=fund_name,
        fund_type=fund_type,
        index_code=index_code,
        can_purchase=can_purchase,
        theme_infos=theme_infos or [],
        relate_themes=relate_themes or [],
        rank_100day=10,
        rank_30day=5,
        year_return=12.0,
        six_month_return=8.0,
    )


def _setup_module(monkeypatch, *, holdings, candidates, fund_info_map):
    service_module = importlib.import_module("src.service.加仓风向标组合算法.加仓风向标新增")
    commit_calls = []

    user = SimpleNamespace(
        customer_name="测试用户",
        account="13918199137",
        mobile_phone="13918199137",
        hqb_value=50000.0,
    )

    monkeypatch.setattr(service_module, "_check_wind_vane_hqb_risk", lambda *args, **kwargs: True)
    monkeypatch.setattr(service_module, "get_sub_account_asset_by_name", lambda *args, **kwargs: holdings)
    monkeypatch.setattr(service_module, "get_fund_investment_indicators", lambda *args, **kwargs: candidates)
    monkeypatch.setattr(service_module, "get_all_fund_info", lambda _user, fund_code: fund_info_map.get(fund_code))
    monkeypatch.setattr(service_module, "nav5_gate", lambda *args, **kwargs: True)
    monkeypatch.setattr(service_module, "getSubAccountNoByName", lambda *args, **kwargs: "sub-001")
    monkeypatch.setattr(
        service_module,
        "commit_order",
        lambda _user, sub_account_no, fund_code, amount: commit_calls.append((sub_account_no, fund_code, amount))
        or SimpleNamespace(amount=amount, busin_serial_no=f"order-{len(commit_calls):03d}"),
    )

    return service_module, user, commit_calls


def test_non_index_candidate_skipped_when_same_theme_already_held(monkeypatch):
    holdings = [SimpleNamespace(fund_code="HOLD1", asset_value=3000.0)]
    candidates = [SimpleNamespace(fund_code="CAND1", fund_name="AI成长混合", fund_type="001", product_rank=1)]
    fund_info_map = {
        "HOLD1": _build_fund_info(
            fund_name="已持有AI混合",
            theme_infos=[_build_theme(sec_code="BK001", sec_name="人工智能", isshow=True)],
        ),
        "CAND1": _build_fund_info(
            fund_name="AI成长混合",
            theme_infos=[_build_theme(sec_code="BK001", sec_name="人工智能", isshow=True)],
        ),
    }

    service_module, user, commit_calls = _setup_module(
        monkeypatch,
        holdings=holdings,
        candidates=candidates,
        fund_info_map=fund_info_map,
    )

    result = service_module.add_new_funds(
        user=user,
        sub_account_name="风向标主题去重",
        total_budget=100000.0,
        amount=2000.0,
        fund_num=1,
    )

    assert result is True
    assert commit_calls == []


def test_non_index_candidate_allows_buy_when_theme_differs(monkeypatch):
    holdings = [SimpleNamespace(fund_code="HOLD1", asset_value=3000.0)]
    candidates = [SimpleNamespace(fund_code="CAND2", fund_name="机器人混合", fund_type="001", product_rank=1)]
    fund_info_map = {
        "HOLD1": _build_fund_info(
            fund_name="已持有AI混合",
            theme_infos=[_build_theme(sec_code="BK001", sec_name="人工智能", isshow=True)],
        ),
        "CAND2": _build_fund_info(
            fund_name="机器人混合",
            theme_infos=[_build_theme(sec_code="BK002", sec_name="机器人", isshow=True)],
        ),
    }

    service_module, user, commit_calls = _setup_module(
        monkeypatch,
        holdings=holdings,
        candidates=candidates,
        fund_info_map=fund_info_map,
    )

    result = service_module.add_new_funds(
        user=user,
        sub_account_name="风向标主题去重",
        total_budget=100000.0,
        amount=2000.0,
        fund_num=1,
    )

    assert result is True
    assert commit_calls == [("sub-001", "CAND2", 2000.0)]
