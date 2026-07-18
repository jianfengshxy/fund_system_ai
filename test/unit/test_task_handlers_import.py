from __future__ import annotations

import importlib
import inspect


HANDLER_MODULES = [
    "src.task.redeem",
    "src.task.increase",
    "src.task.add_new",
    "src.task.add_new_jianlong",
    "src.task.increase_jianlong",
    "src.task.increase_all_fund_plans",
    "src.task.redeem_all_fund_plans",
    "src.task.daily_task",
    "src.task.create_period_index_investment",
    "src.task.dissolve_period_index_investment",
    "src.task.fixed_ratio_redeem",
    "src.task.redeem_jianlong",
    "src.task.add_new_custom",
    "src.task.increase_custom",
    "src.task.redeem_custom",
    "src.task.increase_gold_portfolio",
    "src.task.redeem_gold_portfolio",
    "src.task.increase_gold_dimension_portfolio",
    "src.task.redeem_gold_dimension_portfolio",
]


def test_task_handlers_importable():
    for module_name in HANDLER_MODULES:
        module = importlib.import_module(module_name)
        assert hasattr(module, "handler")
        fn = getattr(module, "handler")
        assert callable(fn)
        signature = inspect.signature(fn)
        assert len(signature.parameters) >= 2

