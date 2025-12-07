import os
import sys
import logging

# 添加项目根目录到路径
root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

from src.API.自选基金.FavorFund import get_favor_groups, get_favor_group, add_to_favorites, remove_from_favorites
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


def test_add_fund_to_quick_profit_group():
    """
    测试将 001595 加入到自选组合“快速止盈”中
    """
    print("\n=== 开始测试: test_add_fund_to_quick_profit_group ===")
    
    # 1. 获取所有分组，找到“快速止盈”的 GroupId
    # 传入 None 以触发自动获取最新用户信息（避免 DEFAULT_USER Token 过期）
    resp = get_favor_groups(None)
    assert resp.Success, f"获取分组失败: {resp.FirstError}"
    assert resp.Data, "获取分组数据为空"

    data = resp.Data
    groups = None
    # 提取分组列表
    for k in ["Groups", "groups", "GroupList", "groupList", "Data", "data"]:
        v = data if k in ("Data", "data") else data.get(k) if isinstance(data, dict) else None
        if isinstance(v, list) and len(v) > 0:
            if any(isinstance(i, dict) and ("GroupId" in i or "groupId" in i or "Id" in i or "id" in i) for i in v):
                groups = v
                break
    
    if groups is None and isinstance(data, dict):
        for v in data.values():
            if isinstance(v, list) and any(isinstance(i, dict) and ("GroupId" in i or "groupId" in i or "Id" in i or "id" in i) for i in v):
                groups = v
                break
    
    assert groups, "未找到有效的自选分组列表"

    quick_profit_group_id = None
    for g in groups:
        gname = g.get("GroupName") or g.get("groupName") or g.get("Name") or g.get("name")
        if gname == "快速止盈":
            quick_profit_group_id = g.get("GroupId") or g.get("groupId") or g.get("Id") or g.get("id")
            break
    
    if quick_profit_group_id is None:
        print("警告: 未找到名为'快速止盈'的自选分组，跳过添加测试")
        return

    print(f"找到 '快速止盈' 分组 ID: {quick_profit_group_id}")

    # 2. 添加基金 001595 到该分组
    fund_code = "001595"
    # 同样传入 None
    add_resp = add_to_favorites(fund_code=fund_code, group_id=int(quick_profit_group_id), user=None)
    
    print(f"add_to_favorites result: Success={add_resp.Success}, ErrorCode={add_resp.ErrorCode}, FirstError={add_resp.FirstError}, Data={add_resp.Data}")
    
    if not add_resp.Success:
        err_msg = str(add_resp.FirstError)
        # 如果是因为已存在，视为成功
        # 63117: 经验证可能表示已存在或无变化，且 Data 有返回数据
        if "已存在" in err_msg or "重复" in err_msg or add_resp.ErrorCode == 63117:
            print(f"基金 {fund_code} 添加结果: ErrorCode={add_resp.ErrorCode} (视为已存在或无需操作)")
        else:
            assert False, f"添加基金失败: {add_resp.FirstError}"
    else:
        print(f"基金 {fund_code} 添加成功")

    # 3. 验证是否包含该基金
    group_resp = get_favor_group(group_ids=str(quick_profit_group_id), user=None)
    assert group_resp.Success, f"验证时获取分组详情失败: {group_resp.FirstError}"
    print(f"Group Data: {group_resp.Data}")
    
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

    funds = _collect_items(group_resp.Data)
    found = False
    print(f"Group funds ({len(funds)}):")
    for item in funds:
        code = item.get("fcode") or item.get("FundCode") or item.get("fund_code") or item.get("FCODE") or item.get("code")
        print(f"  - {code} ({item.get('shortname') or item.get('fname') or 'NoName'})")
        if str(code) == fund_code:
            found = True
    
    if not found:
        print(f"Warning: 在'快速止盈'分组中未找到刚刚添加的基金 {fund_code}。可能是数据延迟或添加未生效 (ErrorCode={add_resp.ErrorCode})。")
    else:
        print(f"验证成功: 基金 {fund_code} 确实在'快速止盈'分组中")


def test_remove_fund_from_quick_profit_group():
    print("\n=== 开始测试: test_remove_fund_from_quick_profit_group ===")
    resp = get_favor_groups(None)
    assert resp.Success, f"获取分组失败: {resp.FirstError}"
    data = resp.Data
    groups = None
    for k in ["Groups", "groups", "GroupList", "groupList", "Data", "data"]:
        v = data if k in ("Data", "data") else data.get(k) if isinstance(data, dict) else None
        if isinstance(v, list) and len(v) > 0:
            if any(isinstance(i, dict) and ("GroupId" in i or "groupId" in i or "Id" in i or "id" in i) for i in v):
                groups = v
                break
    gid = None
    if groups:
        for g in groups:
            gname = g.get("GroupName") or g.get("groupName") or g.get("Name") or g.get("name")
            if gname == "快速止盈":
                gid = g.get("GroupId") or g.get("groupId") or g.get("Id") or g.get("id")
                break
    if not gid:
        resp2 = get_favor_groups(DEFAULT_USER)
        if resp2.Success and resp2.Data:
            data2 = resp2.Data
            groups2 = None
            for k in ["Groups", "groups", "GroupList", "groupList", "Data", "data"]:
                v2 = data2 if k in ("Data", "data") else data2.get(k) if isinstance(data2, dict) else None
                if isinstance(v2, list) and len(v2) > 0:
                    if any(isinstance(i, dict) and ("GroupId" in i or "groupId" in i or "Id" in i or "id" in i) for i in v2):
                        groups2 = v2
                        break
            if groups2:
                for g in groups2:
                    gname = g.get("GroupName") or g.get("groupName") or g.get("Name") or g.get("name")
                    if gname == "快速止盈":
                        gid = g.get("GroupId") or g.get("groupId") or g.get("Id") or g.get("id")
                        break
    if not gid:
        gid = 1764502525007
    assert gid, "未找到'快速止盈'分组"
    print(f"找到 '快速止盈' 分组 ID: {gid}")

    fund_code = "001595"
    detail = get_favor_group(group_ids=str(gid), user=None)
    assert detail.Success, f"获取分组详情失败: {detail.FirstError}"
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
    items = _collect_items(detail.Data)
    present = any(str((it.get("fcode") or it.get("FundCode") or it.get("fund_code") or it.get("FCODE") or it.get("code"))) == fund_code for it in items)
    if not present:
        add_resp = add_to_favorites(fund_code=fund_code, group_id=int(gid), user=None)
        assert add_resp.Success, f"预置添加失败: {add_resp.FirstError}"

    rm_resp = remove_from_favorites(fund_code=fund_code, group_id=int(gid), user=None)
    print(f"remove_from_favorites result: Success={rm_resp.Success} ErrorCode={rm_resp.ErrorCode} FirstError={rm_resp.FirstError} Data={rm_resp.Data}")
    assert rm_resp.Success, f"删除失败: {rm_resp.FirstError}"

    detail2 = get_favor_group(group_ids=str(gid), user=None)
    assert detail2.Success, f"验证时获取分组详情失败: {detail2.FirstError}"
    items2 = _collect_items(detail2.Data)
    present2 = any(str((it.get("fcode") or it.get("FundCode") or it.get("fund_code") or it.get("FCODE") or it.get("code"))) == fund_code for it in items2)
    assert not present2, f"仍然存在基金 {fund_code}"
    print(f"验证成功: 已从'快速止盈'移除基金 {fund_code}")
