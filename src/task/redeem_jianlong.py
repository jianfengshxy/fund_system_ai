from __future__ import annotations

from src.bussiness.见龙在田.redeem import redeem as jianlong_redeem_biz
from src.service.用户管理.用户信息 import get_user_all_info
from src.task.runtime import logger, parse_strategy_event


def handler(event, context):
    try:
        _evt, payload, invoke_source = parse_strategy_event(event, "jianlong_redeem")
        account = payload.get("account")
        password = payload.get("password")
        sub_account_name = payload.get("sub_account_name")
        total_budget = payload.get("total_budget")
        extra = {
            "account": account,
            "sub_account_name": sub_account_name,
            "action": "jianlong_redeem",
            "invoke_source": invoke_source,
        }
        if not all([account, password, sub_account_name]):
            logger.error("Payload缺少必填参数")
            return
        user = get_user_all_info(account, password)
        if not user:
            logger.error(f"获取用户 {account} 信息失败")
            return
        logger.info("[见龙在田] 开始执行止盈...", extra=extra)
        success = jianlong_redeem_biz(user, sub_account_name, total_budget)
        if success:
            logger.info("[见龙在田] 止盈成功", extra=extra)
        else:
            logger.error("[见龙在田] 止盈失败", extra=extra)
    except Exception as exc:
        logger.error(f"redeem_jianlong 异常: {exc}", extra={"action": "jianlong_redeem"})

