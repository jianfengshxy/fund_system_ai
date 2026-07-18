from __future__ import annotations

import inspect


HANDLERS = [
    ("src.task.optimal_profit", "add_new"),
    ("src.task.optimal_profit", "increase"),
    ("src.task.optimal_profit", "redeem"),
    ("src.task.jianlong", "add_new"),
    ("src.task.jianlong", "increase"),
    ("src.task.jianlong", "redeem"),
    ("src.task.custom_portfolio", "add_new"),
    ("src.task.custom_portfolio", "increase"),
    ("src.task.custom_portfolio", "redeem"),
    ("src.task.gold_duoli", "increase"),
    ("src.task.gold_duoli", "redeem"),
    ("src.task.gold_dimension", "increase"),
    ("src.task.gold_dimension", "redeem"),
    ("src.task.global_plans", "increase"),
    ("src.task.global_plans", "redeem"),
    ("src.task.daily_task", "handler"),
    ("src.task.fixed_ratio_redeem", "handler"),
    ("src.task.period_index_investment", "create"),
    ("src.task.period_index_investment", "dissolve"),
]


def test_task_handlers_importable():
    for module_name, attr_name in HANDLERS:
        module = __import__(module_name, fromlist=[attr_name])
        assert hasattr(module, attr_name)
        fn = getattr(module, attr_name)
        assert callable(fn)
        signature = inspect.signature(fn)
        assert len(signature.parameters) >= 2
