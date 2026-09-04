from __future__ import annotations

from typing import Any, Dict, List, Optional, Set, Tuple

from src.bussiness.黄金多利组合.increase import increase as gold_increase_biz
from src.bussiness.黄金多利组合.redeem import redeem as gold_redeem_biz
from src.service.用户管理.用户信息 import get_user_all_info
from src.task.runtime import logger, parse_strategy_event


def _safe_float(value: Any, default: float) -> float:
    try:
        if value in (None, ""):
            return default
        return float(value)
    except Exception:
        return default


def _extract_fund_code(item: Dict[str, Any]) -> Optional[str]:
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
    val = str(code).strip()
    return val or None


def _extract_fund_name(item: Dict[str, Any]) -> Optional[str]:
    name_val = (
        item.get("fund_name")
        or item.get("FundName")
        or item.get("shortname")
        or item.get("fname")
        or item.get("name")
    )
    if name_val is None:
        return None
    val = str(name_val).strip()
    return val or None


def _normalize_payload_fund_list(raw: Any) -> Tuple[List[Dict[str, Any]], Set[str]]:
    if not isinstance(raw, list) or not raw:
        return [], set()
    result: List[Dict[str, Any]] = []
    seen: Set[str] = set()
    for item in raw:
        if not isinstance(item, dict):
            continue
        code = _extract_fund_code(item)
        if not code:
            continue
        if code in seen:
            continue
        normalized: Dict[str, Any] = {"fund_code": code}
        name_val = _extract_fund_name(item)
        if name_val:
            normalized["fund_name"] = name_val
        if "amount" in item:
            normalized["amount"] = _safe_float(item.get("amount"), 0.0)
        raw_init = item.get("init_amount") if "init_amount" in item else item.get("initAmount")
        if "init_amount" in item or "initAmount" in item:
            normalized["init_amount"] = _safe_float(raw_init, 0.0)
        if "limit" in item:
            normalized["limit"] = _safe_float(item.get("limit"), 0.0)
        if "stop_rate" in item:
            normalized["stop_rate"] = item.get("stop_rate")
        result.append(normalized)
        seen.add(code)
    return result, seen


def _merge_favorites_funds(
    *,
    user,
    group_name: str,
    base_funds: List[Dict[str, Any]],
    seen_codes: Set[str],
    default_amount: float,
    default_limit: Optional[float],
    extra: Dict[str, Any],
) -> Tuple[List[Dict[str, Any]], int, int]:
    from src.service.自选基金.自选组合服务 import get_all_group_names, get_group_funds_by_name

    all_favorite_groups = get_all_group_names(user)
    group_name_key = str(group_name).strip()
    favorite_set = {str(g).strip() for g in all_favorite_groups if g} if all_favorite_groups else set()
    if group_name_key not in favorite_set:
        logger.warning(f"[多利组合] 未找到同名自选组合: {group_name_key}", extra=extra)
        return base_funds, 0, 0

    funds = get_group_funds_by_name(group_name_key, user)
    if not funds:
        logger.warning(f"[多利组合] 同名自选组合 {group_name_key} 下无基金", extra=extra)
        return base_funds, 0, 0

    added = 0
    skipped = 0
    for item in funds:
        if not isinstance(item, dict):
            continue
        code = _extract_fund_code(item)
        if not code:
            continue
        if code in seen_codes:
            skipped += 1
            continue
        name_val = _extract_fund_name(item)
        if "amount" in item:
            fund_amount = _safe_float(item.get("amount"), 0.0)
        else:
            fund_amount = default_amount
        fund_item: Dict[str, Any] = {"fund_code": code, "fund_name": name_val, "amount": fund_amount}
        raw_limit = item.get("limit") if "limit" in item else None
        if raw_limit not in (None, ""):
            fund_item["limit"] = _safe_float(raw_limit, default_limit if default_limit is not None else 0.0)
        elif default_limit is not None:
            fund_item["limit"] = default_limit
        base_funds.append(fund_item)
        seen_codes.add(code)
        added += 1

    return base_funds, added, skipped


def increase(event, context):
    try:
        _evt, payload, invoke_source = parse_strategy_event(event, "gold_increase")
        account = payload.get("account")
        password = payload.get("password")
        sub_account_name = payload.get("sub_account_name")
        if "amount" in payload and payload.get("amount") in (None, ""):
            amount = 0.0
        else:
            amount = _safe_float(payload.get("amount", 2000.0), 2000.0)
        raw_init_amount = payload.get("init_amount")
        if "init_amount" in payload and raw_init_amount in (None, ""):
            init_amount = 0.0
        else:
            init_amount = raw_init_amount
        limit = payload.get("limit")
        total_limit = payload.get("total_limit")
        raw_fund_list = payload.get("fund_list") or payload.get("funds")
        fund_list, seen_codes = _normalize_payload_fund_list(raw_fund_list)
        extra = {
            "account": account,
            "sub_account_name": sub_account_name,
            "action": "gold_increase",
            "invoke_source": invoke_source,
        }
        if not all([account, password, sub_account_name]):
            logger.error("Payload缺少必填参数")
            return
        user = get_user_all_info(account, password)
        if not user:
            logger.error(f"获取用户 {account} 信息失败")
            return
        fund_list, added, skipped = _merge_favorites_funds(
            user=user,
            group_name=sub_account_name,
            base_funds=fund_list,
            seen_codes=seen_codes,
            default_amount=amount,
            default_limit=limit,
            extra=extra,
        )
        logger.info(
            f"[多利组合] 候选基金构建完成: payload={len(seen_codes) - added} 从自选组合新增={added} 去重跳过={skipped} 总计={len(fund_list)}",
            extra=extra,
        )
        logger.info("[多利组合] 开始执行加仓检查...", extra=extra)
        success = gold_increase_biz(
            user,
            sub_account_name,
            amount,
            init_amount=init_amount,
            fund_list=fund_list,
            limit=limit,
            total_limit=total_limit,
        )
        if success:
            logger.info("[多利组合] 加仓检查/执行成功", extra=extra)
        else:
            logger.info("[多利组合] 未触发加仓或执行失败", extra=extra)
    except Exception as exc:
        logger.error(f"increase_gold_portfolio 异常: {exc}", extra={"action": "gold_increase"})


def redeem(event, context):
    try:
        _evt, payload, invoke_source = parse_strategy_event(event, "gold_redeem")
        account = payload.get("account")
        password = payload.get("password")
        sub_account_name = payload.get("sub_account_name")
        stop_rate = payload.get("stop_rate")
        raw_fund_list = payload.get("fund_list") or payload.get("funds")
        fund_list, seen_codes = _normalize_payload_fund_list(raw_fund_list)
        extra = {
            "account": account,
            "sub_account_name": sub_account_name,
            "action": "gold_redeem",
            "invoke_source": invoke_source,
        }
        if not all([account, password, sub_account_name]):
            logger.error("Payload缺少必填参数")
            return
        user = get_user_all_info(account, password)
        if not user:
            logger.error(f"获取用户 {account} 信息失败")
            return
        fund_list, added, skipped = _merge_favorites_funds(
            user=user,
            group_name=sub_account_name,
            base_funds=fund_list,
            seen_codes=seen_codes,
            default_amount=0.0,
            extra=extra,
        )
        logger.info(
            f"[黄金多利组合] 入参检查: stop_rate={stop_rate}, payload_fund_count={len(seen_codes) - added}, favorites_added={added}, dedup_skipped={skipped}, fund_list_count={len(fund_list)}",
            extra=extra,
        )
        logger.info("[黄金多利组合] 开始执行止盈检查...", extra=extra)
        success = gold_redeem_biz(user, sub_account_name, fund_list, stop_rate=stop_rate)
        if success:
            logger.info("[黄金多利组合] 止盈检查/执行成功", extra=extra)
        else:
            logger.info("[黄金多利组合] 未触发止盈或执行失败", extra=extra)
    except Exception as exc:
        logger.error(f"redeem_gold_portfolio 异常: {exc}", extra={"action": "gold_redeem"})
