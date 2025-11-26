import os
import sys
from typing import Any, List, Dict

root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
proj_root = os.path.dirname(root_dir)
if proj_root not in sys.path:
    sys.path.insert(0, proj_root)

from src.API.自选基金.FavorFund import get_favor_groups, get_favor_group
from src.common.constant import DEFAULT_USER

def _collect_items(obj: Any) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    def walk(x: Any):
        if isinstance(x, dict):
            if any(k in x for k in ["fcode", "FundCode", "fund_code", "FCODE", "code"]):
                items.append(x)
            else:
                for v in x.values():
                    walk(v)
        elif isinstance(x, list):
            for i in x:
                walk(i)
    walk(obj)
    return items

def get_group_funds_by_name(group_name: str) -> List[Dict[str, Any]]:
    r = get_favor_groups(DEFAULT_USER)
    if not r.Success or r.Data is None:
        return []
    data = r.Data
    groups = None
    if isinstance(data, dict):
        for k in ["Groups", "groups", "GroupList", "groupList", "Data", "data"]:
            v = data if k in ("Data", "data") else data.get(k)
            if isinstance(v, list) and len(v) > 0:
                if any(isinstance(i, dict) and ("GroupId" in i or "groupId" in i or "Id" in i or "id" in i) for i in v):
                    groups = v
                    break
        if groups is None:
            for v in data.values():
                if isinstance(v, list) and any(isinstance(i, dict) and ("GroupId" in i or "groupId" in i or "Id" in i or "id" in i) for i in v):
                    groups = v
                    break
    if not groups:
        return []
    target = None
    for g in groups:
        name = g.get("GroupName") or g.get("groupName") or g.get("Name") or g.get("name")
        if name == group_name:
            target = g
            break
    if not target:
        return []
    gid = target.get("GroupId") or target.get("groupId") or target.get("Id") or target.get("id")
    if not gid:
        return []
    r2 = get_favor_group(group_ids=str(gid), fund_type=0, user=DEFAULT_USER)
    if not r2.Success or r2.Data is None:
        return []
    return _collect_items(r2.Data)

if __name__ == "__main__":
    funds = get_group_funds_by_name("指数基金")
    print(f"funds_count={len(funds)}")
    for i, item in enumerate(funds, 1):
        code = item.get("fcode") or item.get("FundCode") or item.get("fund_code") or item.get("FCODE") or item.get("code")
        name = item.get("shortname") or item.get("fname") or item.get("FundName") or item.get("fund_name") or item.get("name")
        print(f"{i}. {code} {name}")

