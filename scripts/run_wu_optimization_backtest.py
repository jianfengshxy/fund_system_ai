#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
东吴配置优化混合C(011707)定投回测主脚本
整合API数据获取和回测分析
"""

import json
from datetime import datetime
from typing import List, Dict
import pandas as pd

# 导入回测类
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from backtest_dingtou_wu_optimization import DingTouBacktest

def convert_qieman_nav_data(api_response: List[Dict]) -> List[Dict]:
    """
    转换且慢API返回的净值数据格式
    
    Args:
        api_response: mcp_qieman_BatchGetFundNavHistory 返回的数据列表
        
    Returns:
        转换后的净值数据列表，包含 date, nav 字段
    """
    converted_data = []
    
    for fund_data in api_response:
        fund_code = fund_data.get('fundCode', '')
        data_list = fund_data.get('data', [])
        
        for item in data_list:
            # 转换日期格式
            nav_date_str = item.get('navDate', '')
            if not nav_date_str:
                continue
                
            # 转换中文日期格式为标准格式
            date_str = nav_date_str.replace('年', '-').replace('月', '-').replace('日', '')
            try:
                date_obj = datetime.strptime(date_str, '%Y-%m-%d')
            except ValueError:
                continue
            
            # 获取净值
            nav = float(item.get('nav', 0))
            
            converted_data.append({
                'date': date_obj,
                'nav': nav,
                'fundCode': fund_code
            })
    
    # 按日期排序
    converted_data.sort(key=lambda x: x['date'])
    
    return converted_data

def load_api_response_from_file(file_path: str) -> List[Dict]:
    """从文件加载API响应数据"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"文件 {file_path} 不存在")
        return []

def save_api_response_to_file(data: List[Dict], file_path: str):
    """保存API响应数据到文件"""
    # 将datetime对象转换为字符串以便JSON序列化
    serializable_data = []
    for item in data:
        serializable_item = item.copy()
        if 'date' in serializable_item and isinstance(serializable_item['date'], datetime):
            serializable_item['date'] = serializable_item['date'].strftime('%Y-%m-%d')
        serializable_data.append(serializable_item)
    
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(serializable_data, f, ensure_ascii=False, indent=2)
    print(f"已保存数据到 {file_path}")

def main():
    """主函数"""
    print("=" * 60)
    print("东吴配置优化混合C(011707)定投回测分析")
    print("=" * 60)
    
    # 这里应该是从 mcp_qieman_BatchGetFundNavHistory 获取的实际数据
    # 由于我们无法直接调用，这里使用之前API返回的数据结构
    
    # 从文件加载完整的测试数据
    test_data_file = "complete_wu_optimization_data.json"
    try:
        with open(test_data_file, 'r', encoding='utf-8') as f:
            api_response = json.load(f)
        print(f"从 {test_data_file} 加载了测试数据")
    except FileNotFoundError:
        print(f"文件 {test_data_file} 不存在，使用示例数据")
        # 使用示例数据作为后备
        api_response = [
            {
                "fundCode": "011707",
                "data": [
                    {
                        "navDate": "2021年03月08日",
                        "nav": 1.7681,
                        "dailyReturn": "0.00%"
                    },
                    {
                        "navDate": "2021年03月09日",
                        "nav": 1.6979,
                        "dailyReturn": "-3.97%"
                    }
                ]
            }
        ]
    
    print("正在转换API数据格式...")
    converted_data = convert_qieman_nav_data(api_response)
    
    # 保存转换后的数据
    save_api_response_to_file(converted_data, 'wu_optimization_nav_data.json')
    
    # 创建回测实例
    backtest = DingTouBacktest("011707")
    
    # 加载数据
    print("正在加载净值数据...")
    backtest.load_nav_data(converted_data)
    
    # 运行回测
    print("正在运行定投回测策略...")
    results = backtest.simulate_dingtou_strategy()
    
    # 生成报告
    print("\n" + "=" * 60)
    print("回测结果报告")
    print("=" * 60)
    backtest.generate_report()
    
    # 绘制图表
    print("正在生成图表...")
    backtest.plot_results()
    
    # 保存详细结果
    detailed_results = {
        'summary': {
            'total_investment': results['total_investment'],
            'final_value': results['final_value'],
            'total_profit': results['total_profit'],
            'total_return_rate': results['total_return_rate'],
            'annualized_return': results['annualized_return'],
            'max_investment': results['max_investment'],
            'investment_days': results['investment_days']
        },
        'yearly_metrics': backtest.calculate_yearly_metrics(),
        'fund_code': "011707",
        'strategy_description': "5个周定投（周一至周五各10000元） + 28个月定投（1-28号各5000元）",
        'analysis_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    }
    
    with open('wu_optimization_backtest_results.json', 'w', encoding='utf-8') as f:
        json.dump(detailed_results, f, ensure_ascii=False, indent=2)
    
    print(f"\n详细结果已保存到 wu_optimization_backtest_results.json")
    
    return detailed_results

if __name__ == "__main__":
    main()