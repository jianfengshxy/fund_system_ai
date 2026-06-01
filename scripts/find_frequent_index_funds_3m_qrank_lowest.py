import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

project_root = Path(__file__).resolve().parents[1]
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from src.API.基金信息.FundRankDiagram import get_fund_rank_diagram
from src.API.登录接口.login import ensure_user_fresh
from src.common.constant import DEFAULT_USER
from src.db.database_connection import DatabaseConnection


@dataclass(frozen=True)
class FrequentFund:
    fund_code: str
    fund_name: str
    occurrences: int
    latest_update_date: Optional[str]
    fund_type: str
    fund_sub_type: str


@dataclass(frozen=True)
class CandidateResult:
    fund_code: str
    fund_name: str
    occurrences: int
    latest_update_date: Optional[str]
    latest_rank_date: Optional[str]
    latest_qrank: float
    worst_qrank_3m: float
    point_count: int
    start_date: Optional[str]
    end_date: Optional[str]


def _safe_float(value) -> Optional[float]:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        raw = value.strip()
        if not raw or raw == "--":
            return None
        try:
            return float(raw)
        except (TypeError, ValueError):
            return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _extract_rank_points(payload: dict) -> List[dict]:
    if not isinstance(payload, dict):
        return []
    data = payload.get("data")
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for key in ("Datas", "Data", "List", "Points", "points"):
            value = data.get(key)
            if isinstance(value, list):
                return value
    return []


def _extract_point_date(point: dict) -> Optional[str]:
    for key in ("PDATE", "pdate", "DATE", "date", "TDATE", "tdate"):
        value = point.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _extract_qrank(point: dict) -> Optional[float]:
    for key in ("QRANK", "qrank", "Rank", "rank"):
        if key in point:
            return _safe_float(point.get(key))
    return None


def _sort_points(points: Sequence[dict]) -> List[dict]:
    sortable: List[Tuple[str, int, dict]] = []
    for index, point in enumerate(points):
        point_date = _extract_point_date(point)
        if point_date is None:
            return list(points)
        sortable.append((point_date, index, point))
    return [point for _, _, point in sorted(sortable, key=lambda item: (item[0], item[1]))]


def _query_frequent_funds(days: int = 180, min_appear_exclusive: int = 20) -> List[FrequentFund]:
    db = DatabaseConnection()
    recent_dates_sql = """
        SELECT DISTINCT update_date
        FROM fund_investment_indicators
        ORDER BY update_date DESC
        LIMIT %s
    """
    recent_dates = db.execute_query(recent_dates_sql, (days,))
    if not recent_dates:
        return []

    date_list = [row["update_date"] for row in recent_dates if row.get("update_date")]
    if not date_list:
        return []
    min_date = min(date_list)
    max_date = max(date_list)

    sql = """
        SELECT
            fund_code,
            MAX(fund_name) AS fund_name,
            MAX(update_date) AS latest_update_date,
            MAX(fund_type) AS fund_type,
            MAX(fund_sub_type) AS fund_sub_type,
            COUNT(DISTINCT update_date) AS cnt
        FROM fund_investment_indicators
        WHERE update_date BETWEEN %s AND %s
        GROUP BY fund_code
        HAVING cnt > %s
        ORDER BY cnt DESC, fund_code ASC
    """
    rows = db.execute_query(sql, (min_date, max_date, min_appear_exclusive))
    return [
        FrequentFund(
            fund_code=str(row.get("fund_code") or ""),
            fund_name=str(row.get("fund_name") or ""),
            occurrences=int(row.get("cnt") or 0),
            latest_update_date=str(row.get("latest_update_date") or "") or None,
            fund_type=str(row.get("fund_type") or ""),
            fund_sub_type=str(row.get("fund_sub_type") or ""),
        )
        for row in (rows or [])
        if row.get("fund_code")
    ]


def _analyze_fund_qrank_3m(user, fund_code: str) -> Optional[Dict[str, object]]:
    payload = get_fund_rank_diagram(user, fund_code, range_value="3y")
    points = _sort_points(_extract_rank_points(payload) if isinstance(payload, dict) else [])
    if not points:
        return None

    enriched_points: List[Tuple[dict, float]] = []
    for point in points:
        qrank = _extract_qrank(point)
        if qrank is None:
            continue
        enriched_points.append((point, qrank))
    if not enriched_points:
        return None

    latest_point, latest_qrank = enriched_points[-1]
    worst_qrank = max(qrank for _, qrank in enriched_points)
    return {
        "latest_qrank": latest_qrank,
        "worst_qrank_3m": worst_qrank,
        "latest_rank_date": _extract_point_date(latest_point),
        "point_count": len(points),
        "start_date": _extract_point_date(points[0]),
        "end_date": _extract_point_date(points[-1]),
    }


def main() -> int:
    frequent_funds = _query_frequent_funds(days=180, min_appear_exclusive=20)
    if not frequent_funds:
        print("在最近 180 个交易日窗口内，未找到加仓风向标出现次数大于 20 的基金。")
        return 0

    user = ensure_user_fresh(DEFAULT_USER)

    matched_results: List[CandidateResult] = []
    failed_rank_requests: List[Tuple[str, str, str]] = []

    for fund in frequent_funds:
        try:
            rank_info = _analyze_fund_qrank_3m(user, fund.fund_code)
        except Exception as exc:
            failed_rank_requests.append((fund.fund_code, fund.fund_name, str(exc)))
            continue

        if not rank_info:
            failed_rank_requests.append((fund.fund_code, fund.fund_name, "empty rank data"))
            continue

        latest_qrank = float(rank_info["latest_qrank"])
        worst_qrank_3m = float(rank_info["worst_qrank_3m"])
        if abs(latest_qrank - worst_qrank_3m) > 1e-9:
            continue

        matched_results.append(
            CandidateResult(
                fund_code=fund.fund_code,
                fund_name=fund.fund_name,
                occurrences=fund.occurrences,
                latest_update_date=fund.latest_update_date,
                latest_rank_date=rank_info["latest_rank_date"],
                latest_qrank=latest_qrank,
                worst_qrank_3m=worst_qrank_3m,
                point_count=int(rank_info["point_count"]),
                start_date=rank_info["start_date"],
                end_date=rank_info["end_date"],
            )
        )

    matched_results.sort(key=lambda item: (-item.latest_qrank, -item.occurrences, item.fund_code))

    print("筛选条件：")
    print("  1) 数据来源：fund_investment_indicators（加仓风向标入库表）")
    print("  2) 高频定义：最近 180 个交易日内，COUNT(DISTINCT update_date) > 20")
    print("  3) 排名区间：FundRankDiagram(RANGE=3y，近3个月)")
    print("  4) 最低排名定义：最新一条记录的 QRANK == 近3个月全部记录中的最大 QRANK")
    print()
    print(f"高频基金总数：{len(frequent_funds)}")
    print(f"命中基金总数：{len(matched_results)}")
    print(f"排名请求失败/无数据：{len(failed_rank_requests)}")
    print()

    print("高频基金列表：")
    for index, fund in enumerate(frequent_funds, start=1):
        print(
            f"#{index}: {fund.fund_name}({fund.fund_code}) | appearances={fund.occurrences} | "
            f"latest_update_date={fund.latest_update_date} | fund_type={fund.fund_type} | "
            f"fund_sub_type={fund.fund_sub_type}"
        )
    print()

    if failed_rank_requests:
        print("排名请求失败明细：")
        for index, (fund_code, fund_name, error) in enumerate(failed_rank_requests, start=1):
            print(f"#{index}: {fund_name}({fund_code}) | error={error}")
        print()

    if not matched_results:
        print("没有基金满足“最新 QRANK 等于近3个月最差 QRANK”这个条件。")
        return 0

    print("命中列表：")
    for index, item in enumerate(matched_results, start=1):
        print(
            f"#{index}: {item.fund_name}({item.fund_code}) | appearances={item.occurrences} | "
            f"latest_update_date={item.latest_update_date} | latest_rank_date={item.latest_rank_date} | "
            f"latest_qrank={item.latest_qrank} | worst_qrank_3m={item.worst_qrank_3m} | "
            f"points={item.point_count} | span={item.start_date} -> {item.end_date}"
        )

    best_match = matched_results[0]
    print()
    print("近3个月最新 QRANK 最差的基金：")
    print(
        f"{best_match.fund_name}({best_match.fund_code}) | QRANK={best_match.latest_qrank} | "
        f"latest_rank_date={best_match.latest_rank_date} | appearances={best_match.occurrences}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
