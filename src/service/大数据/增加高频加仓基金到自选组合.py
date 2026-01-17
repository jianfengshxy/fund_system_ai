import os
import sys
import logging
from typing import List, Dict, Set, Tuple

# Add root dir to sys.path
root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from src.db.database_connection import DatabaseConnection
from src.common.constant import DEFAULT_USER
from src.API.自选基金.FavorFund import get_favor_groups, add_to_favorites, get_favor_group
from src.common.logger import get_logger

logger = get_logger(__name__)

def get_frequent_index_funds(user, days: int = 30, min_appear: int = 10) -> List[Dict]:
    """
    Find index funds that appeared more than min_appear times in the last days trading days.
    
    Args:
        user: User object (reserved for future use/filtering)
        days: Number of days to look back
        min_appear: Minimum number of appearances
    """
    try:
        db = DatabaseConnection()
    except Exception as e:
        logger.error(f"Failed to connect to database: {e}")
        return []

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
        return []
    
    # Extract min and max date from the result
    dates = [row['update_date'] for row in recent_dates]
    min_date = min(dates)
    max_date = max(dates)
    
    logger.info(f"Analyzing time window: {min_date} to {max_date} ({len(dates)} trading days)")
    
    # 2. Query for frequent index funds
    # fund_type = '000' is typically used for Index Funds in this system
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
    return results

def _collect_items(obj) -> List[Dict]:
    """Helper to recursively collect fund items from API response"""
    items = []
    if isinstance(obj, dict):
        if any(k in obj for k in ["fcode", "FundCode", "fund_code", "FCODE", "code"]):
            items.append(obj)
        else:
            for v in obj.values():
                items.extend(_collect_items(v))
    elif isinstance(obj, list):
        for i in obj:
            items.extend(_collect_items(i))
    return items

def get_group_info(user, group_name: str) -> Tuple[int, Set[str]]:
    """
    Find the group ID and return its current fund codes.
    Returns: (group_id, set_of_existing_fund_codes)
    """
    response = get_favor_groups(user=user)
    if not response.Success:
        logger.error(f"Failed to get favor groups: {response.FirstError}")
        return -1, set()
    
    target_group_id = -1
    existing_funds = set()
    
    if not response.Data:
        return -1, set()
        
    # Handle response.Data being a dict or list
    groups_list = []
    if isinstance(response.Data, list):
        groups_list = response.Data
    elif isinstance(response.Data, dict):
        for key in ["list_group", "ListGroup", "datas", "data", "groups", "Groups", "GroupList"]:
            if key in response.Data:
                val = response.Data[key]
                if isinstance(val, list):
                    groups_list = val
                    break
        
        # If still not found, try to look for any list value
        if not groups_list:
            for v in response.Data.values():
                if isinstance(v, list):
                    groups_list = v
                    break
    
    for group in groups_list:
        if not isinstance(group, dict):
            continue

        name = group.get('groupName') or group.get('group_name') or group.get('GroupName') or group.get('gname') or group.get('Name')
        
        if name == group_name:
            target_group_id = group.get('groupId') or group.get('group_id') or group.get('GroupId') or group.get('Id')
            break
            
    # If found group, get details to find existing funds
    if target_group_id != -1:
        detail_resp = get_favor_group(group_ids=str(target_group_id), user=user)
        if detail_resp.Success and detail_resp.Data:
            funds = _collect_items(detail_resp.Data)
            for f in funds:
                code = f.get("fcode") or f.get("FundCode") or f.get("FCODE") or f.get("fund_code") or f.get("code")
                if code:
                    existing_funds.add(str(code))
                    
    return target_group_id, existing_funds

def add_frequent_funds_to_fast_profit_group(user, days: int = 30, min_appear: int = 10, group_name: str = "快速止盈") -> Dict[str, int]:
    """
    Main service function to add frequent funds to the specified group.
    
    Args:
        user: User object with account info
        days: Number of days to look back
        min_appear: Minimum number of appearances
        group_name: Target group name
        
    Returns:
        Dict with stats: {'total': int, 'added': int, 'skipped': int}
    """
    logger.info(f"Starting to add frequent index funds to '{group_name}' group...")
    
    # 1. Get frequent index funds (DatabaseConnection is handled inside)
    frequent_funds = get_frequent_index_funds(user, days=days, min_appear=min_appear)
    
    if not frequent_funds:
        logger.info("No funds matched the criteria.")
        return {'total': 0, 'added': 0, 'skipped': 0}

    # 2. Get group info
    group_id, existing_funds = get_group_info(user, group_name)
    
    if group_id == -1:
        logger.error(f"Target group '{group_name}' not found in user's favorite groups.")
        return {'total': len(frequent_funds), 'added': 0, 'skipped': 0}
        
    logger.info(f"Target Group: {group_name} (ID: {group_id})")
    logger.info(f"Existing funds in group: {len(existing_funds)}")

    # 3. Add funds to group
    stats = {
        'total': len(frequent_funds),
        'added': 0,
        'skipped': 0
    }
    
    for fund in frequent_funds:
        fund_code = fund['fund_code']
        fund_name = fund['fund_name']
        cnt = fund['cnt']
        
        if str(fund_code) in existing_funds:
            logger.info(f"Skip {fund_name} ({fund_code}): Already in group. (Appearances: {cnt})")
            stats['skipped'] += 1
            continue
            
        logger.info(f"Adding {fund_name} ({fund_code}) to group... (Appearances: {cnt})")
        
        try:
            resp = add_to_favorites(fund_code=fund_code, group_id=int(group_id), user=user)
            if resp.Success:
                logger.info(f"  -> Success")
                stats['added'] += 1
            else:
                # Check if error is "already exists" (ErrorCode 63117 often means duplicate/no change)
                if resp.ErrorCode == 63117 or "已存在" in str(resp.FirstError):
                    logger.info(f"  -> Already exists (API returned error indicating presence)")
                    stats['skipped'] += 1
                else:
                    logger.error(f"  -> Failed: {resp.FirstError} (Code: {resp.ErrorCode})")
        except Exception as e:
            logger.error(f"  -> Exception: {e}")
            
    logger.info("-" * 30)
    logger.info(f"Processing complete. Stats: {stats}")
    return stats

if __name__ == "__main__":
    add_frequent_funds_to_fast_profit_group(user=DEFAULT_USER, group_name="快速止盈")
