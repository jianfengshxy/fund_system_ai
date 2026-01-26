import os
import sys
import logging
import pandas as pd
from datetime import datetime, timedelta
import numpy as np
import requests
import re
import json
from typing import List, Dict, Optional, Tuple

# Add root dir
root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from src.common.constant import DEFAULT_USER
from src.service.公共服务.nav_gate_service import nav5_gate

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class ShareBatch:
    """份额批次类，用于FIFO成本计算"""
    def __init__(self, shares: float, cost: float, buy_date: str):
        self.shares = shares          # 份额数量
        self.cost = cost              # 总成本
        self.buy_date = buy_date      # 买入日期
        self.original_cost_per_share = cost / shares if shares > 0 else 0  # 原始每份成本（不变）

class CustomStrategyBacktestAccount:
    """自定义策略回测账户类"""
    def __init__(self, fund_code: str, fund_name: str, amount: float):
        self.fund_code = fund_code
        self.fund_name = fund_name
        self.amount = amount  # 每次投入金额
        self.shares = 0.0  # 持有份额
        self.total_invested = 0.0  # 总投入金额
        self.total_redeemed = 0.0  # 总赎回金额
        self.avg_cost = 0.0  # 平均成本
        self.realized_profit = 0.0  # 已实现盈利
        self.trades = []  # 交易记录
        self.daily_positions = []  # 每日持仓记录
        self.held_codes = set()  # 持有基金集合（在本案例中只有一个基金）
        self.last_buy_date = None  # 上次买入日期
        self.last_sell_date = None  # 上次卖出日期
        self.sell_profit_records = []  # 记录每次止盈的盈利
        self.share_batches = []  # 份额批次列表，用于FIFO成本计算

    def can_buy_today(self, current_date: str) -> bool:
        """检查是否可以进行买入（T+1规则：距离上次买入/卖出至少1天）"""
        # 检查距离上次买入是否至少1天
        if self.last_buy_date is not None:
            current_dt = datetime.strptime(current_date, "%Y-%m-%d")
            last_buy_dt = datetime.strptime(self.last_buy_date, "%Y-%m-%d")
            days_since_last_buy = (current_dt - last_buy_dt).days
            if days_since_last_buy < 1:
                return False

        # 检查距离上次卖出是否至少1天
        if self.last_sell_date is not None:
            current_dt = datetime.strptime(current_date, "%Y-%m-%d")
            last_sell_dt = datetime.strptime(self.last_sell_date, "%Y-%m-%d")
            days_since_last_sell = (current_dt - last_sell_dt).days
            if days_since_last_sell < 1:
                return False

        return True

    def can_sell_today(self, current_date: str) -> bool:
        """检查是否可以进行卖出（距离上次买入至少7天，确保0手续费）"""
        if self.last_buy_date is None:
            return True  # 如果从未买入过，可以直接卖出（例如初始持仓）

        current_dt = datetime.strptime(current_date, "%Y-%m-%d")
        last_buy_dt = datetime.strptime(self.last_buy_date, "%Y-%m-%d")
        days_since_last_buy = (current_dt - last_buy_dt).days

        return days_since_last_buy >= 7

    def buy(self, nav: float, date: str, action_type: str = "BUY", additional_info: str = ""):
        """买入操作"""
        # 检查是否满足买入条件
        if not self.can_buy_today(date):
            logger.info(f"跳过买入操作：T+1规则限制，当前日期: {date}")
            if self.last_buy_date:
                logger.info(f"  - 距离上次买入({self.last_buy_date})不足1天")
            if self.last_sell_date:
                logger.info(f"  - 距离上次卖出({self.last_sell_date})不足1天")
            return False

        shares_bought = self.amount / nav
        self.shares += shares_bought
        self.total_invested += self.amount

        # 添加新批次
        self.share_batches.append(ShareBatch(
            shares=shares_bought,
            cost=self.amount,
            buy_date=date
        ))

        # 更新平均成本
        if self.shares > 0:
            self.avg_cost = self.total_invested / self.shares

        trade_record = {
            'date': date,
            'action': action_type,
            'nav': nav,
            'amount': self.amount,
            'shares': shares_bought,
            'total_shares': self.shares,
            'total_invested': self.total_invested,
            'additional_info': additional_info
        }
        self.trades.append(trade_record)
        self.last_buy_date = date  # 更新上次买入日期

        logger.info(f"{action_type} {self.fund_name}({self.fund_code}) - 金额: {self.amount}, 份额: {shares_bought:.4f}, 净值: {nav}, 原因: {additional_info}")
        return True

    def sell(self, nav: float, date: str, shares_to_sell: float = None, additional_info: str = ""):
        """卖出操作"""
        if self.shares <= 0:
            return False

        # 检查是否满足卖出条件（距离上次买入至少7天）
        if not self.can_sell_today(date):
            logger.info(f"跳过卖出操作：距离上次买入不满7天，无法获得0手续费，当前日期: {date}, 上次买入: {self.last_buy_date}")
            return False

        # 如果没有指定卖出份额，默认卖出全部
        if shares_to_sell is None:
            shares_to_sell = self.shares

        shares_to_sell = min(shares_to_sell, self.shares)  # 确保不超过持有份额
        amount_sold = shares_to_sell * nav

        # FIFO: 按先进先出原则计算成本
        cost_sold = 0.0
        remaining_to_sell = shares_to_sell
        batches_sold = []  # 记录卖出的批次

        for batch in self.share_batches[:]:  # 创建副本进行遍历
            if remaining_to_sell <= 0:
                break

            shares_from_batch = min(batch.shares, remaining_to_sell)
            # 使用原始每份成本，而不是动态计算的成本
            cost_from_batch = shares_from_batch * batch.original_cost_per_share
            cost_sold += cost_from_batch

            # 更新批次
            batch.shares -= shares_from_batch
            batch.cost -= cost_from_batch  # 同步更新批次成本
            if batch.shares <= 0:
                batches_sold.append(batch)
            else:
                remaining_to_sell -= shares_from_batch

        # 移除已售完的批次
        for batch in batches_sold:
            self.share_batches.remove(batch)

        profit_from_sale = amount_sold - cost_sold
        self.realized_profit += profit_from_sale

        # 更新总赎回金额
        self.total_redeemed += amount_sold

        # 更新持仓
        self.shares -= shares_to_sell
        self.total_invested -= cost_sold

        if self.shares > 0 and self.total_invested > 0:
            self.avg_cost = self.total_invested / self.shares
        else:
            self.avg_cost = 0

        # 记录止盈盈利
        self.sell_profit_records.append({
            'date': date,
            'sold_amount': amount_sold,
            'cost': cost_sold,
            'profit': profit_from_sale,
            'additional_info': additional_info
        })

        trade_record = {
            'date': date,
            'action': 'SELL',
            'nav': nav,
            'amount': amount_sold,
            'shares': shares_to_sell,
            'total_shares': self.shares,
            'total_invested': self.total_invested,
            'additional_info': additional_info,
            'realized_profit': profit_from_sale
        }
        self.trades.append(trade_record)
        self.last_sell_date = date  # 更新上次卖出日期

        logger.info(f"卖出 {self.fund_name}({self.fund_code}) - 金额: {amount_sold:.2f}, 份额: {shares_to_sell:.4f}, 净值: {nav}, 盈利: {profit_from_sale:.2f}, 原因: {additional_info}")
        return True

    def get_asset_value(self, nav: float) -> float:
        """获取当前资产价值"""
        return self.shares * nav

    def get_unrealized_profit(self, nav: float) -> float:
        """获取未实现盈利"""
        if self.avg_cost <= 0 or self.shares <= 0:
            return 0.0
        current_value = self.get_asset_value(nav)
        cost_basis = self.shares * self.avg_cost
        return current_value - cost_basis

    def get_total_profit(self, nav: float) -> float:
        """获取总盈利（已实现+未实现）"""
        return self.realized_profit + self.get_unrealized_profit(nav)

    def get_profit_rate(self, nav: float) -> float:
        """获取当前收益率（基于总投入，含已实现盈利）"""
        if self.total_invested <= 0:
            return 0.0
        total_profit = self.get_total_profit(nav)
        return (total_profit / self.total_invested) * 100

    def get_holding_profit_rate(self, nav: float) -> float:
        """获取当前持仓收益率（仅基于当前持仓成本）"""
        if self.avg_cost <= 0:
            return 0.0
        return (nav - self.avg_cost) / self.avg_cost * 100

    def record_daily_position(self, date: str, nav: float):
        """记录每日持仓状态"""
        asset_value = self.get_asset_value(nav)
        daily_record = {
            'date': date,
            'nav': nav,
            'shares': self.shares,
            'asset_value': asset_value,
            'total_invested': self.total_invested,
            'profit_rate': self.get_profit_rate(nav),
            'profit_amount': self.get_total_profit(nav),
            'realized_profit': self.realized_profit,
            'unrealized_profit': self.get_unrealized_profit(nav)
        }
        self.daily_positions.append(daily_record)


def get_historical_data(fund_code: str) -> pd.DataFrame:
    """获取基金历史净值数据"""
    url = f"http://fund.eastmoney.com/pingzhongdata/{fund_code}.js"
    try:
        logger.info(f"正在获取基金 {fund_code} 的历史数据...")
        response = requests.get(url)
        content = response.text

        # 查找净值数据
        match = re.search(r'Data_netWorthTrend\s*=\s*(\[.*?\]);', content)
        if not match:
            logger.error(f"未能找到基金 {fund_code} 的净值数据")
            return pd.DataFrame()

        data_json = json.loads(match.group(1))
        parsed_data = []
        for item in data_json:
            if item['y'] is not None:  # 确保净值有效
                dt = datetime.fromtimestamp(item['x'] / 1000)
                parsed_data.append({
                    "date": dt.strftime("%Y-%m-%d"),
                    "nav": float(item['y']),
                    "equityReturn": item.get('equityReturn', 0)  # 日收益率
                })

        df = pd.DataFrame(parsed_data)
        df['date'] = pd.to_datetime(df['date'])
        df = df.sort_values('date').reset_index(drop=True)

        logger.info(f"获取到 {len(df)} 条基金 {fund_code} 的历史数据")
        return df
    except Exception as e:
        logger.error(f"获取基金 {fund_code} 数据失败: {e}")
        return pd.DataFrame()


def calculate_technical_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """计算技术指标"""
    df = df.copy()

    # 计算移动平均线
    df['ma5'] = df['nav'].rolling(window=5).mean()
    df['ma10'] = df['nav'].rolling(window=10).mean()
    df['ma20'] = df['nav'].rolling(window=20).mean()
    df['ma30'] = df['nav'].rolling(window=30).mean()
    df['ma5_day_avg'] = df['nav'].rolling(window=5).mean()

    # 计算5日均值偏离度
    df['nav_vs_ma5'] = (df['nav'] - df['ma5']) / df['ma5'] * 100

    # 计算波动率
    df['volatility_30'] = df['nav'].pct_change().rolling(window=30).std() * np.sqrt(252) * 100

    # 计算各种收益率
    df['nav_pct_change'] = df['nav'].pct_change() * 100
    df['week_return'] = df['nav'].pct_change(periods=5) * 100
    df['month_return'] = df['nav'].pct_change(periods=22) * 100
    df['three_month_return'] = df['nav'].pct_change(periods=66) * 100
    df['six_month_return'] = df['nav'].pct_change(periods=132) * 100
    df['year_return'] = df['nav'].pct_change(periods=252) * 100

    # 计算排名（使用近似方法）
    df['rank_30day'] = df['nav'].rolling(window=30).apply(
        lambda x: pd.Series(x).rank(pct=True).iloc[-1] * 100 if len(x) == 30 else np.nan
    ) * 100
    df['rank_100day'] = df['nav'].rolling(window=100).apply(
        lambda x: pd.Series(x).rank(pct=True).iloc[-1] * 100 if len(x) == 100 else np.nan
    ) * 100

    return df


def should_buy_new(account: CustomStrategyBacktestAccount, nav: float, indicators: Dict) -> tuple[bool, str]:
    """判断是否应该新增买入"""
    # 检查是否已有持仓
    if account.shares > 0:
        return False, "已有持仓，使用加仓逻辑"

    # 检查是否可以买入（T+1规则）
    current_date = indicators['date'].strftime("%Y-%m-%d")
    if not account.can_buy_today(current_date):
        return False, "T+1规则限制，无法买入"

    # 检查5日均值条件
    ma5 = indicators.get('ma5')
    if ma5 and nav <= ma5:
        return False, f"净值未突破5日均线: {nav:.4f} <= {ma5:.4f}"

    # 检查年收益率和半年收益率
    year_return = indicators.get('year_return')
    half_year_return = indicators.get('six_month_return')
    if (year_return is not None and year_return <= 0) or (half_year_return is not None and half_year_return <= 0):
        return False, f"年收益率({year_return})或半年收益率({half_year_return})小于等于0"

    # 检查排名条件
    rank_100 = indicators.get('rank_100day')
    if rank_100 is not None and rank_100 < 20:
        return False, f"基金100日排名 {rank_100} < 20"

    rank_30 = indicators.get('rank_30day')
    if rank_30 is not None and rank_30 < 5:
        return False, f"基金30日排名 {rank_30} < 5"

    return True, "新增买入满足条件"


def should_buy_increase(account: CustomStrategyBacktestAccount, nav: float, indicators: Dict) -> tuple[bool, str]:
    """判断是否应该加仓"""
    # 检查是否已有持仓
    if account.shares <= 0:
        return False, "无持仓，使用新增逻辑"

    # 检查是否可以买入（T+1规则）
    current_date = indicators['date'].strftime("%Y-%m-%d")
    if not account.can_buy_today(current_date):
        return False, "T+1规则限制，无法买入"

    # 计算当前收益率
    current_profit_rate = account.get_holding_profit_rate(nav)
    estimated_change = indicators.get('nav_pct_change', 0)
    # 使用当前持仓收益率作为预估收益率（不叠加当日涨跌幅，因为nav已经是今日净值）
    estimated_profit_rate = current_profit_rate

    # 检查是否回撤超过阈值（比如-1%）
    if estimated_profit_rate >= -1.0:
        return False, f"回撤不达标: 预估收益率={estimated_profit_rate:.2f}% (阈值<-1.00%)"

    # 检查5日均值条件
    ma5 = indicators.get('ma5')
    if ma5 and nav <= ma5:
        return False, f"净值未突破5日均线: {nav:.4f} <= {ma5:.4f}"

    # 检查排名条件
    r100 = indicators.get('rank_100day')
    r30 = indicators.get('rank_30day')
    if r100 and (r100 < 20 or r100 > 90):
        reason = "100日排名过低" if r100 < 20 else "100日排名过高"
        return False, f"{reason}: rank_100={r100}"
    if r30 and r30 < 5:
        return False, f"30日排名过低: rank_30={r30}"

    # 检查收益率条件
    week_growth_rate = indicators.get('week_return', 0)
    month_growth_rate = indicators.get('month_return', 0)
    season_growth_rate = indicators.get('three_month_return', 0)

    # 如果所有收益率都为负，不加仓
    if week_growth_rate < 0.0 and month_growth_rate < 0.0 and season_growth_rate < 0.0:
        return False, f"全部收益率为负: 周{week_growth_rate:.2f}%, 月{month_growth_rate:.2f}%, 季{season_growth_rate:.2f}%"

    if season_growth_rate < 0.0 and (month_growth_rate < 0.0 or week_growth_rate < 0.0):
        return False, f"季度收益率为负且月/周收益率至少一个为负"

    if season_growth_rate > 0.0 and (month_growth_rate < 0.0 and week_growth_rate < 0.0):
        return False, f"季度为正但月、周均为负"

    # 特殊情况：当预估收益率低于-5%时，考虑额外加仓
    if estimated_profit_rate < -5.0:
        return True, f"大幅亏损触发额外加仓: 预估收益率={estimated_profit_rate:.2f}%"

    # 一般情况下加仓条件
    return True, "满足加仓条件"


def should_sell(account: CustomStrategyBacktestAccount, nav: float, indicators: Dict) -> tuple[bool, str]:
    """判断是否应该卖出"""
    if account.shares <= 0:
        return False, "无持仓"

    # 检查是否可以卖出（距离上次买入至少7天）
    current_date = indicators['date'].strftime("%Y-%m-%d")
    if not account.can_sell_today(current_date):
        return False, "距离上次买入不满7天，无法获得0手续费"

    # 计算当前收益率
    current_profit_rate = account.get_holding_profit_rate(nav)
    estimated_change = indicators.get('nav_pct_change', 0)
    # 使用当前持仓收益率作为预估收益率
    estimated_profit_rate = current_profit_rate

    # 获取波动率作为止盈阈值
    volatility = indicators.get('volatility_30', 0)
    stop_rate = max(volatility, 3.0)

    # 检查是否达到止盈条件
    if estimated_profit_rate > stop_rate:
        return True, f"达到止盈点: 预估收益率{estimated_profit_rate:.2f}% > 止盈点{stop_rate:.2f}%"

    # 检查其他止盈条件
    if estimated_profit_rate < 1.0:
        return False, f"收益率过低: {estimated_profit_rate:.2f}% < 1.0%"

    # 计算投资次数
    if account.total_invested > 0:
        times = account.get_asset_value(nav) / account.amount
    else:
        times = 0.0

    # 指数基金且非QDII，若仓位不重且今日上涨，立即止盈
    fund_type = '000'  # 指数基金类型
    fund_name = account.fund_name
    if (
        fund_type == '000' and
        "QDII" not in fund_name and
        times < 5.0 and
        estimated_change > 0.5 and
        estimated_profit_rate > 3.0):
        return True, f"指数基金快速止盈: 投资次数{times:.2f}<5.0, 估值增长率{estimated_change:.2f}%>0.5%, 预估收益率{estimated_profit_rate:.2f}%>3.0"

    return False, "未达到止盈条件"


def run_backtest(fund_code: str, fund_name: str, amount: float, start_date: str, end_date: str):
    """运行回测"""
    logger.info(f"开始回测基金 {fund_code} ({fund_name}), 投资金额: {amount}, 时间范围: {start_date} - {end_date}")

    # 获取历史数据
    df = get_historical_data(fund_code)
    if df.empty:
        logger.error(f"无法获取基金 {fund_code} 的历史数据")
        return None

    # 筛选时间范围内的数据
    start_dt = datetime.strptime(start_date, "%Y-%m-%d")
    end_dt = datetime.strptime(end_date, "%Y-%m-%d")
    df = df[(df['date'] >= start_dt) & (df['date'] <= end_dt)]

    if df.empty:
        logger.error(f"在指定时间范围内没有基金 {fund_code} 的数据")
        return None

    # 计算技术指标
    df = calculate_technical_indicators(df)

    # 初始化账户
    account = CustomStrategyBacktestAccount(fund_code, fund_name, amount)

    # 模拟交易
    for idx, row in df.iterrows():
        current_date = row['date'].strftime("%Y-%m-%d")
        nav = row['nav']

        # 获取当日指标
        indicators = row.to_dict()
        indicators['date'] = row['date']  # 保留日期对象用于计算间隔

        # 检查是否新增买入（无持仓时）
        if account.shares <= 0:
            should_buy_new_flag, buy_new_reason = should_buy_new(account, nav, indicators)
            if should_buy_new_flag:
                account.buy(nav, current_date, "NEW_BUY", buy_new_reason)
        else:
            # 有持仓时检查是否加仓
            should_buy_increase_flag, buy_increase_reason = should_buy_increase(account, nav, indicators)
            if should_buy_increase_flag:
                account.buy(nav, current_date, "INCREASE", buy_increase_reason)

        # 检查是否卖出
        should_sell_flag, sell_reason = should_sell(account, nav, indicators)
        if should_sell_flag:
            account.sell(nav, current_date, additional_info=sell_reason)

        # 记录每日持仓
        account.record_daily_position(current_date, nav)

    # 回测结束时，如果有持仓则全部卖出
    if account.shares > 0:
        final_row = df.iloc[-1]
        final_nav = final_row['nav']
        account.sell(final_nav, final_row['date'].strftime("%Y-%m-%d"), additional_info="回测结束强制卖出")

    # 计算最终统计
    if account.daily_positions:
        final_nav = account.daily_positions[-1]['nav']
        # 计算总收益：已实现盈利 + 未实现盈利
        total_profit = account.realized_profit + account.get_unrealized_profit(final_nav)

        # 计算最大回撤
        daily_values = [pos['asset_value'] for pos in account.daily_positions]
        cumulative_invested = [pos['total_invested'] for pos in account.daily_positions]
        daily_profits = [v - i for v, i in zip(daily_values, cumulative_invested)]

        max_value = float('-inf')
        max_drawdown = 0
        for profit in daily_profits:
            if profit > max_value:
                max_value = profit
            drawdown = max_value - profit
            if drawdown > max_drawdown:
                max_drawdown = drawdown

        # 计算资金占用情况
        daily_invested = [pos['total_invested'] for pos in account.daily_positions]
        max_occupied = max(daily_invested) if daily_invested else 0
        avg_occupied = np.mean(daily_invested) if daily_invested else 0

        # 计算买入和卖出金额
        total_buy_amount = sum(trade['amount'] for trade in account.trades if trade['action'] in ['BUY', 'NEW_BUY', 'INCREASE'])
        total_sell_amount = sum(trade['amount'] for trade in account.trades if trade['action'] == 'SELL')

        # 统计止盈次数
        sell_count = len([t for t in account.trades if t['action'] == 'SELL'])

        result = {
            'account': account,
            'total_profit': total_profit,
            'max_drawdown': max_drawdown,
            'max_occupied': max_occupied,
            'avg_occupied': avg_occupied,
            'final_asset_value': account.get_asset_value(final_nav),
            'total_invested': account.total_invested,
            'total_redeemed': account.total_redeemed,
            'total_buy_amount': total_buy_amount,
            'total_sell_amount': total_sell_amount,
            'sell_count': sell_count,
            'realized_profit': account.realized_profit,
            'unrealized_profit': account.get_unrealized_profit(final_nav)
        }

        return result

    return None


def save_backtest_report(result: Dict, fund_code: str, fund_name: str, amount: float):
    """保存回测报告"""
    reports_dir = os.path.join(root_dir, "reports")
    os.makedirs(reports_dir, exist_ok=True)

    # 生成报告内容
    report_content = f"""# 基金 {fund_code} ({fund_name}) 自定义策略回测报告

## 基本信息
- 基金代码: {fund_code}
- 基金名称: {fund_name}
- 每次投资金额: {amount:,.2f} 元
- 回测时间: 2025-01-01 至 2025-12-31

## 回测结果
- 总收益金额: {result['total_profit']:,.2f} 元
  - 已实现盈利: {result['realized_profit']:,.2f} 元
  - 未实现盈利: {result['unrealized_profit']:,.2f} 元
- 最大回撤: {result['max_drawdown']:,.2f} 元
- 最大占用金额: {result['max_occupied']:,.2f} 元
- 平均占用金额: {result['avg_occupied']:,.2f} 元
- 总买入金额: {result['total_buy_amount']:,.2f} 元
- 总止盈金额: {result['total_sell_amount']:,.2f} 元
- 止盈次数: {result['sell_count']} 次
- 最终资产价值: {result['final_asset_value']:,.2f} 元
- 总投入金额: {result['total_invested']:,.2f} 元
- 总赎回金额: {result['total_redeemed']:,.2f} 元

## 每次止盈记录
"""

    # 添加每次止盈记录
    for i, record in enumerate(result['account'].sell_profit_records, 1):
        report_content += f"- 第{i}次止盈: {record['date']} - 卖出金额: {record['sold_amount']:,.2f}, 成本: {record['cost']:,.2f}, 盈利: {record['profit']:,.2f}, 原因: {record['additional_info']}\n"

    report_content += "\n## 交易记录\n"

    for trade in result['account'].trades:
        if trade['action'] == 'SELL':
            realized_profit = trade.get('realized_profit', 0)
            report_content += f"- {trade['date']}: {trade['action']} - 金额: {trade['amount']:,.2f}, 净值: {trade['nav']:.4f}, 盈利: {realized_profit:.2f}, 原因: {trade['additional_info']}\n"
        else:
            report_content += f"- {trade['date']}: {trade['action']} - 金额: {trade['amount']:,.2f}, 净值: {trade['nav']:.4f}, 原因: {trade['additional_info']}\n"

    # 保存报告
    report_filename = f"custom_strategy_backtest_{fund_code}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
    report_path = os.path.join(reports_dir, report_filename)

    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(report_content)

    logger.info(f"回测报告已保存至: {report_path}")


def main():
    # 设置参数
    fund_code = "008888"
    fund_name = "华夏国证半导体芯片ETF联接C"
    amount = 50000.0
    start_date = "2025-01-01"
    end_date = "2025-12-31"

    # 运行回测
    result = run_backtest(fund_code, fund_name, amount, start_date, end_date)

    if result:
        # 打印结果摘要
        print("\n" + "="*60)
        print("回测结果摘要")
        print("="*60)
        print(f"基金代码: {fund_code}")
        print(f"基金名称: {fund_name}")
        print(f"每次投资金额: {amount:,.2f} 元")
        print(f"总收益金额: {result['total_profit']:,.2f} 元")
        print(f"  - 已实现盈利: {result['realized_profit']:,.2f} 元")
        print(f"  - 未实现盈利: {result['unrealized_profit']:,.2f} 元")
        print(f"最大回撤: {result['max_drawdown']:,.2f} 元")
        print(f"最大占用金额: {result['max_occupied']:,.2f} 元")
        print(f"平均占用金额: {result['avg_occupied']:,.2f} 元")
        print(f"总买入金额: {result['total_buy_amount']:,.2f} 元")
        print(f"总止盈金额: {result['total_sell_amount']:,.2f} 元")
        print(f"止盈次数: {result['sell_count']} 次")
        print(f"最终资产价值: {result['final_asset_value']:,.2f} 元")
        print(f"总投入金额: {result['total_invested']:,.2f} 元")
        print(f"总赎回金额: {result['total_redeemed']:,.2f} 元")
        print("="*60)

        # 保存详细报告
        save_backtest_report(result, fund_code, fund_name, amount)

        # 打印每次止盈记录
        print("\n每次止盈记录:")
        for i, record in enumerate(result['account'].sell_profit_records, 1):
            print(f"  第{i}次止盈: {record['date']} - 卖出: {record['sold_amount']:.2f}, 成本: {record['cost']:.2f}, 盈利: {record['profit']:.2f}, 原因: {record['additional_info']}")

        # 打印交易记录
        print("\n交易记录:")
        for trade in result['account'].trades:
            if trade['action'] == 'SELL':
                realized_profit = trade.get('realized_profit', 0)
                print(f"  {trade['date']}: {trade['action']} - 金额: {trade['amount']:,.2f}, "
                      f"净值: {trade['nav']:.4f}, 盈利: {realized_profit:.2f}, 原因: {trade['additional_info']}")
            else:
                print(f"  {trade['date']}: {trade['action']} - 金额: {trade['amount']:,.2f}, "
                      f"净值: {trade['nav']:.4f}, 原因: {trade['additional_info']}")
    else:
        print("回测失败")


if __name__ == "__main__":
    main()
