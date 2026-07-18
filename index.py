from __future__ import annotations


def redeem(event, context):
    from src.task.optimal_profit import redeem as task_callable

    return task_callable(event, context)


def increase(event, context):
    from src.task.optimal_profit import increase as task_callable

    return task_callable(event, context)


def add_new(event, context):
    from src.task.optimal_profit import add_new as task_callable

    return task_callable(event, context)


def add_new_jianlong(event, context):
    from src.task.jianlong import add_new as task_callable

    return task_callable(event, context)


def increase_jianlong(event, context):
    from src.task.jianlong import increase as task_callable

    return task_callable(event, context)


def increase_all_fund_plans(event, context):
    from src.task.global_plans import increase as task_callable

    return task_callable(event, context)


def redeem_all_fund_plans(event, context):
    from src.task.global_plans import redeem as task_callable

    return task_callable(event, context)


def daily_task(event, context):
    from src.task.daily_task import handler as task_callable

    return task_callable(event, context)


def create_period_index_investment(event, context):
    from src.task.period_index_investment import create as task_callable

    return task_callable(event, context)


def dissolve_period_index_investment(event, context):
    from src.task.period_index_investment import dissolve as task_callable

    return task_callable(event, context)


def fixed_ratio_redeem(event, context):
    from src.task.fixed_ratio_redeem import handler as task_callable

    return task_callable(event, context)


def redeem_jianlong(event, context):
    from src.task.jianlong import redeem as task_callable

    return task_callable(event, context)


def add_new_custom(event, context):
    from src.task.custom_portfolio import add_new as task_callable

    return task_callable(event, context)


def increase_custom(event, context):
    from src.task.custom_portfolio import increase as task_callable

    return task_callable(event, context)


def redeem_custom(event, context):
    from src.task.custom_portfolio import redeem as task_callable

    return task_callable(event, context)


def increase_gold_portfolio(event, context):
    from src.task.gold_duoli import increase as task_callable

    return task_callable(event, context)


def redeem_gold_portfolio(event, context):
    from src.task.gold_duoli import redeem as task_callable

    return task_callable(event, context)


def increase_gold_dimension_portfolio(event, context):
    from src.task.gold_dimension import increase as task_callable

    return task_callable(event, context)


def redeem_gold_dimension_portfolio(event, context):
    from src.task.gold_dimension import redeem as task_callable

    return task_callable(event, context)
