import sys
import os
import datetime
import logging
from decimal import Decimal
from typing import List, Dict, Optional

# Add root dir to sys.path
root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from src.common.logger import get_logger
from src.domain.user.User import User
from src.db.database_connection import DatabaseConnection
from src.domain.asset.user_sub_account_asset_daily import UserSubAccountAssetDaily
from src.API.资产管理.getFundAssetListOfBaseV3 import get_fund_asset_list_of_base_v3
from src.API.资产管理.getAssetListOfSub import get_asset_list_of_sub
from src.API.组合管理.SubAccountMrg import getSubAssetMultList
from src.service.定投管理.定投查询.定投查询 import get_target_profit_plan_details
from src.API.工具.utils import get_fund_system_time_trade
from src.common.constant import DEFAULT_USER

logger = get_logger("SyncSubAccountAsset")

def create_table_if_not_exists():
    """
    Create user_sub_account_asset_daily table if it doesn't exist
    """
    db = DatabaseConnection()
    sql = """
    CREATE TABLE IF NOT EXISTS user_sub_account_asset_daily (
        date DATE NOT NULL COMMENT '日期',
        customer_no VARCHAR(64) NOT NULL COMMENT '用户客户号',
        sub_account_no VARCHAR(64) NOT NULL DEFAULT '' COMMENT '子账户编号(空为基础账户)',
        sub_account_name VARCHAR(128) COMMENT '子账户名称',
        asset_value DECIMAL(20, 4) COMMENT '资产市值',
        hold_profit DECIMAL(20, 4) COMMENT '持有收益',
        daily_profit DECIMAL(20, 4) COMMENT '今日收益',
        total_profit DECIMAL(20, 4) COMMENT '累计收益',
        source_type INT DEFAULT 0 COMMENT '来源类型: 1=基础账户, 2=用户组合, 3=目标止盈计划',
        update_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
        PRIMARY KEY (date, customer_no, sub_account_no),
        INDEX idx_customer_date (customer_no, date)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='用户子账户每日资产表';
    """
    try:
        conn = db.get_connection()
        cursor = conn.cursor()
        cursor.execute(sql)
        conn.commit()
        cursor.close()
        db.disconnect(conn)
        logger.info("Table user_sub_account_asset_daily check/creation completed.")
    except Exception as e:
        logger.error(f"Failed to create table: {e}")
        raise

def sync_sub_account_daily_asset(user: User):
    """
    Sync user sub-account asset data to database
    Includes:
    1. Base Account (aggregated)
    2. User Created Sub-accounts
    3. Target Profit Plans
    """
    try:
        # Check if today is a trading day
        trade_status = get_fund_system_time_trade(user)
        if not trade_status.Success or not trade_status.Data.get("IsTrade"):
            logger.info("Current day is not a trading day, skipping sync.")
            return

        # 1. Ensure table exists
        create_table_if_not_exists()
        
        today = datetime.date.today()
        records: List[UserSubAccountAssetDaily] = []
        
        # Safe conversion helper
        def safe_float(val):
            if val is None or val == "": return 0.0
            if isinstance(val, (int, float)): return float(val)
            try:
                return float(str(val).replace(',', ''))
            except:
                return 0.0

        # --- Type 1: Base Account (Aggregated) ---
        try:
            base_assets, _ = get_fund_asset_list_of_base_v3(user)
            if base_assets:
                base_record = UserSubAccountAssetDaily(
                    customer_no=user.customer_no,
                    sub_account_no="",
                    sub_account_name="基础账户",
                    date=today,
                    source_type=1
                )
                
                # Aggregate
                for asset in base_assets:
                    base_record.asset_value += asset.asset_value
                    base_record.hold_profit += asset.hold_profit
                    base_record.daily_profit += asset.daily_profit
                    base_record.total_profit += asset.profit_value # profit_value is accumulated profit
                
                records.append(base_record)
                logger.info(f"Processed Base Account assets: {len(base_assets)} funds aggregated.")
        except Exception as e:
            logger.error(f"Error fetching base account assets: {e}")

        # --- Type 2: User Created Sub-accounts ---
        try:
            sub_res = getSubAssetMultList(user)
            if sub_res.Success and sub_res.Data and sub_res.Data.list_group:
                for group in sub_res.Data.list_group:
                    # Skip if it's a target profit plan (if they appear here, but usually they are separate or we want to treat them as Type 2 if they appear here?)
                    # Requirement says Type 3 is specific to "目标止盈定投".
                    # Let's assume if it's in getSubAssetMultList, we treat it as Type 2.
                    

                    # Fetch detailed asset data to get hold_profit
                    asset_details, meta = get_asset_list_of_sub(user, group.sub_account_no, with_meta=True)
                    
                    summary = meta.get("summary", {}) if meta else {}
                    sub_preview = summary.get("SubAssetPreview", {})
                    
                    # Helper to get value from summary or sub_preview
                    def get_summary_val(key_summary, key_preview):
                        val = summary.get(key_summary)
                        if val is not None and val != "" and val != "--" and val != "---":
                            return safe_float(val)
                        val = sub_preview.get(key_preview)
                        if val is not None and val != "" and val != "--" and val != "---":
                            return safe_float(val)
                        return None

                    # Hold Profit (Using TotalConstantProfit as per user request)
                    # Note: User specified that "ConstantProfit" corresponds to "HoldProfit" in UI.
                    # Priority: TotalConstantProfit -> TotalHoldProfit -> Aggregation
                    
                    # 1. Try TotalConstantProfit from summary
                    hold_profit_total = get_summary_val("TotalConstantProfit", "ConstantProfit")
                    
                    # 2. Try TotalHoldProfit from summary if above failed
                    if hold_profit_total is None:
                        hold_profit_total = get_summary_val("TotalHoldProfit", "HoldProfit")
                    
                    # 3. Fallback to aggregation
                    if hold_profit_total is None:
                        hold_profit_total = 0.0
                        if asset_details:
                            for asset in asset_details:
                                # Try constant profit first, then hold profit
                                val = safe_float(asset.constant_profit)
                                if val == 0.0 and safe_float(asset.hold_profit) != 0.0:
                                    val = safe_float(asset.hold_profit)
                                hold_profit_total += val
                    
                    # Other values (prefer summary, fallback to group info)
                    asset_value = get_summary_val("TotalAssetValue", "AssetValue")
                    if asset_value is None:
                        asset_value = safe_float(group.total_amount_decimal)
                        
                    daily_profit = get_summary_val("TotalDailyProfit", "DailyProfit")
                    if daily_profit is None:
                        daily_profit = safe_float(group.day_profit)
                        
                    total_profit = get_summary_val("TotalProfitValue", "ProfitValue")
                    if total_profit is None:
                        total_profit = safe_float(group.total_profit)

                    record = UserSubAccountAssetDaily(
                        customer_no=user.customer_no,
                        sub_account_no=group.sub_account_no,
                        sub_account_name=group.group_name,
                        date=today,
                        asset_value=asset_value,
                        hold_profit=hold_profit_total,
                        daily_profit=daily_profit,
                        total_profit=total_profit,
                        source_type=2
                    )
                    records.append(record)
                logger.info(f"Processed User Sub-accounts: {len(sub_res.Data.list_group)} groups.")
        except Exception as e:
            logger.error(f"Error fetching user sub-accounts: {e}")

        # --- Type 3: Target Profit Plans ---
        try:
            plans = get_target_profit_plan_details(user)
            if plans:
                for plan in plans:
                    # Requirement: sub_account_name like "目标止盈定投+基金代码"
                    # But the plan object already has subAccountName, likely "目标止盈定投008888"
                    # plan.rationPlan is the detail object
                    rp = plan.rationPlan
                    
                    if not rp.subAccountNo:
                        continue

                    
                    record = UserSubAccountAssetDaily(
                        customer_no=user.customer_no,
                        sub_account_no=rp.subAccountNo,
                        sub_account_name=rp.subAccountName or f"目标止盈定投{rp.fundCode}",
                        date=today,
                        asset_value=safe_float(rp.planAssets),
                        hold_profit=safe_float(rp.rationProfit), # rationProfit is likely hold profit
                        daily_profit=0.0, # Not available in plan details
                        total_profit=safe_float(rp.totalProfit),
                        source_type=3
                    )
                    records.append(record)
                logger.info(f"Processed Target Profit Plans: {len(plans)} plans.")
        except Exception as e:
            logger.error(f"Error fetching target profit plans: {e}")

        # --- Save to DB ---
        if not records:
            logger.warning("No sub-account asset records to save.")
            return

        db = DatabaseConnection()
        conn = db.get_connection()
        cursor = conn.cursor()
        
        sql = """
        INSERT INTO user_sub_account_asset_daily 
        (date, customer_no, sub_account_no, sub_account_name, asset_value, hold_profit, daily_profit, total_profit, source_type)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE
        sub_account_name = VALUES(sub_account_name),
        asset_value = VALUES(asset_value),
        hold_profit = VALUES(hold_profit),
        daily_profit = VALUES(daily_profit),
        total_profit = VALUES(total_profit),
        source_type = VALUES(source_type),
        update_time = CURRENT_TIMESTAMP
        """
        
        values = []
        for r in records:
            values.append((
                r.date,
                r.customer_no,
                r.sub_account_no,
                r.sub_account_name,
                r.asset_value,
                r.hold_profit,
                r.daily_profit,
                r.total_profit,
                r.source_type
            ))
            
        cursor.executemany(sql, values)
        conn.commit()
        cursor.close()
        db.disconnect(conn)
        logger.info(f"Successfully synced {len(records)} sub-account asset records.")

    except Exception as e:
        logger.error(f"Sync failed: {e}")
        # raise # Optional: re-raise if we want the caller to know

if __name__ == "__main__":
    # Test
    sync_sub_account_daily_asset(DEFAULT_USER)
