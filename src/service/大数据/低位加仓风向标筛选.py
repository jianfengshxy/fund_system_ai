# 模块顶层
import os
import sys

# 将项目根目录加入到 sys.path，确保可以 import src.**
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import logging
from src.common.logger import get_logger
from typing import List, Optional, Union

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
    fallback_all_if_insufficient: bool = False,
    fund_type: Optional[Union[str, List[str]]] = None
) -> List[FundInvestmentIndicator]:
    """
    选出“低位的加仓风向标基金”：
    - fund_type 不传或 []：筛选全部基金
    - fund_type 传单个字符串（如 '000'）：筛选该类型基金
    - fund_type 传多个类型（如 ['001','002']）：筛选这些类型的基金
    条件：
      1) season_item_rank > season_item_sc * weak_ratio（季度弱势）
      2) month_item_rank < season_item_sc（月度排名比季度排名靠前）
      3) rank_100day > max_rank_100day（摆脱底部）
      4) days 窗口内出现次数 > min_appear
    最终按出现次数降序取前 20
    """
    logger = get_logger("LowPositionFundIndicatorService")

    # 归一化 fund_type 参数为列表或 None
    def normalize_fund_types(ft_param) -> Optional[List[str]]:
        if ft_param is None:
            return None
        if isinstance(ft_param, str):
            ft = ft_param.strip()
            return [ft] if ft else None
        if isinstance(ft_param, (list, tuple)):
            types = [str(x).strip() for x in ft_param if str(x).strip()]
            return types if types else None
        return None

    filter_types = normalize_fund_types(fund_type)
    if filter_types is None:
        logger.info("[低位筛选] fund_type 未指定或为空列表：筛选全部基金类型")
    else:
        logger.info(f"[低位筛选] 限定基金类型集合: {filter_types}")

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

    # 新增：列出 days 窗口内出现过的所有基金（去重，不按 fund_type 过滤，便于全面审计）
    sql_all_codes = """
        SELECT DISTINCT fund_code
        FROM fund_investment_indicators
        WHERE update_date BETWEEN %s AND %s
    """
    rows_all_codes = db.execute_query(sql_all_codes, (min_date, max_date_window))
    all_codes = [r["fund_code"] for r in (rows_all_codes or [])]
    logger.info(f"[窗口审计] 去重基金数量: {len(all_codes)}（时间窗口: {min_date} ~ {max_date_window}）")

    # 统计出现次数（不按 fund_type 过滤，避免出现“0 次数”假象）
    counts_map = {}
    if all_codes:
        placeholders_all = ",".join(["%s"] * len(all_codes))
        sql_counts_all = f"""
            SELECT fund_code, COUNT(DISTINCT update_date) AS cnt
            FROM fund_investment_indicators
            WHERE update_date BETWEEN %s AND %s
              AND fund_code IN ({placeholders_all})
            GROUP BY fund_code
        """
        rows_counts_all = db.execute_query(sql_counts_all, (min_date, max_date_window, *all_codes))
        for r in (rows_counts_all or []):
            counts_map[r["fund_code"]] = r["cnt"]

    # 为所有窗口基金获取“全表最新记录”（当天缺失不视为错误，用该基金的最新记录）
    latest_map = {}
    if all_codes:
        placeholders_all = ",".join(["%s"] * len(all_codes))
        latest_sql_all = f"""
            SELECT t.*
            FROM fund_investment_indicators t
            JOIN (
                SELECT fund_code, MAX(update_date) AS max_ud
                FROM fund_investment_indicators
                WHERE fund_code IN ({placeholders_all})
                GROUP BY fund_code
            ) m ON t.fund_code = m.fund_code AND t.update_date = m.max_ud
        """
        latest_rows_all = db.execute_query(latest_sql_all, (*all_codes,))
        for r in (latest_rows_all or []):
            latest_map[r["fund_code"]] = r

    # 审计：逐个基金打印出现次数、最新记录日期、类型，并给出保留/剔除原因
    def check_row_and_reason(row: dict, cnt: int) -> (bool, str):
        s_rank = row.get("season_item_rank")
        s_sc   = row.get("season_item_sc")
        m_rank = row.get("month_item_rank")
        r100   = row.get("rank_100day")
        ftype  = row.get("fund_type")

        missing = []
        if s_rank is None: missing.append("season_item_rank")
        if s_sc   is None: missing.append("season_item_sc")
        if m_rank is None: missing.append("month_item_rank")
        if r100   is None: missing.append("rank_100day")
        if filter_types is not None and ftype is None: missing.append("fund_type")
        if missing:
            return False, f"缺少字段: {', '.join(missing)}"

        if s_sc == 0:
            return False, f"数据异常: 分母为0（season_item_sc={s_sc}）"

        if filter_types is not None and ftype not in filter_types:
            return False, f"fund_type不匹配: 期望∈{filter_types}, 实际={ftype}"

        cond_season = (s_rank > s_sc * weak_ratio)   # 条件1：季度弱势
        cond_month  = (m_rank < s_sc)                 # 条件2：月强于季
        cond_r100   = (r100 > max_rank_100day)        # 条件3：100日排名更靠前（摆脱底部）
        cond_count  = (cnt > min_appear)              # 条件4：出现次数大于阈值

        if not (cond_season and cond_month and cond_r100 and cond_count):
            reasons = []
            if not cond_season:
                reasons.append(f"季度弱势未满足: {s_rank} <= {s_sc} * {weak_ratio:.2f}")
            if not cond_month:
                reasons.append(f"月强于季未满足: {m_rank} >= {s_sc}")
            if not cond_r100:
                reasons.append(f"rank_100day未达标: {r100} <= {max_rank_100day}")
            if not cond_count:
                reasons.append(f"出现次数未达标: {cnt} <= {min_appear}")
            return False, "; ".join(reasons)

        return True, "满足四项筛选条件"

    for code in all_codes:
        row = latest_map.get(code)
        cnt = counts_map.get(code, 0)
        if not row:
            logger.warning(f"[窗口审计] 未找到该基金的全表最新记录: fund_code={code}，可能数据不完整")
            continue
        latest_date_global = row.get("update_date")
        ftype = row.get("fund_type")
        ok, reason = check_row_and_reason(row, cnt)
        prefix = "[窗口基金保留]" if ok else "[窗口基金剔除]"
        logger.info(
            f"{prefix} {row.get('fund_name')}({code}) "
            f"出现次数={cnt}, 全表最新日期={latest_date_global}, fund_type={ftype}, "
            f"season={row.get('season_item_rank')}/{row.get('season_item_sc')}, "
            f"month={row.get('month_item_rank')}, rank_100day={row.get('rank_100day')}；原因: {reason}"
        )

    # 原候选与最终过滤逻辑保持，但使用修正后的 counts_map 与 latest_map（不受 fund_type 过滤）
    indicators: List[FundInvestmentIndicator] = repo.get_frequent_indicators(days, effective_threshold)
    logger.info(f"[低位筛选] 初始候选（days={days}, min_appear={min_appear}, effective_threshold={effective_threshold}）数量: {len(indicators)}")
    if not indicators:
        logger.warning("[低位筛选] 候选集为空，直接返回空列表")
        return []

    # 将全表最新记录的关键字段覆盖到候选对象上，评估与日志输出（与现有逻辑一致）
    fields_to_update = [
        "season_item_rank", "season_item_sc",
        "month_item_rank", "month_item_sc",
        "rank_100day", "rank_30day", "volatility", "nav_5day_avg",
        "product_rank", "tracking_index", "update_time", "fund_type"
    ]
    for ind in indicators:
        latest_row = latest_map.get(ind.fund_code)
        if latest_row:
            if latest_row.get("update_date") != max_date_window:
                logger.info(
                    f"[低位筛选] 使用全表最新记录覆盖: {ind.fund_name}({ind.fund_code}) "
                    f"窗口最新={max_date_window} != 全表最新={latest_row.get('update_date')}"
                )
            for f in fields_to_update:
                val = latest_row.get(f, None)
                try:
                    setattr(ind, f, val)
                except Exception:
                    pass
        else:
            logger.warning(f"[低位筛选] 未找到全表最新记录: {ind.fund_name}({ind.fund_code})，沿用窗口内最新数据行")

    # 判定与原因（实现四项条件，并校验 fund_type 集合）
    def check_and_reason(ind: FundInvestmentIndicator) -> (bool, str):
        s_rank = getattr(ind, "season_item_rank", None)
        s_sc   = getattr(ind, "season_item_sc", None)
        m_rank = getattr(ind, "month_item_rank", None)
        r100   = getattr(ind, "rank_100day", None)
        ftype  = getattr(ind, "fund_type", None)
        cnt    = counts_map.get(ind.fund_code, 0)

        missing = []
        if s_rank is None: missing.append("season_item_rank")
        if s_sc   is None: missing.append("season_item_sc")
        if m_rank is None: missing.append("month_item_rank")
        if r100   is None: missing.append("rank_100day")
        if filter_types is not None and ftype is None: missing.append("fund_type")
        if missing:
            return False, f"缺少字段: {', '.join(missing)}"

        if s_sc == 0:
            return False, f"数据异常: 分母为0（season_item_sc={s_sc}）"

        if filter_types is not None and ftype not in filter_types:
            return False, f"fund_type不匹配: 期望∈{filter_types}, 实际={ftype}"

        cond_season = (s_rank > s_sc * weak_ratio)   # 条件1：季度弱势
        cond_month  = (m_rank < s_sc)                 # 条件2：月强于季
        cond_r100   = (r100 > max_rank_100day)        # 条件3：100日排名更靠前（摆脱底部）
        cond_count  = (cnt > min_appear)              # 条件4：出现次数大于阈值

        if not (cond_season and cond_month and cond_r100 and cond_count):
            reasons = []
            if not cond_season:
                reasons.append(f"季度弱势未满足: {s_rank} <= {s_sc} * {weak_ratio:.2f}")
            if not cond_month:
                reasons.append(f"月强于季未满足: {m_rank} >= {s_sc}")
            if not cond_r100:
                reasons.append(f"rank_100day未达标: {r100} <= {max_rank_100day}")
            if not cond_count:
                reasons.append(f"出现次数未达标: {cnt} <= {min_appear}")
            return False, "; ".join(reasons)

        return True, "满足四项筛选条件"

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
                f"month={ind.month_item_rank}, "
                f"rank_100day={getattr(ind, 'rank_100day', None)}, fund_type={getattr(ind, 'fund_type', None)}；原因: {reason}"
            )
        else:
            logger.info(
                f"[剔除] {ind.fund_name}({ind.fund_code}) "
                f"出现次数={count}, 全表最新日期={latest_date_global}, "
                f"season={ind.season_item_rank}/{ind.season_item_sc}, "
                f"month={ind.month_item_rank}, "
                f"rank_100day={getattr(ind, 'rank_100day', None)}, fund_type={getattr(ind, 'fund_type', None)}；原因: {reason}"
            )

    logger.info(f"[低位筛选] 过滤后基金数量: {len(filtered)}")

    # 按出现次数降序排序，取前20
    try:
        filtered.sort(key=lambda x: counts_map.get(x.fund_code, 0), reverse=True)
    except Exception as e:
        logger.warning(f"[低位筛选] 按出现次数排序失败，原因: {e}")

    top_n = filtered[:20]
    logger.info(f"[低位筛选] 最终返回前{len(top_n)}个基金（按出现次数降序）")
    return top_n


if __name__ == "__main__":
    # 简单自检：需要 DEFAULT_USER 与日志配置
    from src.common.constant import DEFAULT_USER

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s - %(message)s")
    result = select_low_position_indicators(
        user=DEFAULT_USER,
        days=50,
        min_appear=10,
        weak_ratio=0.75,
        max_rank_100day=20,
        fallback_all_if_insufficient=True,
        fund_type='000'  # 仅指数基金
    )

    print(f"低位加仓风向标基金筛选完成，总数: {len(result)}")
    for i, ind in enumerate(result, 1):
        print(f"{i}. {ind.fund_name}({ind.fund_code}) "
              f"season={getattr(ind, 'season_item_rank', None)}/{getattr(ind, 'season_item_sc', None)}, "
              f"month={getattr(ind, 'month_item_rank', None)}/{getattr(ind, 'month_item_sc', None)}, "
              f"rank_100day={getattr(ind, 'rank_100day', None)}, product_rank={getattr(ind, 'product_rank', None)}")

    # 示例：筛选全部基金
    result_all = select_low_position_indicators(
        user=DEFAULT_USER,
        days=50,
        min_appear=15,
        weak_ratio=0.75,
        max_rank_100day=20,
        fallback_all_if_insufficient=True,
        fund_type=[]  # 或者不传 fund_type
    )
    print(f"全部基金筛选完成，总数: {len(result_all)}")

    # 示例：仅指数基金
    result_index = select_low_position_indicators(
        user=DEFAULT_USER,
        days=50,
        min_appear=15,
        weak_ratio=0.75,
        max_rank_100day=20,
        fallback_all_if_insufficient=True,
        fund_type='000'
    )
    print(f"指数基金筛选完成，总数: {len(result_index)}")

    # 示例：多类型（股票型 + 混合型）
    result_multi = select_low_position_indicators(
        user=DEFAULT_USER,
        days=50,
        min_appear=15,
        weak_ratio=0.75,
        max_rank_100day=20,
        fallback_all_if_insufficient=True,
        fund_type=[]
    )
    print(f"筛选完成，总数: {len(result_multi)}")
