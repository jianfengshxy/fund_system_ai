#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
转换API返回的历史净值数据格式
将 mcp_qieman_BatchGetFundNavHistory 返回的数据转换为回测脚本可用的格式
"""

import json
from datetime import datetime
from typing import List, Dict

def convert_qieman_nav_data(api_response: List[Dict]) -> List[Dict]:
    """
    转换且慢API返回的净值数据格式
    
    Args:
        api_response: mcp_qieman_BatchGetFundNavHistory 返回的数据列表
        
    Returns:
        转换后的净值数据列表，包含 date, nav, dailyReturn 字段
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
            
            # 获取净值和日收益率
            nav = float(item.get('nav', 0))
            daily_return = item.get('dailyReturn', '0%')
            
            # 转换日收益率字符串为浮点数
            daily_return_pct = 0.0
            if isinstance(daily_return, str) and '%' in daily_return:
                try:
                    daily_return_pct = float(daily_return.replace('%', '').strip())
                except ValueError:
                    daily_return_pct = 0.0
            
            converted_data.append({
                'date': date_obj,
                'nav': nav,
                'dailyReturn': daily_return_pct,
                'fundCode': fund_code
            })
    
    # 按日期排序
    converted_data.sort(key=lambda x: x['date'])
    
    return converted_data

def save_converted_data(converted_data: List[Dict], output_file: str):
    """保存转换后的数据到JSON文件"""
    # 将datetime对象转换为字符串以便JSON序列化
    serializable_data = []
    for item in converted_data:
        serializable_item = item.copy()
        serializable_item['date'] = item['date'].strftime('%Y-%m-%d')
        serializable_data.append(serializable_item)
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(serializable_data, f, ensure_ascii=False, indent=2)
    
    print(f"已保存 {len(serializable_data)} 条数据到 {output_file}")

def load_converted_data(input_file: str) -> List[Dict]:
    """从JSON文件加载转换后的数据"""
    with open(input_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # 将字符串日期转换回datetime对象
    for item in data:
        item['date'] = datetime.strptime(item['date'], '%Y-%m-%d')
    
    return data

# 示例API响应数据（用于测试）
example_api_response = [
    {
        "fundCode": "011707",
        "data": [
            {
                "navDate": "2021年03月08日",
                "nav": 1.7681,
                "dailyReturn": "-3.97%"
            },
            {
                "navDate": "2021年03月09日",
                "nav": 1.6979,
                "dailyReturn": "-3.97%"
            }
        ]
    }
]

def main():
    """主函数 - 用于测试"""
    # 这里应该是从 mcp_qieman_BatchGetFundNavHistory 获取的实际数据
    # 由于我们无法直接调用，这里使用示例数据演示
    
    print("转换示例数据...")
    converted_data = convert_qieman_nav_data(example_api_response)
    
    print("转换后的数据:")
    for item in converted_data:
        print(f"日期: {item['date'].strftime('%Y-%m-%d')}, 净值: {item['nav']}, 日收益率: {item['dailyReturn']}%")
    
    # 保存到文件
    save_converted_data(converted_data, 'converted_nav_data.json')
    
    # 从文件加载
    loaded_data = load_converted_data('converted_nav_data.json')
    print(f"从文件加载了 {len(loaded_data)} 条数据")

if __name__ == "__main__":
    main()