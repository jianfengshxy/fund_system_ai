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

def generate_simulation_paths(df_hist, n_days=252, n_sims=100):
    """
    Generate GBM paths based on historical stats from the last year of df_hist
    """
    last_year = df_hist.tail(252)
    daily_returns = last_year['nav'].pct_change().dropna()
    
    mu = daily_returns.mean() * 252 # Annualized drift
    sigma = daily_returns.std() * np.sqrt(252) # Annualized vol
    
    # Daily parameters for simulation
    dt = 1/252
    daily_mu = mu * dt
    daily_sigma = sigma * np.sqrt(dt)
    
    last_price = df_hist.iloc[-1]['nav']
    last_date = df_hist.iloc[-1]['date']
    
    sim_paths = []
    sim_dates = []
    
    # Generate future dates (business days)
    curr = last_date
    while len(sim_dates) < n_days:
        curr += timedelta(days=1)
        if curr.weekday() < 5: # Mon-Fri
            sim_dates.append(curr)
            
    for _ in range(n_sims):
        prices = [last_price]
        for _ in range(n_days):
            # GBM: P_t = P_{t-1} * exp((mu - 0.5*sigma^2)*dt + sigma*sqrt(dt)*Z)
            # Simplified: P_t = P_{t-1} * (1 + return)
            # Let's use standard GBM formula
            # Z = np.random.normal(0, 1)
            # ret = (mu - 0.5 * sigma**2) * dt + sigma * np.sqrt(dt) * Z
            # price = prices[-1] * np.exp(ret)
            
            # Or Bootstrap from history (more realistic for fat tails)
            # Let's use Bootstrap
            ret = np.random.choice(daily_returns)
            price = prices[-1] * (1 + ret)
            prices.append(price)
            
        # Create DF for this path, but we need history for indicators
        # So we prepend the history
        path_df = pd.DataFrame({
            'date': sim_dates,
            'nav': prices[1:]
        })
        
        # Combine with history for indicator calculation
        full_df = pd.concat([df_hist, path_df]).reset_index(drop=True)
        sim_paths.append((full_df, sim_dates))
        
    return sim_paths

def run_strategy_on_path(sim_dfs, active_plans, target_funds):
    """
    Run strategy on a single set of simulated DFs (one for each fund)
    sim_dfs: {fund_code: (full_df, trading_days)}
    """
    
    # Common trading days (from first fund)
    trading_days = list(sim_dfs.values())[0][1]
    
    # Fund Config
    fund_config = {
        "021740": {"stop_profit": 1.0}, # Gold
        "011707": {"stop_profit": 3.0}  # Dongwu
    }
    
    portfolio = {}
    for p in active_plans:
        sub_no = p.rationPlan.subAccountNo
        portfolio[sub_no] = {
            'fund_code': p.rationPlan.fundCode,
            'shares': [],
            'total_shares': 0,
            'cash_invested': 0,
            'realized_profit': 0,
            'plan_amount': float(p.rationPlan.amount)
        }
        
    total_invested_capital_daily_sum = 0
    max_capital_occupied = 0
    
    # Pre-calculate indicators for speed? 
    # Actually, calculating indicators day by day is safer but slower.
    # Given 252 days * 100 sims, speed matters.
    # We can pre-calculate MA5 and Volatility for the whole dataframe at once using pandas rolling.
    
    processed_dfs = {}
    for fc, (df, _) in sim_dfs.items():
        df = df.copy()
        # Pre-calc
        df['ma5'] = df['nav'].rolling(window=5).mean()
        df['pct_change'] = df['nav'].pct_change()
        
        # Volatility 30 (annualized)
        df['vol30'] = df['pct_change'].rolling(window=30).std() * np.sqrt(252) * 100
        
        # Returns for gates (approx)
        # Week (5 days), Season (60), HalfYear (120), Year (240)
        df['ret_season'] = df['nav'].pct_change(periods=60)
        df['ret_half'] = df['nav'].pct_change(periods=120)
        df['ret_year'] = df['nav'].pct_change(periods=240)
        
        processed_dfs[fc] = df
        
    # Simulation Loop
    for current_date in trading_days:
        # Get index in DF
        # Assuming dates are unique
        
        daily_total_holding_cost = sum(d['cash_invested'] for d in portfolio.values())
        if daily_total_holding_cost > max_capital_occupied:
            max_capital_occupied = daily_total_holding_cost
        
        total_invested_capital_daily_sum += daily_total_holding_cost
        
        for plan in active_plans:
            sub_no = plan.rationPlan.subAccountNo
            fc = plan.rationPlan.fundCode
            df = processed_dfs[fc]
            
            # Find row for current_date
            # Optimization: pass index instead of searching
            row = df[df['date'] == current_date]
            if row.empty: continue
            
            idx = row.index[0]
            nav = row.iloc[0]['nav']
            ma5 = row.iloc[0]['ma5']
            vol30 = row.iloc[0]['vol30']
            ret_season = row.iloc[0]['ret_season']
            ret_half = row.iloc[0]['ret_half']
            ret_year = row.iloc[0]['ret_year']
            
            if pd.isna(ma5): continue
            
            p_data = portfolio[sub_no]
            
            # 1. Stop Profit
            if fc == "021740":
                stop_rate = 1.0
            elif fc == "011707":
                stop_rate = max(3.0, vol30 if not pd.isna(vol30) else 0)
            else:
                stop_rate = 3.0
                
            if p_data['cash_invested'] > 0:
                asset_value = p_data['total_shares'] * nav
                profit_rate = (asset_value - p_data['cash_invested']) / p_data['cash_invested'] * 100
                
                if profit_rate > stop_rate:
                    # FIFO Redeem
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
                        
            # 2. Buy
            # Circuit Breaker (simplified to check if values exist)
            if (pd.notna(ret_season) and ret_season <= 0) or \
               (pd.notna(ret_half) and ret_half <= 0) or \
               (pd.notna(ret_year) and ret_year <= 0):
               continue
               
            amount = p_data['plan_amount']
            current_asset = p_data['total_shares'] * nav
            times = current_asset / amount if amount > 0 else 0
            
            p_type = plan.rationPlan.periodType
            p_value = int(plan.rationPlan.periodValue)
            
            bypass_ma5 = (p_type == 3) and (times <= 1)
            if not bypass_ma5 and nav <= ma5:
                continue
                
            # Est Profit Rate (Buy the Dip)
            # Need prev nav
            if idx > 0:
                prev_nav = df.iloc[idx-1]['nav']
                est_change = (nav - prev_nav) / prev_nav * 100
                curr_profit_rate = 0
                if p_data['cash_invested'] > 0:
                    curr_val_prev = p_data['total_shares'] * prev_nav
                    curr_profit_rate = (curr_val_prev - p_data['cash_invested']) / p_data['cash_invested'] * 100
                
                est_profit_rate = curr_profit_rate + est_change
                is_first = (times <= 1.0)
                if not is_first and est_profit_rate > -1.0:
                    continue
            
            # Schedule
            is_scheduled = False
            if p_type == 1: # Weekly
                if current_date.weekday() + 1 == p_value:
                    is_scheduled = True
            elif p_type == 3: # Monthly
                if current_date.day == p_value:
                    is_scheduled = True
                    
            if is_scheduled:
                shares_bought = amount / nav
                p_data['shares'].append({
                    'date': current_date,
                    'shares': shares_bought,
                    'cost': amount
                })
                p_data['total_shares'] += shares_bought
                p_data['cash_invested'] += amount
                
    # Final Stats
    total_profit = 0
    total_invested_final = 0
    
    # Last day nav
    last_date = trading_days[-1]
    
    for sub_no, data in portfolio.items():
        fc = data['fund_code']
        df = processed_dfs[fc]
        last_nav = df[df['date'] == last_date].iloc[0]['nav']
        
        mv = data['total_shares'] * last_nav
        unrealized = mv - data['cash_invested']
        total_profit += (unrealized + data['realized_profit'])
        total_invested_final += data['cash_invested']
        
    avg_daily_capital = total_invested_capital_daily_sum / len(trading_days)
    yield_rate = (total_profit / avg_daily_capital * 100) if avg_daily_capital > 0 else 0
    
    return {
        'total_profit': total_profit,
        'yield_rate': yield_rate,
        'avg_capital': avg_daily_capital,
        'max_capital': max_capital_occupied
    }

def predict_2026():
    target_funds = {
        "021740": "前海开源黄金ETF联接C",
        "011707": "东吴配置优化混合C"
    }
    
    # Get Plans
    all_user_plans = get_all_fund_plan_details(DEFAULT_USER)
    active_plans = [p for p in all_user_plans if p.rationPlan.fundCode in target_funds]
    
    if not active_plans:
        logger.error("No plans")
        return

    # Get Data
    dfs = {}
    for fc in target_funds:
        dfs[fc] = get_historical_data(fc)
        
    # Generate Simulations
    # We generate N simulations for EACH fund, but we need to pair them?
    # Or assume they are correlated?
    # Simple approach: Independent Bootstrap for each fund.
    # To capture correlation, we should sample dates and take returns for both funds on that date.
    # 1. Align data
    df1 = dfs["021740"].set_index('date')[['nav']].rename(columns={'nav': 'nav1'})
    df2 = dfs["011707"].set_index('date')[['nav']].rename(columns={'nav': 'nav2'})
    
    aligned = df1.join(df2, how='inner').dropna()
    returns = aligned.pct_change().dropna()
    
    n_sims = 50 # 50 scenarios
    n_days = 252 # 1 year
    
    results = []
    
    logger.info(f"Running {n_sims} simulations for 2026...")
    
    for i in range(n_sims):
        # Generate correlated path by sampling rows of returns
        sampled_rets = returns.sample(n=n_days, replace=True) # Bootstrap
        
        sim_dfs = {}
        sim_dates = []
        
        # Base Dates
        curr = dfs["021740"].iloc[-1]['date']
        for _ in range(n_days):
            curr += timedelta(days=1)
            while curr.weekday() >= 5: curr += timedelta(days=1)
            sim_dates.append(curr)
            
        # Construct Paths
        for fc, col in [("021740", "nav1"), ("011707", "nav2")]:
            base_df = dfs[fc]
            last_price = base_df.iloc[-1]['nav']
            
            prices = [last_price]
            fund_rets = sampled_rets[col].values
            
            for r in fund_rets:
                prices.append(prices[-1] * (1 + r))
                
            path_df = pd.DataFrame({
                'date': sim_dates,
                'nav': prices[1:]
            })
            
            full_df = pd.concat([base_df, path_df]).reset_index(drop=True)
            sim_dfs[fc] = (full_df, sim_dates)
            
        # Run Strategy
        res = run_strategy_on_path(sim_dfs, active_plans, target_funds)
        results.append(res)
        
        if (i+1) % 10 == 0:
            logger.info(f"Completed {i+1}/{n_sims} simulations")
            
    # Aggregate
    profits = [r['total_profit'] for r in results]
    yields = [r['yield_rate'] for r in results]
    max_caps = [r['max_capital'] for r in results]
    avg_caps = [r['avg_capital'] for r in results]
    
    print("=" * 60)
    print("PREDICTION FOR 2026 (Bootstrap Simulation N=50)")
    print(f"Strategy: Gold=1%, Dongwu=max(3%, Vol30), No Cash Limit")
    print("-" * 60)
    print(f"Expected Total Profit (Median): {np.median(profits):,.2f} CNY")
    print(f"Expected Yield (Median): {np.median(yields):.2f}%")
    print(f"Expected Max Capital Occupied: {np.median(max_caps):,.2f} CNY")
    print("-" * 60)
    print(f"Profit Range (10th - 90th percentile): {np.percentile(profits, 10):,.2f} - {np.percentile(profits, 90):,.2f}")
    print(f"Yield Range (10th - 90th percentile): {np.percentile(yields, 10):.2f}% - {np.percentile(yields, 90):.2f}%")
    print("=" * 60)

if __name__ == "__main__":
    predict_2026()
