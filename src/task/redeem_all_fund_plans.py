from __future__ import annotations

from src.bussiness.全局智能定投处理.redeem import redeem_all_fund_plans as redeem_all_fund_plans_biz
from src.common.constant import DEFAULT_USER, QIU_XIAOYU


def handler(event, context):
    redeem_all_fund_plans_biz(DEFAULT_USER)
    redeem_all_fund_plans_biz(QIU_XIAOYU)

