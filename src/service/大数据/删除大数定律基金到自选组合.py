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
from src.db.database_connection import DatabaseConnection

logger = get_logger(__name__)

# 目标指数类型
TARGET_TYPES = ["宽基", "行业", "主题", "海外"]


def get_qualified_fund_codes() -> Set[str]:
    """
    查询满足"大数定律"条件的指数的跟踪基金代码集合。

    条件：
      - 未来持有3个月平均收益率 > 10%
      - 未来6个月平均收益率 - 3个月平均收益率 > 10%
      - 未来一年正收益概率 = 100%

    Returns:
        Set of tracking fund codes
    """
    db = DatabaseConnection()
    sql = """
        SELECT DISTINCT s.track_fund_code
        FROM market_index_static s
        INNER JOIN (
            SELECT d1.index_code, d1.avg_return_q, d1.avg_return_hy, d1.profit_rate_y
            FROM market_index_daily d1
            INNER JOIN (
                SELECT index_code, MAX(trade_date) AS max_date
                FROM market_index_daily
                GROUP BY index_code
            ) d2 ON d1.index_code = d2.index_code AND d1.trade_date = d2.max_date
        ) d ON s.index_code = d.index_code
        WHERE s.type_name IN ({placeholders})
          AND s.track_fund_code IS NOT NULL AND s.track_fund_code != ''
          AND d.avg_return_q IS NOT NULL
          AND d.avg_return_q > 10
          AND d.avg_return_hy IS NOT NULL
          AND (d.avg_return_hy - d.avg_return_q) > 10
          AND d.profit_rate_y IS NOT NULL
          AND d.profit_rate_y = 100
    """.format(placeholders=",".join(["%s"] * len(TARGET_TYPES)))

    rows = db.execute_query(sql, TARGET_TYPES)
    codes = {str(r['track_fund_code']) for r in (rows or []) if r.get('track_fund_code')}
    logger.info(f"大数定律条件查询: 满足条件的跟踪基金共 {len(codes)} 个")
    return codes


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
    existing_funds = {}  # code -> name

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


def remove_unqualified_funds_from_lln_group(user, group_name: str = "大数定律") -> Dict[str, int]:
    """
    从"大数定律"自选组合中移出不再满足条件的基金。

    筛选条件（从 market_index_daily 最新数据）：
      - 持有3个月平均收益率(avg_return_q) > 10%
      - 持有6个月平均收益率 - 3个月平均收益率 > 10%
      - 持有1年正收益概率(profit_rate_y) = 100%

    组合中不满足以上任一条件的基金将被移出。

    Args:
        user: User object with account info
        group_name: Target group name (默认 "大数定律")

    Returns:
        Dict with stats: {'total_checked': int, 'removed': int, 'failed': int}
    """
    logger.info(f"开始清理 '{group_name}' 组合（移出不再满足大数定律条件的基金）...")

    # 1. 获取满足条件的跟踪基金代码集合
    qualified_fund_codes = get_qualified_fund_codes()

    # 2. 获取组合信息
    group_id, existing_funds_dict = get_group_info(user, group_name)

    if group_id == -1:
        logger.error(f"目标组合 '{group_name}' 未找到。")
        return {'total_checked': 0, 'removed': 0, 'failed': 0}

    logger.info(f"目标组合: {group_name} (ID: {group_id})")
    logger.info(f"组合当前基金数: {len(existing_funds_dict)}")
    logger.info(f"满足大数定律条件的基金: {len(qualified_fund_codes)} 个")

    # 3. 找出需要移出的基金（在组合中但不在满足条件集合中）
    funds_to_remove = []
    for code, name in existing_funds_dict.items():
        if code not in qualified_fund_codes:
            funds_to_remove.append((code, name))

    if not funds_to_remove:
        logger.info("无需移出: 组合中所有基金均满足大数定律条件。")
        return {'total_checked': len(existing_funds_dict), 'removed': 0, 'failed': 0}

    logger.info(f"需要移出 {len(funds_to_remove)} 个基金。")

    # 4. 逐个移出
    stats = {
        'total_checked': len(existing_funds_dict),
        'removed': 0,
        'failed': 0,
    }

    for code, name in funds_to_remove:
        logger.info(f"移出 {name} ({code})...")
        try:
            resp = remove_from_favorites(fund_code=code, group_id=int(group_id), user=user)
            if resp.Success:
                logger.info(f"  -> 移出成功")
                stats['removed'] += 1
            else:
                logger.error(f"  -> 移出失败: {resp.FirstError} (Code: {resp.ErrorCode})")
                stats['failed'] += 1
        except Exception as e:
            logger.error(f"  -> 异常: {e}")
            stats['failed'] += 1

    logger.info("-" * 40)
    logger.info(f"大数定律组合清理完成. 统计: {stats}")
    return stats


if __name__ == "__main__":
    from src.API.登录接口.login import ensure_user_fresh

    user = ensure_user_fresh(DEFAULT_USER)
    remove_unqualified_funds_from_lln_group(user=DEFAULT_USER, group_name="大数定律")
