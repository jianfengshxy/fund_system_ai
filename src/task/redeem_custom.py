from __future__ import annotations

from src.common.errors import NonRetriableError, RetriableError, ValidationError
from src.service.用户管理.用户信息 import get_user_all_info
from src.task.runtime import logger, parse_strategy_event


def handler(event, context):
    try:
        _evt, payload, invoke_source = parse_strategy_event(event, "custom_redeem")
        account = payload.get("account")
        password = payload.get("password")
        if not all([account, password]):
            logger.error("Payload缺少必填参数: account, password")
            return
        user = get_user_all_info(account, password)
        if not user:
            logger.error(f"获取用户 {account} 信息失败")
            return
        from src.API.组合管理.SubAccountMrg import getSubAssetMultList
        from src.bussiness.自定义组合.redeem import redeem as biz_redeem
        from src.service.自选基金.自选组合服务 import get_all_group_names, get_group_funds_by_name

        all_favorite_groups = get_all_group_names(user)
        if not all_favorite_groups:
            logger.warning("该用户下无任何自选组合，直接返回")
            return
        favorite_set = {g for g in all_favorite_groups}
        sub_asset_response = getSubAssetMultList(user)
        if not sub_asset_response.Success or not sub_asset_response.Data:
            logger.warning("获取用户资产组合列表失败或为空")
            return
        sub_account_list = payload.get("sub_account_list", [])
        sub_account_config = {}
        if isinstance(sub_account_list, list):
            for item in sub_account_list:
                name = item.get("sub_account_name")
                amt = item.get("amount")
                if name:
                    sub_account_config[name] = amt

        for group in sub_asset_response.Data.list_group:
            sub_account_name = group.group_name
            extra = {
                "account": account,
                "sub_account_name": sub_account_name,
                "action": "custom_redeem",
                "invoke_source": invoke_source,
            }
            if not sub_account_name:
                continue
            if sub_account_name not in favorite_set:
                continue
            amount_val = 10000.0
            if sub_account_name in sub_account_config:
                cfg_amt = sub_account_config.get(sub_account_name)
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
        logger.warning(f"[自定义组合-止盈] 异常可重试：{exc}", extra={"action": "custom_redeem"})
    except ValidationError as exc:
        logger.error(f"[自定义组合-止盈] 异常参数错误：{exc}", extra={"action": "custom_redeem"})
    except NonRetriableError as exc:
        logger.error(f"[自定义组合-止盈] 异常不可重试：{exc}", extra={"action": "custom_redeem"})
    except Exception as exc:
        logger.error(f"[自定义组合-止盈] 入口异常：{exc}", extra={"action": "custom_redeem"})

