"""
每日数据同步任务

定时触发（建议 cron: 每天 19:30，基金净值更新完成后），
将当日用户的资产和交易数据同步到数据库，供后续模型训练和统计分析使用。

同步内容：
  1. 投资指标（加仓风向标）
  2. 大数据组合基金更新（快速止盈组合）
  3. 用户总资产快照        -> user_asset_daily
  4. 用户交易记录          -> user_trade_record
  5. 子账户资产汇总        -> user_sub_account_asset_daily
  6. 子账户基金持仓明细    -> user_sub_account_fund_asset_daily
  7. 总账户基金持仓明细    -> user_total_account_fund_asset_daily
"""

from __future__ import annotations

from src.common.constant import DEFAULT_USER
from src.service.大数据.增加高频加仓基金到自选组合 import add_frequent_funds_to_fast_profit_group
from src.service.大数据.加仓风向标服务 import save_fund_investment_indicators
from src.service.大数据.删除高频加仓基金到自选组合 import remove_infrequent_funds_from_group
from src.service.数据同步.sync_sub_account_asset import sync_sub_account_daily_asset
from src.service.数据同步.sync_sub_account_fund_asset import sync_sub_account_fund_asset_daily
from src.service.数据同步.sync_total_account_fund_asset import sync_total_account_fund_asset_daily
from src.service.数据同步.sync_user_asset import sync_user_daily_asset
from src.service.数据同步.sync_user_trade import sync_user_trades_daily
from src.task.runtime import logger


def handler(event, context):
    """阿里云 FC 定时触发器入口"""
    logger.info("每日数据同步任务开始")

    # 1. 大数据：更新投资指标和组合
    save_fund_investment_indicators(DEFAULT_USER)
    add_frequent_funds_to_fast_profit_group(user=DEFAULT_USER, group_name="快速止盈")
    remove_infrequent_funds_from_group(user=DEFAULT_USER, group_name="快速止盈")

    # 2. 资产和交易数据同步
    try:
        logger.info("--- 同步用户总资产 ---")
        sync_user_daily_asset(DEFAULT_USER)

        logger.info("--- 同步用户交易记录 ---")
        sync_user_trades_daily(DEFAULT_USER)

        logger.info("--- 同步子账户资产汇总 ---")
        sync_sub_account_daily_asset(DEFAULT_USER)

        logger.info("--- 同步子账户基金持仓明细 ---")
        sync_sub_account_fund_asset_daily(DEFAULT_USER)

        logger.info("--- 同步总账户基金持仓明细 ---")
        sync_total_account_fund_asset_daily(DEFAULT_USER)
    except Exception as exc:
        logger.error(f"同步用户资产数据失败: {exc}")

    logger.info("每日数据同步任务完成")

