
import os
import sys
import logging
import pandas as pd
from datetime import datetime, timedelta
import numpy as np
import requests
import re
import json

# Add root dir
root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from src.common.constant import DEFAULT_USER
from src.service.定投管理.定投查询.定投查询 import get_all_fund_plan_details

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def get_historical_data(fund_code):
    url = f"http://fund.eastmoney.com/pingzhongdata/{fund_code}.js"
    try:
        logger.info(f"Fetching data for {fund_code} from Eastmoney...")
        response = requests.get(url)
        content = response.text
        match = re.search(r'Data_netWorthTrend\s*=\s*(\[.*?\]);', content)
        if not match: 
            logger.error(f"Data_netWorthTrend not found in response for {fund_code}")
            return pd.DataFrame()
        
        data_json = json.loads(match.group(1))
        parsed_data = []
        for item in data_json:
            dt = datetime.fromtimestamp(item['x'] / 1000)
            parsed_data.append({"date": dt, "nav": float(item['y'])})
            
        df = pd.DataFrame(parsed_data)
        df = df.sort_values('date')
        return df
    except Exception as e:
        logger.error(f"Failed to fetch data for {fund_code}: {e}")
        return pd.DataFrame()

def calculate_indicators(df, current_date):
    # Filter data up to current_date
    history = df[df['date'] <= current_date].tail(365)
    if len(history) < 1:
        return None
    
    current_nav = history.iloc[-1]['nav']
    
    # MA5
    ma5 = history['nav'].rolling(window=5).mean().iloc[-1]
    
    # Returns
    week_ret = (current_nav / history.iloc[-6]['nav'] - 1) * 100 if len(history) >= 6 else 0
    season_ret = (current_nav / history.iloc[-61]['nav'] - 1) * 100 if len(history) >= 61 else 0
    half_year_ret = (current_nav / history.iloc[-121]['nav'] - 1) * 100 if len(history) >= 121 else 0
    year_ret = (current_nav / history.iloc[-241]['nav'] - 1) * 100 if len(history) >= 241 else 0
    
    # Volatility
    daily_rets = history['nav'].pct_change().tail(20)
    volatility = daily_rets.std() * np.sqrt(252) * 100 if len(daily_rets) > 1 else 0

    # Volatility 30 days
    daily_rets_30 = history['nav'].pct_change().tail(30)
    volatility_30 = daily_rets_30.std() * np.sqrt(252) * 100 if len(daily_rets_30) > 1 else 0
    
    return {
        'nav': current_nav,
        'ma5': ma5,
        'week_return': week_ret,
        'season_return': season_ret,
        'six_month_return': half_year_ret,
        'year_return': year_ret,
        'volatility': volatility,
        'volatility_30': volatility_30
    }

def run_combined_backtest():
    target_funds = {
        "021740": "前海开源黄金ETF联接C",
        "011707": "东吴配置优化混合C"
    }
    
    # 1. Get All Plans
    all_user_plans = get_all_fund_plan_details(DEFAULT_USER)
    active_plans = []
    
    for p in all_user_plans:
        fc = p.rationPlan.fundCode
        if fc in target_funds:
            active_plans.append(p)
            
    if not active_plans:
        logger.error("No matching plans found!")
        return

    logger.info(f"Found {len(active_plans)} plans in total.")
    for fc, name in target_funds.items():
        count = sum(1 for p in active_plans if p.rationPlan.fundCode == fc)
        logger.info(f"  - {name} ({fc}): {count} plans")
    
    # 2. Get Historical Data for all funds
    dfs = {}
    for fc in target_funds.keys():
        df = get_historical_data(fc)
        if not df.empty:
            dfs[fc] = df
        else:
            logger.error(f"Could not get data for {fc}, aborting.")
            return

    # Determine trading days (intersection of 2025 days)
    # Use the first fund's days as base, intersect with others
    base_df = list(dfs.values())[0]
    mask_2025 = (base_df['date'] >= '2025-01-01') & (base_df['date'] <= '2025-12-31')
    trading_days = base_df[mask_2025]['date'].tolist()
    # Sort just in case
    trading_days.sort()
    
    # Global Cash Pool - Unlimited
    # GLOBAL_CASH_LIMIT = float('inf') 
    
    # Fund Config
    fund_config = {
        "021740": {"stop_profit": 1.0}, # Gold
        "011707": {"stop_profit": 3.0}  # Dongwu
    }
    
    # 3. Initialize Portfolio
    # Key: sub_account_no
    portfolio = {}
    for p in active_plans:
        sub_no = p.rationPlan.subAccountNo
        portfolio[sub_no] = {
            'fund_code': p.rationPlan.fundCode,
            'shares': [], # list of {date, shares, cost}
            'total_shares': 0,
            'cash_invested': 0,
            'realized_profit': 0,
            'buy_count': 0,
            'plan_amount': float(p.rationPlan.amount) # Use actual plan amount
        }
        
    total_invested_capital_daily_sum = 0
    max_capital_occupied = 0
    total_trading_days = 0
    
    # missed_buys_cash = 0 # No longer tracking missed buys due to cash
    
    # Monthly Stats Aggregation
    monthly_stats = []
    prev_month_total_profit = 0
    month_daily_capital_sum = 0
    month_days_count = 0

    # 4. Simulation Loop
    for i, current_date in enumerate(trading_days):
        total_trading_days += 1
        month_days_count += 1
        current_date_str = current_date.strftime('%Y-%m-%d')
        
        # Calculate indicators for ALL funds for this date
        fund_inds = {}
        for fc, df in dfs.items():
            inds = calculate_indicators(df, current_date)
            fund_inds[fc] = inds
            
        # Check if any fund is missing data for this day (e.g. suspended)
        # If missing, we might skip trading for that fund, or use prev?
        # For simplicity, if indicators are None, we skip that fund.
        
        # Calculate daily holding cost (Sum of all sub-accounts)
        daily_total_holding_cost = sum(d['cash_invested'] for d in portfolio.values())
        if daily_total_holding_cost > max_capital_occupied:
            max_capital_occupied = daily_total_holding_cost
            
        total_invested_capital_daily_sum += daily_total_holding_cost
        month_daily_capital_sum += daily_total_holding_cost
        
        # Process Plans
        for plan in active_plans:
            sub_no = plan.rationPlan.subAccountNo
            fc = plan.rationPlan.fundCode
            inds = fund_inds.get(fc)
            
            if not inds:
                continue # No data for this fund today
                
            nav = inds['nav']
            
            # --- Logic ---
            # 1. Check Stop Profit (Redeem)
            # Stop Rate: 
            # Gold (021740): 1.0%
            # Dongwu (011707): max(3.0, volatility_30)
            if fc == "021740":
                stop_rate = 1.0
            elif fc == "011707":
                vol_30 = inds.get('volatility_30', 0)
                stop_rate = max(3.0, vol_30)
            else:
                stop_rate = 3.0
            
            p_data = portfolio[sub_no]
            if p_data['cash_invested'] > 0:
                asset_value = p_data['total_shares'] * nav
                profit_rate = (asset_value - p_data['cash_invested']) / p_data['cash_invested'] * 100
                
                if profit_rate > stop_rate:
                    # Redeem Logic (FIFO for 7 days)
                    current_holdings = p_data['shares']
                    shares_to_sell = 0
                    cost_sold = 0
                    new_holdings = []
                    
                    for share in current_holdings:
                        days_held = (current_date - share['date']).days
                        if days_held >= 7:
                            shares_to_sell += share['shares']
                            cost_sold += share['cost']
                        else:
                            new_holdings.append(share)
                            
                    if shares_to_sell > 0:
                        redeemed_amt = shares_to_sell * nav
                        realized = redeemed_amt - cost_sold
                        
                        p_data['shares'] = new_holdings
                        p_data['total_shares'] -= shares_to_sell
                        p_data['cash_invested'] -= cost_sold
                        if p_data['cash_invested'] < 0: p_data['cash_invested'] = 0
                        p_data['realized_profit'] += realized
                        
                        # Return cash to pool - Unlimited logic, just track profit
                        # current_cash_pool += cost_sold 
                        
            # 2. Check Buy (Increase)
            # Triple Circuit Breaker
            if inds['season_return'] <= 0 or inds['six_month_return'] <= 0 or inds['year_return'] <= 0:
                continue
                
            # MA5 Gate
            # Exception: Monthly plan & times <= 1
            amount = p_data['plan_amount']
            current_asset = p_data['total_shares'] * nav
            times = current_asset / amount if amount > 0 else 0
            
            p_type = plan.rationPlan.periodType # 1=Week, 3=Month
            p_value = int(plan.rationPlan.periodValue)
            
            bypass_ma5 = (p_type == 3) and (times <= 1)
            if not bypass_ma5 and nav <= inds['ma5']:
                continue
                
            # Est Profit Rate Check (Buy the dip)
            # Use prev day nav to est change
            # Find prev nav
            df = dfs[fc]
            prev_rows = df[df['date'] < current_date]
            if not prev_rows.empty:
                prev_nav = prev_rows.iloc[-1]['nav']
                est_change = (nav - prev_nav) / prev_nav * 100
                
                curr_profit_rate = 0
                if p_data['cash_invested'] > 0:
                    curr_val_prev = p_data['total_shares'] * prev_nav
                    curr_profit_rate = (curr_val_prev - p_data['cash_invested']) / p_data['cash_invested'] * 100
                    
                est_profit_rate = curr_profit_rate + est_change
                
                is_first = (times <= 1.0)
                if not is_first and est_profit_rate > -1.0:
                    continue
            
            # Schedule Check
            is_scheduled = False
            if p_type == 1: # Weekly
                if current_date.weekday() + 1 == p_value:
                    is_scheduled = True
            elif p_type == 3: # Monthly
                if current_date.day == p_value:
                    is_scheduled = True
            
            if is_scheduled:
                # Check Cash Pool - Unlimited
                # if current_cash_pool < amount:
                #    continue
                    
                # BUY
                # current_cash_pool -= amount
                shares_bought = amount / nav
                p_data['shares'].append({
                    'date': current_date,
                    'shares': shares_bought,
                    'cost': amount
                })
                p_data['total_shares'] += shares_bought
                p_data['cash_invested'] += amount
                p_data['buy_count'] += 1
                
        # End of Day Stats (Monthly)
        # Check if month end
        is_month_end = False
        if i == len(trading_days) - 1:
            is_month_end = True
        elif trading_days[i+1].month != current_date.month:
            is_month_end = True
            
        if is_month_end:
            current_total_profit = 0
            for sub_no, data in portfolio.items():
                fc = data['fund_code']
                inds = fund_inds.get(fc)
                if inds:
                    mv = data['total_shares'] * inds['nav']
                    unrealized = mv - data['cash_invested']
                    current_total_profit += (unrealized + data['realized_profit'])
            
            month_profit = current_total_profit - prev_month_total_profit
            avg_cap_month = month_daily_capital_sum / month_days_count if month_days_count > 0 else 0
            yield_month = (month_profit / avg_cap_month * 100) if avg_cap_month > 0 else 0
            
            monthly_stats.append({
                'month': current_date.strftime('%Y-%m'),
                'avg_capital': avg_cap_month,
                'profit_month': month_profit,
                'profit_cum': current_total_profit,
                'yield_month': yield_month
            })
            
            prev_month_total_profit = current_total_profit
            month_daily_capital_sum = 0
            month_days_count = 0

    # 5. Final Results
    total_profit = 0
    total_invested_final = 0
    
    # Let's iterate portfolio to get final stats
    for sub_no, data in portfolio.items():
        fc = data['fund_code']
        # Get last nav
        last_nav = dfs[fc].iloc[-1]['nav'] # Assuming last date is same for all
        # Use the nav from the last trading day we processed
        # inds = calculate_indicators(dfs[fc], trading_days[-1])
        # last_nav = inds['nav']
        # Better:
        last_nav = dfs[fc][dfs[fc]['date'] <= trading_days[-1]].iloc[-1]['nav']
        
        mv = data['total_shares'] * last_nav
        unrealized = mv - data['cash_invested']
        total_profit += (unrealized + data['realized_profit'])
        total_invested_final += data['cash_invested']
        
    avg_daily_capital = total_invested_capital_daily_sum / total_trading_days if total_trading_days > 0 else 0
    yield_rate = (total_profit / avg_daily_capital * 100) if avg_daily_capital > 0 else 0
    
    print("=" * 60)
    print("COMBINED BACKTEST RESULTS (2025)")
    print(f"Funds: {', '.join(target_funds.values())}")
    print(f"Total Plans: {len(active_plans)}")
    print(f"Constraints: No Cash Limit | Stop Profit: Gold=1%, Dongwu=max(3%, Vol30)")
    print("-" * 60)
    print(f"Total Profit (Earnings): {total_profit:,.2f} CNY")
    print(f"Combined Yield: {yield_rate:.2f}%")
    print(f"Average Capital Occupied: {avg_daily_capital:,.2f} CNY")
    print(f"Max Capital Occupied: {max_capital_occupied:,.2f} CNY")
    print(f"Final Principal Held: {total_invested_final:,.2f} CNY")
    # print(f"Missed Buys (Due to Cash Limit): {missed_buys_cash}")
    print("-" * 60)
    
    print("\n[Monthly Performance]")
    print(f"{'Month':<10} | {'Avg Capital':<15} | {'Profit (Mo)':<15} | {'Profit (Cum)':<15} | {'Yield (Mo)':<10}")
    print("-" * 80)
    for m in monthly_stats:
        print(f"{m['month']:<10} | {m['avg_capital']:<15.2f} | {m['profit_month']:<15.2f} | {m['profit_cum']:<15.2f} | {m['yield_month']:.2f}%")
    print("-" * 80)

if __name__ == "__main__":
    run_combined_backtest()
