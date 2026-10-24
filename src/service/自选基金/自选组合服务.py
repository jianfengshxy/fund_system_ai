import os
import sys
import unicodedata
from typing import Any, List, Dict, Optional

root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
proj_root = os.path.dirname(root_dir)
if proj_root not in sys.path:
    sys.path.insert(0, proj_root)

from src.API.自选基金.FavorFund import get_favor_groups, get_favor_group
from src.common.constant import DEFAULT_USER
from src.service.用户管理.用户信息 import get_user_from_store_or_cache

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


def _extract_groups(data: Any) -> List[Dict[str, Any]]:
    if isinstance(data, list):
        return [item for item in data if isinstance(item, dict)]
    if not isinstance(data, dict):
        return []

    groups = None
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
    return [item for item in groups if isinstance(item, dict)]


def _normalize_group_name(group_name: Any) -> str:
    if group_name is None:
        return ""
    text = unicodedata.normalize("NFKC", str(group_name))
    text = text.replace("\u200b", "").replace("\ufeff", "")
    text = text.replace("\u00a0", " ").replace("\u3000", " ")
    return text.strip()

def get_all_group_names(user) -> List[str]:
    r = get_favor_groups(user)
    if not r.Success or r.Data is None:
        return []
    groups = _extract_groups(r.Data)
    if not groups:
        return []
        
    names = []
    for g in groups:
        name = g.get("GroupName") or g.get("groupName") or g.get("Name") or g.get("name")
        if name:
            names.append(name)
    return names


def resolve_group_by_name(group_name: str, user=None) -> Dict[str, Any]:
    if user is None:
        u = get_user_from_store_or_cache(getattr(DEFAULT_USER, 'account', None), getattr(DEFAULT_USER, 'password', None))
    else:
        u = user

    result: Dict[str, Any] = {
        "success": False,
        "group_found": False,
        "group_id": None,
        "matched_name": None,
        "funds": [],
        "error_code": None,
        "first_error": None,
        "available_names": [],
    }

    r = get_favor_groups(u)
    result["error_code"] = r.ErrorCode
    result["first_error"] = r.FirstError
    if not r.Success or r.Data is None:
        return result

    groups = _extract_groups(r.Data)
    available_names: List[str] = []
    target: Optional[Dict[str, Any]] = None
    normalized_target_name = _normalize_group_name(group_name)
    for g in groups:
        raw_name = g.get("GroupName") or g.get("groupName") or g.get("Name") or g.get("name")
        normalized_name = _normalize_group_name(raw_name)
        if normalized_name:
            available_names.append(normalized_name)
        if normalized_name == normalized_target_name and target is None:
            target = g
    result["available_names"] = available_names

    if not target:
        result["success"] = True
        return result

    gid = target.get("GroupId") or target.get("groupId") or target.get("Id") or target.get("id")
    result["group_found"] = True
    result["group_id"] = gid
    result["matched_name"] = _normalize_group_name(
        target.get("GroupName") or target.get("groupName") or target.get("Name") or target.get("name")
    )
    if not gid:
        result["success"] = False
        result["first_error"] = "分组缺少 GroupId"
        return result

    r2 = get_favor_group(group_ids=str(gid), fund_type=0, user=u)
    result["error_code"] = r2.ErrorCode
    result["first_error"] = r2.FirstError
    if not r2.Success or r2.Data is None:
        return result

    result["success"] = True
    result["funds"] = _collect_items(r2.Data)
    return result

def get_group_funds_by_name(group_name: str, user=None) -> List[Dict[str, Any]]:
    return resolve_group_by_name(group_name, user).get("funds", [])

if __name__ == "__main__":
    funds = get_group_funds_by_name("指数基金")
    print(f"funds_count={len(funds)}")
    for i, item in enumerate(funds, 1):
        code = item.get("fcode") or item.get("FundCode") or item.get("fund_code") or item.get("FCODE") or item.get("code")
        name = item.get("shortname") or item.get("fname") or item.get("FundName") or item.get("fund_name") or item.get("name")
        print(f"{i}. {code} {name}")
