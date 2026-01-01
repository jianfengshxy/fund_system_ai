
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
FUND_CODE = "004253"
FUND_NAME = "国泰黄金ETF联接C"
HISTORY_START = "2023-01-01"
HISTORY_END = "2025-12-31"
PREDICT_START = "2026-01-01"
PREDICT_END = "2026-12-31"
INVEST_AMOUNT = 50000.0
SIMULATION_COUNT = 100  # 模拟次数

# --- 类定义 (复用回测逻辑) ---

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
        # C类 >= 7天 免赎回费
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
    """获取2023-2025的历史数据并计算统计特征"""
    url = f"http://fund.eastmoney.com/pingzhongdata/{FUND_CODE}.js"
    try:
        response = requests.get(url)
        content = response.text
        match = re.search(r'Data_netWorthTrend\s*=\s*(\[.*?\]);', content)
        if not match: return None, None, None
        
        data_json = json.loads(match.group(1))
        parsed_data = []
        for item in data_json:
            dt = datetime.fromtimestamp(item['x'] / 1000)
            date_str = dt.strftime('%Y-%m-%d')
            # 仅使用 2023-2025 数据计算参数
            if HISTORY_START <= date_str <= HISTORY_END:
                parsed_data.append(float(item['y']))
        
        if not parsed_data: return None, None, None

        # 计算对数收益率
        log_returns = np.diff(np.log(parsed_data))
        
        # 计算日均收益率(Drift)和日标准差(Volatility)
        mu = np.mean(log_returns)
        sigma = np.std(log_returns)
        
        last_nav = parsed_data[-1]
        
        # 还要返回完整数据用于预热指标计算 (MA5, Vol)
        # 重新解析所有数据
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
    """生成一条未来的价格路径"""
    dt = 1
    path = []
    current_price = start_price
    
    # 生成交易日历 (简化：跳过周末)
    current_date = start_date_obj
    
    for _ in range(days):
        # 寻找下一个工作日
        current_date += timedelta(days=1)
        while current_date.isoweekday() > 5:
            current_date += timedelta(days=1)
            
        # GBM 模型
        # S_t = S_{t-1} * exp((mu - 0.5 * sigma^2) + sigma * Z)
        # 注意: mu 已经是 log return 的 mean，所以直接用 normal(mu, sigma)
        # 或者: r = np.random.normal(mu, sigma)
        # price = price * exp(r)
        
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
    # 合并历史数据(用于指标预热)和未来数据
    # 取历史最后60天用于计算MA5和Vol
    warmup_data = history_data[-60:]
    full_data = warmup_data + future_data
    
    # 建立索引
    nav_values = [d['nav'] for d in full_data]
    returns = []
    for i in range(1, len(nav_values)):
        returns.append((nav_values[i] - nav_values[i-1]) / nav_values[i-1])
        
    ma5_cache = {}
    vol_cache = {}
    
    for i in range(len(full_data)):
        date = full_data[i]['date']
        # MA5
        if i >= 5:
            ma5_cache[date] = sum(nav_values[i-5:i]) / 5.0
        else:
            ma5_cache[date] = None
        # Vol
        if i >= 21:
            hist_returns = returns[i-20:i]
            if len(hist_returns) == 20:
                vol_cache[date] = calculate_volatility(hist_returns)
            else:
                vol_cache[date] = None
        else:
            vol_cache[date] = None
            
    # 初始化账户
    accounts = []
    for day in range(1, 29): accounts.append(Account(f"M_{day}", 3, day))
    for wd in range(1, 6): accounts.append(Account(f"W_{wd}", 1, wd))
    
    # 开始模拟未来部分
    sim_data = future_data # 仅遍历未来部分
    
    # 追踪最大占用
    # 由于是未来预测，我们假设账户从0开始？
    # 用户问 "未来在2026年我仍然采用这种方式"
    # 可能是指 2026年这一年重新开始，或者接续？
    # 通常用户想知道"如果我2026年做一年，预期结果如何"。
    # 假设从零开始 (独立的一年)。如果是接续，需要继承2025年底的持仓，这太复杂且用户未提供当前持仓。
    # 所以假设：2026年1月1日开始全新的定投计划。
    
    # 全局资金流
    daily_net_invested = [] 
    all_trades = []
    
    for i, day_data in enumerate(sim_data):
        current_date = day_data['date']
        current_nav = day_data['nav']
        dt_obj = datetime.strptime(current_date, "%Y-%m-%d")
        
        ma5 = ma5_cache.get(current_date)
        vol = vol_cache.get(current_date)
        
        wd = dt_obj.isoweekday()
        dom = dt_obj.day
        
        for acc in accounts:
            # 1. Invest Check
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
                
                gate_ok = True
                if ma5 is not None and current_nav <= ma5: gate_ok = False
                
                can_buy_gate = True if bypass_ma5 else gate_ok
                
                is_first = (acc.total_shares == 0)
                profit_rate_ok = True
                if not is_first:
                    if acc.get_profit_rate(current_nav) * 100 > -1.0:
                        profit_rate_ok = False
                
                consecutive_ok = True
                if acc.last_buy_date:
                    last_buy_dt = datetime.strptime(acc.last_buy_date, "%Y-%m-%d")
                    if (dt_obj - last_buy_dt).days <= 1: consecutive_ok = False
                    
                if can_buy_gate and profit_rate_ok and consecutive_ok:
                    acc.buy(INVEST_AMOUNT, current_nav, current_date)
                    
            # 2. Redeem Check
            if acc.total_shares > 0 and vol is not None:
                stop_rate = max(vol, 3.0)
                if acc.get_profit_rate(current_nav) * 100 > stop_rate:
                    acc.redeem(current_nav, current_date, min_age=7)

    # 结算
    cum_invested = sum(acc.cash_invested for acc in accounts)
    cum_redeemed = sum(acc.cash_redeemed for acc in accounts)
    final_shares_val = sum(acc.get_asset_value(sim_data[-1]['nav']) for acc in accounts)
    total_profit = final_shares_val + cum_redeemed - cum_invested
    
    # 计算 Max Occupied
    # 重算每日资金流
    all_trades = []
    for acc in accounts: all_trades.extend(acc.trades)
    all_trades.sort(key=lambda x: x['date'])
    
    curr_invested = 0.0
    curr_redeemed = 0.0
    max_occupied = 0.0
    
    trade_idx = 0
    for day_data in sim_data:
        d = day_data['date']
        while trade_idx < len(all_trades) and all_trades[trade_idx]['date'] == d:
            t = all_trades[trade_idx]
            if t['type'] == 'BUY': curr_invested += t['amount']
            elif t['type'] == 'SELL': curr_redeemed += t['amount']
            trade_idx += 1
        
        net = curr_invested - curr_redeemed
        if net > max_occupied: max_occupied = net
        
    # XIRR
    xirr_flows = []
    for t in all_trades:
        dt = datetime.strptime(t['date'], "%Y-%m-%d")
        amt = -t['amount'] if t['type'] == 'BUY' else t['amount']
        xirr_flows.append((dt, amt))
    xirr_flows.append((datetime.strptime(sim_data[-1]['date'], "%Y-%m-%d"), final_shares_val))
    
    x_val = xirr(xirr_flows)
    
    return {
        "max_occupied": max_occupied,
        "total_profit": total_profit,
        "xirr": x_val if x_val else 0.0,
        "total_invested": cum_invested
    }

def main():
    print("正在获取历史数据并计算参数...")
    mu, sigma, last_nav, history_data = get_history_stats()
    
    if mu is None:
        print("无法获取数据")
        return
        
    print(f"历史参数 (2023-2025): 日均收益率(Drift)={mu:.6f}, 日波动率(Vol)={sigma:.6f}")
    print(f"当前净值: {last_nav}")
    print(f"开始 {SIMULATION_COUNT} 次蒙特卡洛模拟 (2026年)...")
    
    results = []
    
    start_date = datetime.strptime(HISTORY_END, "%Y-%m-%d")
    
    for i in range(SIMULATION_COUNT):
        # 生成路径
        path = generate_path(last_nav, mu, sigma, 252, start_date) # 约252个交易日
        # 运行回测
        res = run_simulation_once(path, history_data)
        results.append(res)
        if (i+1) % 10 == 0:
            print(f"完成 {i+1}/{SIMULATION_COUNT} 次模拟...")
            
    # 统计结果
    avg_occupied = np.mean([r['max_occupied'] for r in results])
    avg_profit = np.mean([r['total_profit'] for r in results])
    avg_xirr = np.mean([r['xirr'] for r in results])
    
    # 中位数
    med_occupied = np.median([r['max_occupied'] for r in results])
    med_profit = np.median([r['total_profit'] for r in results])
    med_xirr = np.median([r['xirr'] for r in results])
    
    print("\n" + "="*40)
    print("2026年 投资预测报告 (基于历史波动率模拟)")
    print("="*40)
    print(f"模拟场景: 假设2026年市场延续2023-2025年的波动特征")
    print(f"策略: 28日定投 + 5周定投 (单笔{INVEST_AMOUNT})")
    print("-" * 40)
    print(f"【预计资金占用】 (准备金)")
    print(f"平均值: {avg_occupied:,.2f} 元")
    print(f"中位数: {med_occupied:,.2f} 元")
    print("-" * 40)
    print(f"【预计年度收益金额】")
    print(f"平均值: {avg_profit:,.2f} 元")
    print(f"中位数: {med_profit:,.2f} 元")
    print("-" * 40)
    print(f"【预计年化收益率 (XIRR)】")
    print(f"平均值: {avg_xirr*100:.2f}%")
    print(f"中位数: {med_xirr*100:.2f}%")
    print("="*40)
    print("注: 蒙特卡洛模拟仅供参考，不代表未来实际收益。")

if __name__ == "__main__":
    main()
