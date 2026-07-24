"""
交易分类工具模块

将 TradeResult 列表分类为买入/卖出/撤单。供 get_all_fund_trades 和 sync_user_trade 共用，
避免分类逻辑重复。

交易有效性判断规则（经 021540 真实数据验证）:
  - 撤单: APPStateText 含 "撤单"，或 Colour == "4"
  - ⚠️ StatuIcon=="3" 不代表交易成功（撤单交易也是 "3"）
  - 买入: BusinessType in ("买入","定投")，非撤单，StatuIcon=="3"
  - 卖出: "卖基金" in BusinessType，非撤单，StatuIcon=="3"

  business_code 含义（两个 API 一致）:
    22  = 买入 (活期宝转入基金)
    39  = 定投
    890 = 卖出 (卖出回活期宝)
"""

from typing import List, Optional, Tuple

from src.common.logger import get_logger
from src.domain.trade.TradeResult import TradeResult

logger = get_logger(__name__)


def parse_amount(text: str) -> float:
    """解析金额/份额字符串，如 '5,000.00元' -> 5000.0，'942.77份' -> 942.77"""
    if not text:
        return 0.0
    text = text.strip().replace(',', '')
    for suffix in ['元', '份', ' ']:
        text = text.replace(suffix, '')
    try:
        return float(text)
    except (ValueError, TypeError):
        return 0.0


def classify_trades(trades: List[TradeResult]) -> Tuple[List, List, List]:
    """
    将交易列表分类为买入 / 卖出 / 撤单。

    Args:
        trades: TradeResult 列表（要求来自 get_one_fund_tran_infos，
                因为需要 raw 中的 APPStateText / Colour 字段）

    Returns:
        (buy_trades, sell_trades, cancelled_trades)
        buy_trades:      [(date_str, business_type, amount), ...]
        sell_trades:     [(date_str, business_type, shares, money_received), ...]
        cancelled_trades: [(date_str, business_type, raw_apply_count_str), ...]
    """
    buy_trades = []
    sell_trades = []
    cancelled_trades = []

    for t in trades:
        bt = t.business_type or ''
        date_str = (t.strike_start_date or t.apply_work_day or '')[:10]
        if not date_str:
            continue

        raw = getattr(t, 'raw', {}) or {}
        app_state_text = (raw.get('APPStateText') or '').strip()
        statu_icon = str(raw.get('StatuIcon', ''))
        colour = raw.get('Colour', '')
        confirm_raw = raw.get('ConfirmCount', '') or ''
        apply_raw = raw.get('ApplyCount', '') or ''

        # —— 撤单检查（双重保障） ——
        is_cancelled = '撤单' in app_state_text or colour == '4'
        if is_cancelled:
            cancelled_trades.append((date_str, bt, apply_raw))
            continue

        # —— 买入交易 ——
        if bt in ('买入', '定投'):
            if statu_icon != '3':
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

        # —— 卖出交易 ——
        elif '卖基金' in bt or '赎回' in bt or '卖出' in bt:
            if statu_icon != '3':
                continue

            if colour == '3' and confirm_raw and '元' in confirm_raw:
                money_received = parse_amount(confirm_raw)
                sell_trades.append((date_str, bt, 0, money_received))
            elif colour == '4' and apply_raw and '份' in apply_raw:
                shares = parse_amount(apply_raw)
                if shares > 0:
                    sell_trades.append((date_str, bt, shares, None))

    return buy_trades, sell_trades, cancelled_trades
