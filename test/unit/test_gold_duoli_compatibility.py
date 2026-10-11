from __future__ import annotations

from types import SimpleNamespace


def test_gold_duoli_increase_default_hqb_ratio_limit_enabled(monkeypatch):
    from src.task import gold_duoli

    captured = {}

    monkeypatch.setattr(
        gold_duoli,
        "parse_strategy_event",
        lambda event, action: (
            {},
            {
                "account": "13918199137",
                "password": "pwd",
                "sub_account_name": "黄金多利A",
                "amount": 2000,
            },
            "plain_payload",
        ),
    )
    monkeypatch.setattr(gold_duoli, "get_user_all_info", lambda account, password: SimpleNamespace(account=account))
    monkeypatch.setattr(gold_duoli, "_merge_favorites_funds", lambda **kwargs: (kwargs["base_funds"], 0, 0))

    def fake_increase(user, sub_account_name, amount, **kwargs):
        captured["user"] = user
        captured["sub_account_name"] = sub_account_name
        captured["amount"] = amount
        captured["kwargs"] = kwargs
        return True

    monkeypatch.setattr(gold_duoli, "gold_increase_biz", fake_increase)

    gold_duoli.increase({"payload": {}}, None)

    assert captured["sub_account_name"] == "黄金多利A"
    assert captured["amount"] == 2000.0
    assert captured["kwargs"]["hqb_ratio_limit_enabled"] is True


def test_gold_duoli_increase_accepts_false_string(monkeypatch):
    from src.task import gold_duoli

    captured = {}

    monkeypatch.setattr(
        gold_duoli,
        "parse_strategy_event",
        lambda event, action: (
            {},
            {
                "account": "13918199137",
                "password": "pwd",
                "sub_account_name": "黄金多利B",
                "amount": 3000,
                "hqb_ratio_limit_enabled": "false",
            },
            "plain_payload",
        ),
    )
    monkeypatch.setattr(gold_duoli, "get_user_all_info", lambda account, password: SimpleNamespace(account=account))
    monkeypatch.setattr(gold_duoli, "_merge_favorites_funds", lambda **kwargs: (kwargs["base_funds"], 0, 0))
    monkeypatch.setattr(
        gold_duoli,
        "gold_increase_biz",
        lambda user, sub_account_name, amount, **kwargs: captured.update(
            {
                "sub_account_name": sub_account_name,
                "amount": amount,
                "kwargs": kwargs,
            }
        )
        or True,
    )

    gold_duoli.increase({"payload": {}}, None)

    assert captured["sub_account_name"] == "黄金多利B"
    assert captured["amount"] == 3000.0
    assert captured["kwargs"]["hqb_ratio_limit_enabled"] is False


def test_gold_duoli_increase_invalid_hqb_ratio_limit_enabled_logs_and_falls_back_true(monkeypatch):
    from src.task import gold_duoli

    captured = {}
    warnings = []

    monkeypatch.setattr(
        gold_duoli,
        "parse_strategy_event",
        lambda event, action: (
            {},
            {
                "account": "13918199137",
                "password": "pwd",
                "sub_account_name": "黄金多利B2",
                "amount": 3000,
                "hqb_ratio_limit_enabled": "abc",
            },
            "plain_payload",
        ),
    )
    monkeypatch.setattr(gold_duoli, "get_user_all_info", lambda account, password: SimpleNamespace(account=account))
    monkeypatch.setattr(gold_duoli, "_merge_favorites_funds", lambda **kwargs: (kwargs["base_funds"], 0, 0))
    monkeypatch.setattr(gold_duoli.logger, "warning", lambda message, extra=None: warnings.append((message, extra)))
    monkeypatch.setattr(
        gold_duoli,
        "gold_increase_biz",
        lambda user, sub_account_name, amount, **kwargs: captured.update(
            {
                "sub_account_name": sub_account_name,
                "amount": amount,
                "kwargs": kwargs,
            }
        )
        or True,
    )

    gold_duoli.increase({"payload": {}}, None)

    assert captured["sub_account_name"] == "黄金多利B2"
    assert captured["kwargs"]["hqb_ratio_limit_enabled"] is True
    assert len(warnings) == 1
    assert "hqb_ratio_limit_enabled" in warnings[0][0]
    assert "已按 True 处理" in warnings[0][0]


def test_business_gold_increase_passes_hqb_ratio_limit_enabled(monkeypatch):
    from src.bussiness.黄金多利组合 import increase as increase_module

    captured = {}

    def fake_increase_gold_funds(
        user,
        sub_account_name,
        amount,
        *,
        init_amount=None,
        fund_list=None,
        limit=None,
        total_limit=None,
        hqb_ratio_limit_enabled=True,
    ):
        captured.update(
            {
                "user": user,
                "sub_account_name": sub_account_name,
                "amount": amount,
                "init_amount": init_amount,
                "fund_list": fund_list,
                "limit": limit,
                "total_limit": total_limit,
                "hqb_ratio_limit_enabled": hqb_ratio_limit_enabled,
            }
        )
        return True

    monkeypatch.setattr(increase_module, "increase_gold_funds", fake_increase_gold_funds)

    user = SimpleNamespace(customer_name="施小雨")
    result = increase_module.increase(
        user=user,
        sub_account_name="黄金多利C",
        amount=2500.0,
        init_amount=1500.0,
        fund_list=[{"fund_code": "000001", "amount": 2500.0}],
        limit=20000.0,
        total_limit=100000.0,
        hqb_ratio_limit_enabled=False,
    )

    assert result is True
    assert captured["sub_account_name"] == "黄金多利C"
    assert captured["hqb_ratio_limit_enabled"] is False


def test_service_increase_gold_funds_bypasses_hqb_limit_when_disabled(monkeypatch):
    from src.service.黄金多利组合算法 import 黄金多利加仓 as service_module

    risk_check_calls = []
    commit_calls = []

    monkeypatch.setattr(service_module, "getSubAccountNoByName", lambda user, sub_account_name: "sub-001")
    monkeypatch.setattr(service_module, "get_sub_account_asset_by_name", lambda user, sub_account_name: [])
    monkeypatch.setattr(
        service_module,
        "check_hqb_risk_allowed",
        lambda user, threshold=None: risk_check_calls.append((user, threshold)) or False,
    )
    monkeypatch.setattr(service_module, "has_buy_submission_on_dates", lambda *args, **kwargs: False)
    monkeypatch.setattr(
        service_module,
        "get_all_fund_info",
        lambda user, fund_code: SimpleNamespace(
            fund_name="测试基金",
            nav_date="2026-10-10",
            week_return="1.0",
            month_return="1.0",
            max_purchase=5000.0,
        ),
    )
    monkeypatch.setattr(service_module, "nav5_gate", lambda *args, **kwargs: True)
    monkeypatch.setattr(service_module, "calc_estimated_change", lambda fund_info: (0.0, "估值平"))
    monkeypatch.setattr(
        service_module,
        "commit_order",
        lambda user, sub_account_no, fund_code, amount: commit_calls.append(
            (sub_account_no, fund_code, amount)
        )
        or SimpleNamespace(amount=amount, busin_serial_no="order-001"),
    )

    user = SimpleNamespace(account="13918199137")
    result = service_module.increase_gold_funds(
        user=user,
        sub_account_name="黄金多利D",
        amount=2000.0,
        init_amount=1200.0,
        fund_list=[{"fund_code": "000001", "amount": 2000.0, "init_amount": 1200.0}],
        hqb_ratio_limit_enabled=False,
    )

    assert result is True
    assert risk_check_calls == []
    assert commit_calls == [("sub-001", "000001", 1200.0)]


def test_gold_duoli_redeem_still_compatible(monkeypatch):
    from src.task import gold_duoli

    captured = {}

    monkeypatch.setattr(
        gold_duoli,
        "parse_strategy_event",
        lambda event, action: (
            {},
            {
                "account": "13918199137",
                "password": "pwd",
                "sub_account_name": "黄金多利E",
                "stop_rate": "3.5",
                "fund_list": [{"fund_code": "000001", "stop_rate": "2.5"}],
            },
            "plain_payload",
        ),
    )
    monkeypatch.setattr(gold_duoli, "get_user_all_info", lambda account, password: SimpleNamespace(account=account))
    monkeypatch.setattr(gold_duoli, "_merge_favorites_funds", lambda **kwargs: (kwargs["base_funds"], 0, 0))

    def fake_redeem(user, sub_account_name, fund_list, stop_rate=None):
        captured.update(
            {
                "user": user,
                "sub_account_name": sub_account_name,
                "fund_list": fund_list,
                "stop_rate": stop_rate,
            }
        )
        return True

    monkeypatch.setattr(gold_duoli, "gold_redeem_biz", fake_redeem)

    gold_duoli.redeem({"payload": {}}, None)

    assert captured["sub_account_name"] == "黄金多利E"
    assert captured["stop_rate"] == "3.5"
    assert captured["fund_list"] == [{"fund_code": "000001", "stop_rate": "2.5"}]
