
import logging
import numpy as np
import pandas as pd
import requests
import json
from datetime import datetime, timedelta

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def get_fund_data_eastmoney(fund_code):
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
            logger.warning(f"Data_netWorthTrend not found in response for {fund_code}")
            return pd.DataFrame()
        
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
        return pd.DataFrame()

def simulate_recovery_with_strategy(
    price_history, 
    initial_assets, 
    add_amount=5000.0, 
    n_sims=1000, 
    max_days=730
):
    """
    Simulate recovery time including "buy low" strategy.
    
    Strategy Logic (simplified from files):
    1. Buy (Add):
       - If Profit Rate < -1.0%
       - AND Price > MA5 (Uptrend check from nav5_gate)
       - AND Not all trends (Week/Month/Season) are negative
       - Action: Buy `add_amount`
    2. Sell (Stop Profit):
       - If Profit Rate > 5.0%
       - Action: Stop simulation (Success)
       
    Args:
        price_history (pd.Series): Historical NAVs.
        initial_assets (dict): {'shares': float, 'cost': float, 'nav': float}
        add_amount (float): Amount to add when buy triggered.
    """
    days_to_recover = []
    final_returns = []
    
    # Pre-calculate returns for bootstrap
    daily_returns = price_history.pct_change().dropna().values
    
    # Calculate historical MA5 window for volatility context? 
    # For bootstrap, we construct a price path, then calculate MA5 on that path.
    
    for _ in range(n_sims):
        # 1. Generate Price Path
        # We need enough history to calc MA5 and Season return at step 0?
        # Simulation starts at t=0.
        
        # Sample returns
        sampled_rets = np.random.choice(daily_returns, size=max_days, replace=True)
        
        # Construct Price Path
        # Start from current NAV
        current_nav = initial_assets['nav']
        prices = [current_nav]
        for r in sampled_rets:
            prices.append(prices[-1] * (1 + r))
            
        # 2. Walk through path
        # Initial State
        shares = initial_assets['shares']
        total_cost = initial_assets['cost'] * shares
        last_buy_day = None
        
        success_day = None
        
        # We need to track MA5, Week(5), Month(20), Season(60) returns.
        # Since we only have future path, we can assume:
        # - MA5 at t=0 is based on history (can pass in)
        # - Or just build up history as we go.
        # For simplicity, we use the simulated prices. 
        # But indices < 60 won't have full history. 
        # We can prepend actual recent history to the path for indicator calculation.
        
        # Let's simplify indicators:
        # MA5: Average of last 5 prices
        # Week Ret: p[t]/p[t-5] - 1
        # Month Ret: p[t]/p[t-20] - 1
        # Season Ret: p[t]/p[t-60] - 1
        
        # We need to prepend real history to enable indicators at t=1
        # However, bootstrap path is random, so real history + random future might have a jump if we are not careful?
        # We constructed path starting from current NAV, so it is continuous.
        
        # Let's prepend 60 days of 'flat' or 'trend' prices? 
        # No, better to just use the `price_history` tail as context.
        history_context = list(price_history.values[-60:]) # Last 60 days
        full_path = history_context + prices[1:] # prices[0] is current_nav which should overlap with history[-1] if valid
        
        # Adjust indices: simulation day i corresponds to full_path index (60 + i)
        
        for i in range(max_days):
            # Current Day Index in full_path
            idx = 60 + i + 1 # +1 because prices[1] is day 1
            if idx >= len(full_path): break
            
            curr_p = full_path[idx]
            
            # 1. Update Portfolio Stats
            current_value = shares * curr_p
            # Avg cost
            avg_cost = total_cost / shares if shares > 0 else 0
            
            # Profit Rate
            # Note: User's profit rate calculation might be (NAV - AvgCost) / AvgCost
            profit_rate = (curr_p - avg_cost) / avg_cost * 100
            
            # 2. Check Stop Profit
            if profit_rate > 5.0:
                success_day = i + 1
                break
                
            # 3. Check Buy (Add)
            # Logic from Custom Strategy
            # - Trade Guard: Assume we can buy (ignore T+1 restrictions for simplified sim, or limit frequency)
            #   Let's limit buying to once every 5 days to avoid exploding capital?
            #   The script checks "has_buy_submission_on_dates". 
            #   Let's assume we can buy if we didn't buy yesterday.
            
            # Indicators
            ma5 = np.mean(full_path[idx-5:idx]) # Previous 5 days avg? 
            # nav5_gate uses 'estimated_value' (curr_p) vs 'nav_5day_avg' (avg of t-5 to t-1?)
            # Usually MA5 includes today or yesterday. 
            # Code: est_val > nav5_val. 
            # Let's assume nav5_val is MA of previous 5 closes.
            ma5_prev = np.mean(full_path[idx-5:idx])
            
            # Trend Returns
            # Week: 5 days
            week_ret = full_path[idx] / full_path[idx-5] - 1
            # Month: 20 days
            month_ret = full_path[idx] / full_path[idx-20] - 1
            # Season: 60 days
            season_ret = full_path[idx] / full_path[idx-60] - 1
            
            # Conditions
            # A. Profit Rate < -1.0% (Yes, we are likely here)
            # B. MA5 Gate: Price > MA5
            is_uptrend = curr_p > ma5_prev
            
            # C. Trend Checks (Not all negative)
            all_neg = (week_ret < 0) and (month_ret < 0) and (season_ret < 0)
            
            # D. Mixed Trend Checks
            # if season < 0 and (month < 0 or week < 0) -> skip
            bad_trend_1 = (season_ret < 0) and (month_ret < 0 or week_ret < 0)
            
            # if season > 0 and (month < 0 and week < 0) -> skip
            bad_trend_2 = (season_ret > 0) and (month_ret < 0 and week_ret < 0)
            
            can_buy = (
                profit_rate < -1.0 and
                is_uptrend and
                not all_neg and
                not bad_trend_1 and
                not bad_trend_2
            )
            
            if can_buy:
                # Check frequency limit (T+2 effectively, or just not consecutive days?)
                # If we bought on day i, we can't buy on day i+1 (pending).
                if last_buy_day is None or (i - last_buy_day) >= 2:
                    # Buy
                    shares_bought = add_amount / curr_p
                    shares += shares_bought
                    total_cost += add_amount
                    last_buy_day = i
                
        if success_day:
            # Calculate Annualized Return for this path
            # Viewpoint: Mark-to-Market Return
            # Initial Investment = Initial Asset Value (69155)
            # Additions = Total Added Cash
            # Final Value = Total Cost * (1 + ProfitRate/100)
            # We use XIRR approximation or simple Time-Weighted if cashflows are complex.
            # Simplified: ROI = (FinalValue - (InitialValue + TotalAdded)) / (InitialValue + TotalAdded)
            # This treats additions as if they were present at start for denominator (conservative), 
            # or we can use specific timing.
            # Given short duration, let's use:
            # ROI = (FinalValue - TotalInput) / TotalInput
            # where TotalInput = InitialMarketValue + TotalAddedCash
            
            # Note: FinalValue is determined by the stop condition.
            # But we simulated the price, so we have exact Final Value = shares * curr_p
            
            final_value = shares * curr_p
            total_added_cash = total_cost - initial_assets['cost'] * initial_assets['shares']
            initial_market_value = initial_assets['shares'] * initial_assets['nav']
            
            total_invested_mv = initial_market_value + total_added_cash
            net_profit = final_value - total_invested_mv
            roi = net_profit / total_invested_mv
            
            # Annualize: (1 + ROI) ^ (365 / days) - 1
            # If days < 1, assume 1
            d = max(1, success_day)
            ann_ret = (1 + roi) ** (365.0 / d) - 1
            
            days_to_recover.append(success_day)
            final_returns.append(ann_ret)
        else:
            days_to_recover.append(None)
            final_returns.append(None)
            
    return days_to_recover, final_returns

def run_simulation_scenario(price_history, initial_assets, add_amount, scenario_name, n_sims, max_days):
    logger.info(f"Starting simulation: {scenario_name}...")
    days_results, ret_results = simulate_recovery_with_strategy(
        price_history, 
        initial_assets, 
        add_amount=add_amount,
        n_sims=n_sims, 
        max_days=max_days
    )
    
    reached_indices = [i for i, x in enumerate(days_results) if x is not None]
    reached_days = [days_results[i] for i in reached_indices]
    reached_rets = [ret_results[i] for i in reached_indices]
    
    success_rate = len(reached_days) / n_sims
    
    metrics = {}
    metrics['name'] = scenario_name
    metrics['success_rate'] = success_rate
    
    if reached_days:
        metrics['median_days'] = int(np.median(reached_days))
        metrics['p10_days'] = int(np.percentile(reached_days, 10)) # Optimistic time (short)
        metrics['p90_days'] = int(np.percentile(reached_days, 90)) # Pessimistic time (long)
        metrics['prob_1yr'] = len([x for x in reached_days if x <= 252]) / n_sims * 100
        
        # Returns corresponding to time percentiles? 
        # Usually Optimistic Time (Short) -> Very High Annualized Return
        # Pessimistic Time (Long) -> Lower Annualized Return
        # Let's calculate percentiles of Annualized Return directly.
        # Note: p90 return is High, p10 return is Low.
        # But usually "Optimistic Scenario" means High Return.
        metrics['median_ret'] = np.median(reached_rets) * 100
        metrics['p90_ret'] = np.percentile(reached_rets, 90) * 100 # High Return (Optimistic)
        metrics['p10_ret'] = np.percentile(reached_rets, 10) * 100 # Low Return (Pessimistic)
        
        # Correlation: Short Time usually means High Return?
        # Let's check consistency.
    else:
        metrics['median_days'] = ">" + str(max_days)
        metrics['p10_days'] = ">" + str(max_days)
        metrics['p90_days'] = ">" + str(max_days)
        metrics['prob_1yr'] = 0.0
        metrics['median_ret'] = 0.0
        metrics['p90_ret'] = 0.0
        metrics['p10_ret'] = 0.0
        
    return metrics

def main():
    fund_code = "021031"
    fund_name = "汇添富国证港股通创新药ETF发起式联接C"
    
    # Current State
    current_val = 69155.41
    profit_rate = -13.55
    # Cost Basis = Value / (1 + Rate)
    # Rate = -13.55% -> 1 - 0.1355 = 0.8645
    cost_basis = current_val / (1 + profit_rate/100)
    
    logger.info(f"Fund: {fund_name} ({fund_code})")
    logger.info(f"Initial State: Value={current_val:.2f}, Cost={cost_basis:.2f}, Rate={profit_rate}%")
    
    # 1. Get Data
    df = get_fund_data_eastmoney(fund_code)
    
    if df.empty:
        logger.warning(f"Failed to get data for {fund_code}. Trying proxy fund 010823...")
        df = get_fund_data_eastmoney("010823")
        
    if df.empty:
        logger.error("Failed to get historical data. Cannot simulate.")
        return

    # Current NAV
    current_nav = df.iloc[-1]['nav']
    initial_shares = current_val / current_nav
    initial_cost_per_share = cost_basis / initial_shares
    
    initial_assets = {
        'shares': initial_shares,
        'cost': initial_cost_per_share, 
        'nav': current_nav
    }
    
    n_sims = 2000
    max_days = 730 
    price_history = df['nav']
    
    # Scenario A: Active Strategy
    res_active = run_simulation_scenario(
        price_history, initial_assets, 5000.0, 
        "Active Strategy (Add 5k)", n_sims, max_days
    )
    
    # Scenario B: Passive Holding
    res_passive = run_simulation_scenario(
        price_history, initial_assets, 0.0, 
        "Passive Holding (No Add)", n_sims, max_days
    )
    
    print("\n" + "="*80)
    print(f"  BACKTEST RESULT: {fund_name}")
    print("-" * 80)
    print(f"  Initial State: Profit Rate {profit_rate}% (Float Loss)")
    print(f"  Target: Total Profit Rate > 5.0% (On Cost)")
    print("-" * 80)
    print(f"  {'Metric':<30} | {'Active Strategy':<22} | {'Passive Holding':<22}")
    print("-" * 80)
    print(f"  {'Median Recovery Time':<30} | {str(res_active['median_days']) + ' days':<22} | {str(res_passive['median_days']) + ' days':<22}")
    print(f"  {'Optimistic Time (10% Prob)':<30} | {str(res_active['p10_days']) + ' days':<22} | {str(res_passive['p10_days']) + ' days':<22}")
    print(f"  {'Pessimistic Time (90% Prob)':<30} | {str(res_active['p90_days']) + ' days':<22} | {str(res_passive['p90_days']) + ' days':<22}")
    print("-" * 80)
    print(f"  {'Median Annualized Return':<30} | {res_active['median_ret']:.1f}%{'':<21} | {res_passive['median_ret']:.1f}%{'':<21}")
    print(f"  {'Optimistic Return (90% tile)':<30} | {res_active['p90_ret']:.1f}%{'':<21} | {res_passive['p90_ret']:.1f}%{'':<21}")
    print(f"  {'Pessimistic Return (10% tile)':<30} | {res_active['p10_ret']:.1f}%{'':<21} | {res_passive['p10_ret']:.1f}%{'':<21}")
    print("=" * 80 + "\n")


if __name__ == "__main__":
    main()
