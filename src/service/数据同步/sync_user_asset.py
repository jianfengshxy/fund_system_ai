import sys
import os
import datetime
import logging
from decimal import Decimal

# Add root dir to sys.path
root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from src.API.资产管理.AssetManager import GetMyAssetMainPartAsync
from src.db.database_connection import DatabaseConnection
from src.common.logger import get_logger
from src.domain.user.User import User
from src.common.constant import DEFAULT_USER

logger = get_logger("SyncUserAsset")

def create_table_if_not_exists():
    """
    Create user_asset_daily table if it doesn't exist
    """
    db = DatabaseConnection()
    sql = """
    CREATE TABLE IF NOT EXISTS user_asset_daily (
        date DATE NOT NULL COMMENT '日期',
        customer_no VARCHAR(64) NOT NULL COMMENT '用户客户号',
        mobile_phone VARCHAR(20) COMMENT '手机号',
        name VARCHAR(64) COMMENT '姓名',
        total_asset DECIMAL(20, 4) COMMENT '总资产',
        total_profit DECIMAL(20, 4) COMMENT '总累计收益',
        day_profit DECIMAL(20, 4) COMMENT '今日收益',
        hqb_asset DECIMAL(20, 4) COMMENT '活期宝资产',
        hqb_profit DECIMAL(20, 4) COMMENT '活期宝累计收益',
        hqb_day_profit DECIMAL(20, 4) COMMENT '活期宝今日收益',
        fund_asset DECIMAL(20, 4) COMMENT '基金资产',
        fund_profit DECIMAL(20, 4) COMMENT '基金累计收益',
        fund_day_profit DECIMAL(20, 4) COMMENT '基金今日收益',
        update_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
        PRIMARY KEY (date, customer_no),
        INDEX idx_customer_date (customer_no, date)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='用户每日资产表';
    """
    try:
        conn = db.get_connection()
        cursor = conn.cursor()
        cursor.execute(sql)
        conn.commit()
        cursor.close()
        db.disconnect(conn)
        logger.info("Table user_asset_daily check/creation completed.")
    except Exception as e:
        logger.error(f"Failed to create table: {e}")
        raise

def sync_user_daily_asset(user: User):
    """
    Sync user asset data to database
    """
    try:
        # 1. Ensure table exists
        create_table_if_not_exists()

        # 2. Get asset data from API
        response = GetMyAssetMainPartAsync(user)
        if not response.Success or not response.Data:
            logger.error(f"Failed to get asset data for user {user.account}: {response.FirstError}")
            return

        data = response.Data
        
        # 3. Extract fields
        # YesterDayDate logic: use provided date or current date
        date_str = data.get("YesterDayDate")
        if not date_str:
            date_str = datetime.date.today().strftime("%Y-%m-%d")
        
        # Helper to safely convert to Decimal
        def to_decimal(val):
            if val is None:
                return Decimal("0.0000")
            return Decimal(str(val))

        record = {
            "date": date_str,
            "customer_no": user.customer_no,
            "mobile_phone": getattr(user, "account", ""),
            "name": getattr(user, "customer_name", ""),
            "total_asset": to_decimal(data.get("TotalValue")),
            "total_profit": to_decimal(data.get("CumulProfit")), # Assuming CumulProfit is total accumulated profit
            "day_profit": to_decimal(data.get("ProfitValue")),
            "hqb_asset": to_decimal(data.get("HqbValue")),
            "hqb_profit": to_decimal(data.get("HqbBenifit")),
            "hqb_day_profit": to_decimal(data.get("HqbDailyBenifit")),
            "fund_asset": to_decimal(data.get("TotalFundAsset")),
            "fund_profit": to_decimal(data.get("TotalFundProfit")),
            "fund_day_profit": to_decimal(data.get("FundProfitValue")),
        }

        # 4. Insert or Update into Database
        sql = """
        INSERT INTO user_asset_daily (
            date, customer_no, mobile_phone, name,
            total_asset, total_profit, day_profit,
            hqb_asset, hqb_profit, hqb_day_profit,
            fund_asset, fund_profit, fund_day_profit
        ) VALUES (
            %(date)s, %(customer_no)s, %(mobile_phone)s, %(name)s,
            %(total_asset)s, %(total_profit)s, %(day_profit)s,
            %(hqb_asset)s, %(hqb_profit)s, %(hqb_day_profit)s,
            %(fund_asset)s, %(fund_profit)s, %(fund_day_profit)s
        ) ON DUPLICATE KEY UPDATE
            mobile_phone = VALUES(mobile_phone),
            name = VALUES(name),
            total_asset = VALUES(total_asset),
            total_profit = VALUES(total_profit),
            day_profit = VALUES(day_profit),
            hqb_asset = VALUES(hqb_asset),
            hqb_profit = VALUES(hqb_profit),
            hqb_day_profit = VALUES(hqb_day_profit),
            fund_asset = VALUES(fund_asset),
            fund_profit = VALUES(fund_profit),
            fund_day_profit = VALUES(fund_day_profit);
        """
        
        # Using manual connection for safety and clarity with named parameters
        db = DatabaseConnection()
        conn = db.get_connection()
        cursor = conn.cursor()
        cursor.execute(sql, record)
        conn.commit()
        cursor.close()
        db.disconnect(conn)
        
        logger.info(f"Successfully synced asset data for user {user.account} on {date_str}")
        
    except Exception as e:
        logger.error(f"Error syncing user asset: {e}")
        raise

if __name__ == "__main__":
    # Test with DEFAULT_USER
    try:
        logger.info(f"Starting sync for DEFAULT_USER: {DEFAULT_USER.account}")
        sync_user_daily_asset(DEFAULT_USER)
        logger.info("Sync completed.")
    except Exception as e:
        logger.error(f"Test failed: {e}")
