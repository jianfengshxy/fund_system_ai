# 模块顶层
import os
import sys

# 将项目根目录加入到 sys.path，确保可以 import src.**
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import logging
from typing import List, Optional

# 添加项目根目录到路径（与参考文件一致）
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.domain.fund.fund_investment_indicator import FundInvestmentIndicator
from src.db.fund_investment_indicator_repository_impl import FundInvestmentIndicatorRepositoryImpl


def select_low_position_indicators(
    user,
    days: int = 100,
    min_appear: int = 3,
    weak_ratio: float = 0.75,
    max_rank_100day: int = 20,
    fallback_all_if_insufficient: bool = False
) -> List[FundInvestmentIndicator]:
    """
    选出“低位的加仓风向标基金”：
    1) 最近 days 个交易日内出现至少 min_appear 次（若数据不足导致空集，且 fallback_all_if_insufficient=True，则回退为 threshold=1，即“全选”）
    2) 同时满足弱势条件：
       - season_item_rank > season_item_sc * weak_ratio
       - month_item_rank  > month_item_sc  * weak_ratio
    3) 并且 rank_100day < max_rank_100day

    参数说明：
    - days: 交易日窗口大小（默认 100）
    - min_appear: 至少出现次数（默认 3）
    - weak_ratio: 弱势比例阈值（默认 0.75，取后 25%）
    - max_rank_100day: 100日净值排名上限（默认 20）
    - fallback_all_if_insufficient: 若不足 days 导致候选集为空，则使用“全选”（threshold=1）回退

    返回：
    - 满足条件的 FundInvestmentIndicator 列表
    """
    logger = logging.getLogger("LowPositionFundIndicatorService")
    repo = FundInvestmentIndicatorRepositoryImpl()

    from src.db.database_connection import DatabaseConnection
    db = DatabaseConnection()
    recent_dates_sql = """
        SELECT DISTINCT update_date 
        FROM fund_investment_indicators 
        ORDER BY update_date DESC 
        LIMIT %s
    """
    recent_dates = db.execute_query(recent_dates_sql, (days,))
    logger.info(f"[低位筛选] 可用交易日数量: {len(recent_dates)}（期望={days}）")
    if recent_dates:
        logger.debug(f"[低位筛选] 交易日列表: {[row['update_date'] for row in recent_dates]}")
    if not recent_dates:
        logger.warning("[低位筛选] 无可用交易日数据，返回空列表")
        return []

    date_list = [row['update_date'] for row in recent_dates]
    min_date = min(date_list)
    max_date_window = max(date_list)
    logger.info(f"[低位筛选] 时间窗口: [{min_date} ~ {max_date_window}]")

    # 统一使用传入的出现次数阈值，不回退
    effective_threshold = min_appear
    if len(recent_dates) < days:
        logger.warning(f"[低位筛选] 实际交易日不足 {days}，不回退：仍使用出现次数阈值 {min_appear}")
    logger.info(f"[低位筛选] 使用出现次数阈值: {effective_threshold}")

    # Step 1: 候选集（满足出现次数阈值，并取窗口内最新日期的数据行）
    indicators: List[FundInvestmentIndicator] = repo.get_frequent_indicators(days, effective_threshold)
    logger.info(f"[低位筛选] 初始候选（days={days}, min_appear={min_appear}, effective_threshold={effective_threshold}）数量: {len(indicators)}")
    if not indicators:
        logger.warning("[低位筛选] 候选集为空，直接返回空列表")
        return []

    # 统计出现次数
    codes = [ind.fund_code for ind in indicators]
    counts_map = {}
    if codes:
        placeholders = ",".join(["%s"] * len(codes))
        sql_counts = f"""
            SELECT fund_code, COUNT(DISTINCT update_date) AS cnt
            FROM fund_investment_indicators
            WHERE update_date BETWEEN %s AND %s
              AND fund_code IN ({placeholders})
            GROUP BY fund_code
        """
        rows = db.execute_query(sql_counts, (min_date, max_date_window, *codes))
        for r in rows:
            counts_map[r["fund_code"]] = r["cnt"]

    # 新增：为候选基金获取“全表最新记录”，并用其字段做判断
    latest_map = {}
    if codes:
        placeholders = ",".join(["%s"] * len(codes))
        latest_sql = f"""
            SELECT t.*
            FROM fund_investment_indicators t
            JOIN (
                SELECT fund_code, MAX(update_date) AS max_ud
                FROM fund_investment_indicators
                WHERE fund_code IN ({placeholders})
                GROUP BY fund_code
            ) m ON t.fund_code = m.fund_code AND t.update_date = m.max_ud
        """
        latest_rows = db.execute_query(latest_sql, (*codes,))
        for r in latest_rows:
            latest_map[r["fund_code"]] = r

    # 打印候选基金的出现次数与日期信息
    for ind in indicators:
        cnt = counts_map.get(ind.fund_code, 0)
        latest_row = latest_map.get(ind.fund_code)
        latest_date_global = latest_row["update_date"] if latest_row else None
        logger.info(
            f"[低位筛选] 候选基金: {ind.fund_name}({ind.fund_code}) "
            f"出现次数: {cnt}, 窗口内最新日期: {max_date_window}, 全表最新日期: {latest_date_global}"
        )

    # 使用“全表最新记录”的字段覆盖，确保判断依据是最新数据
    fields_to_update = [
        "season_item_rank", "season_item_sc",
        "month_item_rank", "month_item_sc",
        "rank_100day", "rank_30day", "volatility", "nav_5day_avg",
        "product_rank", "tracking_index", "update_time"
    ]
    for ind in indicators:
        latest_row = latest_map.get(ind.fund_code)
        if latest_row:
            # 记录是否与窗口最新日期不同
            if latest_row["update_date"] != max_date_window:
                logger.info(
                    f"[低位筛选] 使用全表最新记录覆盖: {ind.fund_name}({ind.fund_code}) "
                    f"窗口最新={max_date_window} != 全表最新={latest_row['update_date']}"
                )
            for f in fields_to_update:
                val = latest_row.get(f, None)
                try:
                    setattr(ind, f, val)
                except Exception:
                    # 某些字段可能不在模型里，忽略
                    pass
        else:
            logger.warning(f"[低位筛选] 未找到全表最新记录: {ind.fund_name}({ind.fund_code})，沿用窗口内最新数据行")

    # 判定与原因
    def check_and_reason(ind: FundInvestmentIndicator) -> (bool, str):
        s_rank = getattr(ind, "season_item_rank", None)
        s_sc   = getattr(ind, "season_item_sc", None)
        m_rank = getattr(ind, "month_item_rank", None)
        m_sc   = getattr(ind, "month_item_sc", None)
        r100   = getattr(ind, "rank_100day", None)

        missing = []
        if s_rank is None: missing.append("season_item_rank")
        if s_sc   is None: missing.append("season_item_sc")
        if m_rank is None: missing.append("month_item_rank")
        if m_sc   is None: missing.append("month_item_sc")
        if r100   is None: missing.append("rank_100day")
        if missing:
            return False, f"缺少字段: {', '.join(missing)}"

        if s_sc == 0 or m_sc == 0:
            return False, f"数据异常: 分母为0（season_item_sc={s_sc}, month_item_sc={m_sc}）"

        cond_season = (s_rank > s_sc * weak_ratio)
        cond_month  = (m_rank > m_sc * weak_ratio)
        cond_r100   = (r100 < max_rank_100day)

        if not cond_season or not cond_month or not cond_r100:
            fail_reasons = []
            if not cond_season:
                fail_reasons.append(f"弱势(季)未满足: {s_rank} <= {s_sc} * {weak_ratio:.2f}")
            if not cond_month:
                fail_reasons.append(f"弱势(月)未满足: {m_rank} <= {m_sc} * {weak_ratio:.2f}")
            if not cond_r100:
                fail_reasons.append(f"rank_100day未达标: {r100} >= {max_rank_100day}")
            return False, "; ".join(fail_reasons)

        return True, "满足弱势与排名条件"

    filtered = []
    for ind in indicators:
        ok, reason = check_and_reason(ind)
        count = counts_map.get(ind.fund_code, 0)
        latest_row = latest_map.get(ind.fund_code)
        latest_date_global = latest_row["update_date"] if latest_row else None
        if ok:
            filtered.append(ind)
            logger.info(
                f"[保留] {ind.fund_name}({ind.fund_code}) "
                f"出现次数={count}, 全表最新日期={latest_date_global}, "
                f"season={ind.season_item_rank}/{ind.season_item_sc}, "
                f"month={ind.month_item_rank}/{ind.month_item_sc}, "
                f"rank_100day={getattr(ind, 'rank_100day', None)}；原因: {reason}"
            )
        else:
            logger.info(
                f"[剔除] {ind.fund_name}({ind.fund_code}) "
                f"出现次数={count}, 全表最新日期={latest_date_global}, "
                f"season={ind.season_item_rank}/{ind.season_item_sc}, "
                f"month={ind.month_item_rank}/{ind.month_item_sc}, "
                f"rank_100day={getattr(ind, 'rank_100day', None)}；原因: {reason}"
            )

    logger.info(f"[低位筛选] 过滤后基金数量: {len(filtered)}")

    # 可选：排序（参考“加仓风向标服务.py”，默认按 product_rank 升序）
    try:
        filtered.sort(key=lambda x: getattr(x, "product_rank", float("inf")))
    except Exception as e:
        logger.warning(f"[低位筛选] 按 product_rank 排序失败，原因: {e}")

    return filtered


if __name__ == "__main__":
    # 简单自检：需要 DEFAULT_USER 与日志配置
    from src.common.constant import DEFAULT_USER

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s - %(message)s")
    result = select_low_position_indicators(
        user=DEFAULT_USER,
        days=50,
        min_appear=15,
        weak_ratio=0.75,
        max_rank_100day=20,
        fallback_all_if_insufficient=True
    )

    print(f"低位加仓风向标基金筛选完成，总数: {len(result)}")
    for i, ind in enumerate(result, 1):
        print(f"{i}. {ind.fund_name}({ind.fund_code}) "
              f"season={getattr(ind, 'season_item_rank', None)}/{getattr(ind, 'season_item_sc', None)}, "
              f"month={getattr(ind, 'month_item_rank', None)}/{getattr(ind, 'month_item_sc', None)}, "
              f"rank_100day={getattr(ind, 'rank_100day', None)}, product_rank={getattr(ind, 'product_rank', None)}")