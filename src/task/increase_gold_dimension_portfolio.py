from __future__ import annotations

from src.bussiness.黄金异次元.increase import increase as gold_dimension_increase_biz
from src.service.用户管理.用户信息 import get_user_all_info
from src.task.runtime import logger, parse_strategy_event


def handler(event, context):
    try:
        _evt, payload, invoke_source = parse_strategy_event(event, "gold_dimension_increase")
        account = payload.get("account")
        password = payload.get("password")
        sub_account_name = payload.get("sub_account_name")
        amount = payload.get("amount", 50000.0)
        extra = {
            "account": account,
            "sub_account_name": sub_account_name,
            "action": "gold_dimension_increase",
            "invoke_source": invoke_source,
        }
        if not all([account, password, sub_account_name]):
            logger.error("Payload缺少必填参数")
            return
        user = get_user_all_info(account, password)
        if not user:
            logger.error(f"获取用户 {account} 信息失败")
            return
        logger.info("[黄金异次元组合] 开始执行加仓检查...", extra=extra)
        success = gold_dimension_increase_biz(user, sub_account_name, amount)
        if success:
            logger.info("[黄金异次元组合] 加仓检查/执行成功", extra=extra)
        else:
            logger.info("[黄金异次元组合] 未触发加仓或执行失败", extra=extra)
    except Exception as exc:
        logger.error(f"increase_gold_dimension_portfolio 异常: {exc}", extra={"action": "gold_dimension_increase"})

