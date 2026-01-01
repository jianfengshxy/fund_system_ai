
import requests
import re
import json
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Tuple, Optional
import math
import collections

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- 配置参数 ---
# 使用嘉实黄金(QDII-LOF) 160719 模拟，成立于2011年，能覆盖2012-2018熊市
FUND_CODE = "160719"  
FUND_NAME = "嘉实黄金(QDII-LOF) [模拟熊市]"
START_DATE = "2012-01-01"
END_DATE = "2018-12-31"  # 黄金大熊市周期 (2011高点 - 2015底 - 2018震荡)
INVEST_AMOUNT = 50000.0  # 每次定投金额
INITIAL_CASH = 100000000.0  # 充足本金

# 费率配置 (模拟C类)
# 虽然160719是A类/LOF，但为了测试策略效果，我们假设它是C类(0申购费，7天免赎回)
# 这样能纯粹测试策略逻辑，不受老基金高费率干扰
REDEEM_FEE_7D = 0.015
REDEEM_FEE_OLD = 0.0

# --- 数据获取与处理 ---

def get_fund_data(fund_code: str, start_date: str, end_date: str) -> List[Dict]:
    """获取基金历史净值数据"""
    url = f"http://fund.eastmoney.com/pingzhongdata/{fund_code}.js"
    try:
        response = requests.get(url)
        response.raise_for_status()
        content = response.text
        
        # 提取单位净值 Data_netWorthTrend
        match = re.search(r'Data_netWorthTrend\s*=\s*(\[.*?\]);', content)
        if not match:
            logger.error("无法解析净值数据")
            return []
            
        data_json = json.loads(match.group(1))
        # data_json 格式: [{"x": timestamp, "y": nav, "equityReturn": ...}, ...]
        
        # 提取累计净值 Data_ACWorthTrend (用于计算复权收益，或者直接用单位净值如果分红再投? 
        # 通常回测简单起见用单位净值+分红处理，或者复权净值。
        # 这里简化：使用单位净值，假设C类不分红或分红体现在净值中(积累)。
        # 黄金ETF联接C通常不分红或分红很少。直接用单位净值y)
        
        parsed_data = []
        for item in data_json:
            dt = datetime.fromtimestamp(item['x'] / 1000)
            date_str = dt.strftime('%Y-%m-%d')
            if start_date <= date_str <= end_date:
                parsed_data.append({
                    "date": date_str,
                    "nav": float(item['y'])
                })
        
        # 按日期排序
        parsed_data.sort(key=lambda x: x['date'])
        return parsed_data
        
    except Exception as e:
        logger.error(f"获取数据失败: {e}")
        return []

# --- 辅助计算 ---

def calculate_ma(values: List[float], window: int) -> Optional[float]:
    if len(values) < window:
        return None
    return sum(values[-window:]) / window

def calculate_volatility(returns: List[float], window: int = 20) -> Optional[float]:
    """计算年化波动率"""
    if len(returns) < window:
        return None
    # 取最近window个收益率
    recent_returns = returns[-window:]
    mean_ret = sum(recent_returns) / window
    variance = sum((r - mean_ret) ** 2 for r in recent_returns) / (window - 1)
    std_dev = math.sqrt(variance)
    # 年化 (假设252个交易日)
    annualized_vol = std_dev * math.sqrt(252) * 100  # 百分比
    return annualized_vol

def xirr(cashflows: list[tuple[datetime, float]]) -> float | None:
    """计算XIRR"""
    if not cashflows:
        return None
    cashflows_sorted = sorted(cashflows, key=lambda x: x[0])
    t0 = cashflows_sorted[0][0]
    amounts = [cf for _, cf in cashflows_sorted]
    if not (any(a < 0 for a in amounts) and any(a > 0 for a in amounts)):
        return None
    
    times = [((d - t0).days) / 365.0 for d, _ in cashflows_sorted]
    
    def npv(rate: float) -> float:
        return sum(a / ((1.0 + rate) ** t) for a, t in zip(amounts, times))
    
    def d_npv(rate: float) -> float:
        return sum(-t * a / ((1.0 + rate) ** (t + 1.0)) for a, t in zip(amounts, times) if t != 0)
    
    try:
        r = 0.1
        for _ in range(100):
            f = npv(r)
            fp = d_npv(r)
            if fp == 0:
                return None
            r_next = r - f / fp
            if abs(r_next - r) < 1e-6:
                return r_next
            r = r_next
    except:
        return None
    return None

# --- 回测类定义 ---

class ShareBatch:
    def __init__(self, amount: float, price: float, date: str):
        self.amount = amount  # 份数
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
        self.period_type = period_type  # 1=Weekly, 3=Monthly
        self.period_value = period_value # 1-5 (Mon-Fri) or 1-28
        self.shares: List[ShareBatch] = []
        self.cash_invested = 0.0
        self.cash_redeemed = 0.0
        self.total_profit = 0.0
        self.trades: List[Dict] = [] # Log trades
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
        if self.total_shares == 0:
            return 0.0
        # 收益率 = (当前市值 - 总成本) / 总成本
        # 注意: increase.py 使用 (asset - cost) / cost
        # 这里如果成本为0(已全赎回), 收益率为0
        if self.total_cost == 0:
             return 0.0
        return (self.get_asset_value(current_nav) - self.total_cost) / self.total_cost

    def buy(self, amount: float, nav: float, date: str):
        # 0申购费
        shares_count = amount / nav
        batch = ShareBatch(shares_count, nav, date)
        self.shares.append(batch)
        self.cash_invested += amount
        self.last_buy_date = date
        self.trades.append({
            "date": date,
            "type": "BUY",
            "amount": amount,
            "price": nav,
            "shares": shares_count,
            "fee": 0.0
        })

    def redeem(self, nav: float, date: str, min_age: int = 7) -> float:
        """赎回满足持有期要求的份额"""
        # 筛选满足条件的份额
        redeemable_indices = []
        total_redeem_shares = 0.0
        
        for i, batch in enumerate(self.shares):
            if batch.get_age(date) >= min_age:
                redeemable_indices.append(i)
                total_redeem_shares += batch.amount
        
        if total_redeem_shares == 0:
            return 0.0
            
        # 执行赎回
        redeem_value = total_redeem_shares * nav
        # 费率: >=7天 0% (假设C类)
        fee = 0.0 # 假设满足min_age=7就是0费率
        net_amount = redeem_value - fee
        
        self.cash_redeemed += net_amount
        
        # 移除已赎回的份额 (倒序移除)
        for i in sorted(redeemable_indices, reverse=True):
            batch = self.shares.pop(i)
            # 记录交易
            self.trades.append({
                "date": date,
                "type": "SELL",
                "amount": net_amount, # 实际到手
                "price": nav,
                "shares": batch.amount,
                "fee": fee
            })
            
        return net_amount

# --- 主逻辑 ---

def run_backtest():
    # 1. 初始化账户
    accounts = []
    # 28个日定投 (1-28号) -> Period Type 3
    for day in range(1, 29):
        accounts.append(Account(f"Monthly_{day}", 3, day))
    # 5个周定投 (Mon-Fri -> 1-5) -> Period Type 1
    for weekday in range(1, 6):
        accounts.append(Account(f"Weekly_{weekday}", 1, weekday))
        
    # 2. 获取数据
    data = get_fund_data(FUND_CODE, START_DATE, END_DATE)
    if not data:
        print("无数据")
        return

    # 预处理指标 (MA5, Volatility)
    # 需要完整的历史来计算初始指标，但这里从START_DATE开始回测，
    # 假设START_DATE前有数据? 
    # API获取的数据通常包含START_DATE前的数据吗？
    # 如果get_fund_data只返回范围内数据，计算初期指标会有问题。
    # 应该获取更早的数据。
    # 修改 get_fund_data 获取 2011-08-01 开始的数据用于预热 (嘉实黄金成立于2011-08)
    pre_start_date = "2011-08-01"
    full_data = get_fund_data(FUND_CODE, pre_start_date, END_DATE)
    
    # 建立日期索引
    date_map = {d['date']: i for i, d in enumerate(full_data)}
    nav_values = [d['nav'] for d in full_data]
    returns = []
    for i in range(1, len(nav_values)):
        r = (nav_values[i] - nav_values[i-1]) / nav_values[i-1]
        returns.append(r)
    # returns[i] 是 date[i+1] 的收益率? No, returns[i-1] 对应 date[i] vs date[i-1]
    # returns 长度 len-1. returns[k] = (nav[k+1]-nav[k])/nav[k]
    
    # 指标缓存
    ma5_cache = {} # date -> ma5
    vol_cache = {} # date -> volatility
    
    for i in range(len(full_data)):
        date = full_data[i]['date']
        # MA5: Avg(T-5 ... T-1) ? Increase.py logic uses 'nav_5day_avg'.
        # 通常这是基于昨天收盘的5日均线。
        # 所以在Day T，我们看 Avg(Nav[T-5]...Nav[T-1]).
        if i >= 5:
            ma5 = sum(nav_values[i-5:i]) / 5.0
            ma5_cache[date] = ma5
        else:
            ma5_cache[date] = None
            
        # Volatility: 20-day annualized. Based on T-20...T-1 returns.
        if i >= 21:
            # returns索引: i对应nav[i]. return[i-1]是nav[i]的收益.
            # 最近20个收益: returns[i-20 : i]
            hist_returns = returns[i-20:i]
            if len(hist_returns) == 20:
                vol = calculate_volatility(hist_returns)
                vol_cache[date] = vol
            else:
                vol_cache[date] = None
        else:
            vol_cache[date] = None

    # 开始回测循环
    # 仅遍历在 START_DATE - END_DATE 范围内的数据
    backtest_data = [d for d in full_data if START_DATE <= d['date'] <= END_DATE]
    
    print(f"开始回测: {START_DATE} 至 {END_DATE}, 交易日数量: {len(backtest_data)}")
    
    # 全局统计
    total_invested_history = [] # (date, amount)
    daily_records = []
    occupied_capital_curve = []
    max_loss_amount = 0.0
    
    # Debug stats
    rank_low_skip = 0
    rank_high_skip = 0
    rank_ok_buy = 0
    trend_skip = 0
    bear_prot_skip = 0
    ma5_skip = 0
    profit_skip = 0
    
    for i, day_data in enumerate(backtest_data):
        current_date = day_data['date']
        current_nav = day_data['nav']
        current_dt = datetime.strptime(current_date, "%Y-%m-%d")
        
        # 指标
        ma5 = ma5_cache.get(current_date)
        vol = vol_cache.get(current_date)
        
        # 星期几 (1=Mon, 7=Sun)
        isoweekday = current_dt.isoweekday()
        day_of_month = current_dt.day
        
        # --- 计算动态收益率指标 (模拟 increase.py 中的 week/month/season_return) ---
        # 使用 full_data 和 date_map 来获取历史净值
        full_idx = date_map.get(current_date)
        
        def get_return(days):
            if full_idx is not None and full_idx >= days:
                prev_nav = full_data[full_idx - days]['nav']
                if prev_nav > 0:
                    return (current_nav - prev_nav) / prev_nav
            return 0.0

        week_return = get_return(5)   # 5交易日
        month_return = get_return(20) # 20交易日
        season_return = get_return(60) # 60交易日
        year_return = get_return(250) # 250交易日 (年线)
        
        # 遍历所有账户
        for acc in accounts:
            # --- 1. 定投检查 (Increase Logic) ---
            should_invest = False
            
            # 基础定投日检查
            is_scheduled = False
            if acc.period_type == 3: # Monthly
                if acc.period_value == day_of_month:
                    is_scheduled = True
                # 延期检查逻辑优化: 
                # 检查本月是否已投
                last_buy_dt = datetime.strptime(acc.last_buy_date, "%Y-%m-%d") if acc.last_buy_date else None
                if last_buy_dt and last_buy_dt.year == current_dt.year and last_buy_dt.month == current_dt.month:
                    is_scheduled = False # 本月已投
                elif day_of_month >= acc.period_value:
                    # 如果还没有投，且今天 >= 定投日，尝试投
                    # 但必须确保没有重复投（上面check了last_buy_dt）
                    # 且如果是每月一次，只投一次。
                    is_scheduled = True
                
            elif acc.period_type == 1: # Weekly
                if acc.period_value == isoweekday:
                    is_scheduled = True
                
            if is_scheduled:
                # ---------------------------------------------------------
                # 策略逻辑 (参考 increase.py)
                # ---------------------------------------------------------
                
                # 1. 计算关键指标 (Key Indicators)
                
                # 1.1 收益率 (Week, Month, Season)
                # 定义: week=5days, month=20days, season=60days (approx trading days)
                week_return = get_return(5)
                month_return = get_return(20)
                season_return = get_return(60)
                half_year_return = get_return(125)
                year_return = get_return(250)
                
                week_growth_rate = week_return * 100
                month_growth_rate = month_return * 100
                season_growth_rate = season_return * 100
                half_year_growth_rate = half_year_return * 100
                year_growth_rate = year_return * 100
                
                # 1.2 预估收益率 (Estimated Profit Rate)
                # increase.py: estimated_profit_rate = current_profit_rate + estimated_change
                # In backtest: ((NAV_today - AvgCost) / AvgCost) * 100
                estimated_profit_rate = 0.0
                if acc.total_shares > 0:
                    holding_cost = acc.total_cost / acc.total_shares
                    estimated_profit_rate = ((current_nav - holding_cost) / holding_cost) * 100
                
                # 1.3 资产倍数 (Times)
                # times = 资产市值 / 定投金额
                current_asset_value = acc.total_shares * current_nav
                times = current_asset_value / INVEST_AMOUNT if INVEST_AMOUNT > 0 else 0.0
                
                # 1.4 MA5 均线
                # Already calculated as 'ma5' variable above
                
                # ---------------------------------------------------------
                # 2. 风控检查 (Revoke Checks)
                # ---------------------------------------------------------
                can_buy = True
                skip_reason = ""
                
                # 2.0 首次定投例外 (First Investment Exception)
                is_first_investment = (times <= 1.0) and (acc.period_type != 3) # Strict interpretation of line 167
                
                # 2.1 月/周定投延期检查 (Implicitly handled)
                
                # 2.2 MA5 均线守卫 (MA5 Gate)
                bypass_ma5 = (acc.period_type != 3) and (times <= 1)
                gate_ok = True
                if ma5 is not None and current_nav <= ma5:
                    gate_ok = False
                
                if not gate_ok:
                    if bypass_ma5:
                        pass # Allowed
                    else:
                        if acc.period_type == 3 and times <= 1:
                            pass # Allowed (Line 167)
                        else:
                            can_buy = False
                            skip_reason = "MA5 Guard (Nav <= MA5)"
                            
                # 2.3 同基金不连续守卫 (No Consecutive Buys)
                # Logic: If bought yesterday, don't buy today.
                if can_buy:
                    if acc.last_buy_date:
                        last_buy_dt = datetime.strptime(acc.last_buy_date, "%Y-%m-%d")
                        if (current_dt - last_buy_dt).days <= 1: 
                             # Check if it was really the previous trading day
                             if i > 0 and backtest_data[i-1]['date'] == acc.last_buy_date:
                                 can_buy = False
                                 skip_reason = "Consecutive Buy Guard"

                # 2.4 预估收益率检查 (Profit Rate Check)
                # increase.py: if not is_first_investment and estimated_profit_rate > -1.0: revoke
                if can_buy:
                    # strict check: times==1 is exempted
                    if (not (times <= 1.0)) and estimated_profit_rate > -1.0:
                        can_buy = False
                        skip_reason = f"Profit Rate > -1.0% ({estimated_profit_rate:.2f}%)"

                # 2.5 排名检查 (Rank Checks)
                # Logic: Rank of current NAV in last N days (including today).
                
                if can_buy:
                    # Rank 100
                    if full_idx >= 99:
                        # Last 100 days including today
                        navs_100 = [full_data[full_idx-k]['nav'] for k in range(100)]
                        navs_100.sort()
                        rank_100 = navs_100.index(current_nav) + 1
                        
                        if rank_100 < 20:
                            can_buy = False
                            skip_reason = f"Rank100 too Low ({rank_100} < 20)"
                        elif rank_100 > 90:
                            can_buy = False
                            skip_reason = f"Rank100 too High ({rank_100} > 90)"
                            
                    # Rank 30
                    if can_buy and full_idx >= 29:
                        navs_30 = [full_data[full_idx-k]['nav'] for k in range(30)]
                        navs_30.sort()
                        rank_30 = navs_30.index(current_nav) + 1
                        
                        if rank_30 < 5:
                            can_buy = False
                            skip_reason = f"Rank30 too Low ({rank_30} < 5)"

                # 2.7 年线/半年线/季度线熊市保护 (Strict Bear Protection)
                # 逻辑: 如果年收益率 <= 0 或 半年收益率 <= 0 或 季度收益率 <= 0, 停止一切加仓.
                if can_buy:
                    if season_growth_rate <= 0:
                        can_buy = False
                        skip_reason = f"Strict Bear Protection: Season({season_growth_rate:.1f}%) <= 0"
                    elif half_year_growth_rate <= 0:
                        can_buy = False
                        skip_reason = f"Strict Bear Protection: HalfYear({half_year_growth_rate:.1f}%) <= 0"
                    elif year_growth_rate <= 0:
                        can_buy = False
                        skip_reason = f"Strict Bear Protection: Year({year_growth_rate:.1f}%) <= 0"
                
                # 2.6 收益率趋势检查 (Trend Checks)
                if can_buy:
                    # Condition 1: All Negative
                    if week_growth_rate < 0 and month_growth_rate < 0 and season_growth_rate < 0:
                        can_buy = False
                        skip_reason = "Trend: All Negative (W/M/S < 0)"
                    
                    # Condition 2: Season < 0 and (Month < 0 or Week < 0)
                    elif season_growth_rate < 0 and (month_growth_rate < 0 or week_growth_rate < 0):
                        can_buy = False
                        skip_reason = "Trend: Season < 0 & (M < 0 or W < 0)"
                    
                    # Condition 3: Season > 0 and (Month < 0 and Week < 0)
                    elif season_growth_rate > 0 and (month_growth_rate < 0 and week_growth_rate < 0):
                        can_buy = False
                        skip_reason = "Trend: Season > 0 & (M < 0 and W < 0)"
                
                # ---------------------------------------------------------
                # 3. 执行买入 (Execute Buy)
                # ---------------------------------------------------------
                buy_amt = 0.0
                if can_buy:
                    rank_ok_buy += 1
                    # 3.1 10倍加仓逻辑 (10x Logic)
                    if estimated_profit_rate < -5.0 and times > 15:
                        buy_amt = INVEST_AMOUNT * 10.0
                        # Returns after this in increase.py
                    else:
                        # 3.2 基础加仓 (Base Buy)
                        buy_amt += INVEST_AMOUNT
                        
                        # 3.3 -3.0% 额外加仓 (Extra Buy -3%)
                        if estimated_profit_rate < -3.0:
                            buy_amt += INVEST_AMOUNT
                            
                        # 3.4 -5.0% 额外加仓 (Extra Buy -5%)
                        if estimated_profit_rate < -5.0:
                            buy_amt += INVEST_AMOUNT
                
                else:
                    # 统计 Skip 原因
                    if "Rank100 too Low" in skip_reason or "Rank30 too Low" in skip_reason:
                        rank_low_skip += 1
                    elif "Rank100 too High" in skip_reason:
                        rank_high_skip += 1
                    elif "Trend" in skip_reason:
                        trend_skip += 1
                    elif "Bear Protection" in skip_reason:
                        bear_prot_skip += 1
                    elif "MA5" in skip_reason:
                        ma5_skip += 1
                    elif "Profit Rate > -1.0%" in skip_reason:
                        profit_skip += 1
                        
                if buy_amt > 0:
                    acc.buy(buy_amt, current_nav, current_date)
                    
            # --- 2. 止盈检查 (Redeem Logic) ---
            # Condition: profit_rate > 1.0% (强制1%止盈)
            # Only redeem shares with 0 fee (>= 7 days for C-class)
            if acc.total_shares > 0:
                p_rate = acc.get_profit_rate(current_nav) * 100
                stop_rate = 1.0
                
                if p_rate > stop_rate:
                    # Trigger Redeem
                    # Sell Low Fee Shares (>= 7 days)
                    redeemed = acc.redeem(current_nav, current_date, min_age=7)
        
        # --- End of Day Stats ---
        current_holding_cost = sum(acc.total_cost for acc in accounts)
        current_asset_val = sum(acc.get_asset_value(current_nav) for acc in accounts)
        
        cum_invested = sum(acc.cash_invested for acc in accounts)
        cum_redeemed = sum(acc.cash_redeemed for acc in accounts)
        
        net_invested = cum_invested - cum_redeemed
        occupied_capital_curve.append(net_invested)
        
        profit = current_asset_val + cum_redeemed - cum_invested
        if profit < -max_loss_amount:
            max_loss_amount = -profit
            
        daily_records.append({
            "date": current_date,
            "net_invested": net_invested,
            "holding_cost": current_holding_cost,
            "accumulated_profit": profit
        })
        
    # --- Post Loop Cleanup ---
    final_nav = backtest_data[-1]['nav']
    final_date = backtest_data[-1]['date']
    final_dt = datetime.strptime(final_date, "%Y-%m-%d")
    
    current_holdings_shares = sum(acc.total_shares for acc in accounts)
    final_asset = current_holdings_shares * final_nav
    total_profit = final_asset + cum_redeemed - cum_invested
    max_occupied = max(occupied_capital_curve) if occupied_capital_curve else 0.0
    
    # Collect all trades for XIRR
    all_trades = []
    for acc in accounts:
        for t in acc.trades:
            all_trades.append(t)
    all_trades.sort(key=lambda x: x['date'])
    
    # --- Yearly Statistics ---
    from collections import defaultdict
    yearly_stats = defaultdict(list)
    for r in daily_records:
        year = r['date'][:4]
        yearly_stats[year].append(r)
        
    print("=" * 80)
    print(f"年度详细分析 ({FUND_NAME})")
    print(f"注: 平均持有资金 = 每日持仓成本累加 / 交易日天数")
    print(f"注: 收益率 = 当年收益 / 平均持有资金")
    print("-" * 80)
    print(f"{'年份':<6} | {'平均持有资金':<15} | {'当年收益':<15} | {'收益率(占平均持有)':<20}")
    print("-" * 80)
    
    sorted_years = sorted(yearly_stats.keys())
    last_year_profit = 0.0
    
    for year in sorted_years:
        records = yearly_stats[year]
        if not records: continue
        
        # Average Holding Cost (Daily Held Funds)
        avg_holding = sum(r['holding_cost'] for r in records) / len(records)
        
        # Yearly Profit
        current_year_end_profit = records[-1]['accumulated_profit']
        yearly_profit = current_year_end_profit - last_year_profit
        last_year_profit = current_year_end_profit
        
        # Yields (Based on Average Holding Cost)
        yield_avg = (yearly_profit / avg_holding * 100) if avg_holding > 0 else 0.0
        
        print(f"{year:<6} | {avg_holding:,.2f}        | {yearly_profit:,.2f}        | {yield_avg:>6.2f}%")

    print("=" * 80)

    
    # XIRR
    # Cashflows: (-Amount, Date) for Buys, (+Amount, Date) for Sells.
    # Final Date: (+Asset, FinalDate).
    xirr_flows = []
    for t in all_trades:
        dt = datetime.strptime(t['date'], "%Y-%m-%d")
        if t['type'] == 'BUY':
            xirr_flows.append((dt, -t['amount']))
        elif t['type'] == 'SELL':
            xirr_flows.append((dt, t['amount']))
            
    # Add Terminal Value
    xirr_flows.append((final_dt, final_asset))
    
    xirr_val = xirr(xirr_flows)
    xirr_str = f"{xirr_val*100:.2f}%" if xirr_val else "N/A"
    
    # Calculate Average Occupied Capital
    avg_occupied = sum(occupied_capital_curve) / len(occupied_capital_curve) if occupied_capital_curve else 0.0

    print("-" * 30)
    print(f"Debug Statistics:")
    print(f"  Rank Low Skip (接飞刀熔断): {rank_low_skip}")
    print(f"  Rank High Skip (追高熔断): {rank_high_skip}")
    print(f"  Bear Protection Skip (年线熊市保护): {bear_prot_skip}")
    print(f"  Trend Skip (趋势熔断): {trend_skip}")
    print(f"  MA5 Skip (均线熔断): {ma5_skip}")
    print(f"  Profit > -1% Skip (未亏损不加仓): {profit_skip}")
    print(f"  Buy Executed (实际加仓): {rank_ok_buy}")
    print("-" * 30)
    print(f"回测结果 ({FUND_NAME} {FUND_CODE})")
    print(f"时间范围: {START_DATE} 至 {END_DATE}")
    print(f"定投策略: 28个日定投 + 5个周定投, 每次{INVEST_AMOUNT}")
    print(f"逻辑: Increase(Profit<-1%, MA5 Gate) + Redeem(Profit>1%, 0 Fee Only)")
    print("-" * 30)
    print(f"最大占用金额 (Max Capital Occupied): {max_occupied:,.2f} 元")
    print(f"平均占用金额 (Avg Capital Occupied): {avg_occupied:,.2f} 元")
    print(f"最大浮亏金额 (Max Floating Loss): {max_loss_amount:,.2f} 元")
    print(f"最终总投入 (Total Invested): {cum_invested:,.2f} 元")
    print(f"最终总赎回 (Total Redeemed): {cum_redeemed:,.2f} 元")
    print(f"最终持仓市值 (Final Asset): {final_asset:,.2f} 元")
    print(f"实际收益金额 (Total Profit): {total_profit:,.2f} 元")
    print(f"实际总收益率 (Total Return): {(total_profit/cum_invested*100) if cum_invested else 0:.2f}%")
    print(f"年化收益率 (XIRR): {xirr_str}")
    print("-" * 30)

if __name__ == "__main__":
    run_backtest()
