from __future__ import annotations

from src.bussiness.组合定投.指数型组合定投管理 import create_plan_by_group_for_index_funds, dissolve_plan_by_group_for_index_funds
from src.common.constant import DEFAULT_USER


def create(event, context):
    create_plan_by_group_for_index_funds(DEFAULT_USER, "指数基金组合", 200000.0, 10000.0)


def dissolve(event, context):
    dissolve_plan_by_group_for_index_funds(DEFAULT_USER, "指数基金组合")

