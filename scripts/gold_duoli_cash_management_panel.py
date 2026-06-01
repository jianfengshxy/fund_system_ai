import argparse
import math
import sys
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Iterable, List, Optional

project_root = Path(__file__).resolve().parents[1]
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from src.API.交易管理.trade import get_trades_list
from src.common.constant import DEFAULT_USER
from src.db.database_connection import DatabaseConnection


DEFAULT_SUB_ACCOUNT_NAME = "黄金多利"
DEFAULT_SUB_ACCOUNT_NO = "26559062"
DEFAULT_FUND_CODE = "021740"
DEFAULT_TOTAL_CAPITAL = 100000.0


@dataclass(frozen=True)
class TradeCashflow:
    trade_date: str
    direction: str
    amount: float
    business_code: str
    business_type: str
    app_state_text: str
    remark: str


@dataclass(frozen=True)
class FundAssetDay:
    trade_date: str
    asset_value: float
    available_vol: float
    on_way_count: int
    total_profit: float
    constant_profit: float


@dataclass(frozen=True)
class CycleSummary:
    cycle_no: int
    start_date: str
    end_date: str
    close_zero_date: str
    hold_days: int
    buy_total: float
    sell_total: float
    profit_amount: float
    xirr_percent: Optional[float]
    max_net_invested: float


def _safe_float(value, default: float = 0.0) -> float:
    if value is None:
        return default
    if isinstance(value, (int, float)):
        return float(value)
    raw = str(value).strip()
    if not raw or raw == "--":
        return default
    raw = raw.replace(",", "").replace("元", "").replace("份", "").replace("%", "").strip()
    if not raw or raw == "--":
        return default
    try:
        return float(raw)
    except (TypeError, ValueError):
        return default


def _extract_money(value_candidates: Iterable[object]) -> Optional[float]:
    for value in value_candidates:
        if value is None:
            continue
        text = str(value)
        if "元" in text:
            amount = _safe_float(text, default=math.nan)
            if not math.isnan(amount):
                return amount
    for value in value_candidates:
        if value is None:
            continue
        amount = _safe_float(value, default=math.nan)
        if not math.isnan(amount):
            return amount
    return None


def _is_cancelled_trade(trade) -> bool:
    combined = " ".join(
        [
            str(getattr(trade, "app_state_text", "") or ""),
            str(getattr(trade, "remark", "") or ""),
            str(getattr(trade, "busin_remark", "") or ""),
        ]
    )
    return "撤单" in combined


def _classify_trade_direction(trade) -> Optional[str]:
    business_code = str(getattr(trade, "business_code", "") or "")
    business_type = str(getattr(trade, "business_type", "") or "")
    if business_code == "22":
        return "buy"
    if business_code == "8151":
        return "sell"
    if "赎回" in business_type or "卖出" in business_type:
        return "sell"
    if "买入" in business_type or "转入" in business_type or "申购" in business_type:
        return "buy"
    return None


def _extract_trade_date(trade) -> Optional[str]:
    for value in (getattr(trade, "strike_start_date", None), getattr(trade, "apply_work_day", None)):
        if value:
            return str(value)[:10]
    return None


def _build_trade_cashflows(sub_account_no: str, fund_code: str) -> List[TradeCashflow]:
    trades = get_trades_list(DEFAULT_USER, sub_account_no=sub_account_no, fund_code=fund_code, date_type="")
    cashflows: List[TradeCashflow] = []
    for trade in trades:
        trade_date = _extract_trade_date(trade)
        if not trade_date or _is_cancelled_trade(trade):
            continue

        direction = _classify_trade_direction(trade)
        if direction is None:
            continue

        amount = _extract_money(
            [
                getattr(trade, "confirm_count", None),
                getattr(trade, "amount", None),
                getattr(trade, "apply_amount", None),
                getattr(trade, "apply_count", None),
            ]
        )
        if amount is None:
            continue

        # 赎回记录里偶尔会有非金额字符串，过滤掉这类“成功但无法代表到账金额”的记录。
        if direction == "sell":
            raw_text = " ".join(
                [
                    str(getattr(trade, "confirm_count", "") or ""),
                    str(getattr(trade, "amount", "") or ""),
                    str(getattr(trade, "apply_count", "") or ""),
                ]
            )
            if "元" not in raw_text and str(getattr(trade, "status", "") or "") == "3":
                continue

        cashflows.append(
            TradeCashflow(
                trade_date=trade_date,
                direction=direction,
                amount=round(amount, 2),
                business_code=str(getattr(trade, "business_code", "") or ""),
                business_type=str(getattr(trade, "business_type", "") or ""),
                app_state_text=str(getattr(trade, "app_state_text", "") or ""),
                remark=str(getattr(trade, "remark", "") or ""),
            )
        )
    return sorted(cashflows, key=lambda item: (item.trade_date, item.direction, item.amount))


def _load_fund_asset_days(customer_no: str, sub_account_no: str, fund_code: str) -> List[FundAssetDay]:
    db = DatabaseConnection()
    rows = db.execute_query(
        """
        SELECT date, asset_value, available_vol, on_way_count, total_profit, constant_profit
        FROM user_sub_account_fund_asset_daily
        WHERE customer_no=%s AND sub_account_no=%s AND fund_code=%s
        ORDER BY date ASC
        """,
        (customer_no, sub_account_no, fund_code),
    )
    return [
        FundAssetDay(
            trade_date=row["date"].isoformat(),
            asset_value=_safe_float(row.get("asset_value")),
            available_vol=_safe_float(row.get("available_vol")),
            on_way_count=int(row.get("on_way_count") or 0),
            total_profit=_safe_float(row.get("total_profit")),
            constant_profit=_safe_float(row.get("constant_profit")),
        )
        for row in rows
    ]


def _load_sub_account_asset_rows(customer_no: str, sub_account_no: str, start_date: str, end_date: str) -> List[dict]:
    db = DatabaseConnection()
    rows = db.execute_query(
        """
        SELECT date, asset_value, hold_profit, total_profit
        FROM user_sub_account_asset_daily
        WHERE customer_no=%s AND sub_account_no=%s AND date BETWEEN %s AND %s
        ORDER BY date ASC
        """,
        (customer_no, sub_account_no, start_date, end_date),
    )
    return [
        {
            "date": row["date"].isoformat(),
            "asset_value": _safe_float(row.get("asset_value")),
            "hold_profit": _safe_float(row.get("hold_profit")),
            "total_profit": _safe_float(row.get("total_profit")),
        }
        for row in rows
    ]


def _xirr(cashflows: List[tuple[date, float]]) -> Optional[float]:
    if not cashflows:
        return None
    values = [amount for _, amount in cashflows]
    if not any(value < 0 for value in values) or not any(value > 0 for value in values):
        return None

    ordered = sorted(cashflows, key=lambda item: item[0])
    base_day = ordered[0][0]

    def xnpv(rate: float) -> float:
        total = 0.0
        for flow_day, amount in ordered:
            years = (flow_day - base_day).days / 365.0
            total += amount / ((1.0 + rate) ** years)
        return total

    low = -0.9999
    high = 1.0
    f_low = xnpv(low)
    f_high = xnpv(high)
    expand_steps = 0
    while f_low * f_high > 0 and expand_steps < 80:
        high *= 2.0
        f_high = xnpv(high)
        expand_steps += 1
    if f_low * f_high > 0:
        return None

    for _ in range(200):
        mid = (low + high) / 2.0
        f_mid = xnpv(mid)
        if abs(f_mid) < 1e-12:
            return mid
        if f_low * f_mid <= 0:
            high = mid
            f_high = f_mid
        else:
            low = mid
            f_low = f_mid
    return (low + high) / 2.0


def _is_reset_asset_day(asset_day: FundAssetDay) -> bool:
    return asset_day.available_vol <= 0.01 and abs(asset_day.constant_profit) <= 0.01


def _find_initial_cycle_start_date(
    asset_days: List[FundAssetDay], trade_cashflows: List[TradeCashflow]
) -> Optional[str]:
    """
    识别当前资产覆盖窗口里的首个“可靠周期起点”。

    目标是保证脚本具备长期通用性：
    - 如果资产日表从某个历史中段才开始覆盖，优先用“覆盖开始前最后一次卖出”后的首笔买入作为起点。
    - 如果资产日表本身已经出现过一次明确的“收益与可用份额重置”，则从该重置日之后的首笔买入开始。
    - 如果以上线索都没有，则退化到资产覆盖窗口内的第一笔买入。
    """
    if not asset_days or not trade_cashflows:
        return None

    first_asset_day = asset_days[0].trade_date
    prior_sell_dates = [
        flow.trade_date
        for flow in trade_cashflows
        if flow.direction == "sell" and flow.trade_date < first_asset_day
    ]
    if prior_sell_dates:
        last_sell_before_coverage = max(prior_sell_dates)
        later_buy_dates = [
            flow.trade_date
            for flow in trade_cashflows
            if flow.direction == "buy" and flow.trade_date > last_sell_before_coverage
        ]
        if later_buy_dates:
            return min(later_buy_dates)

    first_reset_day = next((asset_day.trade_date for asset_day in asset_days if _is_reset_asset_day(asset_day)), None)
    if first_reset_day is not None:
        later_buy_dates = [
            flow.trade_date
            for flow in trade_cashflows
            if flow.direction == "buy" and flow.trade_date >= first_reset_day
        ]
        if later_buy_dates:
            return min(later_buy_dates)

    later_buy_dates = [
        flow.trade_date
        for flow in trade_cashflows
        if flow.direction == "buy" and flow.trade_date >= first_asset_day
    ]
    if later_buy_dates:
        return min(later_buy_dates)
    return None


def _build_closed_cycles(asset_days: List[FundAssetDay], trade_cashflows: List[TradeCashflow]) -> List[CycleSummary]:
    initial_cycle_start = _find_initial_cycle_start_date(asset_days, trade_cashflows)
    if initial_cycle_start is None:
        return []

    filtered_flows = [flow for flow in trade_cashflows if flow.trade_date >= initial_cycle_start]
    if not filtered_flows:
        return []

    next_asset_day_by_date = {}
    for index, asset_day in enumerate(asset_days[:-1]):
        next_asset_day_by_date[asset_day.trade_date] = asset_days[index + 1]

    grouped_dates: List[tuple[str, List[TradeCashflow]]] = []
    current_date = None
    bucket: List[TradeCashflow] = []
    for flow in filtered_flows:
        if current_date is None or flow.trade_date != current_date:
            if bucket:
                grouped_dates.append((current_date, bucket))
            current_date = flow.trade_date
            bucket = [flow]
        else:
            bucket.append(flow)
    if bucket:
        grouped_dates.append((current_date, bucket))

    cycles: List[CycleSummary] = []
    current_start: Optional[str] = None
    current_flows: List[TradeCashflow] = []

    for trade_date, day_flows in grouped_dates:
        has_buy = any(flow.direction == "buy" for flow in day_flows)
        has_sell = any(flow.direction == "sell" for flow in day_flows)

        if current_start is None:
            if not has_buy:
                continue
            current_start = trade_date

        current_flows.extend(day_flows)

        next_asset_day = next_asset_day_by_date.get(trade_date)
        if not has_sell or next_asset_day is None:
            continue

        is_reset_next_day = _is_reset_asset_day(next_asset_day)
        if not is_reset_next_day:
            continue

        buy_total = round(sum(flow.amount for flow in current_flows if flow.direction == "buy"), 2)
        sell_total = round(sum(flow.amount for flow in current_flows if flow.direction == "sell"), 2)
        profit_amount = round(sell_total - buy_total, 2)

        net_invested = 0.0
        max_net_invested = 0.0
        xirr_flows: List[tuple[date, float]] = []
        for flow in current_flows:
            signed_amount = -flow.amount if flow.direction == "buy" else flow.amount
            xirr_flows.append((datetime.strptime(flow.trade_date, "%Y-%m-%d").date(), signed_amount))
            net_invested += -signed_amount
            max_net_invested = max(max_net_invested, net_invested)

        start_dt = datetime.strptime(current_start, "%Y-%m-%d").date()
        end_dt = datetime.strptime(trade_date, "%Y-%m-%d").date()
        xirr_value = _xirr(xirr_flows)

        cycles.append(
            CycleSummary(
                cycle_no=len(cycles) + 1,
                start_date=current_start,
                end_date=trade_date,
                close_zero_date=next_asset_day.trade_date,
                hold_days=(end_dt - start_dt).days + 1,
                buy_total=buy_total,
                sell_total=sell_total,
                profit_amount=profit_amount,
                xirr_percent=None if xirr_value is None else round(xirr_value * 100.0, 4),
                max_net_invested=round(max_net_invested, 2),
            )
        )
        current_start = None
        current_flows = []

    return cycles


def _format_money(value: float) -> str:
    return f"{value:,.2f}"


def _format_percent(value: Optional[float]) -> str:
    if value is None:
        return "N/A"
    return f"{value:.4f}%"


def _print_cycle_table(cycles: List[CycleSummary]) -> None:
    print("已闭环周期：")
    print(
        "周期 | 起点 | 终点 | 清仓日 | 持有天数 | 买入金额 | 卖出金额 | 盈利金额 | XIRR | 最大净投入"
    )
    for cycle in cycles:
        print(
            f"{cycle.cycle_no:>2} | {cycle.start_date} | {cycle.end_date} | {cycle.close_zero_date} | "
            f"{cycle.hold_days:>4} | {_format_money(cycle.buy_total):>10} | {_format_money(cycle.sell_total):>10} | "
            f"{_format_money(cycle.profit_amount):>8} | {_format_percent(cycle.xirr_percent):>10} | "
            f"{_format_money(cycle.max_net_invested):>10}"
        )
    print()


def _print_summary(cycles: List[CycleSummary], asset_rows: List[dict], total_capital: float) -> None:
    total_profit = round(sum(cycle.profit_amount for cycle in cycles), 2)
    profitable_count = sum(1 for cycle in cycles if cycle.profit_amount > 0)

    first_start = cycles[0].start_date
    last_end = cycles[-1].end_date
    natural_days = (datetime.strptime(last_end, "%Y-%m-%d").date() - datetime.strptime(first_start, "%Y-%m-%d").date()).days + 1

    active_asset_rows = [row for row in asset_rows if row["asset_value"] > 0]
    avg_asset_all_days = sum(row["asset_value"] for row in asset_rows) / len(asset_rows) if asset_rows else 0.0
    avg_asset_active_days = sum(row["asset_value"] for row in active_asset_rows) / len(active_asset_rows) if active_asset_rows else 0.0

    abs_return = total_profit / total_capital if total_capital else 0.0
    annualized_simple = abs_return * 365.0 / natural_days if natural_days else 0.0
    annualized_compound = (1.0 + abs_return) ** (365.0 / natural_days) - 1.0 if natural_days else 0.0

    peak_total_profit = None
    peak_total_profit_date = None
    max_profit_drawdown = 0.0
    max_profit_drawdown_range = None
    for row in asset_rows:
        value = row["total_profit"]
        if peak_total_profit is None or value > peak_total_profit:
            peak_total_profit = value
            peak_total_profit_date = row["date"]
        drawdown = peak_total_profit - value
        if drawdown > max_profit_drawdown:
            max_profit_drawdown = drawdown
            max_profit_drawdown_range = (
                peak_total_profit_date,
                row["date"],
                peak_total_profit,
                value,
            )

    print("现金管理绩效面板：")
    print(f"  本金设定: {_format_money(total_capital)}")
    print(f"  闭环周期数: {len(cycles)}")
    print(f"  盈利周期数: {profitable_count}")
    print(f"  胜率: {_format_percent(profitable_count / len(cycles) * 100.0 if cycles else None)}")
    print(f"  闭环总盈利: {_format_money(total_profit)}")
    print(f"  10w口径绝对收益率: {_format_percent(abs_return * 100.0)}")
    print(f"  自然日年化(单利): {_format_percent(annualized_simple * 100.0)}")
    print(f"  自然日年化(复利): {_format_percent(annualized_compound * 100.0)}")
    print(f"  日均资产(含空仓日): {_format_money(avg_asset_all_days)}")
    print(f"  日均资产(仅持仓日): {_format_money(avg_asset_active_days)}")
    print(f"  盈利/日均资产(含空仓日): {_format_percent(total_profit / avg_asset_all_days * 100.0 if avg_asset_all_days else None)}")
    print(f"  盈利/日均资产(仅持仓日): {_format_percent(total_profit / avg_asset_active_days * 100.0 if avg_asset_active_days else None)}")
    print(f"  资金利用率(含空仓日): {_format_percent(avg_asset_all_days / total_capital * 100.0 if total_capital else None)}")
    print(f"  资金利用率(仅持仓日): {_format_percent(avg_asset_active_days / total_capital * 100.0 if total_capital else None)}")
    print(f"  空仓快照占比: {_format_percent((len(asset_rows) - len(active_asset_rows)) / len(asset_rows) * 100.0 if asset_rows else None)}")
    print(f"  平均单轮盈利: {_format_money(total_profit / len(cycles) if cycles else 0.0)}")

    valid_xirrs = [cycle.xirr_percent for cycle in cycles if cycle.xirr_percent is not None]
    print(f"  平均单轮XIRR: {_format_percent(sum(valid_xirrs) / len(valid_xirrs) if valid_xirrs else None)}")
    print(f"  最大累计收益回撤金额: {_format_money(max_profit_drawdown)}")
    if max_profit_drawdown_range is not None:
        peak_date, trough_date, peak_value, trough_value = max_profit_drawdown_range
        print(
            "  最大累计收益回撤区间: "
            f"{peak_date}({_format_money(peak_value)}) -> {trough_date}({_format_money(trough_value)})"
        )
    print()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="黄金多利现金管理绩效面板：统计闭环收益、年化、资金利用率与累计收益回撤。"
    )
    parser.add_argument("--sub-account-name", default=DEFAULT_SUB_ACCOUNT_NAME, help="组合名称，仅用于展示。")
    parser.add_argument("--sub-account-no", default=DEFAULT_SUB_ACCOUNT_NO, help="组合编号。")
    parser.add_argument("--fund-code", default=DEFAULT_FUND_CODE, help="策略主基金代码。")
    parser.add_argument("--capital", type=float, default=DEFAULT_TOTAL_CAPITAL, help="现金管理本金，默认 100000。")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    customer_no = DEFAULT_USER.customer_no

    trade_cashflows = _build_trade_cashflows(args.sub_account_no, args.fund_code)
    fund_asset_days = _load_fund_asset_days(customer_no, args.sub_account_no, args.fund_code)
    cycles = _build_closed_cycles(fund_asset_days, trade_cashflows)
    if not cycles:
        print("未识别到完整闭环周期，请检查 fund_code / sub_account_no / 资产同步数据。")
        return 1

    first_start = cycles[0].start_date
    last_end = cycles[-1].end_date
    asset_rows = _load_sub_account_asset_rows(customer_no, args.sub_account_no, first_start, last_end)

    print(f"组合名称: {args.sub_account_name}")
    print(f"组合编号: {args.sub_account_no}")
    print(f"策略基金: {args.fund_code}")
    print(f"统计区间: {first_start} -> {last_end}")
    print()

    _print_cycle_table(cycles)
    _print_summary(cycles, asset_rows, args.capital)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
