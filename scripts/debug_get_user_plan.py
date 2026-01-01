
import sys
import os
import logging

# Add root dir to sys.path
root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from src.common.constant import DEFAULT_USER
from src.service.定投管理.定投查询.定投查询 import get_all_fund_plan_details

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def main():
    print(f"Checking plans for user: {DEFAULT_USER.customer_name}")
    plans = get_all_fund_plan_details(DEFAULT_USER)
    
    found = False
    for plan in plans:
        fund_name = plan.rationPlan.fundName
        fund_code = plan.rationPlan.fundCode
        if ("前海开源" in fund_name and "黄金" in fund_name) or "东吴" in fund_name:
            print(f"Found Plan: {fund_name} ({fund_code})")
            print(f"  Amount: {plan.rationPlan.amount}")
            print(f"  Period Type: {plan.rationPlan.periodType} (1=Weekly, 3=Monthly)")
            print(f"  Period Value: {plan.rationPlan.periodValue}")
            print(f"  Sub Account: {plan.rationPlan.subAccountName} ({plan.rationPlan.subAccountNo})")
            found = True
            
    if not found:
        print("No plan found for 前海开源黄金ETF链接C")
        # List all to be sure
        print("All plans:")
        for plan in plans:
            print(f"  {plan.rationPlan.fundName} ({plan.rationPlan.fundCode})")

if __name__ == "__main__":
    main()
