#!/usr/bin/env python3
"""
基金 021540 - 最近一年交易回测（修正版）

使用 src.service.资产管理.get_all_fund_trades 获取全量交易 + 持仓数据。

指标：
  - 投资总金额 / 最大持仓金额 / 平均日持有金额
  - 收益金额 / 简单收益率 / 资金加权收益率 / 内部收益率 (IRR)
"""
import sys, os, logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple

root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from src.common.constant import DEFAULT_USER, DEFAULT_GTOKEN, DEVICE_ID, IOS_CLIENT_INFO, IOS_OS_VERSION, IOS_USER_AGENT, MOBILE_KEY, PHONE_TYPE, PLATFORM, SERVER_VERSION
from src.common.requests_session import session
from src.service.资产管理.get_all_fund_trades import get_all_fund_trades

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)8s] %(message)s')
logger = logging.getLogger(__name__)

FUND_CODE = "021540"


# ═══════════════════════════════════════════════════════════════
# 工具函数
# ═══════════════════════════════════════════════════════════════

def get_fund_nav_history(fund_code: str, page_size: int = 500) -> List[Tuple[str, float]]:
    """获取基金历史净值列表，按日期降序 (最新在前)"""
    url = 'https://fundmobapi.eastmoney.com/FundMNewApi/FundMNHisNetList'
    headers = {
        'Connection': 'keep-alive', 'Host': 'fundmobapi.eastmoney.com', 'Accept': '*/*',
        'GTOKEN': DEFAULT_GTOKEN, 'clientInfo': IOS_CLIENT_INFO,
        'Accept-Language': 'zh-Hans-CN;q=1', 'User-Agent': IOS_USER_AGENT,
        'Referer': 'https://mpservice.com/516939c37bdb4ba2b1138c50cf69a2e1/release/pages/fundHistoryWorth/index',
        'Content-Type': 'application/x-www-form-urlencoded',
    }
    data = {
        'FCODE': fund_code, 'IsShareNet': 'true', 'MobileKey': MOBILE_KEY,
        'OSVersion': IOS_OS_VERSION, 'appType': 'ttjj', 'appVersion': SERVER_VERSION,
        'cToken': DEFAULT_USER.c_token, 'deviceid': DEVICE_ID,
        'pageIndex': '0', 'pageSize': str(page_size),
        'passportid': DEFAULT_USER.passport_id, 'plat': PLATFORM,
        'product': 'EFund', 'serverVersion': SERVER_VERSION,
        'uToken': DEFAULT_USER.u_token, 'userId': DEFAULT_USER.customer_no,
        'version': SERVER_VERSION,
    }
    resp = session.post(url, headers=headers, data=data, verify=False, timeout=30)
    resp.raise_for_status()
    j = resp.json()
    result = []
    for d in j.get('Datas', []):
        date_str = d.get('FSRQ', '')
        nav = float(d.get('DWJZ', 0))
        if date_str and nav > 0:
            result.append((date_str, nav))
    return result


def lookup_nav(nav_map: Dict[str, float], date_str: str) -> Optional[float]:
    """查找净值，无数据时向前回溯最多 5 天"""
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
    """Newton-Raphson 迭代求解 IRR"""
    if len(cash_flows) < 2:
        return None
    try:
        first_date = datetime.strptime(cash_flows[0][0], "%Y-%m-%d")
    except ValueError:
        return None
    amounts, years = [], []
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
        npv, dnpv = 0.0, 0.0
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


def parse_amount(text: str) -> float:
    """解析 '5,000.00元' -> 5000.0"""
    if not text:
        return 0.0
    text = text.strip().replace(',', '')
    for suffix in ['元', '份', ' ']:
        text = text.replace(suffix, '')
    try:
        return float(text)
    except (ValueError, TypeError):
        return 0.0


# ═══════════════════════════════════════════════════════════════
# 主回测逻辑
# ═══════════════════════════════════════════════════════════════

def backtest():
    print(f"\n{'='*70}")
    print(f"  基金 {FUND_CODE} 华安法国CAC40ETF联接(QDII)C 交易回测")
    print(f"{'='*70}\n")

    # ── Step 0: 获取全量交易 + 持仓数据 ──
    logger.info("获取全量交易和持仓数据...")
    info = get_all_fund_trades(DEFAULT_USER, FUND_CODE)
    if not info:
        print("❌ 获取数据失败")
        return

    current_asset_value = info.current_asset_value   # 持仓市值
    profit_value = info.profit_value                  # 累计收益
    total_invested = info.total_invested              # 全量总投资

    # ── Step 1: 获取持仓详情（净值等信息） ──
    from src.service.资产管理.get_fund_asset_detail import get_fund_total_asset_detail
    asset_detail = get_fund_total_asset_detail(DEFAULT_USER, FUND_CODE)
    current_shares = asset_detail.available_vol if asset_detail else 0
    current_nav = asset_detail.fund_nav if asset_detail else 0
    current_nav_date = asset_detail.nav_date if asset_detail else ""
    hold_profit = asset_detail.hold_profit if asset_detail else 0
    hold_profit_rate = asset_detail.hold_profit_rate if asset_detail else 0

    print(f"  【当前持仓】")
    print(f"    持仓市值: {current_asset_value:>12,.2f} 元")
    print(f"    可用份额: {current_shares:>12,.4f} 份")
    print(f"    最新净值: {current_nav:.4f} 元 ({current_nav_date})")
    print(f"    持有收益: {hold_profit:>+10,.2f} 元 ({hold_profit_rate:+.2f}%)")
    print(f"    累计收益: {profit_value:>+10,.2f} 元")

    # ── Step 2: 获取净值数据 ──
    logger.info("获取净值历史...")
    nav_list = get_fund_nav_history(FUND_CODE)
    nav_map = {date: nav for date, nav in nav_list}
    logger.info(f"共 {len(nav_list)} 条净值数据")

    # ── Step 3: 汇总 ──
    total_bought_1yr = sum(amount for _, _, amount in info.buy_trades)
    total_redeemed = sum(money for _, _, _, money in info.sell_trades if money is not None)

    print(f"\n  【交易汇总】")
    print(f"    有效买入: {len(info.buy_trades)} 笔 (定投+手动)")
    print(f"    有效卖出: {len(info.sell_trades)} 笔")
    print(f"    已撤单交易: {info.cancelled_count} 笔 (已排除)")
    print(f"    近1年买入: {total_bought_1yr:>12,.2f} 元")
    print(f"    近1年赎回: {total_redeemed:>12,.2f} 元")
    if info.pre_window_invest > 0:
        print(f"    1年前投入: {info.pre_window_invest:>12,.2f} 元 (推算,超出API窗口)")
    print(f"    投资总金额: {total_invested:>12,.2f} 元")

    # ── Step 4: 收益 ──
    return_rate_simple = (profit_value / total_invested * 100) if total_invested > 0 else 0.0
    print(f"\n  【收益分析】")
    print(f"    收益金额: {profit_value:>+10,.2f} 元")
    print(f"    持有收益: {hold_profit:>+10,.2f} 元 (收益率 {hold_profit_rate:+.2f}%)")
    print(f"    简单收益率: {return_rate_simple:>+8.2f}%")

    # ── Step 5: 构建现金流（份额追踪） ──
    all_events = []
    for dt, bt, money in info.buy_trades:
        nav = lookup_nav(nav_map, dt)
        if nav is None:
            logger.warning(f"  买入 {dt}: 无法获取净值, 跳过")
            continue
        shares = money / nav
        all_events.append((dt, '买入', -money, shares))

    for dt, bt, shares, money_received in info.sell_trades:
        if money_received is None:
            nav = lookup_nav(nav_map, dt)
            if nav is None:
                logger.warning(f"  卖出 {dt}: 无法获取净值, 跳过")
                continue
            money_received = shares * nav
        all_events.append((dt, '卖出', money_received, -shares))

    all_events.sort(key=lambda x: x[0])

    window_start_date = all_events[0][0] if all_events else current_nav_date

    # 逐日持仓追踪
    position_values = []
    current_shares_track = 0.0
    for dt, evt_type, cash_amount, shares_change in all_events:
        current_shares_track += shares_change
        if current_shares_track > 1e-6:
            nav = lookup_nav(nav_map, dt)
            if nav:
                position_values.append((dt, current_shares_track * nav))

    max_holding = max((v for _, v in position_values), default=0)
    max_holding = max(max_holding, current_asset_value)
    avg_holding = sum(v for _, v in position_values) / len(position_values) if position_values else 0.0

    print(f"\n  【持仓统计】")
    print(f"    当前持仓市值: {current_asset_value:>12,.2f} 元")
    print(f"    最大持仓金额: {max_holding:>12,.2f} 元")
    print(f"    平均日持有金额: {avg_holding:>12,.2f} 元 (基于 {len(position_values)} 个交易日)")
    return_rate_weighted = (profit_value / avg_holding * 100) if avg_holding > 0 else 0.0
    print(f"    资金加权收益率: {return_rate_weighted:>+8.2f}%")

    # ── Step 6: IRR ──
    irr_cash_flows = []
    if info.pre_window_invest > 0:
        try:
            wsd = datetime.strptime(window_start_date, "%Y-%m-%d")
            init_date = (wsd - timedelta(days=1)).strftime("%Y-%m-%d")
        except ValueError:
            init_date = window_start_date
        irr_cash_flows.append((init_date, -info.pre_window_invest))
        logger.info(f"推算期初投入: {info.pre_window_invest:.2f} 元 (日期: {init_date})")

    for dt, evt_type, cash_amount, _ in all_events:
        irr_cash_flows.append((dt, cash_amount))
    if current_asset_value > 0:
        irr_cash_flows.append((current_nav_date, current_asset_value))
    irr_cash_flows.sort(key=lambda x: x[0])

    irr_value = compute_irr(irr_cash_flows)
    if irr_value is not None:
        print(f"    内部收益率 (IRR): {irr_value*100:>+8.2f}% (年化,含推算的期初投入)")

    # ── Step 7: 交易明细 ──
    print(f"\n  【交易明细】（近1年窗口内）")
    if info.pre_window_invest > 0:
        print(f"  ⚠️  窗口前的投入 ({info.pre_window_invest:,.2f} 元) 不在下表，已纳入 IRR 计算")
    print(f"  {'日期':<14} {'类型':<10} {'金额':>12} {'份额变化':>12} {'累计份额':>12}")
    print(f"  {'─'*64}")
    running_shares = 0.0
    for dt, evt_type, cash_amount, shares_change in all_events:
        running_shares += shares_change
        label = '卖出' if evt_type == '卖出' else '买入'
        print(f"  {dt:<14} {label:<10} {cash_amount:>12,.2f} {shares_change:>+12,.4f} {running_shares:>12,.4f}")
    if current_asset_value > 0:
        print(f"  {current_nav_date:<14} {'期末市值':<10} {current_asset_value:>12,.2f}")

    if info.cancelled_count:
        print(f"\n  ⚠️  已撤单交易 ({info.cancelled_count} 笔, 已排除):")
        count = 0
        for t in info.trades_raw:
            raw = getattr(t, 'raw', {}) or {}
            if '撤单' in (raw.get('APPStateText') or ''):
                print(f"    {(t.strike_start_date or t.apply_work_day or '')[:10]} {t.business_type} Apply={raw.get('ApplyCount','')}")
                count += 1
                if count >= 5:
                    break

    print(f"\n{'='*70}\n")


if __name__ == "__main__":
    backtest()
