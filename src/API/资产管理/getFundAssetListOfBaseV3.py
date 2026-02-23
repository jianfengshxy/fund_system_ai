import logging
import requests
import sys
import os

# Add root dir to sys.path
root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from src.common.logger import get_logger
from src.common.requests_session import session
from src.common.constant import SERVER_VERSION, PHONE_TYPE, MOBILE_KEY
from src.domain.asset.asset_details import AssetDetails
from typing import List, Tuple, Optional

def get_fund_asset_list_of_base_v3(user, with_meta: bool = False) -> Tuple[Optional[List[AssetDetails]], Optional[dict]]:
    """
    获取基础账户资产列表 (GetFundAssetListOfBaseV3)
    """
    # Use user.index for subdomain, default to 5 if not available or strictly follow curl if needed
    # Usually project uses tradeapilvs{user.index}
    index = getattr(user, 'index', 5)
    base = f"https://tradeapilvs{index}.1234567.com.cn"
    url = f"{base}/User/Asset/GetFundAssetListOfBaseV3"
    
    headers = {
        "Accept": "*/*",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Content-Type": "application/json; charset=utf-8",
        "Host": f"tradeapilvs{index}.1234567.com.cn",
        "Referer": "https://mpservice.com/33cb2e2622954432b6073633f27149ba/release/pages/accountBaseAsset/index",
        "User-Agent": "okhttp/3.12.13",
        "clientInfo": "ttjj-ZTE 7534N-Android-11",
        "gtoken": "ceaf-5ec1aeaf313a267434fbe314a1575707", # Hardcoded from curl, or could be dynamic
        "mp_instance_id": "166",
        # traceparent/tracestate omitted or dynamic
    }
    
    data_json = {
        "ServerVersion": SERVER_VERSION,
        "PhoneType": PHONE_TYPE,
        "MobileKey": MOBILE_KEY,
        "Version": SERVER_VERSION,
        "UserId": user.customer_no,
        "BankCardNo": "",
        "TypeCode_One": "",
        "UToken": user.u_token,
        "AppType": "ttjj",
        "CustomerNo": user.customer_no,
        "CToken": user.c_token
    }

    logger = get_logger("AssetAPI")
    extra = {"account": getattr(user, 'mobile_phone', None) or getattr(user, 'account', None), "action": "get_fund_asset_list_base_v3"}
    
    token_error = False
    first_error_text = ""

    try:
        r = session.post(url, json=data_json, headers=headers, verify=False, timeout=10)
        r.raise_for_status()
        rd = r.json()
        
        if rd.get("Success") is False:
            err = rd.get('Message') or rd.get('FirstError') or ""
            logger.error(f"获取基础账户资产列表失败: {err}", extra=extra)
            first_error_text = str(err)
            if any(k in first_error_text for k in ['Token', 'token', '凭证', 'passport', '未登录', '请登录', 'UToken', 'CToken', 'passportid', '权限']):
                token_error = True
            
            if with_meta:
                return None, {"token_error": token_error, "first_error": first_error_text}
            return None, None
            
        data = rd.get("Data")
        if not data:
            logger.info("未找到基础账户资产数据", extra=extra)
            if with_meta:
                return [], {"token_error": False, "first_error": "No Data"}
            return [], None
            
        raw_list = data.get("AssetDetails", [])
        asset_list = []
        
        # Helper to clean string numbers
        def clean_num(val):
            if val in ("--", "", None):
                return 0.0
            if isinstance(val, (int, float)):
                return float(val)
            try:
                return float(str(val).replace(',', '').strip('%'))
            except ValueError:
                return 0.0
                
        for item in raw_list:
            asset = AssetDetails()
            asset.fund_name = item.get("FundName")
            asset.fund_code = item.get("FundCode")
            asset.fund_type = item.get("FundType")
            
            asset.hold_profit = clean_num(item.get("HoldProfit"))
            asset.hold_profit_rate = clean_num(item.get("HoldProfitRate"))
            asset.constant_profit = clean_num(item.get("ConstantProfit"))
            asset.constant_profit_rate = clean_num(item.get("ConstantProfitRate"))
            asset.profit_value = clean_num(item.get("ProfitValue")) # Accumulated Profit
            asset.daily_profit = clean_num(item.get("DailyProfit"))
            asset.asset_value = clean_num(item.get("AssetValue"))
            asset.available_vol = clean_num(item.get("AvailableVol"))
            asset.on_way_transaction_count = int(item.get("OnWayTransactionCount") or 0)
            
            asset_list.append(asset)
            
        if with_meta:
            return asset_list, {"token_error": False, "first_error": ""}
        return asset_list, None

    except Exception as e:
        logger.error(f"Request failed: {e}", extra=extra)
        if with_meta:
            return None, {"token_error": False, "first_error": str(e)}
        return None, None

if __name__ == "__main__":
    from src.common.constant import DEFAULT_USER
    
    # Configure logging to stdout
    logging.basicConfig(level=logging.INFO)
    
    print("Testing get_fund_asset_list_of_base_v3...")
    
    assets, meta = get_fund_asset_list_of_base_v3(DEFAULT_USER, with_meta=True)
    
    if assets is not None:
        print(f"\nFound {len(assets)} assets in Base Account:")
        print("="*50)
        for asset in assets:
            print(f"Fund: {asset.fund_name} ({asset.fund_code})")
            print(f"  Asset Value: {asset.asset_value:,.2f}")
            print(f"  Hold Profit: {asset.hold_profit:,.2f}")
            print(f"  Total Profit: {asset.profit_value:,.2f}")
            print("-" * 30)
        print("="*50 + "\n")
    else:
        print(f"Failed to get assets. Error: {meta.get('first_error') if meta else 'Unknown'}")
