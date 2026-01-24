
import requests
import json
import re
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

# Constants
FUND_CODE = "011707"
FUND_NAME = "东吴优化配置C"

class ShareBatch:
    def __init__(self, share, cost, date):
        self.share = share
        self.cost = cost
        self.buy_date = datetime.strptime(date, "%Y-%m-%d")

    def get_age(self, current_date_str):
        current_date = datetime.strptime(current_date_str, "%Y-%m-%d")
        return (current_date - self.buy_date).days

class SharedPool:
    def __init__(self):
        self.holdings = []  # List of ShareBatch
        self.total_shares = 0.0
        self.cash_balance = 0.0 # Track realized P&L + initial cash
        self.total_invested = 0.0 # Net cash flow into the pool
        self.redemption_fee_saved = 0.0
        self.trade_count_enabled = 0 # Count of trades that would have been blocked without pool

    def buy(self, amount, nav, date_str):
        share = amount / nav
        self.holdings.append(ShareBatch(share, amount, date_str))
        self.total_shares += share
        self.total_invested += amount

    def redeem(self, share_to_redeem, nav, date_str, min_age=7):
        # FIFO redemption
        remaining_redeem = share_to_redeem
        redeem_value = 0.0
        fees = 0.0
        
        # Check if we have enough eligible shares (for statistics)
        # Actually, in C-class, fee is usually:
        # 0-7 days: 1.5%
        # >=7 days: 0%
        # We simulate "Fee Optimization": Always sell oldest.
        
        # Sort holdings by date (should be already sorted if appended chronologically)
        self.holdings.sort(key=lambda x: x.buy_date)
        
        new_holdings = []
        
        for batch in self.holdings:
            if remaining_redeem <= 0:
                new_holdings.append(batch)
                continue
                
            age = batch.get_age(date_str)
            
            # Logic: We ALWAYS redeem if requested, but we track the fee.
            # If age < 7, fee = 1.5%. If >= 7, fee = 0.
            
            if batch.share > remaining_redeem:
                # Partial redeem of this batch
                redeemed_part = remaining_redeem
                batch.share -= redeemed_part
                batch.cost -= (batch.cost * (redeemed_part / (batch.share + redeemed_part))) # Pro-rata cost
                
                val = redeemed_part * nav
                fee_rate = 0.015 if age < 7 else 0.0
                fee = val * fee_rate
                
                redeem_value += val - fee
                fees += fee
                remaining_redeem = 0
                new_holdings.append(batch)
            else:
                # Full redeem of this batch
                val = batch.share * nav
                fee_rate = 0.015 if age < 7 else 0.0
                fee = val * fee_rate
                
                redeem_value += val - fee
                fees += fee
                remaining_redeem -= batch.share
                # Batch removed
        
        self.holdings = new_holdings
        self.total_shares -= (share_to_redeem - remaining_redeem)
        
        # Cash flow: We get redeem_value back.
        # Net Invested decreases by redeem_value (treating it as money returned)
        self.total_invested -= redeem_value
        return fees

    def get_market_value(self, nav):
        return self.total_shares * nav

class LogicalPlan:
    def __init__(self, name, period_type, period_value, target_amount):
        self.name = name
        self.period_type = period_type # 1=Weekly, 3=Monthly
        self.period_value = period_value # 1-5 or 1-28
        self.target_amount = target_amount
        self.logical_shares = 0.0
        self.total_invested_logical = 0.0 # For XIRR of this plan alone (theoretical)

    def get_asset_value(self, nav):
        return self.logical_shares * nav

    def get_profit_rate(self, nav):
        if self.total_invested_logical <= 0: return 0.0
        # This is a simplified profit rate: (Current Asset - Net Invested) / Net Invested
        # Or (Current NAV - Avg Cost) / Avg Cost
        # Standard logic: (Market Value - Cost) / Cost
        cost = self.total_invested_logical # Approximation
        # Better: We don't track exact cost basis per plan in "Shared" mode easily without complexity.
        # But for strategy signal, we need "Profit Rate".
        # Let's approximate: profit_rate = (Asset - Invested) / Invested
        # Wait, "Invested" changes on sell.
        # We need "Average Cost".
        if self.logical_shares == 0: return 0.0
        avg_cost = self.total_invested_logical / self.logical_shares
        return (nav - avg_cost) / avg_cost

class StrategyRunnerMixed:
    def __init__(self, fund_code, fund_name, use_bottom_position=False):
        self.fund_code = fund_code
        self.fund_name = fund_name
        self.use_bottom_position = use_bottom_position
        self.pool = SharedPool()
        self.plans = []
        self.history_data = []
        self.date_map = {}
        self.transactions = [] # For XIRR: (date, amount). amount < 0 for buy, > 0 for sell.
        
        # Setup Plans
        # 5 Weekly @ 10,000
        for wd in range(1, 6):
            self.plans.append(LogicalPlan(f"Weekly_{wd}", 1, wd, 10000.0))
        # 28 Monthly @ 5,000
        for day in range(1, 29):
            self.plans.append(LogicalPlan(f"Monthly_{day}", 3, day, 5000.0))
            
    def load_data(self):
        try:
            url = f"http://fund.eastmoney.com/pingzhongdata/{self.fund_code}.js"
            response = requests.get(url)
            content = response.text
            match = re.search(r'Data_netWorthTrend\s*=\s*(\[.*?\]);', content)
            if not match: return False
            
            data_json = json.loads(match.group(1))
            self.history_data = []
            for item in data_json:
                dt = datetime.fromtimestamp(item['x'] / 1000)
                date_str = dt.strftime('%Y-%m-%d')
                self.history_data.append({
                    "date": date_str, 
                    "nav": float(item['y'])
                })
            
            self.history_data.sort(key=lambda x: x['date'])
            self.date_map = {d['date']: i for i, d in enumerate(self.history_data)}
            return True
        except Exception as e:
            print(f"Error loading data: {e}")
            return False

    def run(self):
        # Initial Bottom Position
        start_date = self.history_data[0]['date']
        start_nav = self.history_data[0]['nav']
        
        if self.use_bottom_position:
            # 5000 * 28 = 140,000
            initial_amt = 140000.0
            self.pool.buy(initial_amt, start_nav, start_date)
            self.transactions.append((datetime.strptime(start_date, "%Y-%m-%d"), -initial_amt))
            # Note: This bottom position does NOT belong to any LogicalPlan.
            # It just sits in the pool.
        
        # Loop through days
        max_capital = 0.0
        
        for i, day_data in enumerate(self.history_data):
            date_str = day_data['date']
            nav = day_data['nav']
            dt = datetime.strptime(date_str, "%Y-%m-%d")
            
            # Indicators
            ma5 = None
            if i >= 4:
                ma5 = sum([d['nav'] for d in self.history_data[i-4:i+1]]) / 5.0
            
            # Volatility (252 days)
            volatility = 10.0 # Default
            if i >= 252:
                # Log returns
                navs = [d['nav'] for d in self.history_data[i-252:i+1]]
                log_returns = np.diff(np.log(navs))
                volatility = np.std(log_returns) * np.sqrt(252) * 100
            
            stop_rate = max(volatility, 3.0)
            
            # Execute Plans
            for plan in self.plans:
                # 1. Check Schedule
                is_scheduled = False
                if plan.period_type == 1: # Weekly
                    if dt.isoweekday() == plan.period_value:
                        is_scheduled = True
                elif plan.period_type == 3: # Monthly
                    if dt.day == plan.period_value:
                        is_scheduled = True
                
                # 2. Buy Logic (Gap)
                if is_scheduled:
                    current_asset = plan.get_asset_value(nav)
                    gap = plan.target_amount - current_asset
                    
                    if gap > 100.0:
                        # Risk Checks
                        # Half-year return check
                        safe_to_buy = True
                        if i >= 120:
                            ret_120 = (nav / self.history_data[i-120]['nav'] - 1) * 100
                            if ret_120 <= 0: safe_to_buy = False
                        if i >= 240:
                            ret_240 = (nav / self.history_data[i-240]['nav'] - 1) * 100
                            if ret_240 <= 0: safe_to_buy = False
                        
                        # MA5 Check
                        if ma5 is not None and nav > ma5:
                            safe_to_buy = False
                            
                        if safe_to_buy:
                            self.pool.buy(gap, nav, date_str)
                            self.transactions.append((dt, -gap))
                            
                            # Update Logical Plan
                            added_shares = gap / nav
                            plan.logical_shares += added_shares
                            plan.total_invested_logical += gap
                
                # 3. Sell Logic (Profit Taking)
                if plan.logical_shares > 0:
                    # Logic: Profit > stop_rate AND nav < ma5
                    # Calculate logical avg cost
                    if plan.total_invested_logical > 0:
                        avg_cost = plan.total_invested_logical / plan.logical_shares
                        profit_pct = (nav - avg_cost) / avg_cost * 100
                        
                        if profit_pct > stop_rate:
                            if ma5 is not None and nav < ma5:
                                # Trigger Sell
                                # Check if we have physically mature shares?
                                # The SharedPool.redeem handles fees.
                                # If we use bottom position, we save fees.
                                
                                # Sell EVERYTHING in this plan
                                share_to_sell = plan.logical_shares
                                redeem_val = share_to_sell * nav
                                
                                # Execute physical redeem
                                # We assume we WANT to sell.
                                fee_paid = self.pool.redeem(share_to_sell, nav, date_str)
                                
                                net_cash_back = redeem_val - fee_paid
                                self.transactions.append((dt, net_cash_back))
                                
                                # Reset Logical Plan
                                plan.logical_shares = 0
                                plan.total_invested_logical = 0
            
            # Track Stats
            curr_invested = self.pool.total_invested
            if curr_invested > max_capital:
                max_capital = curr_invested
                
        return max_capital

    def calculate_xirr(self):
        # Add final value
        final_date = self.transactions[-1][0]
        final_val = self.pool.get_market_value(self.history_data[-1]['nav'])
        self.transactions.append((final_date, final_val))
        
        dates = [t[0] for t in self.transactions]
        amounts = [t[1] for t in self.transactions]
        
        if not amounts: return 0.0

        def xnpv(rate, dates, amounts):
            if rate <= -1.0: return float('inf')
            t0 = dates[0]
            val = 0.0
            for d, a in zip(dates, amounts):
                dt = (d - t0).days / 365.0
                val += a / ((1 + rate) ** dt)
            return val

        def xnpv_prime(rate, dates, amounts):
            if rate <= -1.0: return float('inf')
            t0 = dates[0]
            val = 0.0
            for d, a in zip(dates, amounts):
                dt = (d - t0).days / 365.0
                val -= dt * a / ((1 + rate) ** (dt + 1))
            return val

        # Newton-Raphson
        rate = 0.1
        for _ in range(100):
            y = xnpv(rate, dates, amounts)
            dy = xnpv_prime(rate, dates, amounts)
            if abs(dy) < 1e-6: break
            new_rate = rate - y / dy
            if abs(new_rate - rate) < 1e-6:
                return new_rate
            rate = new_rate
        return rate

def run_comparison():
    print("Loading data...")
    
    # 1. Without Bottom Position
    runner_no = StrategyRunnerMixed(FUND_CODE, FUND_NAME, use_bottom_position=False)
    if not runner_no.load_data(): return
    print("Running Strategy WITHOUT Bottom Position...")
    max_cap_no = runner_no.run()
    final_val_no = runner_no.pool.get_market_value(runner_no.history_data[-1]['nav'])
    profit_no = final_val_no - runner_no.pool.total_invested
    xirr_no = runner_no.calculate_xirr()
    
    # 2. With Bottom Position
    runner_yes = StrategyRunnerMixed(FUND_CODE, FUND_NAME, use_bottom_position=True)
    runner_yes.load_data() # Reload to be safe/clean
    print("Running Strategy WITH Bottom Position (140k)...")
    max_cap_yes = runner_yes.run()
    final_val_yes = runner_yes.pool.get_market_value(runner_yes.history_data[-1]['nav'])
    # Total Invested includes the initial 140k? Yes, SharedPool.buy adds to total_invested.
    # But profit should be: Final Value - Net Invested.
    # Wait, Net Invested = Sum(Buys) - Sum(Sells).
    # Profit = Final Value - Net Invested. Correct.
    profit_yes = final_val_yes - runner_yes.pool.total_invested
    xirr_yes = runner_yes.calculate_xirr()
    
    print("\n" + "="*50)
    print(f"对比报告: {FUND_NAME} (混合定投: 周1w + 月5k)")
    print("="*50)
    
    print(f"{'指标':<20} | {'无底仓模式':<15} | {'有底仓模式 (14w)':<15}")
    print("-" * 60)
    print(f"{'最大资金占用':<20} | {max_cap_no:,.2f} | {max_cap_yes:,.2f}")
    print(f"{'最终总资产':<20} | {final_val_no:,.2f} | {final_val_yes:,.2f}")
    print(f"{'累计净盈利':<20} | {profit_no:,.2f} | {profit_yes:,.2f}")
    print(f"{'年化收益(XIRR)':<20} | {xirr_no*100:.2f}% | {xirr_yes*100:.2f}%")
    
    diff_profit = profit_yes - profit_no
    print("-" * 60)
    print(f"底仓带来的额外盈利: {diff_profit:,.2f} 元")
    print(f"底仓本身简单持有收益估算: 140000 * (End/Start - 1)")
    
    start_nav = runner_yes.history_data[0]['nav']
    end_nav = runner_yes.history_data[-1]['nav']
    hold_return = 140000 * (end_nav/start_nav - 1)
    print(f"底仓躺平理论收益: {hold_return:,.2f} 元")
    
    print("\n分析结论:")
    if xirr_yes < xirr_no:
        print("-> 有底仓模式拉低了整体资金效率 (XIRR下降)，因为底仓长期占用资金且收益率低于高频波段。")
    else:
        print("-> 有底仓模式提升了效率。")
        
    print("-> 底仓的主要作用是提供T+0(伪)的流动性，避免7天惩罚性费率。")
    print("-> 但如果策略本身交易频率不高（平均持有>7天），底仓的资金占用成本可能高于其节省的费率价值。")

if __name__ == "__main__":
    run_comparison()
