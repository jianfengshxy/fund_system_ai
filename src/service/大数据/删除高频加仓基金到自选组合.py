import os
import sys
import logging
from typing import List, Dict, Set, Tuple

# Add root dir to sys.path
root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from src.common.constant import DEFAULT_USER
from src.API.自选基金.FavorFund import get_favor_groups, remove_from_favorites, get_favor_group
from src.common.logger import get_logger
from src.service.大数据.高频加仓基金查询 import query_frequent_index_funds

logger = get_logger(__name__)

def get_frequent_index_funds(user, days: int = 180, min_appear: int = 10) -> Set[str]:
    """
    Find index funds that appeared more than min_appear times in the last days trading days.
    Returns a set of fund codes.
    
    Args:
        user: User object (reserved for future use/filtering)
        days: Number of days to look back
        min_appear: Minimum number of appearances
    """
    results = query_frequent_index_funds(user=user, days=days, min_appear=min_appear)
    return {
        str(row['fund_code'])
        for row in (results or [])
        if isinstance(row, dict) and row.get('fund_code')
    }

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

def get_group_info(user, group_name: str) -> Tuple[int, Dict[str, str]]:
    """
    Find the group ID and return its current fund codes with names.
    Returns: (group_id, dict_of_existing_funds {code: name})
    """
    response = get_favor_groups(user=user)
    if not response.Success:
        logger.error(f"Failed to get favor groups: {response.FirstError}")
        return -1, {}
    
    target_group_id = -1
    existing_funds = {} # code -> name
    
    if not response.Data:
        return -1, {}
        
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
                name = f.get("shortname") or f.get("fname") or f.get("FundName") or f.get("fund_name") or "Unknown"
                if code:
                    existing_funds[str(code)] = name
                    
    return target_group_id, existing_funds

def remove_infrequent_funds_from_group(user, group_name: str, days: int = 180, min_appear: int = 10) -> Dict[str, int]:
    """
    Main service function to remove funds from the specified group if they are not frequent enough.
    
    Args:
        user: User object with account info
        group_name: Target group name (Required, cannot be empty)
        days: Number of days to look back
        min_appear: Minimum number of appearances
        
    Returns:
        Dict with stats: {'total_checked': int, 'removed': int, 'failed': int}
    """
    if not group_name:
        logger.error("group_name cannot be empty.")
        return {'total_checked': 0, 'removed': 0, 'failed': 0}

    logger.info(f"Starting to clean up '{group_name}' group (removing infrequent funds)...")
    
    # 1. Get frequent index funds (The "Keep" list)
    frequent_funds_set = get_frequent_index_funds(user, days=days, min_appear=min_appear)
    
    # 活期宝余额风控检查：如果HQB余额大于总资产的 20%，则跳过清理
    # 逻辑：因为活期宝超过限额，所以要扩大投资目标，不删除过期的基金，只有当小于阀值的时候，才清理过期的加仓风向标基金
    # 注意：check_hqb_risk_allowed(user, threshold=20.0) 返回 True 表示余额充足（>20%），返回 False 表示余额不足（<20%）。
    # 但这里的逻辑反过来了：
    # 如果余额 > 20% (充足) -> 不删除 (跳过清理)
    # 如果余额 < 20% (不足) -> 删除 (清理过期基金)
    # check_hqb_risk_allowed 的默认行为是：如果 余额/总资产 < 阈值，返回 False (拦截买入/风险高)。如果 >= 阈值，返回 True (允许买入/风险低)。
    # 所以：
    # check_hqb_risk_allowed(user, 20.0) == True  => 余额 >= 20% => 跳过清理
    # check_hqb_risk_allowed(user, 20.0) == False => 余额 < 20%  => 执行清理
    
    # if check_hqb_risk_allowed(user, threshold=20.0):
    #     logger.info("[风控检查] 活期宝余额充足(>20%)，为扩大投资目标，跳过清理过期风向标基金流程。")
    #     return {'total_checked': 0, 'removed': 0, 'failed': 0}
    # else:
    #     logger.info("[风控检查] 活期宝余额较低(<20%)，执行清理过期风向标基金流程，以聚焦核心标的。")

    # 2. Get group info
    group_id, existing_funds_dict = get_group_info(user, group_name)
    
    if group_id == -1:
        logger.error(f"Target group '{group_name}' not found in user's favorite groups.")
        return {'total_checked': 0, 'removed': 0, 'failed': 0}
        
    logger.info(f"Target Group: {group_name} (ID: {group_id})")
    logger.info(f"Current funds in group: {len(existing_funds_dict)}")

    # 3. Identify funds to remove
    # Remove if NOT in frequent_funds_set
    funds_to_remove = []
    for code, name in existing_funds_dict.items():
        if code not in frequent_funds_set:
            funds_to_remove.append((code, name))
            
    if not funds_to_remove:
        logger.info("No funds need to be removed. All funds in group are frequent.")
        return {'total_checked': len(existing_funds_dict), 'removed': 0, 'failed': 0}

    logger.info(f"Found {len(funds_to_remove)} funds to remove.")
    
    # 4. Remove funds
    stats = {
        'total_checked': len(existing_funds_dict),
        'removed': 0,
        'failed': 0
    }
    
    for code, name in funds_to_remove:
        logger.info(f"Removing {name} ({code})...")
        try:
            resp = remove_from_favorites(fund_code=code, group_id=int(group_id), user=user)
            if resp.Success:
                logger.info(f"  -> Success")
                stats['removed'] += 1
            else:
                logger.error(f"  -> Failed: {resp.FirstError} (Code: {resp.ErrorCode})")
                stats['failed'] += 1
        except Exception as e:
            logger.error(f"  -> Exception: {e}")
            stats['failed'] += 1
            
    logger.info("-" * 30)
    logger.info(f"Processing complete. Stats: {stats}")
    return stats

if __name__ == "__main__":
    remove_infrequent_funds_from_group(user=DEFAULT_USER, group_name="快速止盈")
