
import requests
import re
import json
import logging
import numpy as np
import random
from datetime import datetime, timedelta
from typing import List, Dict, Tuple, Optional
import math

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- 配置参数 ---
# 国泰黄金ETF联接C
HISTORY_FUND_CODE = "004253" 
TARGET_FUND_NAME = "国泰黄金ETF联接C" 
HISTORY_START = "2023-01-01"
HISTORY_END = "2025-12-31"
PREDICT_START = "2026-01-01"
PREDICT_END = "2026-12-31"
INVEST_AMOUNT = 50000.0
SIMULATION_COUNT = 100  # 模拟次数

# --- 类定义 ---

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
        self.period_type = period_type
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
        shares_count = amount / nav
        batch = ShareBatch(shares_count, nav, date)
        self.shares.append(batch)
        self.cash_invested += amount
        self.last_buy_date = date
        self.trades.append({
            "date": date, "type": "BUY", "amount": amount, "price": nav, "shares": shares_count
        })

    def redeem(self, nav: float, date: str, min_age: int = 7) -> float:
        redeemable_indices = []
        total_redeem_shares = 0.0
        for i, batch in enumerate(self.shares):
            if batch.get_age(date) >= min_age:
                redeemable_indices.append(i)
                total_redeem_shares += batch.amount
        
        if total_redeem_shares == 0:
            return 0.0
            
        redeem_value = total_redeem_shares * nav
        # C类 >= 7天 免赎回费 (模拟C类规则)
        net_amount = redeem_value
        self.cash_redeemed += net_amount
        
        for i in sorted(redeemable_indices, reverse=True):
            batch = self.shares.pop(i)
            self.trades.append({
                "date": date, "type": "SELL", "amount": net_amount, "price": nav, "shares": batch.amount
            })
        return net_amount

def calculate_volatility(returns: List[float], window: int = 20) -> Optional[float]:
    if len(returns) < window:
        return None
    recent = returns[-window:]
    mean_ret = sum(recent) / window
    variance = sum((r - mean_ret) ** 2 for r in recent) / (window - 1)
    return math.sqrt(variance) * math.sqrt(252) * 100

def xirr(cashflows: list[tuple[datetime, float]]) -> float | None:
    if not cashflows: return None
    sorted_cf = sorted(cashflows, key=lambda x: x[0])
    if not (any(a < 0 for _, a in sorted_cf) and any(a > 0 for _, a in sorted_cf)):
        return None
    
    t0 = sorted_cf[0][0]
    dates = [((cf[0] - t0).days) / 365.0 for cf in sorted_cf]
    amounts = [cf[1] for cf in sorted_cf]
    
    try:
        r = 0.1
        for _ in range(50):
            npv = sum(a / ((1.0 + r) ** t) for a, t in zip(amounts, dates))
            d_npv = sum(-t * a / ((1.0 + r) ** (t + 1.0)) for a, t in zip(amounts, dates) if t != 0)
            if d_npv == 0: return None
            r_next = r - npv / d_npv
            if abs(r_next - r) < 1e-6: return r_next
            r = r_next
    except:
        return None
    return None

# --- 数据获取与处理 ---

def get_history_stats():
    """获取历史数据并计算统计特征"""
    url = f"http://fund.eastmoney.com/pingzhongdata/{HISTORY_FUND_CODE}.js"
    try:
        response = requests.get(url)
        content = response.text
        match = re.search(r'Data_netWorthTrend\s*=\s*(\[.*?\]);', content)
        if not match: return None, None, None, None
        
        data_json = json.loads(match.group(1))
        parsed_data = []
        for item in data_json:
            dt = datetime.fromtimestamp(item['x'] / 1000)
            date_str = dt.strftime('%Y-%m-%d')
            # 仅使用 2023-2025 数据计算参数
            if HISTORY_START <= date_str <= HISTORY_END:
                parsed_data.append(float(item['y']))
        
        if not parsed_data: return None, None, None, None

        # 计算对数收益率
        log_returns = np.diff(np.log(parsed_data))
        
        mu = np.mean(log_returns)
        sigma = np.std(log_returns)
        last_nav = parsed_data[-1]
        
        # 返回完整数据用于预热
        all_data = []
        for item in data_json:
             dt = datetime.fromtimestamp(item['x'] / 1000)
             date_str = dt.strftime('%Y-%m-%d')
             all_data.append({"date": date_str, "nav": float(item['y'])})
        all_data.sort(key=lambda x: x['date'])
        
        return mu, sigma, last_nav, all_data
        
    except Exception as e:
        logger.error(f"Error: {e}")
        return None, None, None, None

def generate_path(start_price, mu, sigma, days, start_date_obj):
    """生成未来价格路径"""
    current_price = start_price
    current_date = start_date_obj
    path = []
    
    for _ in range(days):
        current_date += timedelta(days=1)
        while current_date.isoweekday() > 5:
            current_date += timedelta(days=1)
            
        r = np.random.normal(mu, sigma)
        current_price = current_price * math.exp(r)
        
        path.append({
            "date": current_date.strftime("%Y-%m-%d"),
            "nav": current_price
        })
        
    return path

# --- 模拟执行 ---

def run_simulation_once(future_data, history_data):
    """运行一次模拟"""
    # 预热数据
    warmup_data = history_data[-60:]
    full_data = warmup_data + future_data
    
    nav_values = [d['nav'] for d in full_data]
    ma5_cache = {}
    
    for i in range(len(full_data)):
        date = full_data[i]['date']
        if i >= 5:
            ma5_cache[date] = sum(nav_values[i-5:i]) / 5.0
        else:
            ma5_cache[date] = None
            
    # 初始化账户
    accounts = []
    for day in range(1, 29): accounts.append(Account(f"M_{day}", 3, day))
    for wd in range(1, 6): accounts.append(Account(f"W_{wd}", 1, wd))
    
    sim_data = future_data
    
    # 指标追踪变量
    daily_stats = []
    
    # 策略执行
    history_prices = [d['nav'] for d in history_data] # 用于计算长周期收益率
    
    for i, day_data in enumerate(sim_data):
        current_date = day_data['date']
        current_nav = day_data['nav']
        
        # 更新历史价格序列用于计算指标
        history_prices.append(current_nav)
        
        dt_obj = datetime.strptime(current_date, "%Y-%m-%d")
        ma5 = ma5_cache.get(current_date)
        
        # 计算动态收益率指标 (模拟 increase.py 中的 week/month/season_return)
        # 假设: 周=5交易日, 月=20交易日, 季=60交易日
        def get_return(days):
            if len(history_prices) > days:
                return (history_prices[-1] - history_prices[-1-days]) / history_prices[-1-days]
            return 0.0

        week_return = get_return(5)
        month_return = get_return(20)
        season_return = get_return(60)

        wd = dt_obj.isoweekday()
        dom = dt_obj.day
        
        for acc in accounts:
            # 1. Increase Check
            is_scheduled = False
            if acc.period_type == 3: # Monthly
                last_buy_dt = datetime.strptime(acc.last_buy_date, "%Y-%m-%d") if acc.last_buy_date else None
                if last_buy_dt and last_buy_dt.year == dt_obj.year and last_buy_dt.month == dt_obj.month:
                    is_scheduled = False
                elif dom >= acc.period_value:
                    is_scheduled = True
            elif acc.period_type == 1: # Weekly
                if acc.period_value == wd: is_scheduled = True
                
            if is_scheduled:
                times = 0.0
                if acc.total_cost > 0: times = acc.get_asset_value(current_nav) / INVEST_AMOUNT
                bypass_ma5 = (acc.period_type != 3) and (times <= 1)
                
                # --- 风控逻辑 1: MA5 守卫 ---
                # 只有在价格 > MA5 时才允许买入 (右侧交易)
                # 或者如果配置了"跌破MA5不买"，这里保持原逻辑
                gate_ok = True
                if ma5 is not None and current_nav <= ma5: gate_ok = False
                can_buy_gate = True if bypass_ma5 else gate_ok
                
                is_first = (acc.total_shares == 0)
                profit_rate_ok = True
                if not is_first:
                    # 亏损加仓: 收益率 < -1.0%
                    if acc.get_profit_rate(current_nav) * 100 > -1.0:
                        profit_rate_ok = False
                
                consecutive_ok = True
                if acc.last_buy_date:
                    last_buy_dt = datetime.strptime(acc.last_buy_date, "%Y-%m-%d")
                    if (dt_obj - last_buy_dt).days <= 1: consecutive_ok = False

                # --- 风控逻辑 2: 趋势过滤 (来自 increase.py) ---
                # 模拟 increase.py 中的 "执行回撤" 逻辑
                trend_ok = True
                
                # 1. 全部收益率为负
                if week_return < 0 and month_return < 0 and season_return < 0:
                    trend_ok = False
                
                # 2. 季度为负且(月或周为负)
                if season_return < 0 and (month_return < 0 or week_return < 0):
                    trend_ok = False
                    
                # 3. 季度为正但(月和周均为负)
                if season_return > 0 and (month_return < 0 and week_return < 0):
                    trend_ok = False

                # 注意: 无法模拟 Rank (排名) 逻辑，因为没有市场数据
                    
                if can_buy_gate and profit_rate_ok and consecutive_ok and trend_ok:
                    acc.buy(INVEST_AMOUNT, current_nav, current_date)
                    
            # 2. Redeem Check (强制 1% 止盈)
            if acc.total_shares > 0:
                p_rate = acc.get_profit_rate(current_nav) * 100
                if p_rate > 1.0:
                    acc.redeem(current_nav, current_date, min_age=7)

        # 每日结算
        total_asset = sum(acc.get_asset_value(current_nav) for acc in accounts)
        total_invested = sum(acc.cash_invested for acc in accounts)
        total_redeemed = sum(acc.cash_redeemed for acc in accounts)
        
        # 累计盈亏
        accumulated_profit = total_asset + total_redeemed - total_invested
        
        # 浮动盈亏 (当前持仓的盈亏)
        current_holding_cost = sum(acc.total_cost for acc in accounts)
        floating_pl = total_asset - current_holding_cost
        
        # 资金占用
        net_invested = total_invested - total_redeemed
        
        daily_stats.append({
            "date": current_date,
            "accumulated_profit": accumulated_profit,
            "floating_pl": floating_pl,
            "net_invested": net_invested,
            "holding_cost": current_holding_cost,
            "total_asset": total_asset,
            "total_cost": current_holding_cost
        })

    # --- 计算指标 ---
    
    # 0. Average Holding Cost (平均持有资金)
    avg_holding = sum(d['holding_cost'] for d in daily_stats) / len(daily_stats) if daily_stats else 0.0

    # 1. Max Occupied (最大资金占用)
    max_occupied = max((d['net_invested'] for d in daily_stats), default=0.0)
    
    # 2. Max Drawdown Amount (最大回撤金额 - 基于累计收益曲线)
    profit_curve = [d['accumulated_profit'] for d in daily_stats]
    max_dd_amount = 0.0
    peak = -float('inf')
    for p in profit_curve:
        if p > peak: peak = p
        dd = peak - p
        if dd > max_dd_amount: max_dd_amount = dd
        
    # 3. Max Floating Loss Ratio (最大浮亏比例)
    min_float_ratio = 0.0
    min_float_amt = 0.0
    for d in daily_stats:
        if d['total_cost'] > 0:
            ratio = d['floating_pl'] / d['total_cost']
            if ratio < min_float_ratio: min_float_ratio = ratio
            if d['floating_pl'] < min_float_amt: min_float_amt = d['floating_pl']
            
    # 4. Yield on Holding (Total Profit / Avg Holding Cost)
    final_profit = daily_stats[-1]['accumulated_profit']
    yield_holding = final_profit / avg_holding if avg_holding > 0 else 0.0
    
    # 5. XIRR
    # Collect all cashflows
    all_trades = []
    for acc in accounts: all_trades.extend(acc.trades)
    xirr_flows = []
    for t in all_trades:
        dt = datetime.strptime(t['date'], "%Y-%m-%d")
        amt = -t['amount'] if t['type'] == 'BUY' else t['amount']
        xirr_flows.append((dt, amt))
    # Add final value
    final_val = sum(acc.get_asset_value(sim_data[-1]['nav']) for acc in accounts)
    xirr_flows.append((datetime.strptime(sim_data[-1]['date'], "%Y-%m-%d"), final_val))
    
    x_val = xirr(xirr_flows)
    
    return {
        "annual_profit": final_profit,
        "max_occupied": max_occupied,
        "avg_holding": avg_holding,
        "yield_holding": yield_holding,
        "max_dd_amount": max_dd_amount,
        "max_float_loss_amt": min_float_amt,
        "max_float_loss_ratio": min_float_ratio,
        "xirr": x_val if x_val else 0.0,
        "total_invested": sum(acc.cash_invested for acc in accounts)
    }

def main():
    print(f"正在获取 {HISTORY_FUND_CODE} (用于模拟 {TARGET_FUND_NAME}) 的历史参数...")
    mu, sigma, last_nav, history_data = get_history_stats()
    
    if mu is None:
        print("无法获取数据")
        return
        
    print(f"历史参数 (2023-2025): 日均收益率={mu:.6f}, 日波动率={sigma:.6f}")
    print(f"当前净值: {last_nav}")
    print(f"开始 {SIMULATION_COUNT} 次蒙特卡洛模拟 (2026年)...")
    
    results = []
    start_date = datetime.strptime(HISTORY_END, "%Y-%m-%d")
    
    for i in range(SIMULATION_COUNT):
        path = generate_path(last_nav, mu, sigma, 252, start_date)
        res = run_simulation_once(path, history_data)
        results.append(res)
        if (i+1) % 20 == 0: print(f"完成 {i+1}/{SIMULATION_COUNT}...")
            
    # 统计
    def get_stats(key):
        vals = [r[key] for r in results]
        return np.mean(vals), np.median(vals), np.min(vals), np.max(vals)
        
    avg_profit, med_profit, _, _ = get_stats("annual_profit")
    avg_occ, med_occ, _, _ = get_stats("max_occupied")
    avg_holding, med_holding, _, _ = get_stats("avg_holding")
    avg_yield_h, med_yield_h, _, _ = get_stats("yield_holding")
    avg_xirr, med_xirr, _, _ = get_stats("xirr")
    avg_mdd, med_mdd, _, _ = get_stats("max_dd_amount")
    avg_mfl, med_mfl, _, _ = get_stats("max_float_loss_amt")
    avg_mflr, med_mflr, _, _ = get_stats("max_float_loss_ratio")
    avg_inv, med_inv, _, _ = get_stats("total_invested")
    
    print("\n" + "="*50)
    print(f"2026年 投资预测报告: {TARGET_FUND_NAME}")
    print("="*50)
    print("策略: 28日定投 + 5周定投 (单笔5w)")
    print("逻辑: 亏损<-1%加仓(MA5守卫) + 强制1%止盈(仅赎回0费率)")
    print("-" * 50)
    
    print(f"【收益预测】")
    print(f"预计年收益金额:  {avg_profit:,.2f} 元 (中位数: {med_profit:,.2f})")
    print(f"预计收益率(占持有): {avg_yield_h*100:.2f}% (中位数: {med_yield_h*100:.2f}%)")
    print(f"预计年化收益率(XIRR): {avg_xirr*100:.2f}% (中位数: {med_xirr*100:.2f}%)")
    print("-" * 50)
    
    print(f"【资金与风险】")
    print(f"最大资金占用:    {avg_occ:,.2f} 元 (建议准备充足本金)")
    print(f"平均持有资金:    {avg_holding:,.2f} 元 (平均每日持仓成本)")
    print(f"最大回撤金额:    {avg_mdd:,.2f} 元 (利润回吐)")
    print(f"最大浮亏金额:    {avg_mfl:,.2f} 元 (本金暂时亏损)")
    print(f"最大浮亏比例:    {avg_mflr*100:.2f}% (持仓最大跌幅)")
    print("-" * 50)
    
    print(f"【交易活跃度】")
    print(f"预计年累计付款:  {avg_inv:,.2f} 元")
    print("="*50)

if __name__ == "__main__":
    main()
