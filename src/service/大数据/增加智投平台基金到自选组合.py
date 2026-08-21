import os
import sys
import re
import math
from typing import List, Dict, Set, Tuple

root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from src.common.constant import DEFAULT_USER
from src.API.自选基金.FavorFund import get_favor_groups, add_to_favorites, get_favor_group
from src.common.logger import get_logger
from src.db.database_connection import DatabaseConnection

logger = get_logger(__name__)

TARGET_TYPES = ["宽基", "行业", "主题", "海外"]


def _get_all_index_names_for_grouping() -> List[Dict]:
    db = DatabaseConnection()
    rows = db.execute_query(
        f"SELECT index_code, index_name FROM market_index_static "
        f"WHERE type_name IN ({','.join(['%s'] * len(TARGET_TYPES))})",
        TARGET_TYPES,
    )
    return rows


def _dedup_similar_indices(indices: List[Dict], all_index_names: List[Dict]) -> List[Dict]:
    if not indices:
        return []

    char_sets: Dict[str, Set[str]] = {}
    char_count: Dict[str, int] = {}
    for r in all_index_names:
        chars = set("".join(re.findall(r"[\u4e00-\u9fff]+", r["index_name"])))
        char_sets[r["index_code"]] = chars
        for c in chars:
            char_count[c] = char_count.get(c, 0) + 1
    total = len(all_index_names)
    idf = {c: math.log(total / cnt) for c, cnt in char_count.items()}

    def _specificity(code: str) -> float:
        return sum(idf[c] for c in char_sets.get(code, set()))

    order = sorted(all_index_names, key=lambda r: (-_specificity(r["index_code"]), r["index_code"]))
    seeds: List[Tuple[str, Set[str]]] = []
    groups: Dict[str, List[str]] = {}
    for r in order:
        code = r["index_code"]
        chars = char_sets.get(code, set())
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

    code_to_gid: Dict[str, str] = {}
    for seed, members in groups.items():
        for code in members:
            code_to_gid[code] = seed

    from collections import OrderedDict

    qualified_groups: Dict[str, List[Dict]] = OrderedDict()
    for idx in indices:
        code = idx["index_code"]
        g = code_to_gid.get(code, code)
        qualified_groups.setdefault(g, []).append(idx)

    result = []
    for g, group in qualified_groups.items():
        best = max(group, key=lambda x: float(x["avg_return_q"]))
        if len(group) > 1:
            removed = [
                f"{x['index_code']} {x['index_name']} (3M={float(x['avg_return_q']):.2f}%)"
                for x in group if x != best
            ]
            logger.info(
                f"[去重] 同类指数: 保留 {best['index_code']} {best['index_name']} "
                f"(3M={float(best['avg_return_q']):.2f}%), "
                f"跳过 {'; '.join(removed)}"
            )
        result.append(best)

    result.sort(key=lambda x: float(x["avg_return_q"]), reverse=True)
    return result


def get_latest_trade_date_for_3m_metrics() -> str:
    db = DatabaseConnection()
    rows = db.execute_query(
        "SELECT MAX(trade_date) AS d FROM market_index_daily "
        "WHERE profit_rate_q IS NOT NULL AND avg_return_q IS NOT NULL"
    )
    return rows[0]["d"] if rows and rows[0].get("d") else ""


def get_qualified_indices() -> List[Dict]:
    db = DatabaseConnection()
    sql = """
        SELECT
            s.index_code, s.index_name, s.track_fund_code, s.track_fund_name,
            d.trade_date, d.profit_rate_q, d.avg_return_q
        FROM market_index_static s
        INNER JOIN (
            SELECT d1.index_code, d1.trade_date, d1.profit_rate_q, d1.avg_return_q
            FROM market_index_daily d1
            INNER JOIN (
                SELECT index_code, MAX(trade_date) AS max_date
                FROM market_index_daily
                WHERE profit_rate_q IS NOT NULL AND avg_return_q IS NOT NULL
                GROUP BY index_code
            ) d2 ON d1.index_code = d2.index_code AND d1.trade_date = d2.max_date
        ) d ON s.index_code = d.index_code
        WHERE s.type_name IN ({placeholders})
          AND s.track_fund_code IS NOT NULL AND s.track_fund_code != ''
          AND d.profit_rate_q > 70
          AND d.avg_return_q > 20
        ORDER BY d.avg_return_q DESC
    """.format(placeholders=",".join(["%s"] * len(TARGET_TYPES)))

    rows = db.execute_query(sql, TARGET_TYPES)
    logger.info(f"智投平台条件查询: 满足条件的指数共 {len(rows)} 个")
    return rows


def _collect_items(obj) -> List[Dict]:
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
    response = get_favor_groups(user=user)
    if not response.Success:
        logger.error(f"Failed to get favor groups: {response.FirstError}")
        return -1, set()

    target_group_id = -1
    existing_funds = set()

    if not response.Data:
        return -1, set()

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
                if code:
                    existing_funds.add(str(code))

    return target_group_id, existing_funds


def add_qualified_funds_to_group(user, group_name: str = "智投平台", dry_run: bool = False) -> Dict[str, int]:
    latest_trade_date = get_latest_trade_date_for_3m_metrics()
    logger.info(f"market_index_daily(含3M指标) 最新交易日: {latest_trade_date}")
    logger.info(f"开始筛选满足条件的基金，目标组合: '{group_name}'...")

    qualified_indices = get_qualified_indices()
    if not qualified_indices:
        logger.info("没有满足条件的指数。")
        return {"total_qualified": 0, "added": 0, "skipped": 0, "no_track_fund": 0}

    all_index_names = _get_all_index_names_for_grouping()
    before_dedup = len(qualified_indices)
    qualified_indices = _dedup_similar_indices(qualified_indices, all_index_names)
    dedup_removed = before_dedup - len(qualified_indices)
    if dedup_removed > 0:
        logger.info(f"同类指数去重: 减少 {dedup_removed} 个，保留 {len(qualified_indices)} 个")

    group_id, existing_funds = get_group_info(user, group_name)
    if group_id == -1:
        logger.error(f"目标组合 '{group_name}' 未找到，请先在天天基金中创建该自选组合。")
        return {"total_qualified": len(qualified_indices), "added": 0, "skipped": 0, "no_track_fund": 0}

    logger.info(f"目标组合: {group_name} (ID: {group_id})")
    logger.info(f"组合当前基金数: {len(existing_funds)}")
    logger.info(f"满足条件的指数: {len(qualified_indices)} 个")

    stats = {
        "total_qualified": len(qualified_indices),
        "added": 0,
        "skipped": 0,
        "no_track_fund": 0,
    }

    for idx in qualified_indices:
        index_code = idx["index_code"]
        index_name = idx["index_name"]
        fund_code = str(idx["track_fund_code"]) if idx.get("track_fund_code") else ""
        fund_name = idx.get("track_fund_name", "Unknown")

        if not fund_code:
            stats["no_track_fund"] += 1
            continue

        logger.info(
            f"[{index_code} {index_name}] 跟踪基金: {fund_code} {fund_name} "
            f"(trade_date={idx.get('trade_date')}, 3M胜率={float(idx['profit_rate_q']):.2f}%, "
            f"3M均值={float(idx['avg_return_q']):.2f}%)"
        )

        if fund_code in existing_funds:
            logger.info("  -> 跳过: 已在组合中")
            stats["skipped"] += 1
            continue

        if dry_run:
            logger.info("  -> dry_run: 不执行添加")
            stats["skipped"] += 1
            continue

        try:
            resp = add_to_favorites(fund_code=fund_code, group_id=int(group_id), user=user)
            if resp.Success:
                logger.info("  -> 添加成功")
                stats["added"] += 1
            else:
                if resp.ErrorCode == 63117 or "已存在" in str(resp.FirstError):
                    logger.info("  -> 已存在 (API 返回重复提示)")
                    stats["skipped"] += 1
                else:
                    logger.error(f"  -> 添加失败: {resp.FirstError} (Code: {resp.ErrorCode})")
        except Exception as e:
            logger.error(f"  -> 异常: {e}")

    logger.info("-" * 40)
    logger.info(f"智投平台组合更新完成. 统计: {stats}")
    return stats


if __name__ == "__main__":
    from src.API.登录接口.login import ensure_user_fresh

    user = ensure_user_fresh(DEFAULT_USER)
    add_qualified_funds_to_group(user=user, group_name="智投平台")
