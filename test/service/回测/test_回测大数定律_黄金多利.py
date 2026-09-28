#!/usr/bin/env python3
"""
大数定律 + 黄金多利组合策略回测

默认口径：
1. 大数定律基金池按历史每日 market_index_daily 条件动态筛选
2. 同类指数去重沿用生产逻辑，且优先保留当前已持仓基金
3. 黄金多利参数沿用默认值：
   - init_amount = 2000
   - amount = 2000
   - 无单基金/组合总额上限
4. 止盈只卖出持有 >= 7 天的 0 费率份额
5. 以交易日收盘净值作为当日成交/估值口径

输出指标：
- 收益金额
- 收益率
- 最大组合占用资金
- 平均日占用资金
- 日均资产收益率
"""

import argparse
import logging
import os
import sys
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from statistics import mean
from typing import Dict, List, Optional, Sequence, Tuple

root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from src.API.交易管理.feeMrg import getFee
from src.common.constant import (
    DEFAULT_GTOKEN,
    DEFAULT_USER,
    DEVICE_ID,
    IOS_CLIENT_INFO,
    IOS_OS_VERSION,
    IOS_USER_AGENT,
    MOBILE_KEY,
    PLATFORM,
    SERVER_VERSION,
)
from src.common.requests_session import session
from src.db.database_connection import DatabaseConnection
from src.service.公共服务.redeem_fee_filter_service import is_high_frequency_index_fee_ok
from src.service.基金信息.基金信息 import get_all_fund_info
from src.service.大数据.增加大数定律基金到自选组合 import (
    _dedup_similar_indices,
    _get_all_index_names_for_grouping,
)


TARGET_TYPES = ["宽基", "行业", "主题", "海外"]
DEFAULT_AMOUNT = 2000.0
DEFAULT_INIT_AMOUNT = 2000.0
ZERO_FEE_HOLD_DAYS = 7


@dataclass
class Lot:
    shares: float
    amount: float
    buy_date: str


@dataclass
class Position:
    lots: List[Lot] = field(default_factory=list)

    def total_shares(self) -> float:
        return sum(lot.shares for lot in self.lots)

    def total_cost(self) -> float:
        return sum(lot.amount for lot in self.lots)

    def is_empty(self) -> bool:
        return self.total_shares() <= 1e-8


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="回测大数定律黄金多利策略")
    parser.add_argument("--start-date", help="开始日期，格式 YYYY-MM-DD")
    parser.add_argument("--end-date", help="结束日期，格式 YYYY-MM-DD")
    parser.add_argument("--amount", type=float, default=DEFAULT_AMOUNT, help="常规加仓金额")
    parser.add_argument("--init-amount", type=float, default=DEFAULT_INIT_AMOUNT, help="首次建仓金额")
    parser.add_argument("--limit", type=float, default=None, help="单基金默认持仓上限")
    parser.add_argument("--seed-snapshot-date", help="从历史持仓快照日期开跑，格式 YYYY-MM-DD")
    parser.add_argument("--seed-sub-account-name", default="大数定律", help="快照对应组合名称")
    return parser


def _fmt_money(value: float) -> str:
    return f"{value:,.2f}"


def _fmt_pct(value: float) -> str:
    return f"{value:+.2f}%"


def _get_default_end_date(db: DatabaseConnection) -> str:
    sql = """
    SELECT MAX(d.trade_date) AS max_date
    FROM market_index_static s
    JOIN market_index_daily d ON s.index_code = d.index_code
    WHERE s.type_name IN (%s, %s, %s, %s)
      AND s.track_fund_code IS NOT NULL AND s.track_fund_code != ''
      AND d.avg_return_q IS NOT NULL AND d.avg_return_q > 10
      AND d.avg_return_hy IS NOT NULL AND (d.avg_return_hy - d.avg_return_q) > 10
      AND d.profit_rate_y IS NOT NULL AND d.profit_rate_y = 100
    """
    row = db.execute_query(sql, TARGET_TYPES)[0]
    return row["max_date"].isoformat()


def _get_trade_dates(db: DatabaseConnection, start_date: str, end_date: str) -> List[str]:
    sql = """
    SELECT DISTINCT trade_date
    FROM market_index_daily
    WHERE trade_date >= %s AND trade_date <= %s
    ORDER BY trade_date
    """
    rows = db.execute_query(sql, [start_date, end_date])
    return [row["trade_date"].isoformat() for row in rows]


def _get_daily_qualified_indices(
    db: DatabaseConnection,
    trade_date: str,
) -> List[Dict]:
    sql = """
    SELECT
        s.index_code,
        s.index_name,
        s.track_fund_code,
        s.track_fund_name,
        d.avg_return_q,
        d.avg_return_hy,
        d.profit_rate_y
    FROM market_index_static s
    JOIN market_index_daily d ON s.index_code = d.index_code
    WHERE d.trade_date = %s
      AND s.type_name IN (%s, %s, %s, %s)
      AND s.track_fund_code IS NOT NULL AND s.track_fund_code != ''
      AND d.avg_return_q IS NOT NULL AND d.avg_return_q > 10
      AND d.avg_return_hy IS NOT NULL AND (d.avg_return_hy - d.avg_return_q) > 10
      AND d.profit_rate_y IS NOT NULL AND d.profit_rate_y = 100
    ORDER BY d.avg_return_q DESC
    """
    return db.execute_query(sql, [trade_date, *TARGET_TYPES])


def _get_unique_candidate_fund_codes(
    db: DatabaseConnection,
    start_date: str,
    end_date: str,
) -> List[str]:
    sql = """
    SELECT DISTINCT s.track_fund_code AS fund_code
    FROM market_index_static s
    JOIN market_index_daily d ON s.index_code = d.index_code
    WHERE d.trade_date >= %s AND d.trade_date <= %s
      AND s.type_name IN (%s, %s, %s, %s)
      AND s.track_fund_code IS NOT NULL AND s.track_fund_code != ''
      AND d.avg_return_q IS NOT NULL AND d.avg_return_q > 10
      AND d.avg_return_hy IS NOT NULL AND (d.avg_return_hy - d.avg_return_q) > 10
      AND d.profit_rate_y IS NOT NULL AND d.profit_rate_y = 100
    """
    rows = db.execute_query(sql, [start_date, end_date, *TARGET_TYPES])
    return sorted({str(row["fund_code"]).strip() for row in rows if row.get("fund_code")})


def _get_fund_nav_history(fund_code: str, page_size: int = 500) -> List[Tuple[str, float]]:
    url = "https://fundmobapi.eastmoney.com/FundMNewApi/FundMNHisNetList"
    headers = {
        "Connection": "keep-alive",
        "Host": "fundmobapi.eastmoney.com",
        "Accept": "*/*",
        "GTOKEN": DEFAULT_GTOKEN,
        "clientInfo": IOS_CLIENT_INFO,
        "Accept-Language": "zh-Hans-CN;q=1",
        "User-Agent": IOS_USER_AGENT,
        "Referer": "https://mpservice.com/516939c37bdb4ba2b1138c50cf69a2e1/release/pages/fundHistoryWorth/index",
        "Content-Type": "application/x-www-form-urlencoded",
    }
    data = {
        "FCODE": fund_code,
        "IsShareNet": "true",
        "MobileKey": MOBILE_KEY,
        "OSVersion": IOS_OS_VERSION,
        "appType": "ttjj",
        "appVersion": SERVER_VERSION,
        "cToken": DEFAULT_USER.c_token,
        "deviceid": DEVICE_ID,
        "pageIndex": "0",
        "pageSize": str(page_size),
        "passportid": DEFAULT_USER.passport_id,
        "plat": PLATFORM,
        "product": "EFund",
        "serverVersion": SERVER_VERSION,
        "uToken": DEFAULT_USER.u_token,
        "userId": DEFAULT_USER.customer_no,
        "version": SERVER_VERSION,
    }
    resp = session.post(url, headers=headers, data=data, verify=False, timeout=30)
    resp.raise_for_status()
    result = []
    for item in resp.json().get("Datas", []):
        nav_date = item.get("FSRQ")
        nav = float(item.get("DWJZ", 0) or 0)
        if nav_date and nav > 0:
            result.append((nav_date, nav))
    return result


def _lookup_nav(nav_map: Dict[str, float], nav_date: str) -> Optional[float]:
    if nav_date in nav_map:
        return nav_map[nav_date]

    cursor = datetime.strptime(nav_date, "%Y-%m-%d").date()
    for _ in range(5):
        cursor -= timedelta(days=1)
        key = cursor.isoformat()
        if key in nav_map:
            return nav_map[key]
    return None


def _calc_week_month_and_ma5(
    nav_series_desc: Sequence[Tuple[str, float]],
    nav_date: str,
) -> Tuple[float, float, Optional[float], Optional[float]]:
    date_to_idx = {dt: idx for idx, (dt, _) in enumerate(nav_series_desc)}
    idx = date_to_idx.get(nav_date)
    if idx is None:
        return 0.0, 0.0, None, None

    current_nav = nav_series_desc[idx][1]
    week_return = 0.0
    month_return = 0.0
    nav_5day_avg = None

    if idx + 5 < len(nav_series_desc):
        prev_5 = nav_series_desc[idx + 5][1]
        if prev_5 > 0:
            week_return = (current_nav / prev_5 - 1) * 100

    if idx + 20 < len(nav_series_desc):
        prev_20 = nav_series_desc[idx + 20][1]
        if prev_20 > 0:
            month_return = (current_nav / prev_20 - 1) * 100

    window = [value for _, value in nav_series_desc[idx: idx + 5]]
    if len(window) == 5:
        nav_5day_avg = sum(window) / 5

    return week_return, month_return, current_nav, nav_5day_avg


def _get_stop_rate(fund_meta: Dict) -> float:
    volatility = float(fund_meta.get("volatility", 0.0) or 0.0)
    fund_type = str(fund_meta.get("fund_type") or "")
    if fund_type == "000":
        return min(max(volatility, 5.0), 10.0)
    return min(max(volatility, 5.0), 15.0)


def _eligible_zero_fee(lot: Lot, current_date: str) -> bool:
    held_days = (date.fromisoformat(current_date) - date.fromisoformat(lot.buy_date)).days
    return held_days >= ZERO_FEE_HOLD_DAYS


def _load_seed_positions(
    db: DatabaseConnection,
    snapshot_date: str,
    sub_account_name: str,
) -> Tuple[str, Dict[str, Position]]:
    sql = """
    SELECT
        date,
        fund_code,
        fund_name,
        asset_value,
        available_vol,
        fund_nav
    FROM user_sub_account_fund_asset_daily
    WHERE sub_account_name = %s
      AND date <= %s
      AND asset_value > 0
    ORDER BY date DESC, asset_value DESC
    """
    rows = db.execute_query(sql, [sub_account_name, snapshot_date])
    if not rows:
        raise RuntimeError(f"未找到组合 {sub_account_name} 在 {snapshot_date} 及之前的持仓快照")

    effective_date = rows[0]["date"].isoformat()
    effective_rows = [row for row in rows if row["date"].isoformat() == effective_date]
    positions: Dict[str, Position] = {}
    for row in effective_rows:
        fund_code = str(row["fund_code"]).strip()
        asset_value = float(row["asset_value"] or 0)
        nav = float(row["fund_nav"] or 0)
        available_vol = float(row["available_vol"] or 0)
        if asset_value <= 0 or nav <= 0:
            continue

        shares = available_vol if available_vol > 0 else (asset_value / nav)
        if shares <= 0:
            continue

        # 有可用份额的持仓视为成熟仓位，允许立即按 0 费率逻辑参与止盈；
        # 可用份额为 0 的在途/新仓位则保守按快照日建仓，避免提前止盈。
        if available_vol > 0:
            buy_date = (date.fromisoformat(effective_date) - timedelta(days=ZERO_FEE_HOLD_DAYS + 1)).isoformat()
        else:
            buy_date = effective_date

        positions[fund_code] = Position([
            Lot(shares=shares, amount=asset_value, buy_date=buy_date)
        ])
    return effective_date, positions


def run_backtest(
    start_date: str,
    end_date: str,
    amount: float,
    init_amount: float,
    limit: Optional[float],
    seed_snapshot_date: Optional[str],
    seed_sub_account_name: str,
) -> Dict:
    db = DatabaseConnection()
    all_index_names = _get_all_index_names_for_grouping()
    trade_dates = _get_trade_dates(db, start_date, end_date)
    if not trade_dates:
        raise RuntimeError("指定窗口内没有可用交易日")

    candidate_funds = _get_unique_candidate_fund_codes(db, start_date, end_date)
    fee_ok_map: Dict[str, bool] = {}
    for fund_code in candidate_funds:
        try:
            fee_ok_map[fund_code] = is_high_frequency_index_fee_ok(getFee(DEFAULT_USER, fund_code))[0]
        except Exception:
            fee_ok_map[fund_code] = False

    enabled_funds = [code for code in candidate_funds if fee_ok_map.get(code)]
    if not enabled_funds:
        raise RuntimeError("费率过滤后没有可回测基金")

    seed_positions: Dict[str, Position] = {}
    effective_seed_date: Optional[str] = None
    if seed_snapshot_date:
        effective_seed_date, seed_positions = _load_seed_positions(
            db,
            snapshot_date=seed_snapshot_date,
            sub_account_name=seed_sub_account_name,
        )
        if effective_seed_date > end_date:
            raise RuntimeError(f"快照日期 {effective_seed_date} 晚于回测结束日 {end_date}")

    all_funds_to_load = sorted(set(enabled_funds) | set(seed_positions.keys()))

    fund_meta_map: Dict[str, Dict] = {}
    nav_map_by_fund: Dict[str, Dict[str, float]] = {}
    nav_desc_by_fund: Dict[str, List[Tuple[str, float]]] = {}
    for fund_code in all_funds_to_load:
        fund_info = get_all_fund_info(DEFAULT_USER, fund_code)
        fund_meta_map[fund_code] = {
            "fund_name": getattr(fund_info, "fund_name", fund_code),
            "fund_type": getattr(fund_info, "fund_type", None),
            "volatility": float(getattr(fund_info, "volatility", 0) or 0),
            "max_purchase": float(getattr(fund_info, "max_purchase", 0) or 0),
        }
        nav_series = _get_fund_nav_history(fund_code)
        nav_desc_by_fund[fund_code] = nav_series
        nav_map_by_fund[fund_code] = {dt: value for dt, value in nav_series}

    daily_candidates_cache: Dict[str, List[Dict]] = {}
    for trade_date in trade_dates:
        rows = _get_daily_qualified_indices(db, trade_date)
        daily_candidates_cache[trade_date] = [
            row for row in rows if str(row["track_fund_code"]).strip() in enabled_funds
        ]

    positions: Dict[str, Position] = {}
    last_buy_day: Dict[str, str] = {}
    daily_assets: List[Tuple[str, float]] = []
    daily_selected_counts: List[Tuple[str, int]] = []
    total_buy_amount = 0.0
    realized_cash = 0.0
    buy_signals = 0
    sell_signals = 0
    first_nonzero_day: Optional[str] = None
    if seed_positions:
        positions = seed_positions
        total_buy_amount += sum(position.total_cost() for position in positions.values())

    for idx, trade_date in enumerate(trade_dates):
        if effective_seed_date and trade_date < effective_seed_date:
            continue
        prev_trade_date = trade_dates[idx - 1] if idx > 0 else None
        existing_funds = set(positions.keys())
        selected_indices = _dedup_similar_indices(
            daily_candidates_cache[trade_date],
            all_index_names,
            existing_funds=existing_funds,
        )
        daily_selected_counts.append((trade_date, len(selected_indices)))

        # 1. 未持有且当日被选入的基金，立即初始化建仓
        for row in selected_indices:
            fund_code = str(row["track_fund_code"]).strip()
            if fund_code in positions:
                continue
            if last_buy_day.get(fund_code) in {trade_date, prev_trade_date}:
                continue
            nav = _lookup_nav(nav_map_by_fund[fund_code], trade_date)
            if not nav:
                continue
            if limit is not None and init_amount > limit:
                continue

            shares = init_amount / nav
            positions[fund_code] = Position([Lot(shares=shares, amount=init_amount, buy_date=trade_date)])
            last_buy_day[fund_code] = trade_date
            total_buy_amount += init_amount
            buy_signals += 1

        # 2. 止盈：只卖 0 费率份额
        for fund_code in list(positions.keys()):
            position = positions.get(fund_code)
            if not position or position.is_empty():
                positions.pop(fund_code, None)
                continue
            if last_buy_day.get(fund_code) in {trade_date, prev_trade_date}:
                continue

            nav = _lookup_nav(nav_map_by_fund[fund_code], trade_date)
            if not nav:
                continue

            asset_value = position.total_shares() * nav
            total_cost = position.total_cost()
            if total_cost <= 0:
                continue

            profit_rate = (asset_value / total_cost - 1) * 100
            stop_rate = _get_stop_rate(fund_meta_map[fund_code])
            if profit_rate <= stop_rate and profit_rate <= 10.0:
                continue

            sellable_lots = [lot for lot in position.lots if _eligible_zero_fee(lot, trade_date)]
            if not sellable_lots:
                continue

            sell_shares = sum(lot.shares for lot in sellable_lots)
            realized_cash += sell_shares * nav
            position.lots = [lot for lot in position.lots if not _eligible_zero_fee(lot, trade_date)]
            if position.is_empty():
                positions.pop(fund_code, None)
            sell_signals += 1

        # 3. 加仓：所有现有持仓都参与，不限于今日选中的基金
        for fund_code in list(positions.keys()):
            position = positions.get(fund_code)
            if not position or position.is_empty():
                positions.pop(fund_code, None)
                continue
            if last_buy_day.get(fund_code) in {trade_date, prev_trade_date}:
                continue

            nav = _lookup_nav(nav_map_by_fund[fund_code], trade_date)
            if not nav:
                continue

            asset_value = position.total_shares() * nav
            total_cost = position.total_cost()
            profit_rate = (asset_value / total_cost - 1) * 100 if total_cost > 0 else 0.0

            should_increase = False
            if asset_value < amount * 0.95:
                should_increase = True
            elif profit_rate < -1.0:
                should_increase = True
            if not should_increase:
                continue
            if limit is not None and asset_value >= limit:
                continue

            buy_amount: Optional[float] = None
            if profit_rate < -5.0:
                max_purchase = float(fund_meta_map[fund_code].get("max_purchase", 0) or 0)
                if not (0 < max_purchase < 2000):
                    week_return, month_return, current_nav, nav_5day_avg = _calc_week_month_and_ma5(
                        nav_desc_by_fund[fund_code],
                        trade_date,
                    )
                    is_deep_drawdown = profit_rate < -10.0
                    has_reversal_signal = (
                        week_return > 0
                        and month_return > 0
                        and asset_value > 0
                        and current_nav is not None
                        and nav_5day_avg is not None
                        and current_nav > nav_5day_avg
                    )
                    if is_deep_drawdown and has_reversal_signal:
                        if profit_rate >= -20.0:
                            buy_amount = asset_value * 0.5
                        else:
                            continue
                    else:
                        continue

            if buy_amount is None:
                multiplier = 2.0 if profit_rate < -4.0 else 1.0
                buy_amount = amount * multiplier
            if limit is not None and asset_value + buy_amount > limit:
                continue

            shares = buy_amount / nav
            position.lots.append(Lot(shares=shares, amount=buy_amount, buy_date=trade_date))
            last_buy_day[fund_code] = trade_date
            total_buy_amount += buy_amount
            buy_signals += 1

        day_asset = 0.0
        for fund_code, position in positions.items():
            nav = _lookup_nav(nav_map_by_fund[fund_code], trade_date)
            if not nav:
                continue
            day_asset += position.total_shares() * nav

        if day_asset > 0 and first_nonzero_day is None:
            first_nonzero_day = trade_date
        daily_assets.append((trade_date, day_asset))

    final_asset = daily_assets[-1][1] if daily_assets else 0.0
    total_profit = realized_cash + final_asset - total_buy_amount
    return_rate = (total_profit / total_buy_amount * 100) if total_buy_amount > 0 else 0.0
    max_asset = max((value for _, value in daily_assets), default=0.0)
    avg_daily_asset = mean((value for _, value in daily_assets)) if daily_assets else 0.0
    active_daily_assets = [value for _, value in daily_assets if value > 0]
    avg_active_daily_asset = mean(active_daily_assets) if active_daily_assets else 0.0
    asset_day_sum = sum(value for _, value in daily_assets)
    daily_asset_return = (total_profit / asset_day_sum * 100) if asset_day_sum > 0 else 0.0

    ending_positions = []
    for fund_code, position in positions.items():
        nav = _lookup_nav(nav_map_by_fund[fund_code], end_date)
        market_value = position.total_shares() * nav if nav else 0.0
        ending_positions.append({
            "fund_code": fund_code,
            "fund_name": fund_meta_map[fund_code]["fund_name"],
            "market_value": market_value,
        })
    ending_positions.sort(key=lambda item: item["market_value"], reverse=True)

    return {
        "start_date": start_date,
        "end_date": end_date,
        "amount": amount,
        "init_amount": init_amount,
        "limit": limit,
        "seed_snapshot_date": seed_snapshot_date,
        "effective_seed_date": effective_seed_date,
        "seed_sub_account_name": seed_sub_account_name if seed_snapshot_date else None,
        "trade_days": len(trade_dates),
        "first_nonzero_day": first_nonzero_day,
        "active_days": len(active_daily_assets),
        "buy_signals": buy_signals,
        "sell_signals": sell_signals,
        "total_buy_amount": total_buy_amount,
        "realized_cash": realized_cash,
        "final_asset": final_asset,
        "total_profit": total_profit,
        "return_rate": return_rate,
        "max_asset": max_asset,
        "avg_daily_asset": avg_daily_asset,
        "avg_active_daily_asset": avg_active_daily_asset,
        "daily_asset_return": daily_asset_return,
        "ending_positions": ending_positions,
        "top_asset_days": sorted(daily_assets, key=lambda item: item[1], reverse=True)[:5],
        "daily_selected_counts_tail": daily_selected_counts[-5:],
    }


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()

    logging.getLogger("urllib3").setLevel(logging.ERROR)
    logging.getLogger("src.service.大数据.增加大数定律基金到自选组合").setLevel(logging.WARNING)
    logging.getLogger("src.service.银行卡账户").setLevel(logging.WARNING)
    logging.getLogger("FundDetailPage").setLevel(logging.WARNING)

    db = DatabaseConnection()
    end_date = args.end_date or _get_default_end_date(db)
    start_date = args.start_date or (date.fromisoformat(end_date) - timedelta(days=365)).isoformat()

    result = run_backtest(
        start_date=start_date,
        end_date=end_date,
        amount=float(args.amount),
        init_amount=float(args.init_amount),
        limit=float(args.limit) if args.limit is not None else None,
        seed_snapshot_date=args.seed_snapshot_date,
        seed_sub_account_name=args.seed_sub_account_name,
    )

    print("\n" + "=" * 72)
    print("  大数定律 + 黄金多利组合策略回测")
    print("=" * 72)
    print(f"回测区间: {result['start_date']} ~ {result['end_date']}")
    print(
        f"参数: init_amount={_fmt_money(result['init_amount'])} / "
        f"amount={_fmt_money(result['amount'])} / "
        f"limit={_fmt_money(result['limit']) if result['limit'] is not None else '无限制'}"
    )
    if result["seed_snapshot_date"]:
        print(
            f"期初快照: {result['seed_sub_account_name']} / "
            f"请求={result['seed_snapshot_date']} / "
            f"生效={result['effective_seed_date']}"
        )
    print(f"交易日数: {result['trade_days']}，有持仓交易日: {result['active_days']}")
    if result["first_nonzero_day"]:
        print(f"首次占资日: {result['first_nonzero_day']}")

    print("\n【核心指标】")
    print(f"收益金额:         {_fmt_money(result['total_profit'])} 元")
    print(f"收益率:           {_fmt_pct(result['return_rate'])}")
    print(f"最大组合占用资金: {_fmt_money(result['max_asset'])} 元")
    print(f"平均日占用资金:   {_fmt_money(result['avg_daily_asset'])} 元")
    print(f"活跃日均占资:     {_fmt_money(result['avg_active_daily_asset'])} 元")
    print(f"日均资产收益率:   {_fmt_pct(result['daily_asset_return'])}")

    print("\n【交易统计】")
    print(f"买入次数: {result['buy_signals']}")
    print(f"卖出次数: {result['sell_signals']}")
    print(f"累计买入: {_fmt_money(result['total_buy_amount'])} 元")
    print(f"累计回款: {_fmt_money(result['realized_cash'])} 元")
    print(f"期末资产: {_fmt_money(result['final_asset'])} 元")

    print("\n【占资峰值 Top 5】")
    for dt, value in result["top_asset_days"]:
        print(f"{dt}: {_fmt_money(value)} 元")

    print("\n【期末持仓 Top 10】")
    for item in result["ending_positions"][:10]:
        print(f"{item['fund_code']} {item['fund_name']}: {_fmt_money(item['market_value'])} 元")

    print("\n【最近5个交易日入选基金数】")
    for dt, cnt in result["daily_selected_counts_tail"]:
        print(f"{dt}: {cnt}")


if __name__ == "__main__":
    main()
