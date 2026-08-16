import os
import sys
import re
import math
import logging
from typing import List, Dict, Set, Tuple

# Add root dir to sys.path
root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from src.common.constant import DEFAULT_USER
from src.API.自选基金.FavorFund import get_favor_groups, add_to_favorites, get_favor_group
from src.common.logger import get_logger
from src.db.database_connection import DatabaseConnection

logger = get_logger(__name__)

# 目标指数类型
TARGET_TYPES = ["宽基", "行业", "主题", "海外"]


def _get_all_index_names_for_grouping() -> List[Dict]:
    """
    获取市场全部指数的名称，用于构建相似度分组。
    轻量查询，仅返回 index_code, index_name。
    """
    db = DatabaseConnection()
    rows = db.execute_query(
        f"SELECT index_code, index_name FROM market_index_static "
        f"WHERE type_name IN ({','.join(['%s'] * len(TARGET_TYPES))})",
        TARGET_TYPES,
    )
    return rows


def _dedup_similar_indices(indices: List[Dict], all_index_names: List[Dict]) -> List[Dict]:
    """
    同类指数去重：基于全量指数名称构建相似度分组，每组只保留3M收益率最高的一个。

    **为什么用全量而非仅过滤结果？**
    同类关系是全局的（如"有色金属"与"国证有色"是同类），
    如果仅对当前过滤出的子集做去重，当下一批指数不同时，同类关系仍应一致。

    匹配规则：两个指数名称含 >=2 个相同中文汉字，即视为同类。
    例："有色金属" {有,色,金,属} vs "国证有色" {国,证,有,色} → 共享"有""色" → 同类

    **与旧版贪心算法的区别（修复跨家族漏去重）**：
    旧版按数据库返回顺序"先到先得"，指数一旦被某组吸收即无法再归属其他组，
    导致"中证有色"因共享{中,证}被中证家族抢先吸收，与同主题的"有色金属"(共享{有,色})失之交臂。
    新版：
      1. 按"主题特异性"(自身字符 IDF 加权和)降序处理，越具体的主题越先成组；
      2. 每个指数加入与其共享汉字 IDF 加权分最高的组（最佳匹配归属）。
    结果确定、与数据库返回顺序无关，桥接类指数(如"中证有色")会归入真正的主题组。
    """
    if not indices:
        return []

    # 1. 提取全量指数名称的汉字集合，并计算各汉字 IDF（出现越少越具主题区分度）
    char_sets: Dict[str, Set[str]] = {}
    char_count: Dict[str, int] = {}
    for r in all_index_names:
        chars = set(''.join(re.findall(r'[\u4e00-\u9fff]+', r['index_name'])))
        char_sets[r['index_code']] = chars
        for c in chars:
            char_count[c] = char_count.get(c, 0) + 1
    total = len(all_index_names)
    idf = {c: math.log(total / cnt) for c, cnt in char_count.items()}

    # 2. 按主题特异性降序（同分按 code 升序保证确定性），贪心构建分组
    def _specificity(code: str) -> float:
        return sum(idf[c] for c in char_sets[code])

    order = sorted(all_index_names, key=lambda r: (-_specificity(r['index_code']), r['index_code']))
    seeds: List[Tuple[str, Set[str]]] = []
    groups: Dict[str, List[str]] = {}
    for r in order:
        code = r['index_code']
        chars = char_sets[code]
        best_seed, best_score = None, 0.0
        for seed_code, seed_chars in seeds:
            shared = chars & seed_chars
            if len(shared) < 2:
                continue
            score = sum(idf[c] for c in shared)
            if score > best_score:
                best_seed, best_score = seed_code, score
        if best_seed is not None:
            groups[best_seed].append(code)
        else:
            seeds.append((code, chars))
            groups[code] = [code]

    # 3. 建立 code -> 组标识 映射（组标识用种子 code）
    code_to_gid: Dict[str, str] = {}
    for seed, members in groups.items():
        for code in members:
            code_to_gid[code] = seed

    # 4. 将过滤出的指数按分组归类
    from collections import OrderedDict
    qualified_groups: Dict[str, List[Dict]] = OrderedDict()
    for idx in indices:
        code = idx['index_code']
        g = code_to_gid.get(code, code)  # 无同类时以自身code为组标识
        qualified_groups.setdefault(g, []).append(idx)

    # 5. 每组取 3M 收益率最高的
    result = []
    for g, group in qualified_groups.items():
        best = max(group, key=lambda x: float(x['avg_return_q']))
        if len(group) > 1:
            removed = [
                f"{x['index_code']} {x['index_name']} (3M={x['avg_return_q']:.2f}%)"
                for x in group if x != best
            ]
            logger.info(
                f"[去重] 同类指数: 保留 {best['index_code']} {best['index_name']} "
                f"(3M={best['avg_return_q']:.2f}%), "
                f"跳过 {'; '.join(removed)}"
            )
        result.append(best)

    result.sort(key=lambda x: float(x['avg_return_q']), reverse=True)
    return result


def get_qualified_indices() -> List[Dict]:
    """
    查询满足"大数定律"条件的指数及其跟踪基金。

    条件：
      - 未来持有3个月平均收益率 > 10%
      - 未来6个月平均收益率 - 3个月平均收益率 > 10%
      - 未来一年正收益概率 = 100%

    从 market_index_daily 取每个指数最新交易日数据，
    关联 market_index_static 获取跟踪基金代码。

    Returns:
        [{index_code, index_name, track_fund_code, track_fund_name,
          avg_return_q, avg_return_hy, profit_rate_y}, ...]
    """
    db = DatabaseConnection()
    sql = """
        SELECT
            s.index_code, s.index_name, s.track_fund_code, s.track_fund_name,
            d.avg_return_q, d.avg_return_hy, d.profit_rate_y
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
        ORDER BY d.avg_return_q DESC
    """.format(placeholders=",".join(["%s"] * len(TARGET_TYPES)))

    rows = db.execute_query(sql, TARGET_TYPES)
    logger.info(f"大数定律条件查询: 满足条件的指数共 {len(rows)} 个")
    return rows


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


def get_group_info(user, group_name: str) -> Tuple[int, Set[str]]:
    """
    Find the group ID and return its current fund codes.
    Returns: (group_id, set_of_existing_fund_codes)
    """
    response = get_favor_groups(user=user)
    if not response.Success:
        logger.error(f"Failed to get favor groups: {response.FirstError}")
        return -1, set()

    target_group_id = -1
    existing_funds = set()

    if not response.Data:
        return -1, set()

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
                if code:
                    existing_funds.add(str(code))

    return target_group_id, existing_funds


def add_qualified_funds_to_lln_group(user, group_name: str = "大数定律") -> Dict[str, int]:
    """
    将满足大数定律条件的指数跟踪基金加入自选组合。

    筛选条件（从 market_index_daily 最新数据）：
      - 持有3个月平均收益率(avg_return_q) > 10%
      - 持有6个月平均收益率 - 3个月平均收益率 > 10%
      - 持有1年正收益概率(profit_rate_y) = 100%

    Args:
        user: User object with account info
        group_name: Target group name (默认 "大数定律")

    Returns:
        Dict with stats: {'total_qualified': int, 'added': int, 'skipped': int, 'no_track_fund': int}
    """
    latest_trade_date = DatabaseConnection().execute_query(
        "SELECT MAX(trade_date) AS d FROM market_index_daily"
    )[0]["d"]
    logger.info(f"market_index_daily 最新交易日: {latest_trade_date}")
    logger.info(f"开始筛选满足大数定律条件的基金，目标组合: '{group_name}'...")

    # 1. 查询满足条件的指数及其跟踪基金
    qualified_indices = get_qualified_indices()

    if not qualified_indices:
        logger.info("没有满足大数定律条件的指数。")
        return {'total_qualified': 0, 'added': 0, 'skipped': 0, 'no_track_fund': 0}

    # 1b. 同类指数去重（基于全量指数构建分组，不依赖过滤子集）
    all_index_names = _get_all_index_names_for_grouping()
    before_dedup = len(qualified_indices)
    qualified_indices = _dedup_similar_indices(qualified_indices, all_index_names)
    dedup_removed = before_dedup - len(qualified_indices)
    if dedup_removed > 0:
        logger.info(f"同类指数去重: 减少 {dedup_removed} 个，保留 {len(qualified_indices)} 个")

    # 2. 获取目标组合信息
    group_id, existing_funds = get_group_info(user, group_name)

    if group_id == -1:
        logger.error(f"目标组合 '{group_name}' 未找到，请先在天天基金中创建该自选组合。")
        return {'total_qualified': len(qualified_indices), 'added': 0, 'skipped': 0, 'no_track_fund': 0}

    logger.info(f"目标组合: {group_name} (ID: {group_id})")
    logger.info(f"组合当前基金数: {len(existing_funds)}")
    logger.info(f"满足条件的指数: {len(qualified_indices)} 个")

    # 3. 逐个添加
    stats = {
        'total_qualified': len(qualified_indices),
        'added': 0,
        'skipped': 0,
        'no_track_fund': 0,
    }

    for idx in qualified_indices:
        index_code = idx['index_code']
        index_name = idx['index_name']
        fund_code = str(idx['track_fund_code'])
        fund_name = idx.get('track_fund_name', 'Unknown')

        logger.info(
            f"[{index_code} {index_name}] 跟踪基金: {fund_code} {fund_name} "
            f"(3M收益={idx['avg_return_q']:.2f}%, 6M收益={idx['avg_return_hy']:.2f}%, "
            f"1Y正收益概率={idx['profit_rate_y']}%)"
        )

        if fund_code in existing_funds:
            logger.info(f"  -> 跳过: 已在组合中")
            stats['skipped'] += 1
            continue

        try:
            resp = add_to_favorites(fund_code=fund_code, group_id=int(group_id), user=user)
            if resp.Success:
                logger.info(f"  -> 添加成功")
                stats['added'] += 1
            else:
                if resp.ErrorCode == 63117 or "已存在" in str(resp.FirstError):
                    logger.info(f"  -> 已存在 (API 返回重复提示)")
                    stats['skipped'] += 1
                else:
                    logger.error(f"  -> 添加失败: {resp.FirstError} (Code: {resp.ErrorCode})")
        except Exception as e:
            logger.error(f"  -> 异常: {e}")

    logger.info("-" * 40)
    logger.info(f"大数定律组合更新完成. 统计: {stats}")
    return stats


if __name__ == "__main__":
    from src.API.登录接口.login import ensure_user_fresh

    user = ensure_user_fresh(DEFAULT_USER)
    add_qualified_funds_to_lln_group(user=DEFAULT_USER, group_name="大数定律")
