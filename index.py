from __future__ import annotations


def redeem(event, context):
    from src.task.redeem import handler

    return handler(event, context)


def increase(event, context):
    from src.task.increase import handler

    return handler(event, context)


def add_new(event, context):
    from src.task.add_new import handler

    return handler(event, context)


def add_new_jianlong(event, context):
    from src.task.add_new_jianlong import handler

    return handler(event, context)


def increase_jianlong(event, context):
    from src.task.increase_jianlong import handler

    return handler(event, context)


def increase_all_fund_plans(event, context):
    from src.task.increase_all_fund_plans import handler

    return handler(event, context)


def redeem_all_fund_plans(event, context):
    from src.task.redeem_all_fund_plans import handler

    return handler(event, context)


def daily_task(event, context):
    from src.task.daily_task import handler

    return handler(event, context)


def create_period_index_investment(event, context):
    from src.task.create_period_index_investment import handler

    return handler(event, context)


def dissolve_period_index_investment(event, context):
    from src.task.dissolve_period_index_investment import handler

    return handler(event, context)


def fixed_ratio_redeem(event, context):
    from src.task.fixed_ratio_redeem import handler

    return handler(event, context)


def redeem_jianlong(event, context):
    from src.task.redeem_jianlong import handler

    return handler(event, context)


def add_new_custom(event, context):
    from src.task.add_new_custom import handler

    return handler(event, context)


def increase_custom(event, context):
    from src.task.increase_custom import handler

    return handler(event, context)


def redeem_custom(event, context):
    from src.task.redeem_custom import handler

    return handler(event, context)


def increase_gold_portfolio(event, context):
    from src.task.increase_gold_portfolio import handler

    return handler(event, context)


def redeem_gold_portfolio(event, context):
    from src.task.redeem_gold_portfolio import handler

    return handler(event, context)


def increase_gold_dimension_portfolio(event, context):
    from src.task.increase_gold_dimension_portfolio import handler

    return handler(event, context)


def redeem_gold_dimension_portfolio(event, context):
    from src.task.redeem_gold_dimension_portfolio import handler

    return handler(event, context)

