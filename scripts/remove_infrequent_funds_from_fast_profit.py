import sys
import os
import logging
from typing import List, Dict, Set

# Add root dir to sys.path
root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from src.db.database_connection import DatabaseConnection
from src.common.constant import DEFAULT_USER
from src.API.自选基金.FavorFund import get_favor_groups, remove_from_favorites, get_favor_group
from src.common.logger import get_logger

# Setup logging
logger = get_logger(__name__)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def get_frequent_index_funds(db: DatabaseConnection, days: int = 30, min_appear: int = 10) -> Set[str]:
    """
    Find index funds that appeared more than min_appear times in the last days trading days.
    Returns a set of fund codes.
    """
    # 1. Get the date range for the last 'days' distinct update dates
    recent_dates_sql = """
        SELECT DISTINCT update_date 
        FROM fund_investment_indicators 
        ORDER BY update_date DESC 
        LIMIT %s
    """
    recent_dates = db.execute_query(recent_dates_sql, (days,))
    
    if not recent_dates:
        logger.warning("No update dates found in database.")
        return set()
    
    # Extract min and max date from the result
    dates = [row['update_date'] for row in recent_dates]
    min_date = min(dates)
    max_date = max(dates)
    
    logger.info(f"Analyzing time window: {min_date} to {max_date} ({len(dates)} trading days)")
    
    # 2. Query for frequent index funds
    sql = """
        SELECT fund_code, MAX(fund_name) as fund_name, COUNT(DISTINCT update_date) as cnt
        FROM fund_investment_indicators
        WHERE update_date BETWEEN %s AND %s
          AND fund_type = '000'
        GROUP BY fund_code
        HAVING cnt > %s
        ORDER BY cnt DESC
    """
    
    results = db.execute_query(sql, (min_date, max_date, min_appear))
    logger.info(f"Found {len(results)} index funds appearing > {min_appear} times.")
    
    frequent_funds = {row['fund_code'] for row in results}
    return frequent_funds

def get_fast_profit_group_info(user) -> tuple[int, Dict[str, str]]:
    """
    Find the '快速止盈' group ID and return its current fund codes with names.
    Returns: (group_id, dict_of_existing_funds {code: name})
    """
    response = get_favor_groups(user=user)
    if not response.Success:
        logger.error(f"Failed to get favor groups: {response.FirstError}")
        return -1, {}
    
    target_group_name = "快速止盈"
    target_group_id = -1
    existing_funds = {} # code -> name
    
    groups_list = []
    if response.Data:
        if isinstance(response.Data, list):
            groups_list = response.Data
        elif isinstance(response.Data, dict):
            possible_keys = ["list_group", "ListGroup", "datas", "data", "groups"]
            for key in possible_keys:
                if key in response.Data:
                    val = response.Data[key]
                    if isinstance(val, list):
                        groups_list = val
                        break
            if not groups_list:
                for v in response.Data.values():
                    if isinstance(v, list):
                        groups_list = v
                        break
    
    for group in groups_list:
        if not isinstance(group, dict):
            continue

        group_name = group.get('groupName') or group.get('group_name') or group.get('GroupName') or group.get('gname')
        
        if group_name == target_group_name:
            target_group_id = group.get('groupId') or group.get('group_id') or group.get('GroupId')
            break
    
    # If found group, get detailed list
    if target_group_id != -1:
        detail_resp = get_favor_group(group_ids=str(target_group_id), user=user)
        if detail_resp.Success and detail_resp.Data:
            def _collect_items(data):
                items = []
                if isinstance(data, list):
                    for x in data:
                        items.extend(_collect_items(x))
                elif isinstance(data, dict):
                    if "fcode" in data or "FundCode" in data or "FCODE" in data:
                        items.append(data)
                    for k, v in data.items():
                        if isinstance(v, (list, dict)):
                            items.extend(_collect_items(v))
                return items

            funds = _collect_items(detail_resp.Data)
            for f in funds:
                code = f.get("fcode") or f.get("FundCode") or f.get("FCODE") or f.get("fund_code")
                name = f.get("shortname") or f.get("fname") or f.get("FundName") or f.get("fund_name") or "Unknown"
                if code:
                    existing_funds[str(code)] = name
                    
    return target_group_id, existing_funds

def main():
    logger.info("Starting script to remove infrequent funds from '快速止盈' group...")
    
    # 1. Connect to DB
    try:
        db = DatabaseConnection()
    except Exception as e:
        logger.error(f"Failed to connect to database: {e}")
        return

    # 2. Get frequent index funds (The "Keep" list)
    frequent_funds_set = get_frequent_index_funds(db, days=30, min_appear=10)
    
    # 3. Get '快速止盈' group info
    user = DEFAULT_USER
    group_id, existing_funds_dict = get_fast_profit_group_info(user)
    
    if group_id == -1:
        logger.error("Target group '快速止盈' not found in user's favorite groups.")
        return
        
    logger.info(f"Target Group: 快速止盈 (ID: {group_id})")
    logger.info(f"Current funds in group: {len(existing_funds_dict)}")

    # 4. Identify funds to remove
    # Remove if NOT in frequent_funds_set
    funds_to_remove = []
    for code, name in existing_funds_dict.items():
        if code not in frequent_funds_set:
            funds_to_remove.append((code, name))
            
    if not funds_to_remove:
        logger.info("No funds need to be removed. All funds in group are frequent.")
        return

    logger.info(f"Found {len(funds_to_remove)} funds to remove.")
    
    # 5. Remove funds
    removed_count = 0
    failed_count = 0
    
    for code, name in funds_to_remove:
        logger.info(f"Removing {name} ({code})...")
        try:
            resp = remove_from_favorites(fund_code=code, group_id=int(group_id), user=user)
            if resp.Success:
                logger.info(f"  -> Success")
                removed_count += 1
            else:
                logger.error(f"  -> Failed: {resp.FirstError} (Code: {resp.ErrorCode})")
                failed_count += 1
        except Exception as e:
            logger.error(f"  -> Exception: {e}")
            failed_count += 1
            
    logger.info("-" * 30)
    logger.info(f"Processing complete.")
    logger.info(f"Total to remove: {len(funds_to_remove)}")
    logger.info(f"Removed: {removed_count}")
    logger.info(f"Failed: {failed_count}")

if __name__ == "__main__":
    main()
