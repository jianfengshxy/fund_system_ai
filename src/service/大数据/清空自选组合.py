import os
import sys
from typing import Any, Dict, List, Optional, Tuple

root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from src.API.自选基金.FavorFund import get_favor_group, get_favor_groups, remove_from_favorites
from src.common.constant import DEFAULT_USER
from src.common.logger import get_logger

logger = get_logger(__name__)


def _collect_items(obj: Any) -> List[Dict]:
    items: List[Dict] = []
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


def _get_groups_list(data: Any) -> List[Dict]:
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for key in ["list_group", "ListGroup", "datas", "data", "groups", "Groups", "GroupList"]:
            val = data.get(key)
            if isinstance(val, list):
                return val
        for v in data.values():
            if isinstance(v, list):
                return v
    return []


def get_group_id_by_name(user: Any, group_name: str) -> Optional[str]:
    resp = get_favor_groups(user=user)
    if not resp.Success:
        logger.error(f"Failed to get favor groups: {resp.FirstError}")
        return None

    groups = _get_groups_list(resp.Data)
    for g in groups:
        if not isinstance(g, dict):
            continue
        name = g.get("groupName") or g.get("group_name") or g.get("GroupName") or g.get("gname") or g.get("Name")
        if name == group_name:
            gid = g.get("groupId") or g.get("group_id") or g.get("GroupId") or g.get("Id")
            return str(gid) if gid is not None else None
    return None


def list_group_funds(user: Any, group_id: str) -> List[Tuple[str, str]]:
    detail = get_favor_group(group_ids=str(group_id), user=user)
    if not detail.Success:
        raise RuntimeError(f"get_favor_group failed: {detail.FirstError}")

    funds = _collect_items(detail.Data or {})
    seen = set()
    result: List[Tuple[str, str]] = []
    for f in funds:
        code = f.get("fcode") or f.get("FundCode") or f.get("FCODE") or f.get("fund_code") or f.get("code")
        name = f.get("shortname") or f.get("fname") or f.get("FundName") or f.get("fund_name") or "Unknown"
        if not code:
            continue
        code = str(code)
        if code in seen:
            continue
        seen.add(code)
        result.append((code, str(name)))
    return result


def clear_favor_group(
    user: Any,
    group_name: str,
    dry_run: bool = False,
    keep_fund_codes: Optional[List[str]] = None,
) -> Dict[str, int]:
    keep = {str(x) for x in (keep_fund_codes or [])}
    gid = get_group_id_by_name(user=user, group_name=group_name)
    if not gid:
        logger.error(f"目标组合 '{group_name}' 未找到")
        return {"total": 0, "removed": 0, "skipped": 0, "failed": 0}

    funds = list_group_funds(user=user, group_id=gid)
    logger.info(f"目标组合: {group_name} (ID: {gid})")
    logger.info(f"组合当前基金数: {len(funds)}")

    stats = {"total": len(funds), "removed": 0, "skipped": 0, "failed": 0}
    for code, name in funds:
        if code in keep:
            logger.info(f"跳过保留: {name}({code})")
            stats["skipped"] += 1
            continue

        logger.info(f"移出 {name}({code})...")
        if dry_run:
            logger.info("  -> dry_run: 不执行移出")
            stats["skipped"] += 1
            continue

        try:
            resp = remove_from_favorites(fund_code=code, group_id=int(gid), user=user)
            if resp.Success:
                logger.info("  -> 移出成功")
                stats["removed"] += 1
            else:
                logger.error(f"  -> 移出失败: {resp.FirstError} (Code: {resp.ErrorCode})")
                stats["failed"] += 1
        except Exception as e:
            logger.error(f"  -> 异常: {e}")
            stats["failed"] += 1

    logger.info(f"清空完成. 统计: {stats}")
    return stats


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("group_name", help="自选组合名称，例如：智投平台")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--keep", nargs="*", default=None)
    args = parser.parse_args()

    from src.API.登录接口.login import ensure_user_fresh

    u = ensure_user_fresh(DEFAULT_USER)
    clear_favor_group(user=u, group_name=args.group_name, dry_run=args.dry_run, keep_fund_codes=args.keep)

