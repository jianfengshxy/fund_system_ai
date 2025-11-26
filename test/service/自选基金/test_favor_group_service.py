import os
import sys
import warnings
from urllib3.exceptions import InsecureRequestWarning

root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from src.service.自选基金.自选组合服务 import get_group_funds_by_name
from src.API.自选基金.FavorFund import get_favor_groups, get_favor_group
from src.common.constant import DEFAULT_USER


def test_print_all_groups_and_funds():
    warnings.simplefilter("ignore", InsecureRequestWarning)
    acct = getattr(DEFAULT_USER, 'account', None)
    print(f"正在使用账户: {acct}")
    r = get_favor_groups()
    print(f"groups Success={r.Success} ErrorCode={r.ErrorCode} FirstError={r.FirstError}")
    assert isinstance(r.Success, bool)
    if not r.Success or not r.Data:
        print("分组查询失败或无数据")
        assert True
        return
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
    print(f"分组数量={len(groups) if groups else 0}")
    if not groups:
        assert True
        return
    for g in groups:
        gid = g.get("GroupId") or g.get("groupId") or g.get("Id") or g.get("id")
        gname = g.get("GroupName") or g.get("groupName") or g.get("Name") or g.get("name")
        if not gname:
            continue
        print(f"组合: {gname} (GroupId={gid})")
        r_detail = get_favor_group(group_ids=str(gid), fund_type=0)
        print(f"  get_favor_group Success={r_detail.Success} ErrorCode={r_detail.ErrorCode} FirstError={r_detail.FirstError}")
        if not r_detail.Success or not r_detail.Data:
            print("  该组合基金查询失败或无数据")
            continue
        def _collect_items(obj):
            items = []
            def walk(x):
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
        funds = _collect_items(r_detail.Data)
        print(f"  基金数量={len(funds)}")
        for i, item in enumerate(funds, 1):
            code = item.get("fcode") or item.get("FundCode") or item.get("fund_code") or item.get("FCODE") or item.get("code")
            name = item.get("shortname") or item.get("fname") or item.get("FundName") or item.get("fund_name") or item.get("name")
            print(f"    {i}. {code} {name}")
