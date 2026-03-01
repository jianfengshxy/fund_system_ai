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

def get_fund_asset_details_of_base_sub_hdt(user, fund_code: str, with_meta: bool = False):
    """
    获取某个基金在整个账户上的持有情况
    """
    base = f"https://tradeapilvs{user.index}.1234567.com.cn"
    url = f"{base}/User/Asset/GetFundAssetDetailsOfBaseSubHdt"
    
    headers = {
        "Accept": "*/*",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Content-Type": "application/json",
        "Host": f"tradeapilvs{user.index}.1234567.com.cn",
        "Referer": "https://mpservice.com/0b74fd40a63b40fb99467fedd9156d8f/release/pages/holdDetailPage",
        "User-Agent": "EMProjJijin/6.8.4 (iPhone; iOS 26.0.1; Scale/3.00)",
        "clientInfo": "ttjj-iPhone18,1-iOS-iOS26.0.1",
        "gtoken": "03FC9273690F4DC4B71CB2247A0E4338", # This might need to be dynamic or from user object if available, but for now using hardcoded or common
        # traceparent/tracestate usually generated or ignored
    }
    
    # Note: Using user.index for subdomain to match other APIs in the project
    
    data_json = {
        "CToken": user.c_token,
        "CustomerNo": user.customer_no,
        "PhoneType": PHONE_TYPE,
        "Version": SERVER_VERSION,
        "ServerVersion": SERVER_VERSION,
        "TransactionAccountId": "",
        "UserId": user.customer_no,
        "SubAccountNo": "",
        "UToken": user.u_token,
        "AppType": "ttjj",
        "NeedReturnZeroVolItemsLevel3": "true",
        "MobileKey": MOBILE_KEY,
        "FundCode": fund_code,
        "NeedReturnZeroVolItems": "true",
        "Passportid": getattr(user, "passport_id", "")
    }

    logger = get_logger("AssetAPI")
    extra = {"account": getattr(user, 'mobile_phone', None) or getattr(user, 'account', None), "action": "get_fund_asset_details_total", "fund_code": fund_code}
    
    token_error = False
    first_error_text = ""

    try:
        r = session.post(url, json=data_json, headers=headers, verify=False, timeout=10)
        r.raise_for_status()
        rd = r.json()
        
        if rd.get("Success") is False:
            err = rd.get('Message') or rd.get('FirstError') or ""
            logger.error(f"获取基金资产详情失败: {err}", extra=extra)
            first_error_text = str(err)
            if any(k in first_error_text for k in ['Token', 'token', '凭证', 'passport', '未登录', '请登录', 'UToken', 'CToken', 'passportid', '权限']):
                token_error = True
            
            if with_meta:
                return None, {"token_error": token_error, "first_error": first_error_text}
            return None
            
        data = rd.get("Data")
        if not data:
            logger.info("未找到该基金资产详情", extra=extra)
            if with_meta:
                return None, {"token_error": False, "first_error": "No Data"}
            return None
            
        asset_detail = AssetDetails()
        asset_detail.fund_name = data.get("FundName")
        asset_detail.fund_code = data.get("FundCode")
        asset_detail.fund_type = data.get("FundType")
        
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

        asset_detail.hold_profit = clean_num(data.get("HoldProfit"))
        asset_detail.hold_profit_rate = clean_num(data.get("HoldProfitRate"))
        asset_detail.constant_profit = clean_num(data.get("ConstantProfit"))
        asset_detail.constant_profit_rate = clean_num(data.get("ConstantProfitRate"))
        
        # Fields mapping based on response example and AssetDetails model
        # The response has "DailyProfit"
        asset_detail.daily_profit = clean_num(data.get("DailyProfit"))
        
        # Mapping TotalProfit to profit_value (Accumulated Profit)
        asset_detail.profit_value = clean_num(data.get("TotalProfit"))
        
        # "TotalAmount" seems to correspond to AssetValue in other contexts? 
        # Or "ShareValue"?
        # In response: "ShareValue": 32077.62, "TotalAmount": 38226.9, "HoldAmount": "38226.90"
        # Usually asset_value is the total market value.
        asset_detail.asset_value = clean_num(data.get("TotalAmount")) 
        
        # AvailableShare / AvailableVol
        asset_detail.available_vol = clean_num(data.get("AvailableShare"))
        
        # FundNav and NavDate
        asset_detail.fund_nav = clean_num(data.get("UnitNav") or data.get("FundNav"))
        asset_detail.nav_date = data.get("NavDate") or data.get("FDate")

        # OnWayTransactionCount is not explicitly in the top level Data, maybe 0 default
        asset_detail.on_way_transaction_count = 0 
        
        if with_meta:
            return asset_detail, {"token_error": False, "first_error": ""}
        return asset_detail

    except Exception as e:
        logger.error(f"Request failed: {e}", extra=extra)
        if with_meta:
            return None, {"token_error": False, "first_error": str(e)}
        return None

if __name__ == "__main__":
    from src.common.constant import DEFAULT_USER
    
    # Configure logging to stdout
    logging.basicConfig(level=logging.INFO)
    
    # Test fund code: 华宝海外科技股票(QDII-LOF)C (017204)
    test_fund_code = "017204"
    print(f"Testing get_fund_asset_details_of_base_sub_hdt for fund {test_fund_code}...")
    
    result = get_fund_asset_details_of_base_sub_hdt(DEFAULT_USER, test_fund_code)
    
    if result:
        print("\n" + "="*50)
        print(f"Fund Name: {result.fund_name}")
        print(f"Fund Code: {result.fund_code}")
        print(f"Hold Profit: {result.hold_profit}")
        print(f"Hold Profit Rate: {result.hold_profit_rate}%")
        print(f"Total Asset Value: {result.asset_value}")
        print(f"Total Profit: {result.profit_value}")
        print(f"Available Vol: {result.available_vol}")
        print("="*50 + "\n")
    else:
        print("Failed to get asset details.")
