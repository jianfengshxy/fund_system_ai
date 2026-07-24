#!/usr/bin/env python3
"""
基金 021540 - 最近一年交易回测

计算指标：
  - 最大持仓金额 (Max Holding Amount)
  - 平均持有金额 (Average Holding Amount)
  - 收益率 (Rate of Return)
  - 收益金额 (Profit)
  - 内部收益率 (IRR)

方法说明：
  1. 通过 get_one_fund_tran_infos API 获取最近一年所有交易记录
  2. 通过 FundMNHisNetList API 获取每日净值
  3. 逐笔解析交易，将买入记为现金流出(-)，卖出记为现金流入(+)
  4. 跟踪份额变化，以最新净值计算当前持仓市值
  5. 基于完整现金流序列计算 IRR
"""
import sys, os, logging, re
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple

root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from src.common.constant import DEFAULT_USER, DEFAULT_GTOKEN, DEVICE_ID, IOS_CLIENT_INFO, IOS_OS_VERSION, IOS_USER_AGENT, MOBILE_KEY, PHONE_TYPE, PLATFORM, SERVER_VERSION
from src.common.requests_session import session
from src.API.交易管理.trade import get_one_fund_tran_infos

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)8s] %(message)s')
logger = logging.getLogger(__name__)

FUND_CODE = "021540"


# ═══════════════════════════════════════════════════════════════
# 工具函数
# ═══════════════════════════════════════════════════════════════

def parse_amount(text: str) -> float:
    """从格式如 '1,999.95元' 或 '942.77份' 的字符串中解析数字"""
    if not text:
        return 0.0
    text = text.strip()
    text = text.replace(',', '')
    # 去掉中文单位
    for suffix in ['元', '份', ' ']:
        text = text.replace(suffix, '')
    try:
        return float(text)
    except (ValueError, TypeError):
        return 0.0


def get_trade_date(trade) -> str:
    """获取交易日期 (YYYY-MM-DD)"""
    raw = getattr(trade, 'strike_start_date', None) or getattr(trade, 'apply_work_day', None) or ''
    return raw[:10] if raw else ''


def get_fund_nav_history(fund_code: str, page_size: int = 500) -> List[Tuple[str, float]]:
    """获取基金历史净值列表，按日期降序 (最新在前)"""
    url = 'https://fundmobapi.eastmoney.com/FundMNewApi/FundMNHisNetList'
    headers = {
        'Connection': 'keep-alive',
        'Host': 'fundmobapi.eastmoney.com',
        'Accept': '*/*',
        'GTOKEN': DEFAULT_GTOKEN,
        'clientInfo': IOS_CLIENT_INFO,
        'Accept-Language': 'zh-Hans-CN;q=1',
        'User-Agent': IOS_USER_AGENT,
        'Referer': 'https://mpservice.com/516939c37bdb4ba2b1138c50cf69a2e1/release/pages/fundHistoryWorth/index',
        'Content-Type': 'application/x-www-form-urlencoded',
    }
    data = {
        'FCODE': fund_code,
        'IsShareNet': 'true',
        'MobileKey': MOBILE_KEY,
        'OSVersion': IOS_OS_VERSION,
        'appType': 'ttjj',
        'appVersion': SERVER_VERSION,
        'cToken': DEFAULT_USER.c_token,
        'deviceid': DEVICE_ID,
        'pageIndex': '0',
        'pageSize': str(page_size),
        'passportid': DEFAULT_USER.passport_id,
        'plat': PLATFORM,
        'product': 'EFund',
        'serverVersion': SERVER_VERSION,
        'uToken': DEFAULT_USER.u_token,
        'userId': DEFAULT_USER.customer_no,
        'version': SERVER_VERSION,
    }
    resp = session.post(url, headers=headers, data=data, verify=False, timeout=30)
    resp.raise_for_status()
    j = resp.json()
    datas = j.get('Datas', [])
    result = []
    for d in datas:
        date_str = d.get('FSRQ', '')
        nav = float(d.get('DWJZ', 0))
        if date_str and nav > 0:
            result.append((date_str, nav))
    return result  # API 已是降序


def lookup_nav(nav_map: Dict[str, float], date_str: str) -> Optional[float]:
    """
    在 NAV 映射中查找指定日期的净值。
    若当天无数据（非交易日），向前回溯最多 5 天。
    """
    if date_str in nav_map:
        return nav_map[date_str]
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError:
        return None
    for _ in range(5):
        dt -= timedelta(days=1)
        key = dt.strftime("%Y-%m-%d")
        if key in nav_map:
            return nav_map[key]
    return None


def compute_irr(cash_flows: List[Tuple[str, float]], guess: float = 0.05) -> Optional[float]:
    """
    基于现金流序列计算内部收益率 (IRR)。
    cash_flows: [(date_str, amount), ...] 买入为负，卖出/期末市值为正。
    使用 Newton-Raphson 迭代求解 NPV=0 的折现率。
    """
    if len(cash_flows) < 2:
        return None

    try:
        first_date = datetime.strptime(cash_flows[0][0], "%Y-%m-%d")
    except ValueError:
        return None

    amounts = []
    years = []
    for date_str, amt in cash_flows:
        try:
            dt = datetime.strptime(date_str[:10], "%Y-%m-%d")
        except (ValueError, IndexError):
            dt = first_date
        year_frac = (dt - first_date).days / 365.0
        amounts.append(amt)
        years.append(year_frac)

    rate = guess
    for _ in range(1000):
        npv = 0.0
        dnpv = 0.0
        for amt, t in zip(amounts, years):
            factor = (1 + rate) ** t
            npv += amt / factor
            dnpv -= t * amt / ((1 + rate) ** (t + 1))
        if abs(npv) < 1e-7:
            break
        if dnpv == 0:
            break
        rate -= npv / dnpv
        if abs(npv / dnpv) < 1e-12:
            break
    else:
        return None

    return rate


# ═══════════════════════════════════════════════════════════════
# 主回测逻辑
# ═══════════════════════════════════════════════════════════════

def backtest():
    print(f"\n{'='*70}")
    print(f"  基金 {FUND_CODE} 最近一年交易回测")
    print(f"{'='*70}\n")

    # ── Step 1: 获取交易记录 ──
    logger.info("获取交易记录...")
    trades = get_one_fund_tran_infos(DEFAULT_USER, fund_code=FUND_CODE, date_type="3")
    logger.info(f"共 {len(trades)} 条交易记录")
    if not trades:
        print("❌ 未获取到交易记录")
        return

    # ── Step 2: 获取净值数据 ──
    logger.info("获取净值历史...")
    nav_list = get_fund_nav_history(FUND_CODE)
    nav_map = {date: nav for date, nav in nav_list}
    logger.info(f"共 {len(nav_list)} 条净值数据")
    if not nav_map:
        print("❌ 未获取到净值数据")
        return

    latest_nav = nav_list[0][1] if nav_list else 0.0
    latest_nav_date = nav_list[0][0] if nav_list else "N/A"
    first_nav = nav_list[-1][1] if nav_list else 0.0
    first_nav_date = nav_list[-1][0] if nav_list else "N/A"

    # ── Step 3: 解析交易 ──
    buy_trades = []   # [(date, type, amount_money)]
    sell_trades = []  # [(date, type, shares, money_or_None)]
    other_trades = []

    for t in trades:
        bt = t.business_type or ''
        date_str = get_trade_date(t)
        if not date_str:
            continue

        if bt in ('买入', '定投'):
            if str(t.status) != '3':
                continue
            raw = getattr(t, 'raw', {}) or {}
            confirm_raw = raw.get('ConfirmCount', '') or ''
            apply_raw = raw.get('ApplyCount', '') or ''
            colour = raw.get('Colour', '')

            if colour == '3' and confirm_raw:
                amount = parse_amount(confirm_raw)
            elif colour == '4' and apply_raw:
                amount = parse_amount(apply_raw)
            elif confirm_raw:
                amount = parse_amount(confirm_raw)
            else:
                amount = parse_amount(apply_raw)

            if amount > 0:
                buy_trades.append((date_str, bt, amount))
            else:
                other_trades.append((date_str, bt, amount, 'buy_parse_fail'))

        elif '卖基金' in bt or '赎回' in bt or '卖出' in bt:
            if str(t.status) != '3':
                continue
            raw = getattr(t, 'raw', {}) or {}
            app_state = (raw.get('APPStateText') or '').strip()
            if '撤单' in app_state:
                other_trades.append((date_str, bt, 0, 'cancelled'))
                continue
            colour = raw.get('Colour', '')
            confirm_raw = raw.get('ConfirmCount', '') or ''
            apply_raw = raw.get('ApplyCount', '') or ''
            if colour == '3' and confirm_raw and '元' in confirm_raw:
                # 成功卖出: ConfirmCount 是金额 (如 "15,428.36元")
                money_received = parse_amount(confirm_raw)
                nav = lookup_nav(nav_map, date_str)
                if nav and nav > 0:
                    shares = money_received / nav
                    sell_trades.append((date_str, bt, shares, money_received))
                else:
                    other_trades.append((date_str, bt, 0, 'sell_no_nav'))
            elif colour == '4' and apply_raw and '份' in apply_raw:
                shares = parse_amount(apply_raw)
                if shares > 0:
                    sell_trades.append((date_str, bt, shares, None))
                else:
                    other_trades.append((date_str, bt, 0, 'sell_parse_fail'))
            else:
                other_trades.append((date_str, bt, 0, f'sell_unknown(colour={colour})'))

        else:
            other_trades.append((date_str, bt, 0, 'unknown_type'))

    logger.info(f"买入交易: {len(buy_trades)} 笔")
    logger.info(f"卖出交易: {len(sell_trades)} 笔")
    if other_trades:
        logger.info(f"其他交易: {len(other_trades)} 笔 (将跳过)")

    if not buy_trades:
        print("❌ 未解析到有效的买入交易")
        return

    # ── Step 4: 逐日持仓追踪 ──
    all_events = []  # (date, type, money_change, shares_change)
    total_buy_money = 0.0
    total_shares_bought = 0.0

    for dt, bt, money in buy_trades:
        nav = lookup_nav(nav_map, dt)
        if nav is None:
            logger.warning(f"  买入 {dt}: 无法获取净值, 跳过此笔")
            continue
        shares = money / nav
        total_buy_money += money
        total_shares_bought += shares
        all_events.append((dt, '买入', -money, shares))

    for dt, bt, shares, money_received in sell_trades:
        if money_received is not None:
            # 已直接提供了金额
            pass
        else:
            nav = lookup_nav(nav_map, dt)
            if nav is None:
                logger.warning(f"  卖出 {dt}: 无法获取净值, 跳过此笔")
                continue
            money_received = shares * nav
        all_events.append((dt, '卖出', money_received, -shares))

    all_events.sort(key=lambda x: x[0])

    # 逐日计算持仓
    current_shares = 0.0
    position_values = []
    total_invested = 0.0
    total_redeemed = 0.0

    for dt, evt_type, money_change, shares_change in all_events:
        if evt_type == '买入':
            total_invested += abs(money_change)
            current_shares += shares_change
        elif evt_type == '卖出':
            total_redeemed += money_change
            current_shares += shares_change

        if current_shares > 1e-6:
            nav = lookup_nav(nav_map, dt)
            if nav:
                position_values.append((dt, current_shares * nav))

    # ── Step 5: 计算指标 ──
    final_shares = max(current_shares, 0.0)
    current_value = final_shares * latest_nav
    profit = current_value + total_redeemed - total_invested

    if position_values:
        avg_holding = sum(v for _, v in position_values) / len(position_values)
        max_holding = max(v for _, v in position_values)
    else:
        avg_holding = 0.0
        max_holding = 0.0

    return_rate_simple = (profit / total_invested * 100) if total_invested > 0 else 0.0
    return_rate_weighted = (profit / avg_holding * 100) if avg_holding > 0 else 0.0

    # ── Step 6: IRR 计算 ──
    irr_cash_flows = []
    for dt, evt_type, money_change, shares_change in all_events:
        irr_cash_flows.append((dt, money_change))
    if final_shares > 0 and latest_nav > 0:
        irr_cash_flows.append((latest_nav_date, current_value))
    irr_cash_flows.sort(key=lambda x: x[0])

    irr_value = compute_irr(irr_cash_flows)

    # ── 输出结果 ──
    print(f"{'─'*70}")
    print(f"  📊 基金信息")
    print(f"  基金代码: {FUND_CODE}")
    print(f"  净值区间: {first_nav_date} ~ {latest_nav_date}")
    print(f"  区间净值: {first_nav:.4f} ~ {latest_nav:.4f}")
    print(f"  区间涨幅: {((latest_nav - first_nav) / first_nav * 100):.2f}%")

    print(f"\n{'─'*70}")
    print(f"  📋 交易汇总")
    print(f"  买入交易: {len(buy_trades)} 笔 (定投+手动)")
    print(f"  卖出交易: {len(sell_trades)} 笔")
    print(f"  总投入金额: {total_invested:>12,.2f} 元")
    print(f"  累计回收: {total_redeemed:>12,.2f} 元")
    print(f"  剩余份额: {final_shares:>12,.4f} 份")

    print(f"\n{'─'*70}")
    print(f"  💰 持仓统计")
    print(f"  当前净值: {latest_nav:.4f} 元 (日期: {latest_nav_date})")
    print(f"  当前持仓市值: {current_value:>12,.2f} 元")
    if position_values:
        max_pos_date = max(position_values, key=lambda x: x[1])[0]
        print(f"  最大持仓金额: {max_holding:>12,.2f} 元 (日期: {max_pos_date})")
    else:
        print("  最大持仓金额: 暂无数据")
    print(f"  平均持有金额: {avg_holding:>12,.2f} 元 (基于 {len(position_values)} 个交易日)")

    print(f"\n{'─'*70}")
    print(f"  📈 收益分析")
    print(f"  收益金额: {profit:>+12,.2f} 元")
    print(f"  简单收益率: {return_rate_simple:>+8.2f}%")
    print(f"  资金加权收益率: {return_rate_weighted:>+8.2f}%")
    if irr_value is not None:
        print(f"  内部收益率 (IRR): {irr_value*100:>+8.2f}% (年化)")
    else:
        print(f"  内部收益率 (IRR): 计算未收敛")

    print(f"\n{'─'*70}")
    print(f"  📋 交易明细")
    print(f"\n  {'日期':<14} {'类型':<16} {'金额':>12} {'份额变化':>12} {'累计份额':>12}")
    print(f"  {'─'*66}")
    running_shares = 0.0
    for dt, evt_type, money_change, shares_change in all_events:
        running_shares += shares_change
        label = '卖出' if evt_type == '卖出' else '买入'
        print(f"  {dt:<14} {label:<16} {money_change:>12,.2f} {shares_change:>+12,.4f} {running_shares:>12,.4f}")

    if final_shares > 0 and latest_nav > 0:
        print(f"  {latest_nav_date:<14} {'期末市值':<16} {current_value:>12,.2f}")

    if other_trades:
        print(f"\n  ⚠️  未处理交易 ({len(other_trades)} 笔):")
        for dt, bt, amt, reason in other_trades[:5]:
            print(f"    {dt} {bt} reason={reason}")

    print(f"\n{'='*70}\n")


if __name__ == "__main__":
    backtest()
