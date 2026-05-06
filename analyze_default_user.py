import sys
import os
import logging
from datetime import datetime

root_dir = "/Users/shixiaoyu/Downloads/shixiaoyu/fund_system_ai"
sys.path.insert(0, root_dir)

from src.common.constant import DEFAULT_USER
from src.API.资产管理.AssetManager import GetMyAssetMainPartAsync
from src.service.定投管理.定投查询.定投查询 import get_all_fund_plan_details
from src.service.资产管理.get_fund_asset_detail import get_fund_asset_detail

def analyze_user():
    print(f"=== 分析用户: {DEFAULT_USER.customer_name} ===")
    
    # 1. 资产概况
    print("\n--- 资产概况 ---")
    try:
        asset_response = GetMyAssetMainPartAsync(DEFAULT_USER)
        if asset_response.Success and asset_response.Data:
            print(f"总资产: {asset_response.Data.get('TotalValue', 0.0)}")
            print(f"活期宝余额: {asset_response.Data.get('HqbValue', 0.0)}")
            print(f"累计收益: {asset_response.Data.get('TotalProfit', 0.0)}")
            print(f"昨日收益: {asset_response.Data.get('YesterdayProfit', 0.0)}")
        else:
            print("获取资产概况失败")
    except Exception as e:
        print(f"获取资产概况异常: {e}")

    # 2. 定投计划和持仓
    print("\n--- 定投计划与持仓 ---")
    try:
        plans = get_all_fund_plan_details(DEFAULT_USER)
        print(f"共有定投计划: {len(plans)} 个")
        
        for plan in plans:
            fund_code = plan.rationPlan.fundCode
            fund_name = plan.rationPlan.fundName
            sub_account_no = plan.rationPlan.subAccountNo
            amount = plan.rationPlan.amount
            
            try:
                asset_detail = get_fund_asset_detail(DEFAULT_USER, sub_account_no, fund_code)
                if asset_detail:
                    asset_val = asset_detail.asset_value
                    profit_rate = asset_detail.constant_profit_rate
                    print(f"计划: {fund_name}({fund_code}) | 组合: {sub_account_no} | 每期金额: {amount} | 当前持仓: {asset_val} | 收益率: {profit_rate}%")
                else:
                    print(f"计划: {fund_name}({fund_code}) | 组合: {sub_account_no} | 每期金额: {amount} | 当前无持仓")
            except Exception as e:
                print(f"获取计划持仓异常: {fund_code} - {e}")
    except Exception as e:
        print(f"获取定投计划异常: {e}")

if __name__ == '__main__':
    analyze_user()
