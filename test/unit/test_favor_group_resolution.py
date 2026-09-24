from __future__ import annotations

import importlib


service = importlib.import_module("src.service.自选基金.自选组合服务")
gold_duoli = importlib.import_module("src.task.gold_duoli")
ApiResponse = importlib.import_module("src.domain.fund_plan.api_response").ApiResponse


def test_resolve_group_by_name_handles_normalized_name(monkeypatch):
    monkeypatch.setattr(
        service,
        "get_favor_groups",
        lambda user: ApiResponse(
            True,
            0,
            {"Groups": [{"GroupId": "1001", "GroupName": "智投平台\u3000"}]},
            None,
            None,
        ),
    )
    monkeypatch.setattr(
        service,
        "get_favor_group",
        lambda group_ids, fund_type=0, user=None: ApiResponse(
            True,
            0,
            {"items": [{"fcode": "011707", "shortname": "东吴配置优化混合C"}]},
            None,
            None,
        ),
    )

    result = service.resolve_group_by_name("智投平台", user=object())

    assert result["success"] is True
    assert result["group_found"] is True
    assert result["group_id"] == "1001"
    assert result["matched_name"] == "智投平台"
    assert len(result["funds"]) == 1
    assert result["funds"][0]["fcode"] == "011707"


def test_merge_favorites_funds_logs_query_failure_instead_of_not_found(monkeypatch):
    monkeypatch.setattr(
        service,
        "resolve_group_by_name",
        lambda group_name, user=None: {
            "success": False,
            "group_found": False,
            "funds": [],
            "error_code": 63120,
            "first_error": "未登录,或登录超时(通行证)",
        },
    )

    warnings = []

    def fake_warning(message, extra=None):
        warnings.append(message)

    monkeypatch.setattr(gold_duoli.logger, "warning", fake_warning)

    funds, added, skipped = gold_duoli._merge_favorites_funds(
        user=object(),
        group_name="智投平台",
        base_funds=[],
        seen_codes=set(),
        default_amount=2000.0,
        default_limit=None,
        extra={"account": "13918199137", "sub_account_name": "智投平台", "action": "gold_increase"},
    )

    assert funds == []
    assert added == 0
    assert skipped == 0
    assert warnings
    assert "查询自选组合失败" in warnings[0]
    assert "63120" in warnings[0]
