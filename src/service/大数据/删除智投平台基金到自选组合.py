import os
import sys
from typing import Dict, Set, Tuple

root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from src.common.constant import DEFAULT_USER
from src.API.自选基金.FavorFund import get_favor_groups, remove_from_favorites, get_favor_group
from src.common.logger import get_logger
from src.db.database_connection import DatabaseConnection
from src.service.大数据.增加智投平台基金到自选组合 import (
    TARGET_TYPES,
    _dedup_similar_indices,
    _get_all_index_names_for_grouping,
    get_latest_trade_date_for_3m_metrics,
    get_qualified_indices,
)

logger = get_logger(__name__)


def _collect_items(obj):
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
    response = get_favor_groups(user=user)
    if not response.Success:
        logger.error(f"Failed to get favor groups: {response.FirstError}")
        return -1, {}

    target_group_id = -1
    existing_funds = {}

    if not response.Data:
        return -1, {}

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
        if not groups_list:
            for v in response.Data.values():
                if isinstance(v, list):
                    groups_list = v
                    break

    for group in groups_list:
        if not isinstance(group, dict):
            continue

        name = group.get("groupName") or group.get("group_name") or group.get("GroupName") or group.get("gname") or group.get("Name")
        if name == group_name:
            target_group_id = group.get("groupId") or group.get("group_id") or group.get("GroupId") or group.get("Id")
            break

    if target_group_id != -1:
        detail_resp = get_favor_group(group_ids=str(target_group_id), user=user)
        if detail_resp.Success and detail_resp.Data:
            funds = _collect_items(detail_resp.Data)
            for f in funds:
                code = f.get("fcode") or f.get("FundCode") or f.get("FCODE") or f.get("fund_code") or f.get("code")
                name = f.get("shortname") or f.get("fname") or f.get("FundName") or f.get("fund_name") or "Unknown"
                if code:
                    existing_funds[str(code)] = str(name)

    return target_group_id, existing_funds


def get_qualified_fund_codes() -> Set[str]:
    qualified_indices = get_qualified_indices()
    if not qualified_indices:
        return set()

    all_index_names = _get_all_index_names_for_grouping()
    qualified_indices = _dedup_similar_indices(qualified_indices, all_index_names)
    return {str(r["track_fund_code"]) for r in qualified_indices if r.get("track_fund_code")}


def remove_unqualified_funds_from_group(user, group_name: str = "智投平台", dry_run: bool = False) -> Dict[str, int]:
    latest_trade_date = get_latest_trade_date_for_3m_metrics()
    logger.info(f"market_index_daily(含3M指标) 最新交易日: {latest_trade_date}")
    logger.info(f"开始清理 '{group_name}' 组合（移出不再满足条件的基金）...")

    qualified_fund_codes = get_qualified_fund_codes()

    group_id, existing_funds_dict = get_group_info(user, group_name)
    if group_id == -1:
        logger.error(f"目标组合 '{group_name}' 未找到。")
        return {"total_checked": 0, "removed": 0, "failed": 0}

    logger.info(f"目标组合: {group_name} (ID: {group_id})")
    logger.info(f"组合当前基金数: {len(existing_funds_dict)}")
    logger.info(f"满足条件的基金: {len(qualified_fund_codes)} 个")

    funds_to_remove = []
    for code, name in existing_funds_dict.items():
        if code not in qualified_fund_codes:
            funds_to_remove.append((code, name))

    if not funds_to_remove:
        logger.info("无需移出: 组合中所有基金均满足条件。")
        return {"total_checked": len(existing_funds_dict), "removed": 0, "failed": 0}

    logger.info(f"需要移出 {len(funds_to_remove)} 个基金。")

    stats = {
        "total_checked": len(existing_funds_dict),
        "removed": 0,
        "failed": 0,
    }

    for code, name in funds_to_remove:
        logger.info(f"移出 {name} ({code})...")
        if dry_run:
            logger.info("  -> dry_run: 不执行移出")
            continue
        try:
            resp = remove_from_favorites(fund_code=code, group_id=int(group_id), user=user)
            if resp.Success:
                logger.info("  -> 移出成功")
                stats["removed"] += 1
            else:
                logger.error(f"  -> 移出失败: {resp.FirstError} (Code: {resp.ErrorCode})")
                stats["failed"] += 1
        except Exception as e:
            logger.error(f"  -> 异常: {e}")
            stats["failed"] += 1

    logger.info("-" * 40)
    logger.info(f"智投平台组合清理完成. 统计: {stats}")
    return stats


if __name__ == "__main__":
    from src.API.登录接口.login import ensure_user_fresh

    user = ensure_user_fresh(DEFAULT_USER)
    remove_unqualified_funds_from_group(user=user, group_name="智投平台")

