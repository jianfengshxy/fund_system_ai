#!/usr/bin/env python3
"""
基金 021540 - 最近一年交易回测（修正版）

问题：旧版回测将已撤单(已支付)的交易误判为有效买入，导致数据严重失实。
修正方式：
  1. 优先从持仓接口（get_fund_total_asset_detail）获取当前真实持仓数据
  2. 交易记录严格排除已撤单交易（APPStateText 含"撤单"字眼）
  3. 基于修正后的现金流计算 IRR

指标：
  - 总投入金额 (Total Invested)
  - 最大持仓金额 (Max Holding Amount)
  - 平均持有金额 (Average Holding Amount)
  - 收益金额 (Profit)
  - 收益率 (Rate of Return)
  - 内部收益率 (IRR)
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
from src.service.资产管理.get_fund_asset_detail import get_fund_total_asset_detail

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
    print(f"  基金 {FUND_CODE} 最近一年交易回测（修正版）")
    print(f"{'='*70}\n")

    # ── Step 0: 获取当前真实持仓 ──
    logger.info("获取当前真实持仓数据...")
    asset = get_fund_total_asset_detail(DEFAULT_USER, FUND_CODE)
    if not asset:
        print("❌ 获取当前持仓失败")
        return

    current_asset_value = asset.asset_value       # 31,515.01
    current_shares = asset.available_vol            # 27,713.67
    current_nav = asset.fund_nav                    # 1.065
    current_nav_date = asset.nav_date               # 2026-07-23
    hold_profit = asset.hold_profit                 # -484.04
    hold_profit_rate = asset.hold_profit_rate       # -1.61
    profit_value = asset.profit_value               # 601.75

    print(f"\n  【当前持仓】")
    print(f"    持仓市值: {current_asset_value:>12,.2f} 元")
    print(f"    可用份额: {current_shares:>12,.4f} 份")
    print(f"    最新净值: {current_nav:.4f} 元 ({current_nav_date})")
    print(f"    持有收益: {hold_profit:>+10,.2f} 元 ({hold_profit_rate:+.2f}%)")
    print(f"    持有成本: {current_asset_value - hold_profit:>12,.2f} 元")
    print(f"    累计收益: {profit_value:>+10,.2f} 元")

    # ── Step 1: 获取交易记录 ──
    # date_type="3" 返回最近1年交易记录
    # 该基金成立于 2024-06，1年前的买入交易超出窗口，需通过持仓API推算补全
    logger.info("获取交易记录（近1年）...")
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

    first_nav = nav_list[-1][1] if nav_list else 0.0
    first_nav_date = nav_list[-1][0] if nav_list else "N/A"

    # ── Step 3: 解析交易（修正版：严格排除已撤单） ──
    buy_trades = []
    sell_trades = []
    skipped_trades = []
    cancelled_trades = []

    for t in trades:
        bt = t.business_type or ''
        date_str = get_trade_date(t)
        if not date_str:
            continue

        raw = getattr(t, 'raw', {}) or {}
        app_state_text = (raw.get('APPStateText') or '').strip()
        statu_icon = str(raw.get('StatuIcon', ''))
        colour = raw.get('Colour', '')
        confirm_raw = raw.get('ConfirmCount', '') or ''
        apply_raw = raw.get('ApplyCount', '') or ''

        # 撤单检查
        is_cancelled = '撤单' in app_state_text
        if is_cancelled:
            cancelled_trades.append((date_str, bt, apply_raw))
            continue

        # 买入交易
        if bt in ('买入', '定投'):
            if statu_icon != '3':
                skipped_trades.append((date_str, bt, statu_icon, app_state_text, 'not_confirmed'))
                continue

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
                skipped_trades.append((date_str, bt, amount, 'buy_parse_fail'))

        # 卖出交易
        elif '卖基金' in bt or '赎回' in bt or '卖出' in bt:
            if statu_icon != '3':
                continue

            if colour == '3' and confirm_raw and '元' in confirm_raw:
                money_received = parse_amount(confirm_raw)
                nav = lookup_nav(nav_map, date_str)
                if nav and nav > 0:
                    shares = money_received / nav
                    sell_trades.append((date_str, bt, shares, money_received))
                else:
                    skipped_trades.append((date_str, bt, 0, 'sell_no_nav'))
            elif colour == '4' and apply_raw and '份' in apply_raw:
                shares = parse_amount(apply_raw)
                if shares > 0:
                    sell_trades.append((date_str, bt, shares, None))
                else:
                    skipped_trades.append((date_str, bt, 0, 'sell_parse_fail'))
            else:
                skipped_trades.append((date_str, bt, 0, f'sell_unknown(colour={colour})'))

    logger.info(f"有效买入: {len(buy_trades)} 笔")
    logger.info(f"有效卖出: {len(sell_trades)} 笔")
    logger.info(f"已撤单: {len(cancelled_trades)} 笔")
    logger.info(f"其他跳过: {len(skipped_trades)} 笔")

    if not buy_trades:
        print("❌ 未解析到有效的买入交易")
        return

    # ── Step 4: 计算关键指标 ──
    total_bought_1yr = sum(amount for _, _, amount in buy_trades)
    total_redeemed = sum(money for _, _, _, money in sell_trades)

    # 从 API 推算全量总投入:
    #   累计收益 = 当前市值 + 累计赎回 - 总投入 (含已实现+未实现+分红)
    #   => 总投入 = 当前市值 + 累计赎回 - 累计收益
    total_invested = current_asset_value + total_redeemed - profit_value
    pre_window_invested = total_invested - total_bought_1yr

    print(f"\n  【交易汇总】")
    print(f"    有效买入: {len(buy_trades)} 笔 (定投+手动)")
    print(f"    有效卖出: {len(sell_trades)} 笔")
    print(f"    已撤单交易: {len(cancelled_trades)} 笔 (已排除)")
    print(f"    近1年买入: {total_bought_1yr:>12,.2f} 元")
    print(f"    近1年赎回: {total_redeemed:>12,.2f} 元")
    if pre_window_invested > 0:
        print(f"    1年前投入: {pre_window_invested:>12,.2f} 元 (推算,超出API窗口)")
    print(f"    投资总金额: {total_invested:>12,.2f} 元")

    # ── Step 5: 收益计算 ──
    profit = profit_value  # 累计收益（含已实现+未实现+分红）
    return_rate_simple = (profit / total_invested * 100) if total_invested > 0 else 0.0

    print(f"\n  【收益分析】")
    print(f"    收益金额: {profit:>+10,.2f} 元")
    print(f"    持有收益: {hold_profit:>+10,.2f} 元 (收益率 {hold_profit_rate:+.2f}%)")
    print(f"    简单收益率: {return_rate_simple:>+8.2f}%")

    # ── Step 6: 构建现金流（用于 IRR + 持仓追踪） ──
    all_events = []
    for dt, bt, money in buy_trades:
        nav = lookup_nav(nav_map, dt)
        if nav is None:
            logger.warning(f"  买入 {dt}: 无法获取净值, 跳过此笔")
            continue
        shares = money / nav
        all_events.append((dt, '买入', -money, shares))

    for dt, bt, shares, money_received in sell_trades:
        if money_received is None:
            nav = lookup_nav(nav_map, dt)
            if nav is None:
                logger.warning(f"  卖出 {dt}: 无法获取净值, 跳过此笔")
                continue
            money_received = shares * nav
        all_events.append((dt, '卖出', money_received, -shares))

    all_events.sort(key=lambda x: x[0])

    # 窗口内最早的日期
    window_start_date = all_events[0][0] if all_events else current_nav_date

    # 逐日持仓追踪（仅1年窗口内）
    position_values = []
    current_shares_track = 0.0
    for dt, evt_type, cash_amount, shares_change in all_events:
        current_shares_track += shares_change
        if current_shares_track > 1e-6:
            nav = lookup_nav(nav_map, dt)
            if nav:
                position_values.append((dt, current_shares_track * nav))

    max_holding = max(v for _, v in position_values) if position_values else 0.0
    avg_holding = sum(v for _, v in position_values) / len(position_values) if position_values else 0.0
    max_holding = max(max_holding, current_asset_value)

    print(f"\n  【持仓统计】")
    print(f"    当前持仓市值: {current_asset_value:>12,.2f} 元")
    print(f"    最大持仓金额: {max_holding:>12,.2f} 元")
    print(f"    平均持有金额: {avg_holding:>12,.2f} 元 (基于 {len(position_values)} 个交易日)")

    return_rate_weighted = (profit / avg_holding * 100) if avg_holding > 0 else 0.0
    print(f"    资金加权收益率: {return_rate_weighted:>+8.2f}%")

    # ── Step 7: IRR 计算（含窗口前推算投入） ──
    irr_cash_flows = []

    # 1年前窗口外的投入作为一笔初始投入（放在窗口开始日的前一天）
    if pre_window_invested > 0:
        try:
            wsd = datetime.strptime(window_start_date, "%Y-%m-%d")
            init_date = (wsd - timedelta(days=1)).strftime("%Y-%m-%d")
        except ValueError:
            init_date = window_start_date
        irr_cash_flows.append((init_date, -pre_window_invested))
        logger.info(f"推算1年前初始投入: {pre_window_invested:.2f} 元 (日期: {init_date})")

    for dt, evt_type, cash_amount, _ in all_events:
        irr_cash_flows.append((dt, cash_amount))
    # 当前持仓市值作为最后一笔正现金流
    if current_asset_value > 0:
        irr_cash_flows.append((current_nav_date, current_asset_value))
    irr_cash_flows.sort(key=lambda x: x[0])

    irr_value = compute_irr(irr_cash_flows)
    if irr_value is not None:
        print(f"    内部收益率 (IRR): {irr_value*100:>+8.2f}% (年化,含推算的期初投入)")

    # ── 交易明细 ──
    print(f"\n  【交易明细】（近1年窗口内）")
    if pre_window_invested > 0:
        print(f"  ⚠️  窗口前的投入 ({pre_window_invested:,.2f} 元) 不在下表，已纳入 IRR 计算")
    print(f"  {'日期':<14} {'类型':<16} {'金额':>12} {'份额变化':>12} {'累计份额':>12}")
    print(f"  {'─'*66}")
    running_shares = 0.0
    for dt, evt_type, cash_amount, shares_change in all_events:
        running_shares += shares_change
        label = '卖出' if evt_type == '卖出' else '买入'
        print(f"  {dt:<14} {label:<16} {cash_amount:>12,.2f} {shares_change:>+12,.4f} {running_shares:>12,.4f}")
    if current_asset_value > 0:
        print(f"  {current_nav_date:<14} {'期末市值':<16} {current_asset_value:>12,.2f}")

    if cancelled_trades:
        print(f"\n  ⚠️  已撤单交易 ({len(cancelled_trades)} 笔, 已排除):")
        for dt, bt, raw_amt in cancelled_trades[:5]:
            print(f"    {dt} {bt} ApplyCount={raw_amt}")

    print(f"\n{'='*70}\n")


if __name__ == "__main__":
    backtest()
