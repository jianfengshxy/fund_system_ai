import sys
import os
import datetime
import logging
from decimal import Decimal

# Add root dir to sys.path
root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from src.API.交易管理.trade import get_trades_list, get_trade_order_result
from src.service.定投管理.定投查询.定投查询 import get_all_fund_plan_details
from src.API.组合管理.SubAccountMrg import getSubAccountList
from src.API.资产管理.getAssetListOfSub import get_asset_list_of_sub
from src.db.database_connection import DatabaseConnection
from src.common.logger import get_logger
from src.domain.user.User import User
from src.API.工具.utils import get_fund_system_time_trade
from src.common.constant import DEFAULT_USER

logger = get_logger("SyncUserTrade")

def create_table_if_not_exists():
    """
    Create user_trade_record table if it doesn't exist
    """
    db = DatabaseConnection()
    sql = """
    CREATE TABLE IF NOT EXISTS user_trade_record (
        customer_no VARCHAR(64) NOT NULL COMMENT '用户客户号',
        busin_serial_no VARCHAR(64) NOT NULL COMMENT '交易流水号',
        product_code VARCHAR(20) COMMENT '基金/产品代码',
        product_name VARCHAR(128) COMMENT '产品名称',
        business_type VARCHAR(64) COMMENT '业务类型',
        business_code VARCHAR(64) COMMENT '业务代码',
        apply_amount DECIMAL(20, 4) COMMENT '申请金额/份额',
        apply_count DECIMAL(20, 4) COMMENT '申请数量',
        confirm_count DECIMAL(20, 4) COMMENT '确认份额',
        status VARCHAR(32) COMMENT '状态',
        strike_start_date DATETIME COMMENT '交易发生时间',
        app_state_text VARCHAR(64) COMMENT 'APP状态文案',
        remark TEXT COMMENT '备注',
        sub_account_no VARCHAR(64) NULL COMMENT '子账户编号',
        sub_account_name VARCHAR(128) NULL COMMENT '子账户名称',
        update_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
        PRIMARY KEY (customer_no, busin_serial_no),
        INDEX idx_customer_date (customer_no, strike_start_date)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='用户交易记录表';
    """
    try:
        conn = db.get_connection()
        cursor = conn.cursor()
        cursor.execute(sql)
        
        # 尝试添加新增字段（如果表已存在）
        try:
            cursor.execute("ALTER TABLE user_trade_record ADD COLUMN sub_account_no VARCHAR(64) NULL COMMENT '子账户编号'")
        except Exception:
            pass # 忽略已存在错误
            
        try:
            cursor.execute("ALTER TABLE user_trade_record ADD COLUMN sub_account_name VARCHAR(128) NULL COMMENT '子账户名称'")
        except Exception:
            pass # 忽略已存在错误
            
        conn.commit()
        cursor.close()
        db.disconnect(conn)
        logger.info("Table user_trade_record check/creation completed.")
    except Exception as e:
        logger.error(f"Failed to create table: {e}")
        raise

def sync_user_weekly_trades(user: User):
    """
    Sync user weekly trade records to database
    """
    try:
        # Check if today is a trading day
        # trade_status = get_fund_system_time_trade(user)
        # if not trade_status.Success or not trade_status.Data.get("IsTrade"):
        #     logger.info("Current day is not a trading day, skipping sync.")
        #     return

        # 1. Ensure table exists
        create_table_if_not_exists()

        # 2. Get weekly trade records from API
        # date_type="1" means recent 1 month (changed from "5" which is 1 week)
        trades = get_trades_list(user, date_type="1")
        
        if not trades:
            logger.info(f"No trade records found for user {user.account} in the last month.")
            return

        logger.info(f"Found {len(trades)} trade records for user {user.account} in the last month.")
        
        # 2.0 Fetch all fund plans to map fund_code to sub_account (for '定投' trades where get_trade_order_result fails)
        fund_plan_map = {}
        try:
            # Fetch all plans with details (including sub-account info)
            # get_all_fund_plan_details returns List[FundPlanDetail]
            plan_details = get_all_fund_plan_details(user)
            if plan_details:
                for detail in plan_details:
                    plan = detail.rationPlan
                    if plan and plan.fundCode and plan.subAccountNo:
                        fund_plan_map[plan.fundCode] = {
                            "sub_account_no": plan.subAccountNo,
                            "sub_account_name": plan.subAccountName
                        }
            logger.info(f"Loaded {len(fund_plan_map)} fund plans for sub-account mapping. Sample codes: {list(fund_plan_map.keys())[:5]}")
        except Exception as e:
            logger.warning(f"Failed to load fund plans: {e}")

        # 2.1 Fetch sub-account info for each trade if missing
        for i, trade in enumerate(trades):
            if not getattr(trade, "sub_account_no", None):
                serial_no = getattr(trade, "busin_serial_no", None) or getattr(trade, "id", None) or getattr(trade, "ID", None)
                business_code = getattr(trade, "business_code", None)
                
                # Method 1: Try get_trade_order_result (works for normal Buy/Redeem)
                if serial_no and business_code:
                    try:
                        # Only fetch for valid business types (e.g. 22 for buy, 24 for redeem, etc.)
                        # Skip if business_code is not numeric to avoid API errors
                        if str(business_code).isdigit():
                            detail = get_trade_order_result(user, serial_no, str(business_code))
                            if detail and detail.get("Data"):
                                data = detail["Data"]
                                sub_no = data.get("SubAccountNo")
                                sub_name = data.get("SubAccountName")
                                
                                if sub_no:
                                    trade.sub_account_no = sub_no
                                if sub_name:
                                    trade.sub_account_name = sub_name
                                    
                                logger.info(f"Updated sub-account for trade {serial_no}: {sub_no} - {sub_name}")
                    except Exception as e:
                        # Some trades (e.g. '定投' business_code=39) fail with "当前交易不存在"
                        logger.warning(f"Failed to fetch details for trade {serial_no}: {e}")

                # Method 2: Fallback to fund plan mapping (for '定投' trades)
                if not getattr(trade, "sub_account_no", None):
                    fund_code = getattr(trade, "fund_code", None) or getattr(trade, "product_code", None)
                    # Try both fund_code and product_code (sometimes one is missing/different format?)
                    # Usually they are same.
                    if fund_code:
                        if fund_code in fund_plan_map:
                            plan_info = fund_plan_map[fund_code]
                            trade.sub_account_no = plan_info["sub_account_no"]
                            trade.sub_account_name = plan_info["sub_account_name"]
                            logger.info(f"Mapped sub-account from plan for trade {serial_no} (Fund {fund_code}): {plan_info['sub_account_no']}")
                        else:
                            # Debug: log why mapping failed for known problematic trades
                            if str(business_code) == '39':
                                logger.debug(f"Trade {serial_no} (Fund {fund_code}) not found in plan map. Available keys: {list(fund_plan_map.keys())[:5]}...")


        # 2.2 Asset Scan Fallback: If still missing sub-account info, scan current assets to map fund -> sub-account
        # This is useful for '海外基金组合' or other portfolio trades where API details are missing but assets exist.
        missing_sub_trades = [t for t in trades if not getattr(t, "sub_account_no", None)]
        if missing_sub_trades:
            logger.info(f"Still have {len(missing_sub_trades)} trades without sub-account info. Starting Asset Scan...")
            asset_sub_map = {}
            try:
                # Get all sub-accounts
                sub_res = getSubAccountList(user)
                if sub_res and sub_res.Data:
                    sub_accounts = sub_res.Data
                    for sub in sub_accounts:
                        # Handle both object and dict (just in case)
                        if isinstance(sub, dict):
                            sub_no = sub.get("SubAccountNo") or sub.get("F_002")
                            sub_name = sub.get("SubAccountName") or sub.get("F_003")
                        else:
                            sub_no = getattr(sub, "sub_account_no", None)
                            sub_name = getattr(sub, "sub_account_name", None)
                            
                        if not sub_no: continue
                        
                        # Fetch assets for this sub-account
                        try:
                            # Use with_meta=False to get just the list
                            assets = get_asset_list_of_sub(user, sub_no, with_meta=False)
                            if assets:
                                for asset in assets:
                                    f_code = getattr(asset, "fund_code", None)
                                    if f_code:
                                        # Map fund_code to sub-account
                                        # Note: If a fund is in multiple sub-accounts, the last one processed wins.
                                        # However, for unique portfolio funds, this is sufficient.
                                        asset_sub_map[f_code] = {
                                            "sub_account_no": sub_no,
                                            "sub_account_name": sub_name
                                        }
                        except Exception as e:
                            logger.warning(f"Failed to fetch assets for sub {sub_no}: {e}")
                            
                logger.info(f"Built asset map with {len(asset_sub_map)} funds from sub-accounts.")
                
                # Apply map to missing trades
                count_updated = 0
                for trade in missing_sub_trades:
                    fund_code = getattr(trade, "fund_code", None) or getattr(trade, "product_code", None)
                    if fund_code and fund_code in asset_sub_map:
                        info = asset_sub_map[fund_code]
                        trade.sub_account_no = info["sub_account_no"]
                        trade.sub_account_name = info["sub_account_name"]
                        count_updated += 1
                        logger.info(f"Mapped sub-account from assets for trade {getattr(trade, 'busin_serial_no', 'N/A')} (Fund {fund_code}): {info['sub_account_no']}")
                
                if count_updated > 0:
                    logger.info(f"Successfully mapped {count_updated} trades using asset scan.")
                        
            except Exception as e:
                logger.error(f"Asset Scan failed: {e}")


        # Helper to safely convert to Decimal
        def to_decimal(val):
            if val is None or val == "" or val == "--":
                return Decimal("0.0000")
            try:
                # Remove common non-numeric characters like commas and units
                cleaned_val = str(val).replace(",", "").replace("份", "").replace("元", "").strip()
                return Decimal(cleaned_val)
            except:
                return Decimal("0.0000")

        # 3. Prepare data for insertion
        db = DatabaseConnection()
        conn = db.get_connection()
        cursor = conn.cursor()
        
        sql = """
        INSERT INTO user_trade_record (
            customer_no, busin_serial_no, product_code, product_name,
            business_type, business_code, apply_amount, apply_count,
            confirm_count, status, strike_start_date, app_state_text, remark,
            sub_account_no, sub_account_name
        ) VALUES (
            %(customer_no)s, %(busin_serial_no)s, %(product_code)s, %(product_name)s,
            %(business_type)s, %(business_code)s, %(apply_amount)s, %(apply_count)s,
            %(confirm_count)s, %(status)s, %(strike_start_date)s, %(app_state_text)s, %(remark)s,
            %(sub_account_no)s, %(sub_account_name)s
        ) ON DUPLICATE KEY UPDATE
            product_code = VALUES(product_code),
            product_name = VALUES(product_name),
            business_type = VALUES(business_type),
            business_code = VALUES(business_code),
            apply_amount = VALUES(apply_amount),
            apply_count = VALUES(apply_count),
            confirm_count = VALUES(confirm_count),
            status = VALUES(status),
            strike_start_date = VALUES(strike_start_date),
            app_state_text = VALUES(app_state_text),
            remark = VALUES(remark),
            sub_account_no = VALUES(sub_account_no),
            sub_account_name = VALUES(sub_account_name);
        """

        inserted_count = 0
        for trade in trades:
            # Ensure busin_serial_no exists (fallback to ID or id if needed)
            serial_no = getattr(trade, "busin_serial_no", None)
            if not serial_no:
                # 尝试获取 "ID" 或 "id"
                serial_no = getattr(trade, "ID", None) or getattr(trade, "id", None)
            
            if not serial_no:
                logger.warning(f"Skipping trade record without serial number: {trade}")
                continue

            record = {
                "customer_no": user.customer_no,
                "busin_serial_no": serial_no,
                "product_code": getattr(trade, "product_code", "") or getattr(trade, "fund_code", ""),
                "product_name": getattr(trade, "product_name", ""),
                "business_type": getattr(trade, "business_type", ""),
                "business_code": getattr(trade, "business_code", ""),
                "apply_amount": to_decimal(getattr(trade, "amount", 0) or getattr(trade, "apply_amount", 0)), 
                "apply_count": to_decimal(getattr(trade, "apply_count", 0)),
                "confirm_count": to_decimal(getattr(trade, "confirm_count", 0)),
                "status": getattr(trade, "status", ""),
                "strike_start_date": getattr(trade, "strike_start_date", None) or getattr(trade, "apply_work_day", None),
                "app_state_text": getattr(trade, "app_state_text", ""),
                "remark": getattr(trade, "remark", ""),
                "sub_account_no": getattr(trade, "sub_account_no", None),
                "sub_account_name": getattr(trade, "sub_account_name", None),
            }
            
            cursor.execute(sql, record)
            inserted_count += 1

        conn.commit()
        cursor.close()
        db.disconnect(conn)
        
        logger.info(f"Successfully synced {inserted_count} trade records for user {user.account}")
        
    except Exception as e:
        logger.error(f"Error syncing user trades: {e}")
        raise

if __name__ == "__main__":
    # Test with DEFAULT_USER
    try:
        logger.info(f"Starting trade sync for DEFAULT_USER: {DEFAULT_USER.account}")
        sync_user_weekly_trades(DEFAULT_USER)
        logger.info("Trade sync completed.")
    except Exception as e:
        logger.error(f"Test failed: {e}")
