from __future__ import annotations

from src.bussiness.全局智能定投处理.increase import increase_all_fund_plans as increase_all_fund_plans_biz
from src.bussiness.全局智能定投处理.redeem import redeem_all_fund_plans as redeem_all_fund_plans_biz
from src.common.constant import DEFAULT_USER, QIU_XIAOYU


def increase(event, context):
    increase_all_fund_plans_biz(DEFAULT_USER)
    increase_all_fund_plans_biz(QIU_XIAOYU)


def redeem(event, context):
    redeem_all_fund_plans_biz(DEFAULT_USER)
    redeem_all_fund_plans_biz(QIU_XIAOYU)

