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
from src.API.自选基金.FavorFund import get_favor_groups, add_to_favorites
from src.common.logger import get_logger

# Setup logging
logger = get_logger(__name__)
logging.basicConfig(level=logging.INFO)

def get_frequent_index_funds(db: DatabaseConnection, days: int = 30, min_appear: int = 10) -> List[Dict]:
    """
    Find index funds that appeared more than min_appear times in the last days trading days.
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

def get_fast_profit_group_id(user) -> tuple[int, Set[str]]:
    """
    Find the '快速止盈' group ID and return its current fund codes.
    Returns: (group_id, set_of_existing_fund_codes)
    """
    response = get_favor_groups(user=user)
    if not response.Success:
        logger.error(f"Failed to get favor groups: {response.FirstError}")
        return -1, set()
    
    target_group_name = "快速止盈"
    target_group_id = -1
    existing_funds = set()
    
    if response.Data:
        # Handle response.Data being a dict or list
        groups_list = []
        if isinstance(response.Data, list):
            groups_list = response.Data
        elif isinstance(response.Data, dict):
            # Try to find the list under common keys
            # Based on error "dict object has no attribute list_group", maybe the key IS 'list_group'?
            # If the user code was trying .list_group, maybe they saw it somewhere or guessed.
            # But since it's a dict, we must use ["list_group"].
            possible_keys = ["list_group", "ListGroup", "datas", "data", "groups"]
            for key in possible_keys:
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
        
        if not groups_list:
             logger.warning(f"Could not find groups list in response. Data type: {type(response.Data)}")
             if isinstance(response.Data, dict):
                 logger.warning(f"Data keys: {response.Data.keys()}")

        for group in groups_list:
            # Ensure group is a dict (it should be)
            if not isinstance(group, dict):
                continue

            # Check various possible key names for group name
            group_name = group.get('groupName') or group.get('group_name') or group.get('GroupName') or group.get('gname')
            
            if group_name == target_group_name:
                target_group_id = group.get('groupId') or group.get('group_id') or group.get('GroupId')
                # Collect existing funds in this group to avoid duplicates
                # The group object might contain funds directly or we might need to query group details.
                # get_favor_groups typically returns a summary. The 'funds' might be in 'related_funds' or similar.
                # Let's inspect the structure if possible, but safely we can iterate 'funds' if present.
                
                # Based on previous file reading (FavorFund.py), get_favor_groups returns a list of groups.
                # Each group usually has a list of funds.
                # Let's try to extract funds if available.
                funds_list = group.get('funds', [])
                # If funds_list is empty, it might be because the summary doesn't include full list.
                # But typically we can just rely on add_to_favorites handling duplicates, 
                # or we could call get_favor_group(group_id) to be sure. 
                # For now, let's assume we can rely on the API or empty set if not found.
                
                # Let's try to get details to be sure
                from src.API.自选基金.FavorFund import get_favor_group
                detail_resp = get_favor_group(group_ids=str(target_group_id), user=user)
                if detail_resp.Success and detail_resp.Data:
                    # detail_resp.Data might be a list or dict depending on API
                    # The test code used _collect_items(group_resp.Data)
                    pass 
                    # We will do a robust collection below using the test code's logic if needed.
                    # But actually, simpler is to just return the ID and let the add function handle duplication (API usually idempotent or returns specific error).
                
                # Let's try to parse funds from detail_resp if possible, otherwise empty set.
                if detail_resp.Success and detail_resp.Data:
                     # Data structure varies, let's try to be generic
                     data_list = detail_resp.Data if isinstance(detail_resp.Data, list) else [detail_resp.Data]
                     for item in data_list:
                         # Flatten if needed
                         pass
                
                break
    
    # If found group, let's get the accurate list of existing funds
    if target_group_id != -1:
        from src.API.自选基金.FavorFund import get_favor_group
        detail_resp = get_favor_group(group_ids=str(target_group_id), user=user)
        if detail_resp.Success and detail_resp.Data:
            # Assuming Data is a list of funds or contains it
            # Flatten logic from test_favor_group_get.py
            def _collect_items(data):
                items = []
                if isinstance(data, list):
                    for x in data:
                        items.extend(_collect_items(x))
                elif isinstance(data, dict):
                    # Check if this dict represents a fund
                    if "fcode" in data or "FundCode" in data or "FCODE" in data:
                        items.append(data)
                    # Also check nested lists
                    for k, v in data.items():
                        if isinstance(v, (list, dict)):
                            items.extend(_collect_items(v))
                return items

            funds = _collect_items(detail_resp.Data)
            for f in funds:
                code = f.get("fcode") or f.get("FundCode") or f.get("FCODE") or f.get("fund_code")
                if code:
                    existing_funds.add(str(code))
                    
    return target_group_id, existing_funds

def main():
    logger.info("Starting script to add frequent index funds to '快速止盈' group...")
    
    # 1. Connect to DB
    try:
        db = DatabaseConnection()
    except Exception as e:
        logger.error(f"Failed to connect to database: {e}")
        return

    # 2. Get frequent index funds
    # "30个交易日内出现10次以上"
    frequent_funds = get_frequent_index_funds(db, days=30, min_appear=10)
    
    if not frequent_funds:
        logger.info("No funds matched the criteria.")
        return

    # 3. Get '快速止盈' group
    user = DEFAULT_USER
    group_id, existing_funds = get_fast_profit_group_id(user)
    
    if group_id == -1:
        logger.error("Target group '快速止盈' not found in user's favorite groups.")
        return
        
    logger.info(f"Target Group: 快速止盈 (ID: {group_id})")
    logger.info(f"Existing funds in group: {len(existing_funds)}")

    # 4. Add funds to group
    added_count = 0
    skipped_count = 0
    
    for fund in frequent_funds:
        fund_code = fund['fund_code']
        fund_name = fund['fund_name']
        cnt = fund['cnt']
        
        if fund_code in existing_funds:
            logger.info(f"Skip {fund_name} ({fund_code}): Already in group. (Appearances: {cnt})")
            skipped_count += 1
            continue
            
        logger.info(f"Adding {fund_name} ({fund_code}) to group... (Appearances: {cnt})")
        
        try:
            resp = add_to_favorites(fund_code=fund_code, group_id=int(group_id), user=user)
            if resp.Success:
                logger.info(f"  -> Success")
                added_count += 1
            else:
                # Check if error is "already exists" (ErrorCode 63117 often means duplicate/no change)
                if resp.ErrorCode == 63117 or "已存在" in str(resp.FirstError):
                    logger.info(f"  -> Already exists (API returned error indicating presence)")
                    skipped_count += 1
                else:
                    logger.error(f"  -> Failed: {resp.FirstError} (Code: {resp.ErrorCode})")
        except Exception as e:
            logger.error(f"  -> Exception: {e}")
            
    logger.info("-" * 30)
    logger.info(f"Processing complete.")
    logger.info(f"Total candidates: {len(frequent_funds)}")
    logger.info(f"Added: {added_count}")
    logger.info(f"Skipped (Already present): {skipped_count}")

if __name__ == "__main__":
    main()
