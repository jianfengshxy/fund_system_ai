from __future__ import annotations

from src.bussiness.最优止盈组合.add_new import add_new_funds as add_new_biz
from src.bussiness.最优止盈组合.increase import increase as increase_biz
from src.bussiness.最优止盈组合.redeem import redeem as redeem_biz
from src.common.errors import NonRetriableError, RetriableError, ValidationError
from src.service.用户管理.用户信息 import get_user_all_info
from src.task.runtime import logger, parse_strategy_event


def add_new(event, context):
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


def increase(event, context):
    try:
        _evt, payload, invoke_source = parse_strategy_event(event, "increase")
        account = payload.get("account")
        password = payload.get("password")
        sub_account_name = payload.get("sub_account_name")
        total_budget = payload.get("total_budget")
        amount = payload.get("amount")
        fund_type = payload.get("fund_type", "all")
        extra = {
            "account": account,
            "sub_account_name": sub_account_name,
            "action": "increase",
            "invoke_source": invoke_source,
        }
        if not all([account, password, sub_account_name, total_budget]):
            logger.error("Payload缺少必填参数: account, password, sub_account_name 或 total_budget")
            return
        user = get_user_all_info(account, password)
        if not user:
            logger.error(f"获取用户 {account} 信息失败")
            return
        logger.info(
            f"开始为用户 {user.customer_name} 执行加仓操作，组合：{sub_account_name}，预算：{total_budget}，amount：{amount}，fund_type：{fund_type}",
            extra=extra,
        )
        success = increase_biz(user, sub_account_name, total_budget, amount, fund_type)
        if success:
            logger.info(f"用户 {user.customer_name} 加仓操作成功", extra=extra)
        else:
            logger.error(f"用户 {user.customer_name} 加仓操作失败", extra=extra)
    except RetriableError as exc:
        logger.warning(f"执行加仓时发生异常可重试: {exc}", extra={"action": "increase"})
    except ValidationError as exc:
        logger.error(f"执行加仓时发生异常参数错误: {exc}", extra={"action": "increase"})
    except NonRetriableError as exc:
        logger.error(f"执行加仓时发生异常不可重试: {exc}", extra={"action": "increase"})
    except Exception as exc:
        logger.error(f"执行加仓时发生异常: {exc}", extra={"action": "increase"})


def redeem(event, context):
    try:
        _evt, payload, invoke_source = parse_strategy_event(event, "redeem")
        account = payload.get("account")
        password = payload.get("password")
        sub_account_name = payload.get("sub_account_name")
        total_budget = payload.get("total_budget")
        extra = {
            "account": account,
            "sub_account_name": sub_account_name,
            "action": "redeem",
            "invoke_source": invoke_source,
        }
        if not all([account, password, sub_account_name]):
            logger.error("Payload缺少必填参数: account, password, sub_account_name")
            return
        user = get_user_all_info(account, password)
        if not user:
            logger.error(f"获取用户 {account} 信息失败")
            return
        logger.info(
            f"开始为用户 {user.customer_name} 执行止盈操作，组合：{sub_account_name}，预算：{total_budget}",
            extra=extra,
        )
        success = redeem_biz(user, sub_account_name, total_budget)
        if success:
            logger.info(f"用户 {user.customer_name} 止盈操作成功", extra=extra)
        else:
            logger.error(f"用户 {user.customer_name} 止盈操作失败", extra=extra)
    except RetriableError as exc:
        logger.warning(f"执行止盈时发生异常可重试: {exc}", extra={"action": "redeem"})
    except ValidationError as exc:
        logger.error(f"执行止盈时发生异常参数错误: {exc}", extra={"action": "redeem"})
    except NonRetriableError as exc:
        logger.error(f"执行止盈时发生异常不可重试: {exc}", extra={"action": "redeem"})
    except Exception as exc:
        logger.error(f"执行止盈时发生异常: {exc}", extra={"action": "redeem"})

