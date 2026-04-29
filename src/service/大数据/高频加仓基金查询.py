import os
import sys
from typing import List, Dict, Optional

root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from src.db.database_connection import DatabaseConnection
from src.common.logger import get_logger
from src.service.基金信息.基金信息 import get_all_fund_info
from src.common.constant import DEFAULT_USER
logger = get_logger(__name__)


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
            filtered_results.append(enriched)
        except Exception as e:
            logger.warning(f"Skip {fund_name}({fund_code}): failed to get rank_100day ({e})")
            continue

    logger.info(f"After rank_100day filter [20,80], remaining funds: {len(filtered_results)}")
    return filtered_results

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
