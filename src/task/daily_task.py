from __future__ import annotations

from src.common.constant import DEFAULT_USER
from src.service.大数据.增加高频加仓基金到自选组合 import add_frequent_funds_to_fast_profit_group
from src.service.大数据.加仓风向标服务 import save_fund_investment_indicators
from src.service.大数据.删除高频加仓基金到自选组合 import remove_infrequent_funds_from_group
from src.service.数据同步.sync_sub_account_asset import sync_sub_account_daily_asset
from src.service.数据同步.sync_sub_account_fund_asset import sync_sub_account_fund_asset_daily
from src.service.数据同步.sync_total_account_fund_asset import sync_total_account_fund_asset_daily
from src.service.数据同步.sync_user_asset import sync_user_daily_asset
from src.service.数据同步.sync_user_trade import sync_user_weekly_trades
from src.task.runtime import logger


def handler(event, context):
    save_fund_investment_indicators(DEFAULT_USER)
    add_frequent_funds_to_fast_profit_group(user=DEFAULT_USER, group_name="快速止盈")
    remove_infrequent_funds_from_group(user=DEFAULT_USER, group_name="快速止盈")
    try:
        sync_user_daily_asset(DEFAULT_USER)
        sync_user_weekly_trades(DEFAULT_USER)
        sync_sub_account_daily_asset(DEFAULT_USER)
        sync_sub_account_fund_asset_daily(DEFAULT_USER)
        sync_total_account_fund_asset_daily(DEFAULT_USER)
    except Exception as exc:
        logger.error(f"同步用户资产数据失败: {exc}")
    logger.info("同步加仓数据完成")

