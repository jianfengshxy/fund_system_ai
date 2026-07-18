from __future__ import annotations

from src.bussiness.最优止盈组合.add_new import add_new_funds as add_new_biz
from src.common.errors import NonRetriableError, RetriableError, ValidationError
from src.service.用户管理.用户信息 import get_user_all_info
from src.task.runtime import logger, parse_strategy_event


def handler(event, context):
    try:
        _evt, payload, invoke_source = parse_strategy_event(event, "add_new")
        account = payload.get("account")
        password = payload.get("password")
        sub_account_name = payload.get("sub_account_name")
        total_budget = payload.get("total_budget")
        amount = payload.get("amount")
        fund_type = payload.get("fund_type", "all")
        extra = {
            "account": account,
            "sub_account_name": sub_account_name,
            "action": "add_new",
            "invoke_source": invoke_source,
        }
        if not all([account, password, sub_account_name, total_budget]):
            logger.error("Payload缺少必填参数: account, password, sub_account_name 或 total_budget")
            return
        user = get_user_all_info(account, password)
        if not user:
            logger.error(f"获取用户 {account} 信息失败")
            return
        logger.info(f"开始为用户 {user.customer_name} 执行新增基金操作", extra=extra)
        add_new_biz(user, sub_account_name, total_budget, amount, fund_type)
    except RetriableError as exc:
        logger.warning(f"add_new 异常可重试: {exc}", extra={"action": "add_new"})
    except ValidationError as exc:
        logger.error(f"add_new 异常参数错误: {exc}", extra={"action": "add_new"})
    except NonRetriableError as exc:
        logger.error(f"add_new 异常不可重试: {exc}", extra={"action": "add_new"})
    except Exception as exc:
        logger.error(f"add_new 函数执行错误: {str(exc)}", extra={"action": "add_new"})

