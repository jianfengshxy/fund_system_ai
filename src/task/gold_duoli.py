from __future__ import annotations

from src.bussiness.黄金多利组合.increase import increase as gold_increase_biz
from src.bussiness.黄金多利组合.redeem import redeem as gold_redeem_biz
from src.service.用户管理.用户信息 import get_user_all_info
from src.task.runtime import logger, parse_strategy_event


def increase(event, context):
    try:
        _evt, payload, invoke_source = parse_strategy_event(event, "gold_increase")
        account = payload.get("account")
        password = payload.get("password")
        sub_account_name = payload.get("sub_account_name")
        amount = payload.get("amount", 2000.0)
        init_amount = payload.get("init_amount")
        total_limit = payload.get("total_limit")
        fund_list = payload.get("fund_list") or payload.get("funds")
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
        if not fund_list:
            from src.service.自选基金.自选组合服务 import get_all_group_names, get_group_funds_by_name

            all_favorite_groups = get_all_group_names(user)
            favorite_set = {g for g in all_favorite_groups} if all_favorite_groups else set()
            if sub_account_name in favorite_set:
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
                        fund_amount = item.get("amount", amount)
                        built_list.append({"fund_code": code, "fund_name": name_val, "amount": fund_amount})
                    if built_list:
                        fund_list = built_list
                        logger.info(
                            f"[多利组合] 未传 fund_list，已从同名自选组合 {sub_account_name} 构建候选基金数: {len(fund_list)}",
                            extra=extra,
                        )
                else:
                    logger.warning(f"[多利组合] 未传 fund_list，且同名自选组合 {sub_account_name} 下无基金", extra=extra)
            else:
                logger.warning(f"[多利组合] 未传 fund_list，且未找到同名自选组合: {sub_account_name}", extra=extra)
        logger.info("[多利组合] 开始执行加仓检查...", extra=extra)
        success = gold_increase_biz(
            user,
            sub_account_name,
            amount,
            init_amount=init_amount,
            fund_list=fund_list,
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
        fund_list = payload.get("fund_list") or payload.get("funds")
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
        logger.info(
            f"[黄金多利组合] 入参检查: stop_rate={stop_rate}, fund_list_count={len(fund_list) if isinstance(fund_list, list) else 0}",
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
