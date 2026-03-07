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
from src.API.资产管理.getAssetListOfSub import get_asset_list_of_sub
from src.API.组合管理.SubAccountMrg import getSubAssetMultList
from src.API.工具.utils import get_fund_system_time_trade
from src.common.constant import DEFAULT_USER

logger = get_logger("SyncSubAccountFundAsset")

def create_table_if_not_exists():
    """
    Create user_sub_account_fund_asset_daily table if it doesn't exist
    """
    db = DatabaseConnection()
    sql = """
    CREATE TABLE IF NOT EXISTS user_sub_account_fund_asset_daily (
        date DATE NOT NULL COMMENT '净值日期',
        customer_no VARCHAR(64) NOT NULL COMMENT '用户客户号',
        sub_account_name VARCHAR(128) COMMENT '子账户名称',
        sub_account_no VARCHAR(64) NOT NULL DEFAULT '' COMMENT '子账户编号',
        fund_code VARCHAR(32) NOT NULL COMMENT '基金代码',
        fund_name VARCHAR(128) COMMENT '基金名称',
        fund_type VARCHAR(32) COMMENT '基金类型',
        asset_value DECIMAL(20, 4) COMMENT '资产市值',
        hold_profit DECIMAL(20, 4) COMMENT '持有收益',
        hold_profit_rate DECIMAL(10, 4) COMMENT '持有收益率(%)',
        constant_profit DECIMAL(20, 4) COMMENT '参考持有收益(ConstantProfit)',
        constant_profit_rate DECIMAL(10, 4) COMMENT '参考持有收益率(%)',
        daily_profit DECIMAL(20, 4) COMMENT '今日收益',
        total_profit DECIMAL(20, 4) COMMENT '累计收益(ProfitValue)',
        fund_nav DECIMAL(10, 4) COMMENT '单位净值',
        available_vol DECIMAL(20, 4) COMMENT '可用份额',
        on_way_count INT DEFAULT 0 COMMENT '在途交易数',
        update_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
        PRIMARY KEY (date, customer_no, sub_account_no, fund_code),
        INDEX idx_customer_date (customer_no, date)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='用户子账户基金每日资产明细表';
    """
    try:
        conn = db.get_connection()
        cursor = conn.cursor()
        cursor.execute(sql)
        
        # Check and add sub_account_name column if missing (for existing table)
        cursor.execute("SHOW COLUMNS FROM user_sub_account_fund_asset_daily LIKE 'sub_account_name'")
        if not cursor.fetchone():
            cursor.execute("ALTER TABLE user_sub_account_fund_asset_daily ADD COLUMN sub_account_name VARCHAR(128) COMMENT '子账户名称' AFTER customer_no")
            logger.info("Added column sub_account_name to user_sub_account_fund_asset_daily")
            
        conn.commit()
        cursor.close()
        db.disconnect(conn)
        logger.info("Table user_sub_account_fund_asset_daily check/creation completed.")
    except Exception as e:
        logger.error(f"Failed to create table: {e}")
        raise

def parse_nav_date(nav_date_str: str) -> datetime.date:
    """
    Parse Navdate string like "02-27" to date object.
    Assumes current year, handles year boundary if needed.
    """
    if not nav_date_str:
        return datetime.date.today()
    
    try:
        today = datetime.date.today()
        # Append current year
        date_str = f"{today.year}-{nav_date_str}"
        dt = datetime.datetime.strptime(date_str, "%Y-%m-%d").date()
        
        # If parsed date is in the future (e.g. today is 2023-12-31, nav_date is "01-01"),
        # it might mean previous year (unlikely for nav date)
        # Or if today is 2024-01-01 and nav_date is "12-31", it means 2023.
        if dt > today + datetime.timedelta(days=1):
             # Logic: NavDate shouldn't be in the future. 
             # If parsed date is significantly ahead, subtract a year.
             dt = dt.replace(year=dt.year - 1)
        
        return dt
    except Exception as e:
        logger.warning(f"Failed to parse date {nav_date_str}, using today: {e}")
        return datetime.date.today()

def safe_float(val):
    if val is None or val == "" or val == "--" or val == "---": return 0.0
    if isinstance(val, (int, float)): return float(val)
    try:
        # Remove % if present
        s = str(val).replace(',', '').replace('%', '')
        return float(s)
    except:
        return 0.0

def sync_sub_account_fund_asset_daily(user: User):
    """
    Sync user sub-account fund asset data to database
    Focuses on User Created Sub-accounts (Type 2) as per requirements.
    """
    try:
        # Check if today is a trading day
        # trade_status = get_fund_system_time_trade(user)
        # if not trade_status.Success or not trade_status.Data.get("IsTrade"):
        #     logger.info("Current day is not a trading day, skipping sync.")
        #     return

        # 1. Ensure table exists
        create_table_if_not_exists()
        
        records = []
        
        # --- Type 2: User Created Sub-accounts ---
        try:
            sub_res = getSubAssetMultList(user)
            if sub_res.Success and sub_res.Data and sub_res.Data.list_group:
                for group in sub_res.Data.list_group:
                    sub_account_no = group.sub_account_no
                    sub_account_name = group.group_name
                    
                    # Fetch detailed asset data for this sub-account
                    asset_details = get_asset_list_of_sub(user, sub_account_no)
                    
                    if not asset_details:
                        continue
                        
                    for asset in asset_details:
                        # Extract data according to requirements
                        nav_date = parse_nav_date(asset.nav_date)
                        
                        record = {
                            "date": nav_date,
                            "customer_no": user.customer_no,
                            "sub_account_name": sub_account_name,
                            "sub_account_no": sub_account_no,
                            "fund_code": asset.fund_code,
                            "fund_name": asset.fund_name,
                            "fund_type": str(asset.fund_type),
                            "asset_value": safe_float(asset.asset_value),
                            "hold_profit": safe_float(asset.hold_profit),
                            "hold_profit_rate": safe_float(asset.hold_profit_rate),
                            "constant_profit": safe_float(asset.constant_profit),
                            "constant_profit_rate": safe_float(asset.constant_profit_rate),
                            "daily_profit": safe_float(asset.daily_profit),
                            "total_profit": safe_float(asset.profit_value), # ProfitValue
                            "fund_nav": safe_float(asset.fund_nav),
                            "available_vol": safe_float(asset.available_vol),
                            "on_way_count": int(asset.on_way_transaction_count) if asset.on_way_transaction_count else 0
                        }
                        records.append(record)
                        
                logger.info(f"Processed User Sub-accounts: {len(sub_res.Data.list_group)} groups, {len(records)} fund records.")
        except Exception as e:
            logger.error(f"Error fetching user sub-accounts: {e}")

        # --- Save to DB ---
        if not records:
            logger.warning("No sub-account fund asset records to save.")
            return

        db = DatabaseConnection()
        conn = db.get_connection()
        cursor = conn.cursor()
        
        sql = """
        INSERT INTO user_sub_account_fund_asset_daily 
        (date, customer_no, sub_account_name, sub_account_no, fund_code, fund_name, fund_type, asset_value, 
         hold_profit, hold_profit_rate, constant_profit, constant_profit_rate, 
         daily_profit, total_profit, fund_nav, available_vol, on_way_count)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE
        sub_account_name = VALUES(sub_account_name),
        fund_name = VALUES(fund_name),
        fund_type = VALUES(fund_type),
        asset_value = VALUES(asset_value),
        hold_profit = VALUES(hold_profit),
        hold_profit_rate = VALUES(hold_profit_rate),
        constant_profit = VALUES(constant_profit),
        constant_profit_rate = VALUES(constant_profit_rate),
        daily_profit = VALUES(daily_profit),
        total_profit = VALUES(total_profit),
        fund_nav = VALUES(fund_nav),
        available_vol = VALUES(available_vol),
        on_way_count = VALUES(on_way_count),
        update_time = CURRENT_TIMESTAMP
        """
        
        values = []
        for r in records:
            values.append((
                r["date"],
                r["customer_no"],
                r["sub_account_name"],
                r["sub_account_no"],
                r["fund_code"],
                r["fund_name"],
                r["fund_type"],
                r["asset_value"],
                r["hold_profit"],
                r["hold_profit_rate"],
                r["constant_profit"],
                r["constant_profit_rate"],
                r["daily_profit"],
                r["total_profit"],
                r["fund_nav"],
                r["available_vol"],
                r["on_way_count"]
            ))
            
        cursor.executemany(sql, values)
        conn.commit()
        cursor.close()
        db.disconnect(conn)
        logger.info(f"Successfully synced {len(records)} sub-account fund asset records.")

    except Exception as e:
        logger.error(f"Sync failed: {e}")

if __name__ == "__main__":
    # Test
    sync_sub_account_fund_asset_daily(DEFAULT_USER)
