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
    monkeypatch.setattr(service_module, "getFee", lambda *args, **kwargs: {})
    monkeypatch.setattr(service_module, "is_high_frequency_index_fee_ok", lambda *args, **kwargs: (True, "ok"))
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


def test_index_candidate_skipped_when_same_theme_already_held_with_different_index(monkeypatch):
    holdings = [SimpleNamespace(fund_code="HOLD_IDX", asset_value=3000.0)]
    candidates = [SimpleNamespace(fund_code="CAND_IDX", fund_name="科技通信指数", fund_type="000", product_rank=1)]
    fund_info_map = {
        "HOLD_IDX": _build_fund_info(
            fund_name="已持有互联网指数",
            fund_type="000",
            index_code="H30535",
            theme_infos=[_build_theme(sec_code="BK000388", sec_name="TMT", isshow=True)],
        ),
        "CAND_IDX": _build_fund_info(
            fund_name="科技通信指数",
            fund_type="000",
            index_code="H30318",
            theme_infos=[_build_theme(sec_code="BK000388", sec_name="TMT", isshow=True)],
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


def test_index_candidates_same_theme_prefer_higher_heat_on_init(monkeypatch):
    holdings = []
    candidates = [
        SimpleNamespace(fund_code="LOW", fund_name="低热度TMT指数", fund_type="000", product_rank=1),
        SimpleNamespace(fund_code="HIGH", fund_name="高热度TMT指数", fund_type="000", product_rank=9),
    ]
    fund_info_map = {
        "LOW": _build_fund_info(
            fund_name="低热度TMT指数",
            fund_type="000",
            index_code="IDX_LOW",
            theme_infos=[_build_theme(sec_code="BK000388", sec_name="TMT", isshow=True)],
        ),
        "HIGH": _build_fund_info(
            fund_name="高热度TMT指数",
            fund_type="000",
            index_code="IDX_HIGH",
            theme_infos=[_build_theme(sec_code="BK000388", sec_name="TMT", isshow=True)],
        ),
    }
    heat_map = {"IDX_LOW": 21.0, "IDX_HIGH": 66.0}

    service_module, user, commit_calls = _setup_module(
        monkeypatch,
        holdings=holdings,
        candidates=candidates,
        fund_info_map=fund_info_map,
    )
    monkeypatch.setattr(service_module, "get_latest_realtime_index_heat", lambda _user, index_code, cache=None: heat_map.get(index_code))

    result = service_module.add_new_funds(
        user=user,
        sub_account_name="风向标主题去重",
        total_budget=100000.0,
        amount=2000.0,
        fund_num=1,
    )

    assert result is True
    assert commit_calls == [("sub-001", "HIGH", 2000.0)]
