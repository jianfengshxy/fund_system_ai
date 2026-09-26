from __future__ import annotations

from typing import Any, Dict

from src.bussiness.全局智能定投处理.increase import increase_all_fund_plans as increase_all_fund_plans_biz
from src.bussiness.全局智能定投处理.redeem import redeem_all_fund_plans as redeem_all_fund_plans_biz
from src.common.constant import DEFAULT_USER, QIU_XIAOYU
from src.service.用户管理.用户信息 import get_user_all_info
from src.task.runtime import logger, parse_strategy_event


def _safe_float(value: Any) -> float | None:
    try:
        if value in (None, ""):
            return None
        return float(value)
    except Exception:
        return None


def _extract_fund_code(item: Dict[str, Any]) -> str | None:
    code = (
        item.get("fund_code")
        or item.get("fundcode")
        or item.get("FundCode")
        or item.get("fcode")
        or item.get("FCODE")
        or item.get("code")
    )
    if code is None:
        return None
    code_text = str(code).strip()
    return code_text or None


def _build_stop_rate_overrides(payload: Dict[str, Any]) -> Dict[str, float]:
    raw_fund_list = payload.get("fund_list") or payload.get("funds")
    if not isinstance(raw_fund_list, list):
        return {}

    overrides: Dict[str, float] = {}
    for item in raw_fund_list:
        if not isinstance(item, dict):
            continue
        fund_code = _extract_fund_code(item)
        stop_rate = _safe_float(item.get("stop_rate"))
        if not fund_code or stop_rate is None:
            continue
        overrides[fund_code] = stop_rate
    return overrides


def increase(event, context):
    increase_all_fund_plans_biz(DEFAULT_USER)
    increase_all_fund_plans_biz(QIU_XIAOYU)


def redeem(event, context):
    _evt, payload, invoke_source = parse_strategy_event(event, "global_plans_redeem")
    stop_rate_overrides = _build_stop_rate_overrides(payload if isinstance(payload, dict) else {})

    account = payload.get("account") if isinstance(payload, dict) else None
    password = payload.get("password") if isinstance(payload, dict) else None

    if account or password:
        if not all([account, password]):
            logger.error("[全局定投计划] payload 缺少 account/password，无法按指定用户执行")
            return
        user = get_user_all_info(account, password)
        if not user:
            logger.error(f"[全局定投计划] 获取用户 {account} 信息失败")
            return
        logger.info(
            f"[全局定投计划] 按 payload 执行止盈，账号={account}，基金级止盈率覆盖数={len(stop_rate_overrides)}，来源={invoke_source}"
        )
        redeem_all_fund_plans_biz(user, stop_rate_overrides=stop_rate_overrides)
        return

    logger.info(
        f"[全局定投计划] 按默认用户执行止盈，基金级止盈率覆盖数={len(stop_rate_overrides)}，来源={invoke_source}"
    )
    redeem_all_fund_plans_biz(DEFAULT_USER, stop_rate_overrides=stop_rate_overrides)
    redeem_all_fund_plans_biz(QIU_XIAOYU, stop_rate_overrides=stop_rate_overrides)
