"""
基金全量交易记录获取服务

设计背景：
  GetOneFundTranInfos API 的 DateType 参数经探针测试，所有取值（"0"~"12", "30", "365", "9999", ""）
  均返回相同数量的记录（约最近 1 年），API 本身不支持返回超过 1 年的全量记录。

  因此本模块采用"API 记录 + 持仓反推"的策略，补全全量投资画像：
    1. 调用 get_one_fund_tran_infos(date_type="3") 获取最近 1 年所有交易
    2. 调用 get_fund_total_asset_detail 获取当前真实持仓
    3. 通过公式反推窗口前的总投资：总投入 = 当前市值 + 累计赎回 - 累计收益
    4. 返回全量交易记录 + 推算的窗口前投入

使用示例：
    from src.service.资产管理.get_all_fund_trades import get_all_fund_trades, FullTradeInfo
    result = get_all_fund_trades(user, "021540")
    # result.total_invested   -> float              全量总投资
    # result.pre_window_invest -> float              窗口前投入（推算）
    # result.buy_trades       -> [(date, type, amount), ...]
    # result.sell_trades      -> [(date, type, shares, money), ...]
"""

import sys, os, logging
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from src.common.logger import get_logger
from src.API.交易管理.trade import get_one_fund_tran_infos
from src.service.资产管理.get_fund_asset_detail import get_fund_total_asset_detail
from src.service.交易管理.trade_classifier import classify_trades

logger = get_logger(__name__)


# ═══════════════════════════════════════════════════════
# 数据类
# ═══════════════════════════════════════════════════════

@dataclass
class FullTradeInfo:
    """全量交易信息"""
    trades_raw: List = field(default_factory=list)
    """所有通过 API 获取的交易记录（TradeResult 列表，含撤单）"""

    buy_trades: List[Tuple[str, str, float]] = field(default_factory=list)
    """有效买入列表: [(date, business_type, amount), ...]"""

    sell_trades: List[Tuple[str, str, float, Optional[float]]] = field(default_factory=list)
    """有效卖出列表: [(date, business_type, shares, money_received_or_None), ...]"""

    total_invested: float = 0.0
    """全量总投资金额（含窗口前推算投入）"""

    pre_window_invest: float = 0.0
    """窗口前投入金额（推算值，API 无法返回的早期买入）"""

    pre_window_date: str = ""
    """窗口起始日期（API 所能返回的最早交易日期）"""

    total_redeemed: float = 0.0
    """窗口内累计赎回金额"""

    current_asset_value: float = 0.0
    """当前持仓市值（来自持仓 API）"""

    profit_value: float = 0.0
    """累计收益（来自持仓 API）"""

    cancelled_count: int = 0
    """已撤单交易数量"""

    raw_total_count: int = 0
    """API 返回的交易总数（含撤单）"""


def get_all_fund_trades(user, fund_code: str) -> Optional[FullTradeInfo]:
    """
    获取指定基金的全量交易记录及投资总额。

    策略：
      1. 调用 GetOneFundTranInfos(date_type="3") 获取最近 1 年所有交易（含分页）
      2. 调用持仓 API 获取当前真实持仓数据
      3. 反推窗口前投入：总投入 = 当前市值 + 累计赎回 - 累计收益
         该公式成立的前提是 get_fund_total_asset_detail 返回的 profit_value
         为"累计收益"（含已实现 + 未实现 + 分红），不依赖窗口内可见交易。

    Args:
        user: 用户对象
        fund_code: 基金代码

    Returns:
        FullTradeInfo 或 None（当前无持仓时返回 None）

    Example:
        info = get_all_fund_trades(user, "021540")
        if info:
            print(f"总投资: {info.total_invested:.2f}")
            print(f"累计收益: {info.profit_value:+.2f}")
            print(f"有效买入: {len(info.buy_trades)} 笔")
            print(f"有效卖出: {len(info.sell_trades)} 笔")
            if info.pre_window_invest > 0:
                print(f"⚠️  窗口前投入 {info.pre_window_invest:.2f} 元（API 无法返回）")
    """
    # 1. 获取当前持仓
    asset = get_fund_total_asset_detail(user, fund_code)
    if not asset or asset.asset_value <= 0:
        logger.warning(f"基金 {fund_code} 无有效持仓")
        return None

    current_asset_value = asset.asset_value
    profit_value = asset.profit_value

    # 2. 获取最近 1 年交易记录
    #    date_type="3" 是 API 返回最多记录的参数（经探针验证，"0"~"9999" 均返回相同条数）
    trades = get_one_fund_tran_infos(user, fund_code=fund_code, date_type="3")

    # 3. 分类统计
    buy_trades, sell_trades, cancelled_trades = classify_trades(trades)
    cancelled_count = len(cancelled_trades)

    total_bought_1yr = sum(amount for _, _, amount in buy_trades)
    total_redeemed = sum(money for _, _, _, money in sell_trades if money is not None)

    # 4. 反推全量总投资
    #    累计收益 = 当前市值 + 累计赎回 - 总投入
    #    => 总投入 = 当前市值 + 累计赎回 - 累计收益
    total_invested = current_asset_value + total_redeemed - profit_value
    pre_window_invest = total_invested - total_bought_1yr

    # 窗口起始日期（API 返回的最早交易）
    window_start_date = ""
    if trades:
        window_start_date = (trades[-1].strike_start_date or trades[-1].apply_work_day or '')[:10]

    info = FullTradeInfo(
        trades_raw=trades,
        buy_trades=buy_trades,
        sell_trades=sell_trades,
        total_invested=max(total_invested, 0),
        pre_window_invest=max(pre_window_invest, 0),
        pre_window_date=window_start_date,
        total_redeemed=total_redeemed,
        current_asset_value=current_asset_value,
        profit_value=profit_value,
        cancelled_count=cancelled_count,
        raw_total_count=len(trades),
    )

    logger.info(
        f"基金 {fund_code}: {len(buy_trades)}笔买入/{len(sell_trades)}笔卖出/{cancelled_count}笔撤单, "
        f"总投资 {total_invested:,.2f} (含窗口前 {pre_window_invest:,.2f}), "
        f"累计收益 {profit_value:+,.2f}"
    )

    return info


if __name__ == "__main__":
    import logging as _logging
    _logging.basicConfig(
        level=_logging.INFO,
        format='%(asctime)s [%(levelname)8s] %(message)s',
        stream=sys.stdout,
    )
    # 屏蔽 urllib3 警告
    _logging.getLogger("urllib3").setLevel(_logging.ERROR)
    # 屏蔽 apscheduler/bank 的冗长日志
    _logging.getLogger("src.service.银行卡账户").setLevel(_logging.WARNING)

    from src.common.constant import DEFAULT_USER

    fund_code = sys.argv[1] if len(sys.argv) > 1 else "021540"

    print(f"\n{'='*60}")
    print(f"  get_all_fund_trades 测试 — 基金 {fund_code}")
    print(f"{'='*60}\n")

    info = get_all_fund_trades(DEFAULT_USER, fund_code)

    if info is None:
        print("  ❌ 无有效持仓，返回 None")
        sys.exit(0)

    print(f"  当前持仓市值:     {info.current_asset_value:>12,.2f} 元")
    print(f"  累计收益:         {info.profit_value:>+10,.2f} 元")
    print(f"  ─────────────────────────────────────")
    print(f"  有效买入:         {len(info.buy_trades)} 笔")
    print(f"  有效卖出:         {len(info.sell_trades)} 笔")
    print(f"  已撤单交易:       {info.cancelled_count} 笔")
    print(f"  ─────────────────────────────────────")
    total_bought_1yr = sum(a for _, _, a in info.buy_trades)
    total_redeemed = sum(m for _, _, _, m in info.sell_trades if m is not None)
    print(f"  近 1 年买入金额:  {total_bought_1yr:>12,.2f} 元")
    print(f"  近 1 年赎回金额:  {total_redeemed:>12,.2f} 元")
    if info.pre_window_invest > 0:
        print(f"  窗口前推算投入:   {info.pre_window_invest:>12,.2f} 元 (≤{info.pre_window_date})")
    print(f"  ─────────────────────────────────────")
    print(f"  投资总金额:       {info.total_invested:>12,.2f} 元")
    print(f"  简单收益率:       {info.profit_value / info.total_invested * 100:>+8.2f}%")
    print(f"  累计回收占比:    {total_redeemed / info.total_invested * 100:>7.1f}%")
    print()

    # 打印最近 10 笔买入明细
    print(f"  【最近 5 笔买入记录】")
    print(f"  {'日期':<14} {'类型':<8} {'金额':>10}")
    print(f"  {'─'*34}")
    for dt, bt, amt in reversed(info.buy_trades[-5:]):
        print(f"  {dt:<14} {bt:<8} {amt:>10,.2f}")

    if info.sell_trades:
        print(f"\n  【卖出记录】")
        print(f"  {'日期':<14} {'类型':<8} {'金额':>10}")
        print(f"  {'─'*34}")
        for dt, bt, _, money in info.sell_trades:
            print(f"  {dt:<14} {bt:<8} {money:>10,.2f}")

    print()
