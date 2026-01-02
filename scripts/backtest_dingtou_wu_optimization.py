#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
东吴配置优化混合C(011707)定投回测脚本
模拟5个周定投（周一至周五各10000元）和28个月定投（1-28号各5000元）策略
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import json
from typing import Dict, List, Tuple
import matplotlib.pyplot as plt
import seaborn as sns
import matplotlib

# 设置中文字体
matplotlib.rcParams['font.sans-serif'] = ['SimHei', 'Arial Unicode MS', 'DejaVu Sans']
matplotlib.rcParams['axes.unicode_minus'] = False

class DingTouBacktest:
    def __init__(self, fund_code: str = "011707"):
        self.fund_code = fund_code
        self.nav_data = []
        self.trading_days = []
        self.results = {}
        
    def load_nav_data(self, nav_data: List[Dict]):
        """加载净值数据"""
        self.nav_data = []
        self.trading_days = []
        
        # 转换API返回的数据格式
        for item in nav_data:
            if 'date' in item and 'nav' in item:
                # 已经是转换后的格式
                if isinstance(item['date'], str):
                    item['date'] = datetime.strptime(item['date'], '%Y-%m-%d')
                self.nav_data.append(item)
                self.trading_days.append(item['date'])
            elif 'navDate' in item:
                # 原始API格式，需要转换
                date_str = item['navDate'].replace('年', '-').replace('月', '-').replace('日', '')
                try:
                    date_obj = datetime.strptime(date_str, '%Y-%m-%d')
                    nav_value = float(item.get('nav', 0))
                    
                    self.nav_data.append({
                        'date': date_obj,
                        'nav': nav_value,
                        'dailyReturn': item.get('dailyReturn', '0%')
                    })
                    self.trading_days.append(date_obj)
                except:
                    continue
        
        # 按日期排序
        self.nav_data.sort(key=lambda x: x.get('date', datetime.min))
        self.trading_days.sort()
        
        print(f"加载了 {len(self.nav_data)} 个交易日数据")
        print(f"数据时间范围: {self.trading_days[0]} 到 {self.trading_days[-1]}")
    
    def simulate_dingtou_strategy(self):
        """模拟定投策略"""
        if not self.nav_data:
            raise ValueError("请先加载净值数据")
        
        # 初始化投资记录
        investment_records = []
        total_investment = 0
        total_shares = 0
        max_investment = 0
        cash_balance = 0
        
        # 按日期处理每个交易日
        for day_data in self.nav_data:
            if 'date' not in day_data or 'nav' not in day_data:
                continue
                
            current_date = day_data['date']
            current_nav = float(day_data['nav'])
            
            # 检查是否为定投日
            daily_investment = 0
            
            # 周定投：周一至周五各10000元
            if current_date.weekday() < 5:  # 0-4 表示周一到周五
                daily_investment += 10000
            
            # 月定投：1-28号各5000元
            if 1 <= current_date.day <= 28:
                daily_investment += 5000
            
            # 执行定投
            if daily_investment > 0:
                shares_bought = daily_investment / current_nav
                total_shares += shares_bought
                total_investment += daily_investment
                cash_balance += daily_investment
                
                investment_records.append({
                    'date': current_date,
                    'nav': current_nav,
                    'investment': daily_investment,
                    'shares_bought': shares_bought,
                    'total_investment': total_investment,
                    'total_shares': total_shares,
                    'portfolio_value': total_shares * current_nav,
                    'cash_balance': cash_balance
                })
                
                # 更新最大投资金额
                if cash_balance > max_investment:
                    max_investment = cash_balance
            else:
                # 非定投日，只更新市值
                portfolio_value = total_shares * current_nav
                investment_records.append({
                    'date': current_date,
                    'nav': current_nav,
                    'investment': 0,
                    'shares_bought': 0,
                    'total_investment': total_investment,
                    'total_shares': total_shares,
                    'portfolio_value': portfolio_value,
                    'cash_balance': cash_balance
                })
        
        # 计算最终结果
        final_record = investment_records[-1]
        final_value = final_record['portfolio_value']
        total_profit = final_value - total_investment
        total_return_rate = (total_profit / total_investment) * 100 if total_investment > 0 else 0
        
        # 计算年化收益率
        days_invested = (final_record['date'] - investment_records[0]['date']).days
        annualized_return = ((1 + total_return_rate/100) ** (365/days_invested) - 1) * 100 if days_invested > 0 else 0
        
        self.results = {
            'total_investment': total_investment,
            'final_value': final_value,
            'total_profit': total_profit,
            'total_return_rate': total_return_rate,
            'annualized_return': annualized_return,
            'max_investment': max_investment,
            'investment_days': days_invested,
            'investment_records': investment_records
        }
        
        return self.results
    
    def calculate_yearly_metrics(self):
        """计算历年指标"""
        yearly_metrics = {}
        
        for record in self.results['investment_records']:
            year = record['date'].year
            
            if year not in yearly_metrics:
                yearly_metrics[year] = {
                    'year': year,
                    'total_investment': 0,
                    'ending_value': 0,
                    'max_investment': 0,
                    'investment_count': 0
                }
            
            yearly_metrics[year]['total_investment'] = record['total_investment']
            yearly_metrics[year]['ending_value'] = record['portfolio_value']
            yearly_metrics[year]['max_investment'] = max(yearly_metrics[year].get('max_investment', 0), 
                                                       record['cash_balance'])
            if record['investment'] > 0:
                yearly_metrics[year]['investment_count'] += 1
        
        # 计算年收益率
        years = sorted(yearly_metrics.keys())
        for i, year in enumerate(years):
            if i > 0:
                prev_year = years[i-1]
                beginning_value = yearly_metrics[prev_year]['ending_value']
                yearly_investment = yearly_metrics[year]['total_investment'] - yearly_metrics[prev_year]['total_investment']
                ending_value = yearly_metrics[year]['ending_value']
                
                yearly_return = ((ending_value - beginning_value - yearly_investment) / 
                               (beginning_value + yearly_investment)) * 100 if (beginning_value + yearly_investment) > 0 else 0
                yearly_metrics[year]['yearly_return'] = yearly_return
            else:
                yearly_metrics[year]['yearly_return'] = 0
        
        return list(yearly_metrics.values())
    
    def generate_report(self):
        """生成详细报告"""
        yearly_metrics = self.calculate_yearly_metrics()
        
        print("=" * 60)
        print("东吴配置优化混合C(011707)定投回测报告")
        print("=" * 60)
        print(f"基金代码: {self.fund_code}")
        print(f"回测期间: {self.results['investment_records'][0]['date'].strftime('%Y-%m-%d')} 到 {self.results['investment_records'][-1]['date'].strftime('%Y-%m-%d')}")
        print(f"投资天数: {self.results['investment_days']} 天")
        print(f"总投资金额: {self.results['total_investment']:,.2f} 元")
        print(f"最终市值: {self.results['final_value']:,.2f} 元")
        print(f"总收益: {self.results['total_profit']:,.2f} 元")
        print(f"总收益率: {self.results['total_return_rate']:.2f}%")
        print(f"年化收益率: {self.results['annualized_return']:.2f}%")
        print(f"最大占据金额: {self.results['max_investment']:,.2f} 元")
        print("\n" + "=" * 60)
        print("历年业绩指标:")
        print("=" * 60)
        print(f"{'年份':<8} {'投资金额(元)':<15} {'年末市值(元)':<15} {'年收益率(%)':<12} {'最大金额(元)':<15} {'定投次数':<8}")
        
        for metrics in yearly_metrics:
            print(f"{metrics['year']:<8} {metrics['total_investment']:>15,.2f} {metrics['ending_value']:>15,.2f} "
                  f"{metrics.get('yearly_return', 0):>12.2f} {metrics['max_investment']:>15,.2f} {metrics['investment_count']:>8}")
    
    def plot_results(self):
        """绘制图表"""
        df = pd.DataFrame(self.results['investment_records'])
        
        # 创建图表
        fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(15, 12))
        
        # 1. 净值曲线和投资金额
        ax1.plot(df['date'], df['nav'], 'b-', label='基金净值')
        ax1.set_xlabel('日期')
        ax1.set_ylabel('净值', color='b')
        ax1.tick_params(axis='y', labelcolor='b')
        ax1.grid(True, alpha=0.3)
        
        ax1_twin = ax1.twinx()
        ax1_twin.plot(df['date'], df['total_investment'], 'r-', label='累计投资')
        ax1_twin.set_ylabel('累计投资金额(元)', color='r')
        ax1_twin.tick_params(axis='y', labelcolor='r')
        
        ax1.legend(loc='upper left')
        ax1_twin.legend(loc='upper right')
        ax1.set_title('基金净值与累计投资金额')
        
        # 2. 市值增长曲线
        ax2.plot(df['date'], df['portfolio_value'], 'g-', label='投资组合市值')
        ax2.plot(df['date'], df['total_investment'], 'r--', label='累计投资金额')
        ax2.set_xlabel('日期')
        ax2.set_ylabel('金额(元)')
        ax2.grid(True, alpha=0.3)
        ax2.legend()
        ax2.set_title('投资组合市值增长')
        
        # 3. 收益率曲线
        df['return_rate'] = (df['portfolio_value'] - df['total_investment']) / df['total_investment'] * 100
        ax3.plot(df['date'], df['return_rate'], 'purple')
        ax3.axhline(y=0, color='red', linestyle='--', alpha=0.7)
        ax3.set_xlabel('日期')
        ax3.set_ylabel('收益率(%)')
        ax3.grid(True, alpha=0.3)
        ax3.set_title('投资收益率变化')
        
        # 4. 月度投资分布
        monthly_investment = df.groupby([df['date'].dt.year, df['date'].dt.month])['investment'].sum()
        months = [f"{y}-{m:02d}" for y, m in monthly_investment.index]
        ax4.bar(range(len(months)), monthly_investment.values, alpha=0.7)
        ax4.set_xlabel('年月')
        ax4.set_ylabel('月投资金额(元)')
        ax4.set_title('月度投资金额分布')
        ax4.set_xticks(range(0, len(months), max(1, len(months)//12)))
        ax4.set_xticklabels(months[::max(1, len(months)//12)], rotation=45)
        
        plt.tight_layout()
        plt.savefig(f'dingtou_backtest_{self.fund_code}.png', dpi=300, bbox_inches='tight')
        plt.show()

def main():
    # 创建回测实例
    backtest = DingTouBacktest("011707")
    
    # 这里应该从API获取的数据，暂时用示例数据
    # 实际使用时需要从 mcp_qieman_BatchGetFundNavHistory 返回的数据转换
    
    # 模拟数据加载（实际应该从API获取）
    print("正在加载净值数据...")
    
    # 这里需要将API返回的数据转换为脚本可用的格式
    # 实际实现时应该从 mcp_qieman_BatchGetFundNavHistory 的结果转换
    
    # 运行回测
    print("正在运行定投回测...")
    results = backtest.simulate_dingtou_strategy()
    
    # 生成报告
    backtest.generate_report()
    
    # 绘制图表
    backtest.plot_results()
    
    return results

if __name__ == "__main__":
    main()