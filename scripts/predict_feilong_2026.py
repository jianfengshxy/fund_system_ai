
import sys
import os
import logging
import pandas as pd
import numpy as np
import requests
import json
from datetime import datetime, timedelta

# Add root dir to sys.path
root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from src.common.constant import DEFAULT_USER
from src.service.资产管理.get_fund_asset_detail import get_sub_account_asset_by_name
from src.service.定投管理.定投查询.定投查询 import get_all_fund_plan_details

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- Eastmoney API ---
def get_historical_data(fund_code):
    """
    Fetch historical NAV data from Eastmoney (Pingzhong Data).
    Returns DataFrame with columns: ['date', 'nav']
    """
    url = f"http://fund.eastmoney.com/pingzhongdata/{fund_code}.js"
    try:
        logger.info(f"Fetching data for {fund_code} from Eastmoney...")
        response = requests.get(url)
        content = response.text
        
        # Regex to find Data_netWorthTrend
        import re
        match = re.search(r'Data_netWorthTrend\s*=\s*(\[.*?\]);', content)
        if not match: 
            logger.error(f"Data_netWorthTrend not found in response for {fund_code}")
            return None
        
        data_json = json.loads(match.group(1))
        parsed_data = []
        for item in data_json:
            # Timestamp is in milliseconds
            dt = datetime.fromtimestamp(item['x'] / 1000)
            parsed_data.append({"date": dt, "nav": float(item['y'])})
            
        df = pd.DataFrame(parsed_data)
        df = df.sort_values('date')
        return df
    except Exception as e:
        logger.error(f"Failed to fetch data for {fund_code}: {e}")
        return None

# --- Simulation Logic ---
def generate_correlated_paths(fund_dfs, n_days=252, n_sims=50):
    """
    Generate correlated price paths using bootstrap resampling of dates.
    """
    # 1. Align Data
    # Create a master DF with date index and columns for each fund's return
    master_df = pd.DataFrame()
    
    # Use the intersection of dates
    common_dates = None
    
    fund_codes = list(fund_dfs.keys())
    
    for fc in fund_codes:
        df = fund_dfs[fc].set_index('date')[['nav']].rename(columns={'nav': fc})
        df[f'{fc}_ret'] = df[fc].pct_change()
        
        if master_df.empty:
            master_df = df
        else:
            master_df = master_df.join(df, how='outer') # Outer join to keep as much as possible, then dropna
            
    # Drop rows with NaN (incomplete data for some funds)
    # We need returns for ALL funds on a given date to preserve correlation
    ret_cols = [f'{fc}_ret' for fc in fund_codes]
    returns_df = master_df[ret_cols].dropna()
    
    logger.info(f"Number of common historical days for simulation: {len(returns_df)}")
    if len(returns_df) < 30:
        logger.warning("Very short common history! Simulation results may be unstable.")
    elif len(returns_df) < 100:
        logger.warning(f"Only {len(returns_df)} common data points found. Simulation might be less robust.")
        
    # 2. Simulation Loop
    simulations = []
    
    # Base Dates for 2026
    # Start from the latest date in data
    start_date = master_df.index.max()
    future_dates = []
    curr = start_date
    while len(future_dates) < n_days:
        curr += timedelta(days=1)
        if curr.weekday() < 5: # Mon-Fri
            future_dates.append(curr)
            
    for i in range(n_sims):
        # Sample N dates from history
        sampled_dates = np.random.choice(returns_df.index, size=n_days, replace=True)
        sampled_returns = returns_df.loc[sampled_dates]
        
        sim_data = {}
        for fc in fund_codes:
            # Construct price path
            last_price = fund_dfs[fc].iloc[-1]['nav']
            path_prices = [last_price]
            rets = sampled_returns[f'{fc}_ret'].values
            
            for r in rets:
                path_prices.append(path_prices[-1] * (1 + r))
                
            # Create DF
            path_df = pd.DataFrame({
                'date': future_dates,
                'nav': path_prices[1:]
            })
            
            # Combine with history (for volatility calc)
            full_df = pd.concat([fund_dfs[fc], path_df]).reset_index(drop=True)
            sim_data[fc] = full_df
            
        simulations.append((sim_data, future_dates))
        
    return simulations

def calculate_volatility(df, current_date, window=30):
    """Calculate annualized volatility for the window ending at current_date."""
    # Filter data up to current_date
    # Optimization: assume df is sorted and we can index by date or just look back
    # But for safety, we slice.
    # To speed up, we can pre-calculate or just slice tail since we move forward day by day.
    # Actually, inside the loop, we are at index `t`.
    # It's better to pass the slice or the full series and index.
    
    # For simplicity in this script:
    subset = df[df['date'] <= current_date].tail(window + 1)
    if len(subset) < window:
        return 0.0
    
    rets = subset['nav'].pct_change().dropna()
    if len(rets) < 2:
        return 0.0
        
    vol = rets.std() * np.sqrt(252) * 100
    return vol

def run_strategy(sim_data, dates, initial_assets, active_plan):
    """
    Run "飞龙在天" strategy on a single simulation path.
    active_plan: {'code': '011707', 'amount': 3000}
    """
    # Portfolio State
    # shares: {code: float}
    shares = {fc: asset['shares'] for fc, asset in initial_assets.items()}
    
    # Cash Flow
    total_invested = 0.0
    total_redeemed = 0.0
    
    # Initial Capital (Market Value)
    initial_mv = sum([asset['asset_value'] for asset in initial_assets.values()])
    
    max_capital_occupied = initial_mv
    
    # Track realized profit
    realized_profit = 0.0
    
    # Plan details
    plan_code = active_plan['code']
    plan_amount = active_plan['amount']
    
    fund_codes = list(sim_data.keys())
    
    # Pre-calculate indicators if possible? 
    # Volatility changes daily.
    
    for date in dates:
        # 1. Update Portfolio Value & Check Logic
        daily_mv = 0.0
        current_navs = {}
        
        # Calculate daily portfolio stats
        sell_candidates = []
        
        for fc in fund_codes:
            df = sim_data[fc]
            # Find row for date
            row = df[df['date'] == date]
            if row.empty:
                continue
            
            nav = row.iloc[-1]['nav']
            current_navs[fc] = nav
            
            # Current Holding
            holding_shares = shares.get(fc, 0.0)
            holding_mv = holding_shares * nav
            daily_mv += holding_mv
            
            if holding_shares <= 0:
                continue
                
            # Calculate Indicators
            # Profit Rate: We need Average Cost?
            # The simplified logic uses "constant_profit_rate" + "estimated_change".
            # "constant_profit_rate" is (CurrentMV - Cost) / Cost.
            # But we don't track Cost accurately here (FIFO/Average).
            # Let's approximate:
            # We track "Weighted Average Cost" for simplicity, or just track Total Invested per fund.
            # Let's add 'cost' to shares dict or separate dict.
            pass

    # RE-DESIGN LOOP for Cost Tracking
    fund_states = {} # code -> {'shares': X, 'cost_basis': Y}
    for fc, asset in initial_assets.items():
        # Estimate cost basis from current profit rate
        # profit_rate = (mv - cost) / cost => cost = mv / (1 + rate/100)
        mv = asset['asset_value']
        rate = asset['profit_rate']
        if rate == -100: # specific case
             cost = mv
        else:
             cost = mv / (1 + rate/100)
        
        fund_states[fc] = {
            'shares': asset['shares'],
            'total_cost': cost
        }
        
    for date in dates:
        daily_total_mv = 0.0
        
        # Identify Sell Candidates
        candidates = []
        
        for fc in fund_codes:
            df = sim_data[fc]
            # Fast lookup: assume dates are sorted and continuous in sim_data
            # But easier to just filter (slower but safe)
            # Optimization: Pre-index by date
            pass
            
    # Optimization: Convert DFs to dict of date->nav
    nav_lookup = {}
    for fc in fund_codes:
        nav_lookup[fc] = dict(zip(sim_data[fc]['date'], sim_data[fc]['nav']))
        
    # Re-loop with fast lookup
    for date in dates:
        daily_total_mv = 0.0
        current_navs = {}
        
        # Update NAVs
        for fc in fund_codes:
            nav = nav_lookup[fc].get(date)
            if nav:
                current_navs[fc] = nav
        
        # Check Sells (Max 3)
        sells_executed = 0
        
        # We need volatility for sell threshold
        # Calculating volatility every day for 16 funds is slow.
        # But we must.
        # Optimize: Volatility doesn't change drasticallly. Maybe update weekly?
        # Or just calculate. 50 sims * 252 days * 16 funds = 200k calcs. Feasible in Python?
        # Maybe slow. 1-2 mins. Acceptable.
        
        # Check Buys
        # Only for plan_code
        if plan_code in current_navs:
            nav = current_navs[plan_code]
            # Calculate Profit Rate
            state = fund_states.get(plan_code, {'shares': 0, 'total_cost': 0})
            if state['shares'] > 0:
                mv = state['shares'] * nav
                cost = state['total_cost']
                profit_rate = (mv - cost) / cost * 100 if cost > 0 else 0
            else:
                profit_rate = 0 # Can't buy dip if no position? Or treat as 0?
                # Usually if no position, profit rate is 0. 
                # If logic is "Buy if profit < -1%", then 0 > -1, so NO BUY.
                # But wait, if I have no position, I should probably buy to start?
                # The user's logic is "Increase" (加仓). Usually assumes existing position.
                # If empty, maybe logic allows buy?
                # For now, stick to logic: if profit > -1.0, skip. So 0 skip.
                # This implies we only add to losing positions.
                
            if profit_rate <= -1.0:
                # BUY
                invest_amt = plan_amount
                shares_to_buy = invest_amt / nav
                
                if plan_code not in fund_states:
                    fund_states[plan_code] = {'shares': 0, 'total_cost': 0}
                    
                fund_states[plan_code]['shares'] += shares_to_buy
                fund_states[plan_code]['total_cost'] += invest_amt
                
                total_invested += invest_amt
                
        # Check Sells
        # Gather all candidates
        candidates = []
        for fc in fund_codes:
            if fc not in current_navs: continue
            state = fund_states.get(fc)
            if not state or state['shares'] <= 0: continue
            
            nav = current_navs[fc]
            mv = state['shares'] * nav
            cost = state['total_cost']
            profit_rate = (mv - cost) / cost * 100 if cost > 0 else 0
            
            # Volatility
            # Get from DF
            df = sim_data[fc]
            # Slice up to date
            # To optimize: assume date index
            # We can pass the full history df and use date lookup
            # Calculate 30-day vol
            # We need the PREVIOUS 30 days.
            # Use `df[df['date'] <= date].tail(30)`
            # This is the slow part.
            
            # Let's try to just use a rough constant or pre-calculated rolling vol?
            # No, user asked for dynamic.
            # I will implement calculate_volatility properly.
            
            vol = calculate_volatility(df, date, window=30)
            threshold = max(vol, 3.0)
            
            if profit_rate > threshold:
                candidates.append({
                    'code': fc,
                    'profit_rate': profit_rate,
                    'threshold': threshold,
                    'nav': nav,
                    'shares': state['shares'],
                    'cost': state['total_cost']
                })
                
        # Execute Sells (Max 3)
        # Prioritize? The file said "Wind Vane" first/last.
        # Since we don't know Wind Vane, maybe prioritize highest profit excess?
        # Or random?
        # I'll prioritize highest profit rate.
        candidates.sort(key=lambda x: x['profit_rate'], reverse=True)
        
        for cand in candidates[:3]:
            # Sell Logic: "Sell 0-fee shares".
            # Simplified: Sell ALL shares (assuming held long enough).
            # Or Sell 50%? The file calls `sell_0_fee_shares`.
            # I'll assume 100% sell for simplicity in prediction (Take Profit).
            
            fc = cand['code']
            nav = cand['nav']
            shares_sold = cand['shares']
            
            redeem_amt = shares_sold * nav
            
            # Update realized profit
            cost_sold = cand['cost']
            profit = redeem_amt - cost_sold
            realized_profit += profit
            
            total_redeemed += redeem_amt
            
            # Update State
            fund_states[fc]['shares'] = 0
            fund_states[fc]['total_cost'] = 0
            
        # Update Daily MV for Capital Occupied
        curr_mv = 0
        for fc, state in fund_states.items():
            if fc in current_navs:
                curr_mv += state['shares'] * current_navs[fc]
        
        # Max Capital Occupied logic:
        # Net Investment = Initial + Invested - Redeemed (This is Cash Flow view)
        # But "Capital Occupied" usually means "Market Value of Portfolio".
        # Or "Net Principal Invested"?
        # User asked "最大持有的金额" (Max Holding Amount).
        # This usually means Max Market Value.
        max_capital_occupied = max(max_capital_occupied, curr_mv)
        
    # End of Year
    final_mv = 0
    for fc, state in fund_states.items():
        # Get last nav
        df = sim_data[fc]
        last_nav = df.iloc[-1]['nav']
        final_mv += state['shares'] * last_nav
        
    # Total Profit
    # Profit = (Final MV - Initial MV) + (Redeemed - Invested)
    # Or = Realized Profit + Unrealized Profit
    # Unrealized = Final MV - Remaining Cost
    # Realized = Sum(Redeem - Cost)
    
    # Let's use Cash Flow method:
    # Profit = Ending Assets + Cash Out - Cash In - Starting Assets
    total_profit = final_mv + total_redeemed - total_invested - initial_mv
    
    # Yield
    # Yield = Total Profit / Max Capital Occupied?
    # Or Profit / Initial Capital?
    # User asked for "收益率".
    # Usually Return on Investment.
    # If Max Capital is used as denominator, it's conservative.
    # If Initial is used, it ignores additional investment.
    # I'll use Max Capital Occupied as denominator.
    yield_rate = (total_profit / max_capital_occupied * 100) if max_capital_occupied > 0 else 0
    
    return {
        'total_profit': total_profit,
        'yield_rate': yield_rate,
        'max_capital': max_capital_occupied
    }

def main():
    # 1. Get Funds & Assets
    print("Fetching '飞龙在天' assets...")
    assets_list = get_sub_account_asset_by_name(DEFAULT_USER, "飞龙在天")
    if not assets_list:
        logger.error("No assets found in '飞龙在天'")
        return

    initial_assets = {}
    fund_codes = []
    
    for asset in assets_list:
        fc = asset.fund_code
        fund_codes.append(fc)
        initial_assets[fc] = {
            'asset_value': asset.asset_value,
            'shares': asset.available_vol, # approximation
            'profit_rate': asset.constant_profit_rate
        }
        
    print(f"Found {len(fund_codes)} funds.")
    
    # 2. Get Plan Details (Active Plan)
    # We found 011707 is the active one with 3000 amount.
    active_plan = {'code': '011707', 'amount': 3000.0}
    print(f"Active Plan: {active_plan}")
    
    # 3. Fetch History
    print("Fetching historical data (this may take a moment)...")
    fund_dfs = {}
    for fc in fund_codes:
        df = get_historical_data(fc)
        if df is not None and not df.empty:
            fund_dfs[fc] = df
            
    # Remove funds with no data
    valid_codes = list(fund_dfs.keys())
    initial_assets = {k:v for k,v in initial_assets.items() if k in valid_codes}
    
    if not initial_assets:
        logger.error("No valid data for any funds.")
        return
        
    # 4. Generate Simulations
    print("Generating 50 correlated simulation paths...")
    sims = generate_correlated_paths(fund_dfs, n_days=252, n_sims=50)
    
    # 5. Run Strategy
    print("Running strategy on simulations...")
    results = []
    for i, (sim_data, dates) in enumerate(sims):
        res = run_strategy(sim_data, dates, initial_assets, active_plan)
        results.append(res)
        if (i+1) % 10 == 0:
            print(f"Completed {i+1}/50")
            
    # 6. Aggregate
    profits = [r['total_profit'] for r in results]
    yields = [r['yield_rate'] for r in results]
    max_caps = [r['max_capital'] for r in results]
    
    print("=" * 60)
    print("PREDICTION FOR '飞龙在天' 2026")
    print("-" * 60)
    print(f"Expected Total Profit (Median): {np.median(profits):,.2f} CNY")
    print(f"Expected Yield (Median): {np.median(yields):.2f}%")
    print(f"Expected Max Capital Occupied: {np.median(max_caps):,.2f} CNY")
    print("-" * 60)
    print(f"Profit Range (10th - 90th): {np.percentile(profits, 10):,.2f} - {np.percentile(profits, 90):,.2f}")
    print(f"Yield Range (10th - 90th): {np.percentile(yields, 10):.2f}% - {np.percentile(yields, 90):.2f}%")
    print("=" * 60)

if __name__ == "__main__":
    main()
