from __future__ import annotations

from src.common.errors import NonRetriableError, RetriableError, ValidationError
from src.service.用户管理.用户信息 import get_user_all_info
from src.task.runtime import logger, parse_strategy_event


def handler(event, context):
    try:
        _evt, payload, invoke_source = parse_strategy_event(event, "custom_increase")
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
        from src.bussiness.自定义组合.increase import increase as biz_increase
        from src.service.自选基金.自选组合服务 import get_all_group_names, get_group_funds_by_name
        from src.service.资产管理.get_fund_asset_detail import get_sub_account_asset_by_name

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
                "action": "custom_increase",
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
        logger.warning(f"[自定义组合-加仓] 异常可重试：{exc}", extra={"action": "custom_increase"})
    except ValidationError as exc:
        logger.error(f"[自定义组合-加仓] 异常参数错误：{exc}", extra={"action": "custom_increase"})
    except NonRetriableError as exc:
        logger.error(f"[自定义组合-加仓] 异常不可重试：{exc}", extra={"action": "custom_increase"})
    except Exception as exc:
        logger.error(f"[自定义组合-加仓] 入口异常：{exc}", extra={"action": "custom_increase"})

