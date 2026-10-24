from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from src.common.errors import NonRetriableError, RetriableError, ValidationError
from src.domain.user.User import User
from src.service.用户管理.用户信息 import get_user_all_info
from src.task.runtime import logger, parse_strategy_event


def _build_sub_account_configs_from_payload(
    payload: Dict[str, Any], require_total_budget: bool
) -> Tuple[List[Dict[str, Any]], Optional[str]]:
    """从 payload.sub_account_list 构建组合配置列表。

    返回 (configs, first_error)。first_error 非空表示校验失败。
    每个 config 至少包含 sub_account_name；可能还带 amount / total_budget。
    """
    raw = payload.get("sub_account_list")
    if not raw or not isinstance(raw, list) or len(raw) == 0:
        return [], "Payload缺少必填参数: sub_account_list（必须显式指定要处理的组合）"
    seen_names = set()
    configs: List[Dict[str, Any]] = []
    for idx, item in enumerate(raw):
        if not isinstance(item, dict):
            return [], f"Payload.sub_account_list[{idx}] 不是对象"
        name = item.get("sub_account_name")
        if not name or not isinstance(name, str) or not name.strip():
            return [], f"Payload.sub_account_list[{idx}] 缺少 sub_account_name"
        key = name.strip()
        if key in seen_names:
            return [], f"Payload.sub_account_list 中存在重复的 sub_account_name: {key}"
        seen_names.add(key)
        cfg: Dict[str, Any] = {"sub_account_name": key}
        if "amount" in item:
            cfg["amount"] = item["amount"]
        if require_total_budget and "total_budget" in item:
            cfg["total_budget"] = item["total_budget"]
        configs.append(cfg)
    return configs, None


def _resolve_sub_account_sets(
    user: User,
) -> Tuple[Dict[str, Any], Dict[str, Any], Optional[str]]:
    """拉取自选组合名集合与资产组合名集合。

    返回 (favorite_set, asset_set, first_error)。first_error 非空表示拉取失败。
    """
    from src.API.组合管理.SubAccountMrg import getSubAssetMultList
    from src.service.自选基金.自选组合服务 import get_all_group_names

    favorite_names = get_all_group_names(user)
    if not favorite_names:
        return {}, {}, "该用户下无任何自选组合"
    favorite_set: Dict[str, Any] = {name.strip(): True for name in favorite_names if name}

    sub_asset_resp = getSubAssetMultList(user)
    if not sub_asset_resp.Success or not sub_asset_resp.Data:
        return favorite_set, {}, "获取用户资产组合列表失败或为空"
    asset_set: Dict[str, Any] = {}
    list_group = getattr(sub_asset_resp.Data, "list_group", None) or []
    for group in list_group:
        gname = getattr(group, "group_name", None)
        if gname:
            asset_set[str(gname).strip()] = True
    return favorite_set, asset_set, None


def _validate_sub_account_name(
    sub_account_name: str,
    favorite_set: Dict[str, Any],
    asset_set: Dict[str, Any],
    action: str,
) -> Optional[str]:
    """校验指定组合必须在自选组合与资产组合中均存在，任一侧缺失则返回错误信息。"""
    in_fav = sub_account_name in favorite_set
    in_asset = sub_account_name in asset_set
    if in_fav and in_asset:
        return None
    if not in_fav and not in_asset:
        return (
            f"[{action}] 组合 '{sub_account_name}' 既不在用户的自选组合中，"
            f"也不在资产组合列表中，请检查 payload.sub_account_list 的名称是否正确"
        )
    if not in_fav:
        return (
            f"[{action}] 组合 '{sub_account_name}' 不存在于用户的自选组合中，"
            f"请先在天天基金添加该名称的自选组合或修正 payload 中的 sub_account_name"
        )
    return (
        f"[{action}] 组合 '{sub_account_name}' 不存在于用户的资产组合列表中，"
        f"请先在天天基金创建同名子账户（组合）或修正 payload 中的 sub_account_name"
    )


def add_new(event, context):
    action = "custom_add_new"
    try:
        _evt, payload, invoke_source = parse_strategy_event(event, action)
        account = payload.get("account")
        password = payload.get("password")
        if not all([account, password]):
            logger.error("Payload缺少必填参数: account, password", extra={"action": action})
            return
        user = get_user_all_info(account, password)
        if not user:
            logger.error(f"获取用户 {account} 信息失败", extra={"action": action})
            return
        from src.bussiness.自定义组合.add_new import add_new as biz_add_new
        from src.service.自选基金.自选组合服务 import get_group_funds_by_name

        configs, cfg_err = _build_sub_account_configs_from_payload(payload, require_total_budget=True)
        if cfg_err:
            logger.error(cfg_err, extra={"action": action, "account": account})
            return
        favorite_set, asset_set, resolve_err = _resolve_sub_account_sets(user)
        if resolve_err:
            logger.error(resolve_err, extra={"action": action, "account": account})
            return

        for cfg in configs:
            sub_account_name = cfg["sub_account_name"]
            extra = {
                "account": account,
                "sub_account_name": sub_account_name,
                "action": action,
                "invoke_source": invoke_source,
            }
            validate_err = _validate_sub_account_name(sub_account_name, favorite_set, asset_set, action)
            if validate_err:
                logger.error(validate_err, extra=extra)
                continue
            amount_val = 10000.0
            total_budget_val = 0.0
            cfg_amt = cfg.get("amount")
            if cfg_amt is not None:
                try:
                    amount_val = float(cfg_amt)
                except (ValueError, TypeError):
                    pass
            cfg_budget = cfg.get("total_budget")
            if cfg_budget is not None:
                try:
                    total_budget_val = float(cfg_budget)
                except (ValueError, TypeError):
                    pass

            logger.info(f"组合 {sub_account_name} 准备新增，使用金额: {amount_val}，预算限制: {total_budget_val}", extra=extra)
            funds = get_group_funds_by_name(sub_account_name, user)
            if not funds:
                logger.warning(f"自选组合基金为空，跳过：{sub_account_name}", extra=extra)
                continue
            fund_list = []
            for item in funds:
                code = item.get("fcode") or item.get("FundCode") or item.get("fund_code") or item.get("FCODE") or item.get("code")
                name_val = (
                    item.get("shortname")
                    or item.get("fname")
                    or item.get("FundName")
                    or item.get("fund_name")
                    or item.get("name")
                )
                if not code:
                    continue
                fund_list.append({"fund_code": code, "fund_name": name_val, "amount": amount_val})
            logger.info(
                f"[自定义组合-新增] 开始为用户 {user.customer_name} 执行新增，组合：{sub_account_name}，基金数：{len(fund_list)}",
                extra=extra,
            )
            success = biz_add_new(user, sub_account_name, fund_list, total_budget=total_budget_val)
            if success:
                logger.info(f"[自定义组合-新增] 用户 {user.customer_name} 新增完成：{sub_account_name}", extra=extra)
            else:
                logger.info(f"[自定义组合-新增] 无新增交易或候选未达条件（非失败）：{sub_account_name}", extra=extra)
    except RetriableError as exc:
        logger.warning(f"[自定义组合-新增] 异常可重试：{exc}", extra={"action": action})
    except ValidationError as exc:
        logger.error(f"[自定义组合-新增] 异常参数错误：{exc}", extra={"action": action})
    except NonRetriableError as exc:
        logger.error(f"[自定义组合-新增] 异常不可重试：{exc}", extra={"action": action})
    except Exception as exc:
        logger.error(f"[自定义组合-新增] 入口异常：{exc}", extra={"action": action})


def increase(event, context):
    action = "custom_increase"
    try:
        _evt, payload, invoke_source = parse_strategy_event(event, action)
        account = payload.get("account")
        password = payload.get("password")
        if not all([account, password]):
            logger.error("Payload缺少必填参数: account, password", extra={"action": action})
            return
        user = get_user_all_info(account, password)
        if not user:
            logger.error(f"获取用户 {account} 信息失败", extra={"action": action})
            return
        from src.bussiness.自定义组合.increase import increase as biz_increase
        from src.service.自选基金.自选组合服务 import get_group_funds_by_name
        from src.service.资产管理.get_fund_asset_detail import get_sub_account_asset_by_name

        configs, cfg_err = _build_sub_account_configs_from_payload(payload, require_total_budget=False)
        if cfg_err:
            logger.error(cfg_err, extra={"action": action, "account": account})
            return
        favorite_set, asset_set, resolve_err = _resolve_sub_account_sets(user)
        if resolve_err:
            logger.error(resolve_err, extra={"action": action, "account": account})
            return

        for cfg in configs:
            sub_account_name = cfg["sub_account_name"]
            extra = {
                "account": account,
                "sub_account_name": sub_account_name,
                "action": action,
                "invoke_source": invoke_source,
            }
            validate_err = _validate_sub_account_name(sub_account_name, favorite_set, asset_set, action)
            if validate_err:
                logger.error(validate_err, extra=extra)
                continue
            amount_val = 10000.0
            cfg_amt = cfg.get("amount")
            if cfg_amt is not None:
                try:
                    amount_val = float(cfg_amt)
                except (ValueError, TypeError):
                    pass

            logger.info(f"组合 {sub_account_name} 准备加仓，使用金额: {amount_val}", extra=extra)
            assets = get_sub_account_asset_by_name(user, sub_account_name)
            if not assets:
                logger.warning(f"资产组合未找到详细资产信息，跳过：{sub_account_name}", extra=extra)
                continue
            funds = get_group_funds_by_name(sub_account_name, user)
            fund_list = []
            if funds:
                for item in funds:
                    code = item.get("fcode") or item.get("FundCode") or item.get("fund_code") or item.get("FCODE") or item.get("code")
                    name_val = (
                        item.get("shortname")
                        or item.get("fname")
                        or item.get("FundName")
                        or item.get("fund_name")
                        or item.get("name")
                    )
                    if not code:
                        continue
                    fund_list.append({"fund_code": code, "fund_name": name_val, "amount": amount_val})
            else:
                logger.warning(f"自选组合基金为空，改用当前持仓作为候选：{sub_account_name}", extra=extra)
                for a in assets or []:
                    try:
                        code = getattr(a, "fund_code", None)
                        name_val = getattr(a, "fund_name", None)
                        vol = float(getattr(a, "available_vol", 0.0) or 0.0)
                        val = float(getattr(a, "asset_value", 0.0) or 0.0)
                        if code and (vol > 0.01 or val > 1.0):
                            fund_list.append({"fund_code": code, "fund_name": name_val, "amount": amount_val})
                    except Exception:
                        continue
                if not fund_list:
                    logger.warning(f"无有效持仓可用于加仓，跳过：{sub_account_name}", extra=extra)
                    continue
            logger.info(
                f"[自定义组合-加仓] 开始为用户 {user.customer_name} 执行加仓，组合：{sub_account_name}，基金数：{len(fund_list)}",
                extra=extra,
            )
            success = biz_increase(user, sub_account_name, fund_list)
            if success:
                logger.info(f"[自定义组合-加仓] 用户 {user.customer_name} 加仓完成：{sub_account_name}", extra=extra)
            else:
                logger.info(f"[自定义组合-加仓] 无加仓交易或候选未达条件（非失败）：{sub_account_name}", extra=extra)
    except RetriableError as exc:
        logger.warning(f"[自定义组合-加仓] 异常可重试：{exc}", extra={"action": action})
    except ValidationError as exc:
        logger.error(f"[自定义组合-加仓] 异常参数错误：{exc}", extra={"action": action})
    except NonRetriableError as exc:
        logger.error(f"[自定义组合-加仓] 异常不可重试：{exc}", extra={"action": action})
    except Exception as exc:
        logger.error(f"[自定义组合-加仓] 入口异常：{exc}", extra={"action": action})


def redeem(event, context):
    action = "custom_redeem"
    try:
        _evt, payload, invoke_source = parse_strategy_event(event, action)
        account = payload.get("account")
        password = payload.get("password")
        if not all([account, password]):
            logger.error("Payload缺少必填参数: account, password", extra={"action": action})
            return
        user = get_user_all_info(account, password)
        if not user:
            logger.error(f"获取用户 {account} 信息失败", extra={"action": action})
            return
        from src.bussiness.自定义组合.redeem import redeem as biz_redeem
        from src.service.自选基金.自选组合服务 import get_group_funds_by_name

        configs, cfg_err = _build_sub_account_configs_from_payload(payload, require_total_budget=False)
        if cfg_err:
            logger.error(cfg_err, extra={"action": action, "account": account})
            return
        favorite_set, asset_set, resolve_err = _resolve_sub_account_sets(user)
        if resolve_err:
            logger.error(resolve_err, extra={"action": action, "account": account})
            return

        for cfg in configs:
            sub_account_name = cfg["sub_account_name"]
            extra = {
                "account": account,
                "sub_account_name": sub_account_name,
                "action": action,
                "invoke_source": invoke_source,
            }
            validate_err = _validate_sub_account_name(sub_account_name, favorite_set, asset_set, action)
            if validate_err:
                logger.error(validate_err, extra=extra)
                continue
            amount_val = 10000.0
            cfg_amt = cfg.get("amount")
            if cfg_amt is not None:
                try:
                    amount_val = float(cfg_amt)
                except (ValueError, TypeError):
                    pass

            logger.info(f"组合 {sub_account_name} 准备止盈，使用金额: {amount_val}", extra=extra)
            fund_list = None
            funds = get_group_funds_by_name(sub_account_name, user)
            if funds:
                built_list = []
                for item in funds:
                    code = item.get("fcode") or item.get("FundCode") or item.get("fund_code") or item.get("FCODE") or item.get("code")
                    name_val = (
                        item.get("shortname")
                        or item.get("fname")
                        or item.get("FundName")
                        or item.get("fund_name")
                        or item.get("name")
                    )
                    if not code:
                        continue
                    built_list.append({"fund_code": code, "fund_name": name_val, "amount": amount_val})
                if built_list:
                    fund_list = built_list

            logger.info(
                f"[自定义组合-止盈] 开始为用户 {user.customer_name} 执行止盈，组合：{sub_account_name}，候选基金数：{len(fund_list) if fund_list else 0}",
                extra=extra,
            )
            success = biz_redeem(user, sub_account_name, fund_list)
            if success:
                logger.info(f"[自定义组合-止盈] 用户 {user.customer_name} 止盈完成：{sub_account_name}", extra=extra)
            else:
                logger.info(f"[自定义组合-止盈] 无止盈交易或候选未达条件（非失败）：{sub_account_name}", extra=extra)
    except RetriableError as exc:
        logger.warning(f"[自定义组合-止盈] 异常可重试：{exc}", extra={"action": action})
    except ValidationError as exc:
        logger.error(f"[自定义组合-止盈] 异常参数错误：{exc}", extra={"action": action})
    except NonRetriableError as exc:
        logger.error(f"[自定义组合-止盈] 异常不可重试：{exc}", extra={"action": action})
    except Exception as exc:
        logger.error(f"[自定义组合-止盈] 入口异常：{exc}", extra={"action": action})
