import requests
import re
import json
import logging
import numpy as np
from datetime import datetime, timedelta
from typing import List, Dict, Optional

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- 配置参数 ---
FUND_CODE = "011707"  # 东吴优化配置C
FUND_NAME = "东吴优化配置C"
TARGET_AMOUNT = 50000.0  # 单个计划目标金额
HQB_RATIO_THRESHOLD = 10.0 # 活期宝占比阈值 (模拟设为 100 以忽略，或设为 0 以触发风控? 用户没给 HQB 数据，这里默认忽略此风控)

# --- 类定义 ---

class ShareBatch:
    def __init__(self, amount: float, price: float, date: str):
        self.amount = amount  # 份额
        self.cost_price = price
        self.buy_date = date
        self.initial_value = amount * price

    def get_age(self, current_date: str) -> int:
        d1 = datetime.strptime(self.buy_date, "%Y-%m-%d")
        d2 = datetime.strptime(current_date, "%Y-%m-%d")
        return (d2 - d1).days

class Account:
    def __init__(self, name: str, period_type: int, period_value: int):
        self.name = name
        self.period_type = period_type # 1=Week, 3=Month
        self.period_value = period_value
        self.shares: List[ShareBatch] = []
        self.cash_invested = 0.0
        self.cash_redeemed = 0.0
        self.trades: List[Dict] = []
        self.last_buy_date: Optional[str] = None

    @property
    def total_shares(self) -> float:
        return sum(s.amount for s in self.shares)

    @property
    def total_cost(self) -> float:
        return sum(s.initial_value for s in self.shares)

    def get_asset_value(self, current_nav: float) -> float:
        return self.total_shares * current_nav

    def get_profit_rate(self, current_nav: float) -> float:
        if self.total_shares == 0 or self.total_cost == 0:
            return 0.0
        return (self.get_asset_value(current_nav) - self.total_cost) / self.total_cost

    def buy(self, amount: float, nav: float, date: str):
        if amount <= 0: return
        shares_count = amount / nav
        batch = ShareBatch(shares_count, nav, date)
        self.shares.append(batch)
        self.cash_invested += amount
        self.last_buy_date = date
        self.trades.append({
            "date": date, "type": "BUY", "amount": amount, "price": nav, "shares": shares_count
        })

    def redeem_all(self, nav: float, date: str, min_age: int = 7) -> float:
        redeemable_indices = []
        total_redeem_shares = 0.0
        
        # 找出满足持有期要求的份额
        for i, batch in enumerate(self.shares):
            if batch.get_age(date) >= min_age:
                redeemable_indices.append(i)
                total_redeem_shares += batch.amount
        
        if total_redeem_shares == 0:
            return 0.0

        redeem_value = total_redeem_shares * nav
        # C类 >= 7天 免赎回费 (模拟)
        net_amount = redeem_value
        self.cash_redeemed += net_amount
        
        # 从后往前删除，避免索引错位
        for i in sorted(redeemable_indices, reverse=True):
            batch = self.shares.pop(i)
            self.trades.append({
                "date": date, "type": "SELL", "amount": net_amount, "price": nav, "shares": batch.amount
            })
            
        return net_amount

# --- 数据获取 ---

def get_history_data():
    url = f"http://fund.eastmoney.com/pingzhongdata/{FUND_CODE}.js"
    try:
        logger.info(f"Downloading data for {FUND_CODE}...")
        response = requests.get(url)
        content = response.text
        
        # 提取净值
        match = re.search(r'Data_netWorthTrend\s*=\s*(\[.*?\]);', content)
        if not match:
            logger.error("Regex match failed for netWorthTrend")
            return None

        data_json = json.loads(match.group(1))
        parsed_data = []
        for item in data_json:
            dt = datetime.fromtimestamp(item['x'] / 1000)
            date_str = dt.strftime('%Y-%m-%d')
            parsed_data.append({"date": date_str, "nav": float(item['y'])})
            
        parsed_data.sort(key=lambda x: x['date'])
        logger.info(f"Got {len(parsed_data)} data points. Range: {parsed_data[0]['date']} to {parsed_data[-1]['date']}")
        return parsed_data
    except Exception as e:
        logger.error(f"Error getting history: {e}")
        return None

# --- 回测逻辑 ---

def calculate_ma5(nav_values, index):
    if index < 4: return None
    return sum(nav_values[index-4:index+1]) / 5.0

def get_return(prices, index, days):
    if index < days: return 0.0
    # Return = (Current - Old) / Old
    return (prices[index] - prices[index-days]) / prices[index-days]

def run_backtest():
    history_data = get_history_data()
    if not history_data: return

    # 初始化账户 (33个计划)
    accounts = []
    # 5个周定投 (周一=1 ... 周五=5)
    for wd in range(1, 6):
        accounts.append(Account(f"Weekly_{wd}", 1, wd))
    # 28个月定投 (1号 ... 28号)
    for day in range(1, 29):
        accounts.append(Account(f"Monthly_{day}", 3, day))

    logger.info(f"Initialized {len(accounts)} plans.")

    # 预计算指标所需的序列
    navs = [d['nav'] for d in history_data]
    dates = [d['date'] for d in history_data]
    
    # 波动率计算窗口 (252天)
    vol_window = 252

    # 统计数据
    daily_stats = []

    for i in range(len(history_data)):
        current_date = dates[i]
        current_nav = navs[i]
        dt_obj = datetime.strptime(current_date, "%Y-%m-%d")
        wd = dt_obj.isoweekday()
        dom = dt_obj.day

        # 1. 计算指标
        ma5 = calculate_ma5(navs, i)
        
        # 收益率 (用于最强风控)
        # 假设: 半年=120交易日, 年=240交易日
        half_year_return = get_return(navs, i, 120) * 100
        year_return = get_return(navs, i, 240) * 100
        
        # 波动率 (用于止盈)
        volatility = 0.0
        if i >= vol_window:
            # 计算过去252天的对数收益率标准差 * sqrt(252)
            # 简化: 使用普通收益率标准差
            # log_returns = np.diff(np.log(navs[i-vol_window:i+1]))
            # volatility = np.std(log_returns) * np.sqrt(252) * 100
            # 这里的 redeem.py 使用的是 fund_info.volatility (通常是近1年波动率)
            # 我们这里实时计算 rolling volatility
            window_navs = navs[i-vol_window:i+1]
            if len(window_navs) > 1:
                log_rets = np.diff(np.log(window_navs))
                volatility = np.std(log_rets) * np.sqrt(252) * 100
        else:
            volatility = 10.0 # 默认值，如果数据不足

        # 2. 遍历账户
        for acc in accounts:
            asset_val = acc.get_asset_value(current_nav)
            
            # --- 加仓逻辑 (Increase) ---
            # 1. 判断是否是定投日
            is_scheduled = False
            if acc.period_type == 1: # Weekly
                if wd == acc.period_value: is_scheduled = True
            elif acc.period_type == 3: # Monthly
                if dom == acc.period_value: is_scheduled = True
            
            # 2. 如果是定投日，尝试买入
            if is_scheduled:
                # 目标市值填补逻辑 (Asset < Target)
                # 如果当前资产 < 50000，则尝试买入差额
                # 但要经过风控检查
                gap = TARGET_AMOUNT - asset_val
                
                # 2.1 基础检查: 是否需要买入
                # 如果 gap <= 0，且没有其他强力买入信号(如10倍加仓)，则不买
                # increase.py 中只要 times (asset/amount) 没被拦截，且 est_profit < -1.0，就可以买
                # 但为了模拟 "每个5w" 的目标感，我们使用 Gap Filling 策略，
                # 同时允许在亏损时补仓 (Martingale) ?
                # 鉴于 "Asset 5k < Fund Amount 10k" 的 Context，我们严格执行 Gap Filling
                # 即: 只有当资产不足 5w 时才买入 (或者亏损严重时?)
                # 暂定: Gap > 0 才买入。
                
                if gap > 100.0: # 最小买入金额
                    can_buy = True
                    reason = ""

                    # [风控1] 最强风控 (Strict Bear Protection)
                    # 半年收益率 <= 0 或 年收益率 <= 0 -> 停止
                    if half_year_return <= 0:
                        can_buy = False; reason = f"半年收益率({half_year_return:.2f}%)<=0"
                    elif year_return <= 0:
                        can_buy = False; reason = f"年收益率({year_return:.2f}%)<=0"
                    
                    # [风控2] 5日均线守卫 (MA5 Gate)
                    # NAV > MA5 -> 停止 (趋势向上不追高)
                    # 注意: Weekly/Monthly 总是检查 (bypass_ma5=False)
                    if can_buy and ma5 is not None and current_nav > ma5:
                        can_buy = False; reason = f"NAV({current_nav}) > MA5({ma5:.4f})"

                    # [风控3] 预估收益率守卫 (Profit Rate Guard)
                    # 只有当预估收益率 < -1.0% 时才允许加仓 (逢低买入)
                    # 首次定投 (asset=0) 除外? increase.py logic: if not first and est > -1.0 -> revoke
                    # 这里 asset < target (gap>0)，不算 strict first investment (unless asset=0)
                    # increase.py: times == 1.0 (Full?) -> First? 逻辑有点乱
                    # 我们采用: 如果 Asset > 0 (非首次)，则必须 EstProfit < -1.0
                    if can_buy and asset_val > 0:
                        # Est Profit Rate ~= Current Profit Rate + Est Change (using 0 here as we use close nav)
                        # Backtest uses Close NAV as "Current", so Est Change is 0 relative to Close.
                        # Wait, backtest usually runs on Close.
                        # Real-time logic uses Est NAV. Backtest uses Close.
                        # So Est Profit Rate = (Close - Cost) / Cost
                        est_profit_rate = acc.get_profit_rate(current_nav) * 100
                        if est_profit_rate > -1.0:
                            can_buy = False; reason = f"收益率({est_profit_rate:.2f}%) > -1.0%"

                    # [风控4] 连续购买守卫
                    # 昨/今已买 -> 停止。
                    if can_buy and acc.last_buy_date:
                        last_dt = datetime.strptime(acc.last_buy_date, "%Y-%m-%d")
                        days_diff = (dt_obj - last_dt).days
                        if days_diff <= 1:
                            can_buy = False; reason = "连续购买"

                    if can_buy:
                        # 执行买入
                        buy_amt = gap
                        # 确保不买碎股? 任意金额都行
                        acc.buy(buy_amt, current_nav, current_date)
                        # logger.info(f"{current_date} {acc.name} BUY {buy_amt:.2f} @ {current_nav}")

            # --- 止盈逻辑 (Redeem) ---
            # 1. 检查是否有持仓
            if acc.total_shares > 0:
                # 2. 计算止盈点
                stop_rate = max(volatility, 3.0)
                profit_rate = acc.get_profit_rate(current_nav) * 100
                
                # 3. 检查条件
                # (1) 收益率 > 止盈点
                # (2) NAV < MA5 (趋势向下)
                if profit_rate > stop_rate:
                     if ma5 is not None and current_nav < ma5:
                         # 满足止盈条件
                         amt = acc.redeem_all(current_nav, current_date, min_age=7)
                         if amt > 0:
                             pass
                             # logger.info(f"{current_date} {acc.name} SELL {amt:.2f} (Profit: {profit_rate:.2f}%, Vol: {volatility:.2f}%)")

        # 3. 每日结算 (Global Stats)
        total_asset = sum(acc.get_asset_value(current_nav) for acc in accounts)
        total_invested = sum(acc.cash_invested for acc in accounts)
        total_redeemed = sum(acc.cash_redeemed for acc in accounts)
        net_invested = total_invested - total_redeemed
        accumulated_profit = total_asset + total_redeemed - total_invested
        
        daily_stats.append({
            "date": current_date,
            "net_invested": net_invested,
            "total_asset": total_asset,
            "accumulated_profit": accumulated_profit,
            "nav": current_nav
        })

    # --- 分析结果 ---
    analyze_results(daily_stats, accounts)

def analyze_results(stats, accounts):
    if not stats: return

    # 1. 最大回撤 (Max Drawdown)
    # 基于累计收益 (Accumulated Profit) 还是 净值 (NAV)? 
    # 投资组合的最大回撤通常指 累计收益曲线 的回撤
    profit_curve = [d['accumulated_profit'] for d in stats]
    max_dd_amt = 0.0
    peak = -float('inf')
    for p in profit_curve:
        if p > peak: peak = p
        dd = peak - p
        if dd > max_dd_amt: max_dd_amt = dd

    # 2. 资金占用
    invested_curve = [d['net_invested'] for d in stats]
    max_occupied = max(invested_curve)
    avg_occupied = sum(invested_curve) / len(invested_curve)

    # 3. 年化收益率 (XIRR)
    # 收集所有现金流
    flows = [] # (date, amount)
    for acc in accounts:
        for t in acc.trades:
            d = datetime.strptime(t['date'], "%Y-%m-%d")
            amt = -t['amount'] if t['type'] == 'BUY' else t['amount']
            flows.append((d, amt))
    
    # 添加最终市值
    last_date = datetime.strptime(stats[-1]['date'], "%Y-%m-%d")
    final_value = stats[-1]['total_asset']
    flows.append((last_date, final_value))
    
    xirr_val = xirr(flows)
    
    # 4. 年度收益
    # 按年份聚合
    yearly_stats = {}
    trade_counts = {} # year -> count
    
    for d in stats:
        year = d['date'][:4]
        if year not in yearly_stats:
            yearly_stats[year] = {"start": d, "end": d}
        else:
            yearly_stats[year]["end"] = d
            
    # Count trades
    for acc in accounts:
        for t in acc.trades:
            y = t['date'][:4]
            trade_counts[y] = trade_counts.get(y, 0) + 1
            
    print("\n" + "="*80)
    print(f"回测报告: {FUND_NAME} ({FUND_CODE})")
    print(f"策略: 33个计划 (5周+28月), 单个目标 {TARGET_AMOUNT}, 逢低填补(Gap Filling)")
    print(f"时间范围: {stats[0]['date']} 至 {stats[-1]['date']}")
    print("-" * 80)
    print(f"【整体表现】")
    print(f"最终总资产:      {final_value:,.2f} 元")
    print(f"累计总盈利:      {stats[-1]['accumulated_profit']:,.2f} 元")
    print(f"最大资金占用:    {max_occupied:,.2f} 元")
    print(f"平均资金占用:    {avg_occupied:,.2f} 元")
    print(f"最大回撤金额:    {max_dd_amt:,.2f} 元")
    # Max Drawdown Ratio (approx)
    max_dd_ratio = max_dd_amt / max_occupied if max_occupied > 0 else 0.0
    print(f"最大回撤比率:    {max_dd_ratio*100:.2f}% (相对于最大投入)")
    print(f"年化收益率(XIRR): {xirr_val*100:.2f}%")
    print("-" * 80)
    print(f"【年度明细】")
    print(f"{'年份':<6} | {'盈利金额':<15} | {'年末资产':<15} | {'平均占用资金':<15} | {'收益率':<10} | {'交易次数':<8}")
    
    sorted_years = sorted(yearly_stats.keys())
    accumulated_prev = 0.0
    
    for year in sorted_years:
        start_data = yearly_stats[year]["start"]
        end_data = yearly_stats[year]["end"]
        
        current_accumulated = end_data['accumulated_profit']
        year_profit = current_accumulated - accumulated_prev
        accumulated_prev = current_accumulated
        
        # Calculate avg capital for this year
        year_invs = [d['net_invested'] for d in stats if d['date'].startswith(year)]
        year_avg_cap = sum(year_invs) / len(year_invs) if year_invs else 0
        
        if year_avg_cap > 0:
            yield_rate = f"{year_profit / year_avg_cap * 100:.2f}%"
        elif year_avg_cap < 0:
            yield_rate = "FreeRoll" # Negative capital means we took out more than put in
        else:
            yield_rate = "0.00%"
            
        t_count = trade_counts.get(year, 0)
        
        print(f"{year:<6} | {year_profit:>12,.2f} | {end_data['total_asset']:>12,.2f} | {year_avg_cap:>12,.2f} | {yield_rate:>10} | {t_count:>8}")
    
    print("="*80)

def xirr(transactions):
    """
    计算XIRR
    transactions: list of (datetime, amount). amount < 0 for investment, > 0 for return.
    """
    if not transactions: return 0.0
    dates = [t[0] for t in transactions]
    amounts = [t[1] for t in transactions]
    
    if sum(amounts) == 0: return 0.0
    if all(a >= 0 for a in amounts) or all(a <= 0 for a in amounts): return 0.0
    
    min_date = min(dates)
    # Normalize dates to days
    days = [(d - min_date).days for d in dates]
    
    # Newton-Raphson method
    rate = 0.1
    for _ in range(100):
        f_val = 0.0
        df_val = 0.0
        for i in range(len(amounts)):
            d = days[i] / 365.0
            term = amounts[i] / ((1 + rate) ** d)
            f_val += term
            df_val -= term * d / (1 + rate)
        
        if abs(f_val) < 1e-6: return rate
        if df_val == 0: return rate
        new_rate = rate - f_val / df_val
        if abs(new_rate - rate) < 1e-6: return new_rate
        rate = new_rate
        
    return rate

if __name__ == "__main__":
    run_backtest()
