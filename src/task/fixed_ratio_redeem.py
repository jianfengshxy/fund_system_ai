from __future__ import annotations

from src.bussiness.特殊止盈.定投固定比率止盈 import process_fixed_ratio_redeem
from src.service.用户管理.用户信息 import get_user_all_info
from src.task.runtime import logger, parse_strategy_event


def handler(event, context):
    try:
        _evt, payload, invoke_source = parse_strategy_event(event, "fixed_ratio_redeem")
        account = payload.get("account")
        password = payload.get("password")
        extra = {"account": account, "action": "fixed_ratio_redeem", "invoke_source": invoke_source}
        if not all([account, password]):
            logger.error("Payload缺少必填参数: account, password")
            return
        user = get_user_all_info(account, password)
        if not user:
            logger.error(f"获取用户 {account} 信息失败")
            return
        logger.info(f"开始执行固定比率止盈，用户：{user.customer_name}", extra=extra)
        process_fixed_ratio_redeem(user, payload)
        logger.info(f"用户 {user.customer_name} 固定比率止盈执行完成", extra=extra)
    except Exception as exc:
        logger.error(f"执行固定比率止盈时发生异常: {exc}", extra={"action": "fixed_ratio_redeem"})

