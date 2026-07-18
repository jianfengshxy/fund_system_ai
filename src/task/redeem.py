from __future__ import annotations

from src.bussiness.最优止盈组合.redeem import redeem as redeem_biz
from src.common.errors import NonRetriableError, RetriableError, ValidationError
from src.service.用户管理.用户信息 import get_user_all_info
from src.task.runtime import logger, parse_strategy_event


def handler(event, context):
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

