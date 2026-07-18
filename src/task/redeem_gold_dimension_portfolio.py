from __future__ import annotations

from src.bussiness.黄金异次元.redeem import redeem as gold_dimension_redeem_biz
from src.service.用户管理.用户信息 import get_user_all_info
from src.task.runtime import logger, parse_strategy_event


def handler(event, context):
    try:
        _evt, payload, invoke_source = parse_strategy_event(event, "gold_dimension_redeem")
        account = payload.get("account")
        password = payload.get("password")
        sub_account_name = payload.get("sub_account_name")
        extra = {
            "account": account,
            "sub_account_name": sub_account_name,
            "action": "gold_dimension_redeem",
            "invoke_source": invoke_source,
        }
        if not all([account, password, sub_account_name]):
            logger.error("Payload缺少必填参数")
            return
        user = get_user_all_info(account, password)
        if not user:
            logger.error(f"获取用户 {account} 信息失败")
            return
        logger.info("[黄金异次元组合] 开始执行止盈检查...", extra=extra)
        success = gold_dimension_redeem_biz(user, sub_account_name)
        if success:
            logger.info("[黄金异次元组合] 止盈检查/执行成功", extra=extra)
        else:
            logger.info("[黄金异次元组合] 未触发止盈或执行失败", extra=extra)
    except Exception as exc:
        logger.error(f"redeem_gold_dimension_portfolio 异常: {exc}", extra={"action": "gold_dimension_redeem"})

