import os
import sys
import logging

# 添加项目根目录到路径
root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

from src.API.自选基金.FavorFund import get_favor_groups, get_favor_group
from src.common.constant import DEFAULT_USER


def test_get_favor_groups_with_default_user():
    resp = get_favor_groups(DEFAULT_USER)
    print(f"get_favor_groups Success={resp.Success} ErrorCode={resp.ErrorCode} FirstError={resp.FirstError}")
    assert isinstance(resp.Success, bool)
    if resp.Success and resp.Data:
        data = resp.Data
        # 提取分组列表（兼容不同字段名/结构）
        groups = None
        for k in ["Groups", "groups", "GroupList", "groupList", "Data", "data"]:
            v = data if k in ("Data", "data") else data.get(k) if isinstance(data, dict) else None
            if isinstance(v, list) and len(v) > 0:
                # 选择包含分组特征的列表
                if any(isinstance(i, dict) and ("GroupId" in i or "groupId" in i or "Id" in i or "id" in i) for i in v):
                    groups = v
                    break
        if groups is None and isinstance(data, dict):
            # 兜底：在所有值里找可能的分组列表
            for v in data.values():
                if isinstance(v, list) and any(isinstance(i, dict) and ("GroupId" in i or "groupId" in i or "Id" in i or "id" in i) for i in v):
                    groups = v
                    break
        print(f"favor groups count={len(groups) if groups else 0}")
        if groups:
            for idx, g in enumerate(groups, 1):
                gid = g.get("GroupId") or g.get("groupId") or g.get("Id") or g.get("id")
                gname = g.get("GroupName") or g.get("groupName") or g.get("Name") or g.get("name")
                fcnt = g.get("FundCount") or g.get("fundCount") or g.get("Count") or g.get("count")
                print(f"{idx}. GroupId={gid} GroupName={gname} FundCount={fcnt}")
                if gid:
                    r_detail = get_favor_group(group_ids=str(gid), fund_type=0, user=DEFAULT_USER)
                    print(f"get_favor_group({gid}) Success={r_detail.Success} ErrorCode={r_detail.ErrorCode} FirstError={r_detail.FirstError}")
                    if r_detail.Success and r_detail.Data:
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
                        print(f"group({gid}) funds count={len(funds)}")
                        for i, item in enumerate(funds, 1):
                            code = item.get("fcode") or item.get("FundCode") or item.get("fund_code") or item.get("FCODE") or item.get("code")
                            name = item.get("shortname") or item.get("fname") or item.get("FundName") or item.get("fund_name") or item.get("name")
                            print(f"  {i}. {code} {name}")
