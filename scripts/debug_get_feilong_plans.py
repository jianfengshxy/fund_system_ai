
import sys
import os
import logging

# Add root dir to sys.path
root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from src.common.constant import DEFAULT_USER
from src.service.定投管理.定投查询.定投查询 import get_all_fund_plan_details

from src.service.资产管理.get_fund_asset_detail import get_sub_account_asset_by_name

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def main():
    print(f"Checking plans for user: {DEFAULT_USER.customer_name}")
    plans = get_all_fund_plan_details(DEFAULT_USER)
    
    feilong_funds = []
    
    for plan in plans:
        sub_account = getattr(plan.rationPlan, 'subAccountName', '')
        if sub_account == "飞龙在天":
            fund_name = plan.rationPlan.fundName
            fund_code = plan.rationPlan.fundCode
            amount = plan.rationPlan.amount
            period_type = plan.rationPlan.periodType
            period_value = plan.rationPlan.periodValue
            
            print(f"Found Feilong Plan: {fund_name} ({fund_code})")
            print(f"  Amount: {amount}")
            print(f"  Frequency: Type={period_type}, Value={period_value}")
            
            feilong_funds.append({"code": fund_code, "name": fund_name, "amount": amount})
            
    # Check Current Assets
    print("-" * 30)
    print("Current Assets in '飞龙在天':")
    assets = get_sub_account_asset_by_name(DEFAULT_USER, "飞龙在天")
    if assets:
        for asset in assets:
            print(f"  Fund: {asset.fund_name} ({asset.fund_code})")
            print(f"  Asset Value: {asset.asset_value}") # Fixed attribute name
            print(f"  Hold Amount: {asset.hold_amount}")
            print(f"  Profit Rate: {asset.constant_profit_rate}")
    else:
        print("  No assets found.")

if __name__ == "__main__":
    main()
