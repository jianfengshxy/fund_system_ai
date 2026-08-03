from __future__ import annotations

"""
FC 部署验收用 smoke test：
- 仅做基金估值查询与第三方指数回填链路验证
- 不触发任何交易/下单逻辑
"""

from typing import Any, Dict, List

from src.common.third_party_index import fetch_valuation
from src.service.用户管理.用户信息 import get_user_all_info
from src.service.基金信息.基金信息 import get_all_fund_info
from src.task.runtime import logger, parse_strategy_event


def handler(event=None, context=None):
    action = "valuation_smoke_test"
    _evt, payload, invoke_source = parse_strategy_event(event, action)

    account = payload.get("account")
    password = payload.get("password")
    if not account or not password:
        logger.error("Payload缺少必填参数: account, password", extra={"action": action, "invoke_source": invoke_source})
        return {"success": False, "error": "missing account/password"}

    fund_codes = payload.get("fund_codes") or ["015016", "021540"]
    if isinstance(fund_codes, str):
        fund_codes = [c.strip() for c in fund_codes.split(",") if c.strip()]
    if not isinstance(fund_codes, list) or not fund_codes:
        fund_codes = ["015016", "021540"]

    user = get_user_all_info(account, password)
    if not user:
        logger.error("获取用户信息失败", extra={"action": action, "account": account, "invoke_source": invoke_source})
        return {"success": False, "error": "get_user_all_info failed"}

    funds: List[Dict[str, Any]] = []
    for code in fund_codes:
        try:
            fi = get_all_fund_info(user, str(code))
        except Exception as exc:
            funds.append({"fund_code": str(code), "success": False, "error": str(exc)})
            continue
        if not fi:
            funds.append({"fund_code": str(code), "success": False, "error": "fund_info is None"})
            continue

        idx_code = getattr(fi, "index_code", None)
        idx_val = None
        if idx_code:
            try:
                tv = fetch_valuation(idx_code)
                if tv.success:
                    idx_val = {
                        "index_code": idx_code,
                        "source": tv.source,
                        "change_pct": tv.change_pct,
                        "update_time": tv.update_time,
                    }
            except Exception:
                idx_val = None

        funds.append(
            {
                "fund_code": fi.fund_code,
                "fund_name": fi.fund_name,
                "fund_type": getattr(fi, "fund_type", None),
                "index_code": idx_code,
                "estimated_change": getattr(fi, "estimated_change", None),
                "estimated_time": getattr(fi, "estimated_time", None),
                "third_party_index": idx_val,
                "success": True,
            }
        )

    return {"success": True, "funds": funds}
