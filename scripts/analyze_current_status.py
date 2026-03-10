import os
import sys
import json
import urllib3
from datetime import datetime, timedelta

# 禁用 InsecureRequestWarning
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# 获取项目根目录路径
root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from src.common.constant import DEFAULT_USER
from src.API.组合管理.SubAccountMrg import getSubAssetMultList
from src.API.资产管理.getAssetListOfSub import get_asset_list_of_sub
from src.API.交易管理.trade import get_trades_list
from src.API.资产管理.getFundAssetListOfBaseV3 import get_fund_asset_list_of_base_v3

def analyze():
    print(f"========== DEFAULT_USER 账户概览 ==========")
    print(f"用户: {DEFAULT_USER.customer_name} ({DEFAULT_USER.account})")
    print(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

    # 1. 获取组合资产列表
    print("--- 正在获取组合资产概览 ---")
    sub_mult_resp = getSubAssetMultList(DEFAULT_USER)
    if not sub_mult_resp.Success:
        print(f"获取组合资产列表失败: {sub_mult_resp.FirstError}")
        return

    sub_mult_data = sub_mult_resp.Data
    print(f"总资产预估: {sub_mult_data.sub_total_amount}")
    print(f"基础账户余额预估: {sub_mult_data.base_account_amount}")
    print(f"昨日收益预估: {sub_mult_data.yesterday_profit}\n")

    # 2. 遍历各组合并获取明细
    all_assets = []
    print("--- 正在获取各组合持仓明细 ---")
    for group in sub_mult_data.list_group:
        print(f"组合: {group.group_name} ({group.sub_account_no})")
        print(f"  总资产: {group.total_amount}, 总收益率: {group.total_profit_rate}%")
        
        assets = get_asset_list_of_sub(DEFAULT_USER, group.sub_account_no)
        for asset in assets:
            all_assets.append({
                "sub_account_name": group.group_name,
                "fund_name": asset.fund_name,
                "fund_code": asset.fund_code,
                "asset_value": asset.asset_value,
                "hold_profit": asset.hold_profit,
                "hold_profit_rate": asset.hold_profit_rate,
                "on_way_count": asset.on_way_transaction_count
            })
            print(f"  - {asset.fund_name}({asset.fund_code}): 市值 {asset.asset_value}, 收益率 {asset.hold_profit_rate}%, 在途 {asset.on_way_transaction_count}")
        print()

    # 3. 获取基础账户明细 (如果金额较大)
    if float(sub_mult_data.base_account_amount.replace(',', '')) > 1:
        print("--- 正在获取基础账户持仓明细 ---")
        base_assets, _ = get_fund_asset_list_of_base_v3(DEFAULT_USER)
        if base_assets:
            for asset in base_assets:
                all_assets.append({
                    "sub_account_name": "基础账户",
                    "fund_name": asset.fund_name,
                    "fund_code": asset.fund_code,
                    "asset_value": asset.asset_value,
                    "hold_profit": asset.hold_profit,
                    "hold_profit_rate": asset.hold_profit_rate,
                    "on_way_count": asset.on_way_transaction_count
                })
                print(f"  - {asset.fund_name}({asset.fund_code}): 市值 {asset.asset_value}, 收益率 {asset.hold_profit_rate}%, 在途 {asset.on_way_transaction_count}")
        else:
            print("  未找到基础账户资产明细。")
        print()

    # 4. 获取最近交易记录 (2-3天)
    print("--- 正在获取最近 3 天的交易记录 ---")
    recent_trades = get_trades_list(DEFAULT_USER, date_type="5") # 近一周
    three_days_ago = (datetime.now() - timedelta(days=3)).strftime("%Y-%m-%d")
    
    filtered_trades = []
    for trade in recent_trades:
        # 兼容日期字段
        trade_date = getattr(trade, 'strike_start_date', None) or getattr(trade, 'apply_work_day', None)
        if trade_date and trade_date >= three_days_ago:
            filtered_trades.append(trade)
            print(f"日期: {trade_date}, 基金: {trade.product_name}, 类型: {trade.business_type}, 状态: {trade.status}, 金额/份额: {trade.amount}")
    
    if not filtered_trades:
        print("最近 3 天无交易记录。")

    print("\n========== 分析报告结束 ==========")

if __name__ == "__main__":
    analyze()
