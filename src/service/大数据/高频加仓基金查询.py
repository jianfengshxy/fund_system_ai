import os
import sys
import re
import math
from typing import List, Dict, Optional, Set, Tuple

root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from src.db.database_connection import DatabaseConnection
from src.common.logger import get_logger
from src.service.基金信息.基金信息 import get_all_fund_info
from src.common.constant import DEFAULT_USER
logger = get_logger(__name__)

TARGET_TYPES = ["宽基", "行业", "主题", "海外"]


def _get_all_index_names_for_grouping(db: DatabaseConnection) -> List[Dict]:
    rows = db.execute_query(
        f"SELECT index_code, index_name FROM market_index_static "
        f"WHERE type_name IN ({','.join(['%s'] * len(TARGET_TYPES))})",
        TARGET_TYPES,
    )
    return rows or []


def _build_similar_index_groups(all_index_names: List[Dict]) -> Dict[str, str]:
    if not all_index_names:
        return {}

    char_sets: Dict[str, Set[str]] = {}
    char_count: Dict[str, int] = {}
    for r in all_index_names:
        code = r.get("index_code")
        name = r.get("index_name")
        if not code or not name:
            continue
        chars = set("".join(re.findall(r"[\u4e00-\u9fff]+", str(name))))
        char_sets[str(code)] = chars
        for c in chars:
            char_count[c] = char_count.get(c, 0) + 1

    total = len(char_sets)
    if total == 0:
        return {}
    idf = {c: math.log(total / cnt) for c, cnt in char_count.items()}

    def _specificity(code: str) -> float:
        return sum(idf.get(c, 0.0) for c in char_sets.get(code, set()))

    order = sorted(char_sets.keys(), key=lambda code: (-_specificity(code), code))
    seeds: List[Tuple[str, Set[str]]] = []
    groups: Dict[str, List[str]] = {}
    for code in order:
        chars = char_sets.get(code, set())
        best_seed, best_score = None, 0.0
        for seed_code, seed_chars in seeds:
            shared = chars & seed_chars
            if len(shared) < 2:
                continue
            score = sum(idf.get(c, 0.0) for c in shared)
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
    return code_to_gid


def _dedup_funds_by_similar_index(funds: List[Dict], all_index_names: List[Dict]) -> List[Dict]:
    if not funds:
        return []

    code_to_gid = _build_similar_index_groups(all_index_names)
    grouped: Dict[str, List[Dict]] = {}
    for f in funds:
        idx_code = str(f.get("index_code") or "")
        gid = code_to_gid.get(idx_code, idx_code) if idx_code else f"fund:{f.get('fund_code')}"
        grouped.setdefault(gid, []).append(f)

    result: List[Dict] = []
    for gid, group in grouped.items():
        best = max(
            group,
            key=lambda x: (
                int(x.get("cnt") or 0),
                str(x.get("fund_code") or ""),
            ),
        )
        if len(group) > 1:
            removed = [
                f"{x.get('fund_code')} {x.get('fund_name')} (cnt={x.get('cnt')})"
                for x in group if x is not best
            ]
            logger.info(
                f"[去重] 同类指数: 保留 {best.get('fund_code')} {best.get('fund_name')} "
                f"(index={best.get('index_code')} {best.get('index_name')}, cnt={best.get('cnt')}), "
                f"跳过 {'; '.join(removed)}"
            )
        result.append(best)

    result.sort(key=lambda x: int(x.get("cnt") or 0), reverse=True)
    return result


def query_frequent_index_funds(
    user,
    days: int = 180,
    min_appear: int = 10,
    fund_type: Optional[str] = "000",
    fund_sub_type: Optional[str] = "000001"
) -> List[Dict]:
    try:
        db = DatabaseConnection()
    except Exception as e:
        logger.error(f"Failed to connect to database: {e}")
        return []

    recent_dates_sql = """
        SELECT DISTINCT update_date
        FROM fund_investment_indicators
        ORDER BY update_date DESC
        LIMIT %s
    """
    recent_dates = db.execute_query(recent_dates_sql, (days,))

    if not recent_dates:
        logger.warning("No update dates found in database.")
        return []

    dates = [row['update_date'] for row in recent_dates]
    min_date = min(dates)
    max_date = max(dates)

    logger.info(f"Analyzing time window: {min_date} to {max_date} ({len(dates)} trading days)")

    sql = """
        SELECT fund_code, MAX(fund_name) as fund_name, COUNT(DISTINCT update_date) as cnt
        FROM fund_investment_indicators
        WHERE update_date BETWEEN %s AND %s
    """
    params = [min_date, max_date]
    if fund_type:
        sql += " AND fund_type = %s"
        params.append(fund_type)
    if fund_sub_type:
        sql += " AND fund_sub_type = %s"
        params.append(fund_sub_type)
    sql += """
        GROUP BY fund_code
        HAVING cnt > %s
        ORDER BY cnt DESC
    """
    params.append(min_appear)

    results = db.execute_query(sql, tuple(params))
    logger.info(f"Found {len(results)} index funds appearing > {min_appear} times.")

    filtered_results: List[Dict] = []
    for row in (results or []):
        fund_code = str(row.get("fund_code") or "")
        fund_name = str(row.get("fund_name") or "")
        if not fund_code:
            continue
        try:
            fund_info = get_all_fund_info(user, fund_code)
            actual_sub_type = getattr(fund_info, "fund_sub_type", None) if fund_info else None
            if fund_sub_type and fund_sub_type != actual_sub_type:
                logger.info(f"Skip {fund_name}({fund_code}): fund_sub_type={actual_sub_type} mismatch")
                continue
            rank_100 = getattr(fund_info, "rank_100day", None) if fund_info else None
            rank_100 = float(rank_100) if isinstance(rank_100, (int, float)) else None
            if rank_100 is None or rank_100 < 20 or rank_100 > 80:
                logger.info(f"Skip {fund_name}({fund_code}): rank_100day={rank_100} not in [20, 80]")
                continue
            enriched = dict(row)
            enriched["rank_100day"] = rank_100
            enriched["fund_sub_type"] = actual_sub_type
            enriched["index_code"] = getattr(fund_info, "index_code", None) if fund_info else None
            filtered_results.append(enriched)
        except Exception as e:
            logger.warning(f"Skip {fund_name}({fund_code}): failed to get rank_100day ({e})")
            continue

    logger.info(f"After rank_100day filter [20,80], remaining funds: {len(filtered_results)}")

    index_codes = [str(r.get("index_code")) for r in filtered_results if r.get("index_code")]
    index_name_map: Dict[str, str] = {}
    if index_codes:
        placeholders = ",".join(["%s"] * len(index_codes))
        rows = db.execute_query(
            f"SELECT index_code, index_name FROM market_index_static WHERE index_code IN ({placeholders})",
            tuple(index_codes),
        )
        for r in rows or []:
            if r.get("index_code") and r.get("index_name"):
                index_name_map[str(r["index_code"])] = str(r["index_name"])
    for r in filtered_results:
        idx_code = r.get("index_code")
        if idx_code:
            r["index_name"] = index_name_map.get(str(idx_code), "")

    all_index_names = _get_all_index_names_for_grouping(db)
    deduped = _dedup_funds_by_similar_index(filtered_results, all_index_names)
    logger.info(f"After similar-index dedup, remaining funds: {len(deduped)}")
    return deduped

if __name__ == "__main__":
    selected = query_frequent_index_funds(user=DEFAULT_USER)
    if not selected:
        logger.info("No funds selected.")
        raise SystemExit(0)
    lines: List[str] = []
    for i, row in enumerate(selected, start=1):
        fund_code = row.get("fund_code")
        fund_name = row.get("fund_name")
        cnt = row.get("cnt")
        rank_100day = row.get("rank_100day")
        sub_type = row.get("fund_sub_type")
        lines.append(f"{i:02d}. {fund_name}({fund_code}) cnt={cnt} rank_100day={rank_100day} fund_sub_type={sub_type}")
    logger.info("Selected funds:\n" + "\n".join(lines))
