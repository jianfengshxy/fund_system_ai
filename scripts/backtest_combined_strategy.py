import requests
import re
import json
import logging
import numpy as np
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- 公共类定义 ---

class ShareBatch:
    def __init__(self, amount: float, price: float, date: str):
        self.amount = amount
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
        
        for i, batch in enumerate(self.shares):
            if batch.get_age(date) >= min_age:
                redeemable_indices.append(i)
                total_redeem_shares += batch.amount
        
        if total_redeem_shares == 0:
            return 0.0

        redeem_value = total_redeem_shares * nav
        net_amount = redeem_value
        self.cash_redeemed += net_amount
        
        for i in sorted(redeemable_indices, reverse=True):
            batch = self.shares.pop(i)
            self.trades.append({
                "date": date, "type": "SELL", "amount": net_amount, "price": nav, "shares": batch.amount
            })
            
        return net_amount

# --- 辅助函数 ---

def calculate_ma5(nav_values, index):
    if index < 4: return None
    return sum(nav_values[index-4:index+1]) / 5.0

def get_return(prices, index, days):
    if index < days: return 0.0
    return (prices[index] - prices[index-days]) / prices[index-days]

def xirr(transactions):
    if not transactions: return 0.0
    dates = [t[0] for t in transactions]
    amounts = [t[1] for t in transactions]
    if sum(amounts) == 0: return 0.0
    if all(a >= 0 for a in amounts) or all(a <= 0 for a in amounts): return 0.0
    
    min_date = min(dates)
    days = [(d - min_date).days for d in dates]
    
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

# --- 策略运行器 ---

class StrategyRunner:
    def __init__(self, fund_code, fund_name, target_amount):
        self.fund_code = fund_code
        self.fund_name = fund_name
        self.target_amount = target_amount
        self.accounts = []
        self.history_data = []
        self.date_map = {} # date_str -> index in history_data
        self.stats_cache = {} # date_str -> stats dict
        
        # Init accounts
        for wd in range(1, 6):
            self.accounts.append(Account(f"Weekly_{wd}", 1, wd))
        for day in range(1, 29):
            self.accounts.append(Account(f"Monthly_{day}", 3, day))

    def load_data(self):
        url = f"http://fund.eastmoney.com/pingzhongdata/{self.fund_code}.js"
        try:
            logger.info(f"Downloading data for {self.fund_name} ({self.fund_code})...")
            response = requests.get(url)
            content = response.text
            match = re.search(r'Data_netWorthTrend\s*=\s*(\[.*?\]);', content)
            if not match: return False
            
            data_json = json.loads(match.group(1))
            self.history_data = []
            for item in data_json:
                dt = datetime.fromtimestamp(item['x'] / 1000)
                date_str = dt.strftime('%Y-%m-%d')
                self.history_data.append({"date": date_str, "nav": float(item['y'])})
            
            self.history_data.sort(key=lambda x: x['date'])
            # Build date map
            for i, d in enumerate(self.history_data):
                self.date_map[d['date']] = i
                
            logger.info(f"Loaded {len(self.history_data)} records for {self.fund_name}.")
            return True
        except Exception as e:
            logger.error(f"Error loading {self.fund_code}: {e}")
            return False

    def execute_date(self, date_str: str) -> Dict:
        """
        执行指定日期的策略。如果该日期无数据，保持前一天的状态（或返回0 if not started）。
        """
        if date_str not in self.date_map:
            # Check if date is before start
            if not self.history_data or date_str < self.history_data[0]['date']:
                return {
                    "net_invested": 0.0, "total_asset": 0.0, 
                    "accumulated_profit": 0.0, "nav": 0.0, "active": False
                }
            # If date is after end or in a gap (holiday), we should ideally use the last valid state.
            # But for simplicity in this step-by-step runner, we assume the caller iterates chronological.
            # If it's a holiday, we just return the current state without trading.
            # However, to get current state, we need NAV. We'll use the latest available NAV before this date.
            # For backtest accuracy, we usually skip holidays in the main loop or just hold.
            # Let's find the last known NAV index.
            # But wait, if it's a holiday, no trading happens.
            # We just return the last calculated stats if available.
            return self._get_current_stats(date_str, use_last_known=True)

        idx = self.date_map[date_str]
        current_nav = self.history_data[idx]['nav']
        
        # --- Run Strategy Logic ---
        navs = [d['nav'] for d in self.history_data] # This is heavy if done every step? 
        # Optimization: pass full nav list to helper, access by index.
        # But `navs` is static after load. We can store it.
        
        # Indicators
        ma5 = calculate_ma5(navs, idx)
        half_year_return = get_return(navs, idx, 120) * 100
        year_return = get_return(navs, idx, 240) * 100
        
        vol_window = 252
        volatility = 0.0
        if idx >= vol_window:
            window_navs = navs[idx-vol_window:idx+1]
            if len(window_navs) > 1:
                log_rets = np.diff(np.log(window_navs))
                volatility = np.std(log_rets) * np.sqrt(252) * 100
        else:
            volatility = 10.0

        dt_obj = datetime.strptime(date_str, "%Y-%m-%d")
        wd = dt_obj.isoweekday()
        dom = dt_obj.day

        for acc in self.accounts:
            asset_val = acc.get_asset_value(current_nav)
            
            # Buy Logic
            is_scheduled = False
            if acc.period_type == 1 and wd == acc.period_value: is_scheduled = True
            elif acc.period_type == 3 and dom == acc.period_value: is_scheduled = True
            
            if is_scheduled:
                gap = self.target_amount - asset_val
                if gap > 100.0:
                    can_buy = True
                    if half_year_return <= 0: can_buy = False
                    elif year_return <= 0: can_buy = False
                    
                    if can_buy and ma5 is not None and current_nav > ma5: can_buy = False
                    
                    if can_buy and asset_val > 0:
                        est_profit_rate = acc.get_profit_rate(current_nav) * 100
                        if est_profit_rate > -1.0: can_buy = False
                    
                    if can_buy and acc.last_buy_date:
                        last_dt = datetime.strptime(acc.last_buy_date, "%Y-%m-%d")
                        if (dt_obj - last_dt).days <= 1: can_buy = False
                    
                    if can_buy:
                        acc.buy(gap, current_nav, date_str)
            
            # Sell Logic
            if acc.total_shares > 0:
                stop_rate = max(volatility, 3.0)
                profit_rate = acc.get_profit_rate(current_nav) * 100
                if profit_rate > stop_rate:
                    if ma5 is not None and current_nav < ma5:
                        acc.redeem_all(current_nav, date_str, min_age=7)

        return self._get_current_stats(date_str, current_nav=current_nav)

    def _get_current_stats(self, date_str, current_nav=None, use_last_known=False):
        if use_last_known and current_nav is None:
            # Find last known NAV
            # Simplified: just return previous day's stats if exist, or 0
            # This handles holidays in the combined loop
            # But wait, if we return previous stats, 'nav' might be old.
            return self.stats_cache.get("last", {
                "net_invested": 0.0, "total_asset": 0.0, 
                "accumulated_profit": 0.0, "nav": 0.0, "active": False
            })

        total_asset = sum(acc.get_asset_value(current_nav) for acc in self.accounts)
        total_invested = sum(acc.cash_invested for acc in self.accounts)
        total_redeemed = sum(acc.cash_redeemed for acc in self.accounts)
        net_invested = total_invested - total_redeemed
        accumulated_profit = total_asset + total_redeemed - total_invested
        
        stats = {
            "net_invested": net_invested,
            "total_asset": total_asset,
            "accumulated_profit": accumulated_profit,
            "nav": current_nav,
            "active": True
        }
        self.stats_cache["last"] = stats
        return stats

    def get_trades(self):
        all_trades = []
        for acc in self.accounts:
            all_trades.extend(acc.trades)
        return all_trades

# --- 主程序 ---

def run_combined_backtest():
    # 1. Setup
    runner_gold = StrategyRunner("004253", "国泰黄金ETF联接C", 50000.0)
    runner_dongwu = StrategyRunner("011707", "东吴优化配置C", 10000.0)
    
    if not runner_gold.load_data() or not runner_dongwu.load_data():
        logger.error("Failed to load data")
        return

    # 2. Date Union
    dates_gold = set(runner_gold.date_map.keys())
    dates_dongwu = set(runner_dongwu.date_map.keys())
    all_dates = sorted(list(dates_gold | dates_dongwu))
    
    # 3. Simulation Loop
    combined_stats = []
    
    logger.info(f"Starting combined simulation on {len(all_dates)} days from {all_dates[0]} to {all_dates[-1]}...")
    
    for date_str in all_dates:
        s_gold = runner_gold.execute_date(date_str)
        s_dongwu = runner_dongwu.execute_date(date_str)
        
        combined_net_invested = s_gold["net_invested"] + s_dongwu["net_invested"]
        combined_asset = s_gold["total_asset"] + s_dongwu["total_asset"]
        combined_profit = s_gold["accumulated_profit"] + s_dongwu["accumulated_profit"]
        
        combined_stats.append({
            "date": date_str,
            "gold": s_gold,
            "dongwu": s_dongwu,
            "net_invested": combined_net_invested,
            "total_asset": combined_asset,
            "accumulated_profit": combined_profit
        })

    # 4. Analysis
    analyze_combined(combined_stats, runner_gold, runner_dongwu)

def analyze_combined(stats, runner_gold, runner_dongwu):
    if not stats: return
    
    # --- Individual Analysis (Recalculate max stats for comparison) ---
    def get_metrics(stat_list, key_prefix=None):
        # stat_list is list of dicts. If key_prefix provided, access sub-dict
        invested = []
        profits = []
        
        for d in stat_list:
            item = d[key_prefix] if key_prefix else d
            invested.append(item['net_invested'])
            profits.append(item['accumulated_profit'])
            
        max_occ = max(invested) if invested else 0
        avg_occ = sum(invested)/len(invested) if invested else 0
        
        # Max Drawdown
        peak = -float('inf')
        max_dd = 0.0
        for p in profits:
            if p > peak: peak = p
            dd = peak - p
            if dd > max_dd: max_dd = dd
            
        return max_occ, avg_occ, max_dd, profits[-1]

    # Gold
    g_max_occ, g_avg_occ, g_max_dd, g_final_profit = get_metrics(stats, "gold")
    # Dongwu
    d_max_occ, d_avg_occ, d_max_dd, d_final_profit = get_metrics(stats, "dongwu")
    # Combined
    c_max_occ, c_avg_occ, c_max_dd, c_final_profit = get_metrics(stats, None)

    # Calculate XIRR for Combined
    flows = []
    # Collect all trades from both
    for t in runner_gold.get_trades():
        amt = -t['amount'] if t['type'] == 'BUY' else t['amount']
        flows.append((datetime.strptime(t['date'], "%Y-%m-%d"), amt))
    for t in runner_dongwu.get_trades():
        amt = -t['amount'] if t['type'] == 'BUY' else t['amount']
        flows.append((datetime.strptime(t['date'], "%Y-%m-%d"), amt))
    
    # Add final value
    last_date = datetime.strptime(stats[-1]['date'], "%Y-%m-%d")
    final_val = stats[-1]['total_asset']
    flows.append((last_date, final_val))
    
    c_xirr = xirr(flows)

    # Correlation Analysis
    # Calculate daily NAV changes correlation
    # We need aligned dates where both are active
    nav_gold = []
    nav_dongwu = []
    
    for d in stats:
        if d['gold']['active'] and d['dongwu']['active'] and d['gold']['nav'] > 0 and d['dongwu']['nav'] > 0:
            nav_gold.append(d['gold']['nav'])
            nav_dongwu.append(d['dongwu']['nav'])
            
    corr = 0.0
    if len(nav_gold) > 10:
        # Calculate log returns
        ret_g = np.diff(np.log(nav_gold))
        ret_d = np.diff(np.log(nav_dongwu))
        if len(ret_g) > 0:
            corr = np.corrcoef(ret_g, ret_d)[0, 1]

    # --- Report ---
    print("\n" + "="*80)
    print(f"双策略并行回测报告: {runner_gold.fund_name} & {runner_dongwu.fund_name}")
    print(f"时间范围: {stats[0]['date']} 至 {stats[-1]['date']}")
    print("-" * 80)
    
    # 1. 独立表现对比
    print(f"【独立表现】")
    print(f"{'指标':<15} | {'国泰黄金':<15} | {'东吴优配':<15} | {'直接叠加(理论值)':<15}")
    print("-" * 70)
    print(f"{'总盈利':<15} | {g_final_profit:>15,.2f} | {d_final_profit:>15,.2f} | {(g_final_profit+d_final_profit):>15,.2f}")
    print(f"{'最大资金占用':<15} | {g_max_occ:>15,.2f} | {d_max_occ:>15,.2f} | {(g_max_occ+d_max_occ):>15,.2f}")
    print(f"{'平均资金占用':<15} | {g_avg_occ:>15,.2f} | {d_avg_occ:>15,.2f} | {(g_avg_occ+d_avg_occ):>15,.2f}")
    print(f"{'最大回撤金额':<15} | {g_max_dd:>15,.2f} | {d_max_dd:>15,.2f} | {(g_max_dd+d_max_dd):>15,.2f}")
    
    # 2. 组合表现
    print("-" * 80)
    print(f"【组合实际表现】 (互补效应分析)")
    print(f"组合总盈利:        {c_final_profit:,.2f} 元")
    print(f"组合最大资金占用:  {c_max_occ:,.2f} 元  <-- 相比直接叠加节省了 {(g_max_occ+d_max_occ - c_max_occ):,.2f} 元")
    print(f"组合平均资金占用:  {c_avg_occ:,.2f} 元")
    print(f"组合最大回撤金额:  {c_max_dd:,.2f} 元  <-- 相比直接叠加减少了 {(g_max_dd+d_max_dd - c_max_dd):,.2f} 元")
    print(f"组合最大回撤比率:  {(c_max_dd/c_max_occ*100 if c_max_occ else 0):.2f}% (相对于组合最大投入)")
    print(f"组合年化收益(XIRR): {c_xirr*100:.2f}%")
    print(f"两基金日涨跌相关性: {corr:.4f} (负相关/低相关 = 互补强; 高相关 = 共振强)")
    
    # 3. 资金利用效率评价
    print("-" * 80)
    print(f"【资金利用效率评价】")
    
    saving_ratio = (g_max_occ + d_max_occ - c_max_occ) / (g_max_occ + d_max_occ) * 100
    print(f"1. 资金峰值错位度: {saving_ratio:.2f}%")
    print(f"   (这意味着您不需要准备两份满额本金，因为它们不会同时达到资金占用峰值)")
    
    print(f"2. 风险对冲效果: 组合回撤比率 {(c_max_dd/c_max_occ*100):.2f}% vs 单一最大 {(d_max_dd/d_max_occ*100 if d_max_occ else 0):.2f}%")
    if (c_max_dd/c_max_occ) < (d_max_dd/d_max_occ):
        print("   -> 组合显著降低了整体风险水平 (平滑了波动)")
    else:
        print("   -> 组合风险水平适中")

    print("="*80)

if __name__ == "__main__":
    run_combined_backtest()
