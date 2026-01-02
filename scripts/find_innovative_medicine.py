
import sys
import os
import logging

# Add root dir to path
root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from src.domain.user.User import User
from src.common.constant import DEFAULT_USER
from src.service.资产管理.get_fund_asset_detail import get_sub_account_asset_by_name

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def find_fund():
    sub_account_name = "快速止盈"
    logger.info(f"Looking for '创新药' in {sub_account_name} for {DEFAULT_USER.customer_name}...")
    
    assets = get_sub_account_asset_by_name(DEFAULT_USER, sub_account_name)
    if not assets:
        logger.error("No assets found or sub-account not found.")
        return

    found = False
    for asset in assets:
        # Check if name contains "创新药"
        # asset object usually has fund_name, fund_code, asset_value, current_cost (or similar)
        # Based on previous tool outputs, attributes might be camelCase or snake_case depending on source, 
        # but asset_details.py showed snake_case: fund_name, fund_code.
        
        f_name = getattr(asset, 'fund_name', '')
        if "创新药" in f_name:
            found = True
            logger.info(f"FOUND: {f_name} ({asset.fund_code})")
            logger.info(f"  Asset Value: {asset.asset_value}")
            logger.info(f"  Available Vol: {asset.available_vol}")
            logger.info(f"  Profit Rate: {asset.constant_profit_rate}%")
            # We need cost price to simulate accurately, but profit rate + current NAV (from asset value/vol) is enough to derive it.
            
    if not found:
        logger.info("Did not find any fund with '创新药' in the name.")
        # List all to be sure
        for asset in assets:
            logger.info(f"  - {getattr(asset, 'fund_name', 'Unknown')} ({getattr(asset, 'fund_code', '')})")

if __name__ == "__main__":
    find_fund()
