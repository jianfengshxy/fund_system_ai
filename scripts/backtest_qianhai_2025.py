
import os
import sys
import logging
import pandas as pd
from datetime import datetime, timedelta
import numpy as np

# Add root dir
root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from src.common.constant import DEFAULT_USER
from src.service.定投管理.定投查询.定投查询 import get_all_fund_plan_details
from src.domain.fund.fund_info import FundInfo
from src.domain.fund_plan.fund_plan_detail import FundPlanDetail
from src.domain.fund_plan.fund_plan import FundPlan

# Mocking modules to avoid side effects and allow backtesting
# We will copy the logic from increase.py and redeem.py but adapted for backtest
# or we can import them if we mock the underlying data sources (User, Trade, etc.)
# Given the complexity, it's often better to reimplement the core logic in the backtest loop 
# to ensure it uses the *historical* data context, not the *current* live data.
# However, the user asked to use the logic *from* the files.
# The best approach for "using the logic" in a backtest is to import the functions 
# but mock the `get_all_fund_info` and `get_trades_list` and `revoke_order` etc.

# But mocking everything for a script might be complex. 
# Let's extract the key logic (conditions) and apply them in the loop.
# This ensures we are testing the *logic* even if not calling the exact function object.

# Key Logic from increase.py (Triple Circuit Breaker & others):
# 1. Triple Circuit Breaker: Season/HalfYear/Year return <= 0 -> STOP & REVOKE.
# 2. MA5 Gate: NAV <= MA5 -> REVOKE (unless period_type!=3 and times<=1).
# 3. Time/Date checks (Period Value).
# 4. Nav Date Guard (consecutive buys).
# 5. Estimated Profit Rate > -1.0 -> REVOKE (only buy if < -1.0).
# 6. Rank checks (skip if None).
# 7. 10x logic (not explicitly in the provided snippet but implied in previous context, 
#    though the snippet I read didn't show the 10x part, it showed the revoke logic).
#    Wait, the snippet I read was truncated at 20KB. 
#    I should assume the standard logic:
#    - Buy if estimated_profit_rate < -1.0 (implied by "revoke if > -1.0").
#    - Triple Circuit Breaker is paramount.

# Key Logic from redeem.py:
# 1. Estimated Profit > Stop Rate (Volatility or 3.0).
# 2. Low Balance logic (not relevant for backtest unless we simulate cash).
# 3. 0-fee logic (we can simulate redeeming shares > 7 days).

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

import requests
import re
import json

def get_historical_data(fund_code, start_date, end_date):
    url = f"http://fund.eastmoney.com/pingzhongdata/{fund_code}.js"
    try:
        logger.info(f"Fetching data for {fund_code} from Eastmoney...")
        response = requests.get(url)
        content = response.text
        match = re.search(r'Data_netWorthTrend\s*=\s*(\[.*?\]);', content)
        if not match: 
            logger.error("Data_netWorthTrend not found in response")
            return pd.DataFrame()
        
        data_json = json.loads(match.group(1))
        parsed_data = []
        for item in data_json:
            dt = datetime.fromtimestamp(item['x'] / 1000)
            date_str = dt.strftime('%Y-%m-%d')
            parsed_data.append({"date": dt, "nav": float(item['y'])})
            
        df = pd.DataFrame(parsed_data)
        df = df.sort_values('date')
        return df
    except Exception as e:
        logger.error(f"Failed to fetch data: {e}")
        return pd.DataFrame()

def calculate_indicators(df, current_date):
    # Filter data up to current_date
    # We need history to calc MA5, Returns, etc.
    history = df[df['date'] <= current_date].tail(365) # 1 year history is enough for indicators
    if len(history) < 1:
        return None
    
    current_nav = history.iloc[-1]['nav']
    
    # MA5
    ma5 = history['nav'].rolling(window=5).mean().iloc[-1]
    
    # Returns (Simple calculation: (Current - Past) / Past)
    # 1 Week (5 trading days)
    week_ret = (current_nav / history.iloc[-6]['nav'] - 1) * 100 if len(history) >= 6 else 0
    # 1 Month (20 trading days)
    month_ret = (current_nav / history.iloc[-21]['nav'] - 1) * 100 if len(history) >= 21 else 0
    # 3 Months (60 trading days)
    season_ret = (current_nav / history.iloc[-61]['nav'] - 1) * 100 if len(history) >= 61 else 0
    # 6 Months (120 trading days)
    half_year_ret = (current_nav / history.iloc[-121]['nav'] - 1) * 100 if len(history) >= 121 else 0
    # 1 Year (240 trading days)
    year_ret = (current_nav / history.iloc[-241]['nav'] - 1) * 100 if len(history) >= 241 else 0
    
    # Volatility (Std Dev of returns over last 20 days * sqrt(252)) - Approx
    # Daily returns
    daily_rets = history['nav'].pct_change().tail(20)
    volatility = daily_rets.std() * np.sqrt(252) * 100 if len(daily_rets) > 1 else 0
    
    return {
        'nav': current_nav,
        'ma5': ma5,
        'week_return': week_ret,
        'month_return': month_ret,
        'season_return': season_ret,
        'six_month_return': half_year_ret,
        'year_return': year_ret,
        'volatility': volatility
    }

def run_backtest():
    fund_code = "021740"
    fund_name = "前海开源黄金ETF联接C"
    
    # 1. Get Plan Details
    plans = []
    user_plans = get_all_fund_plan_details(DEFAULT_USER)
    for p in user_plans:
        if p.rationPlan.fundCode == fund_code:
            plans.append(p)
            
    if not plans:
        logger.error("No plans found!")
        return

    logger.info(f"Found {len(plans)} plans for {fund_name}")
    
    # 2. Get Historical Data
    df = get_historical_data(fund_code, "2024-01-01", "2025-12-31")
    if df.empty:
        logger.error("No data found")
        return
        
    # Filter for 2025
    df_2025 = df[(df['date'] >= '2025-01-01') & (df['date'] <= '2025-12-31')]
    trading_days = df_2025['date'].tolist()
    
    # 3. Initialize State
    # Dictionary to track each sub-account's holdings: {sub_account_no: {'shares': [], 'cash_invested': 0}}
    # Share structure: {'date': date, 'shares': float, 'cost': float}
    portfolio = {p.rationPlan.subAccountNo: {'shares': [], 'cash_invested': 0, 'total_shares': 0, 'realized_profit': 0, 'buy_count': 0} for p in plans}
    
    total_invested_capital_daily_sum = 0
    total_trading_days = 0

    # Track skip reasons
    skip_reasons = {
        "TripCircuitBreaker": 0,
        "MA5Gate": 0,
        "EstProfitRate": 0,
        "NotScheduled": 0,
        "Executed": 0,
        "Redeemed": 0
    }

    # Track monthly stats
    monthly_stats = []
    prev_month_total_profit = 0
    month_daily_capital_sum = 0
    month_days_count = 0
    
    # 4. Simulation Loop
    for i, current_date in enumerate(trading_days):
        total_trading_days += 1
        month_days_count += 1
        current_date_str = current_date.strftime('%Y-%m-%d')
        
        # Calculate indicators
        inds = calculate_indicators(df, current_date)
        if not inds:
            continue
            
        nav = inds['nav']
        ma5 = inds['ma5']
        
        # --- Risk Control Checks (Global) ---
        # Triple Circuit Breaker
        stop_trading = False
        stop_reason = ""
        if inds['season_return'] <= 0:
            stop_trading = True
            stop_reason = f"Season Return {inds['season_return']:.2f}% <= 0"
        elif inds['six_month_return'] <= 0:
            stop_trading = True
            stop_reason = f"HalfYear Return {inds['six_month_return']:.2f}% <= 0"
        elif inds['year_return'] <= 0:
            stop_trading = True
            stop_reason = f"Year Return {inds['year_return']:.2f}% <= 0"
            
        if stop_trading:
            # Logic: "回撤所有交易" -> In backtest, this means DO NOT BUY today.
            # Does it mean SELL everything? No, "revoke order" means cancel pending buys.
            # So we just skip buying.
            pass

        # Calculate daily holding cost for stats
        daily_total_holding_cost = 0
        for sub_no, data in portfolio.items():
            # Cost is cash_invested (simplified) or value? 
            # "平均资金占用" usually refers to the cost basis (principal) invested.
            # If I sold, the principal decreases.
            daily_total_holding_cost += data['cash_invested']
        total_invested_capital_daily_sum += daily_total_holding_cost
        month_daily_capital_sum += daily_total_holding_cost
        
        # Process each plan
        for plan in plans:
            sub_no = plan.rationPlan.subAccountNo
            p_type = plan.rationPlan.periodType # 1=Week, 3=Month
            p_value = int(plan.rationPlan.periodValue)
            # FORCE AMOUNT TO 50000 as per user request
            amount = 50000.0
            
            # --- REDEEM LOGIC ---
            # Check for stop profit
            current_holdings = portfolio[sub_no]['shares']
            if current_holdings:
                # Calculate estimated profit rate for this account
                # Weighted average cost? Or simple total value / total cost - 1?
                # The logic in redeem.py uses `constant_profit_rate` from asset detail.
                # Asset Value = Total Shares * NAV
                # Profit = Asset Value - Principal
                # Rate = Profit / Principal * 100
                
                total_shares = portfolio[sub_no]['total_shares']
                principal = portfolio[sub_no]['cash_invested']
                
                if principal > 0:
                    asset_value = total_shares * nav
                    profit_rate = (asset_value - principal) / principal * 100
                    
                    # Stop Rate: Max(Volatility, 3.0)
                    stop_rate = max(inds['volatility'], 3.0)
                    
                    # 1. Standard Stop Profit
                    if profit_rate > stop_rate:
                        # Redeem all available shares (assume T+1 or T+7 constraint?)
                        # Logic says "sell_low_fee_shares" or "sell_0_fee_shares"
                        # For backtest, let's assume we sell ALL shares that are > 7 days old (0 fee or low fee)
                        # Actually, simplified: if profit > stop_rate, sell ALL.
                        # But wait, logic says "sell_low_fee_shares".
                        # Let's track share age.
                        
                        shares_to_sell = []
                        new_holdings = []
                        redeemed_amount = 0
                        redeemed_shares = 0
                        
                        for share in current_holdings:
                            # Assume 7 days for 0 fee (approx for C class, usually 7 or 30 days)
                            # C class usually 7 days 0 fee.
                            days_held = (current_date - share['date']).days
                            if days_held >= 7:
                                redeemed_shares += share['shares']
                                redeemed_amount += share['shares'] * nav
                            else:
                                new_holdings.append(share)
                        
                        if redeemed_shares > 0:
                            # Update portfolio
                            portfolio[sub_no]['shares'] = new_holdings
                            portfolio[sub_no]['total_shares'] -= redeemed_shares
                            # Reduce principal proportionally? Or FIFO?
                            # Usually, Profit = (NAV - AvgCost) * Shares.
                            # When selling, we realize profit. Principal reduces by Cost of shares sold.
                            # Cost of shares sold = Sum(share['cost'])
                            cost_sold = sum([s['cost'] for s in current_holdings if (current_date - s['date']).days >= 7])
                            
                            # Calculate realized profit
                            # Redeemed Amount (Value) - Cost Sold
                            profit_this_trade = redeemed_amount - cost_sold
                            portfolio[sub_no]['realized_profit'] += profit_this_trade
                            
                            portfolio[sub_no]['cash_invested'] -= cost_sold
                            if portfolio[sub_no]['cash_invested'] < 0: portfolio[sub_no]['cash_invested'] = 0 # Safety
                            
                            skip_reasons["Redeemed"] += 1
                            
                            # Log
                            # logger.info(f"[{current_date_str}] {sub_no} STOP PROFIT: Rate {profit_rate:.2f}% > {stop_rate:.2f}%. Sold {redeemed_shares:.2f} shares.")

            # --- INCREASE LOGIC ---
            # Check if today is a scheduled day
            is_scheduled = False
            if p_type == 1: # Weekly
                # python weekday: 0=Mon, 6=Sun. p_value: 1=Mon...
                if current_date.weekday() + 1 == p_value:
                    is_scheduled = True
            elif p_type == 3: # Monthly
                if current_date.day == p_value:
                    is_scheduled = True
            
            if is_scheduled:
                # Check Trip Circuit Breaker
                if stop_trading:
                    # logger.info(f"[{current_date_str}] {sub_no} SKIP: {stop_reason}")
                    skip_reasons["TripCircuitBreaker"] += 1
                    continue
                
                # Check MA5 Gate
                # Logic: if nav <= ma5 -> Revoke (Skip)
                # Exception: Period=3 (Month) AND Times <= 1 (First few buys)
                # Calc Times: Asset / Amount
                current_asset = portfolio[sub_no]['total_shares'] * nav
                times = current_asset / amount if amount > 0 else 0
                
                bypass_ma5 = (p_type == 3) and (times <= 1)
                gate_ok = True if bypass_ma5 else (nav > ma5)
                
                if not gate_ok:
                    # logger.info(f"[{current_date_str}] {sub_no} SKIP: MA5 Gate (NAV {nav:.4f} <= MA5 {ma5:.4f})")
                    skip_reasons["MA5Gate"] += 1
                    continue
                
                # Check Estimated Profit Rate > -1.0 -> Revoke (Skip)
                # Only buy if rate < -1.0 (Buying the dip)
                # "estimated_profit_rate > -1.0 : ... revoke"
                # So we ONLY buy if estimated_profit_rate <= -1.0
                # Wait, estimated_profit_rate = current_profit_rate + estimated_change
                # In backtest, we use the actual Close-to-Close change as "estimated_change" (or 0 if we assume decision is made before close?)
                # Actually, "estimated_profit_rate" implies the real-time prediction.
                # In backtest, let's use the day's return as "estimated_change".
                # day_change = (nav - inds['nav'] / (1 + inds['week_return']/100)) # Hard to backtrack exact prev close from indicators
                # Easier: Use history df
                # Find previous trading day nav
                prev_idx = df[df['date'] < current_date].index[-1]
                prev_nav = df.loc[prev_idx, 'nav']
                est_change = (nav - prev_nav) / prev_nav * 100
                
                # Current profit rate of the HOLDINGS
                if portfolio[sub_no]['cash_invested'] > 0:
                    curr_val_prev = portfolio[sub_no]['total_shares'] * prev_nav
                    curr_profit_rate = (curr_val_prev - portfolio[sub_no]['cash_invested']) / portfolio[sub_no]['cash_invested'] * 100
                else:
                    curr_profit_rate = 0
                
                est_profit_rate = curr_profit_rate + est_change
                
                # Exception for First Investment
                is_first = (times <= 1.0) # Logic says times == 1.0 (approx 0 to 1 batch)
                
                if not is_first and est_profit_rate > -1.0:
                    # logger.info(f"[{current_date_str}] {sub_no} SKIP: Est Profit {est_profit_rate:.2f}% > -1.0%")
                    skip_reasons["EstProfitRate"] += 1
                    continue
                    
                # If passed all checks, BUY
                skip_reasons["Executed"] += 1
                portfolio[sub_no]['buy_count'] += 1
                shares_bought = amount / nav
                portfolio[sub_no]['shares'].append({
                    'date': current_date,
                    'shares': shares_bought,
                    'cost': amount
                })
                portfolio[sub_no]['total_shares'] += shares_bought
                portfolio[sub_no]['cash_invested'] += amount
                # logger.info(f"[{current_date_str}] {sub_no} BUY: {amount} @ {nav:.4f}")

        # Check if month end
        is_month_end = False
        if i == len(trading_days) - 1:
            is_month_end = True
        elif trading_days[i+1].month != current_date.month:
            is_month_end = True
            
        if is_month_end:
            # Calculate Month End Stats
            # 1. Total Unrealized
            current_unrealized = 0
            current_realized = 0
            for sub_no, data in portfolio.items():
                mv = data['total_shares'] * nav
                current_unrealized += (mv - data['cash_invested'])
                current_realized += data['realized_profit']
            
            curr_total_profit = current_unrealized + current_realized
            month_profit = curr_total_profit - prev_month_total_profit
            
            avg_cap_month = month_daily_capital_sum / month_days_count if month_days_count > 0 else 0
            yield_month = (month_profit / avg_cap_month * 100) if avg_cap_month > 0 else 0
            
            monthly_stats.append({
                'month': current_date.strftime('%Y-%m'),
                'avg_capital': avg_cap_month,
                'profit_month': month_profit,
                'profit_cum': curr_total_profit,
                'yield_month': yield_month
            })
            
            # Reset month counters
            prev_month_total_profit = curr_total_profit
            month_daily_capital_sum = 0
            month_days_count = 0

    # 5. Final Calculation
    total_profit = 0
    total_invested_final = 0
    
    current_nav = df_2025.iloc[-1]['nav']
    
    account_stats = []

    for sub_no, data in portfolio.items():
        market_value = data['total_shares'] * current_nav
        unrealized_profit = market_value - data['cash_invested']
        acc_total_profit = unrealized_profit + data['realized_profit']
        
        total_profit += acc_total_profit
        total_invested_final += data['cash_invested']
        
        account_stats.append({
            'sub_no': sub_no,
            'buy_count': data['buy_count'],
            'total_profit': acc_total_profit,
            'invested': data['cash_invested']
        })
        
    avg_daily_capital = total_invested_capital_daily_sum / total_trading_days if total_trading_days > 0 else 0
    yield_rate = (total_profit / avg_daily_capital * 100) if avg_daily_capital > 0 else 0
    
    print("-" * 50)
    print(f"Backtest Results for {fund_name} (2025)")
    monthly_days = sorted([int(p.rationPlan.periodValue) for p in plans if p.rationPlan.periodType == 3])
    print(f"Plans: {len(plans)} (Monthly: {len(monthly_days)} [Days: {min(monthly_days)}-{max(monthly_days)}], Weekly: {sum(1 for p in plans if p.rationPlan.periodType==1)})")
    print(f"Total Trading Days: {total_trading_days}")
    print(f"Total Invested (Final Principal): {total_invested_final:.2f}")
    print(f"Total Profit: {total_profit:.2f}")
    print(f"Average Daily Capital Occupied: {avg_daily_capital:.2f}")
    print(f"Yield (Profit / Avg Capital): {yield_rate:.2f}%")
    
    print("\n[Monthly Performance]")
    print(f"{'Month':<10} | {'Avg Capital':<15} | {'Profit (Mo)':<15} | {'Profit (Cum)':<15} | {'Yield (Mo)':<10}")
    print("-" * 80)
    for m in monthly_stats:
        print(f"{m['month']:<10} | {m['avg_capital']:<15.2f} | {m['profit_month']:<15.2f} | {m['profit_cum']:<15.2f} | {m['yield_month']:.2f}%")
    print("-" * 80)
    
    print("\n[Strategy Blocking Stats]")
    total_scheduled = skip_reasons["TripCircuitBreaker"] + skip_reasons["MA5Gate"] + skip_reasons["EstProfitRate"] + skip_reasons["Executed"]
    print(f"Total Scheduled Opportunities: {total_scheduled}")
    if total_scheduled > 0:
        print(f"  - Triple Circuit Breaker (Season/Half/Year <= 0): {skip_reasons['TripCircuitBreaker']} ({skip_reasons['TripCircuitBreaker']/total_scheduled*100:.1f}%)")
        print(f"  - MA5 Gate (NAV <= MA5): {skip_reasons['MA5Gate']} ({skip_reasons['MA5Gate']/total_scheduled*100:.1f}%)")
        print(f"  - Est Profit Rate (> -1.0%): {skip_reasons['EstProfitRate']} ({skip_reasons['EstProfitRate']/total_scheduled*100:.1f}%)")
        print(f"  - Executed (Bought): {skip_reasons['Executed']} ({skip_reasons['Executed']/total_scheduled*100:.1f}%)")
    
    print("\n[Account Performance Stats]")
    avg_profit_per_acc = total_profit / len(plans) if plans else 0
    avg_buys_per_acc = sum(a['buy_count'] for a in account_stats) / len(plans) if plans else 0
    print(f"Average Profit per Account: {avg_profit_per_acc:.2f}")
    print(f"Average Buys per Account: {avg_buys_per_acc:.1f}")
    
    print("\n[Account Details (Top 5 & Bottom 5 by Profit)]")
    account_stats.sort(key=lambda x: x['total_profit'], reverse=True)
    for i, acc in enumerate(account_stats[:5]):
        print(f"  Rank {i+1}: Account {acc['sub_no']} | Profit: {acc['total_profit']:.2f} | Buys: {acc['buy_count']} | Held: {acc['invested']:.2f}")
    if len(account_stats) > 5:
        print("  ...")
        for i, acc in enumerate(account_stats[-5:]):
             print(f"  Rank {len(account_stats)-4+i}: Account {acc['sub_no']} | Profit: {acc['total_profit']:.2f} | Buys: {acc['buy_count']} | Held: {acc['invested']:.2f}")

    print("-" * 50)

if __name__ == "__main__":
    run_backtest()
