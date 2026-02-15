import logging

if __name__ == "__main__":
    import os
    import sys

    root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    if root_dir not in sys.path:
        sys.path.insert(0, root_dir)

from src.common.logger import get_logger
import urllib.parse
import requests
from typing import List, Tuple, Dict, Any
from src.common.requests_session import session

# 使用绝对导入
from src.domain.fund_plan import ApiResponse
from src.common.constant import SERVER_VERSION, PHONE_TYPE, MOBILE_KEY
from src.domain.asset.asset_details import AssetDetails

def get_asset_list_of_sub(user, sub_account_no, with_meta: bool = False):
    base = f"https://tradeapilvs{user.index}.1234567.com.cn"
    url_list = [
        f"{base}/User/Asset/GetFundAssetListOfSubV2",
        f"{base}/User/Asset/GetFundAssetListOfSub"
    ]
    headers = {
        "Accept": "*/*",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Content-Type": "application/json; charset=utf-8",
        "Host": f"tradeapilvs{user.index}.1234567.com.cn",
        "Referer": "https://mpservice.com/33cb2e2622954432b6073633f27149ba/release/pages/SubAccountDetail",
        "User-Agent": "okhttp/3.12.13",
        "clientInfo": "ttjj-ZTE 7534N-Android-11",
        "gtoken": "ceaf-5ec1aeaf313a267434fbe314a1575707",
        "mp_instance_id": "162",
        "traceparent": "00-0000000046aa4cae000001968ae7a434-0000000000000000-01",
        "tracestate": "pid=0xc3c6c4a,taskid=0x7f81dfc"
    }
    data_json = {
        "ServerVersion": SERVER_VERSION,
        "PhoneType": PHONE_TYPE,
        "MobileKey": MOBILE_KEY,
        "Version": SERVER_VERSION,
        "UserId": user.customer_no,
        "UToken": user.u_token,
        "AppType": "ttjj",
        "CustomerNo": user.customer_no,
        "CToken": user.c_token,
        "SubAccountNo": sub_account_no,
        "Passportid": getattr(user, "passport_id", "")
    }
    data_form = {
        "BankCardNo": "",
        "CustomerNo": user.customer_no,
        "MobileKey": MOBILE_KEY,
        "Passportid": getattr(user, "passport_id", ""),
        "PhoneType": PHONE_TYPE,
        "SubAccountNo": sub_account_no,
        "UnifiedType": "",
        "appType": "ttjj",
        "appVersion": SERVER_VERSION,
        "ctoken": user.c_token,
        "deviceid": MOBILE_KEY,
        "plat": PHONE_TYPE,
        "product": "EFund",
        "serverversion": SERVER_VERSION,
        "userid": user.customer_no,
        "utoken": user.u_token,
        "version": SERVER_VERSION
    }
    logger = get_logger("AssetAPI")
    extra = {"account": getattr(user, 'mobile_phone', None) or getattr(user, 'account', None), "action": "get_asset_list", "sub_account_no": sub_account_no}
    response_data = None
    token_error = False
    first_error_text = ""
    for url in url_list:
        try:
            r = session.post(url, json=data_json, headers=headers, verify=False, timeout=10)
            r.raise_for_status()
            rd = r.json()
            if rd.get("Success") is False:
                # 检查是否为正常空数据（ErrorCode=0）
                error_code = rd.get("ErrorCode")
                if error_code == 0 or str(error_code) == "0":
                    pass # 视为正常，不记录 token_error
                else:
                    err = str(rd.get("FirstError", "") or "")
                    first_error_text = (first_error_text or err)
                    if any(k in err for k in ['Token', 'token', '凭证', 'passport', '未登录', '请登录', 'UToken', 'CToken', 'passportid', '权限']):
                        token_error = True
            if rd.get("Data", {}).get("AssetDetails"):
                response_data = rd
                break
        except requests.exceptions.RequestException as e:
            pass
        try:
            r = session.post(url, data=data_form, headers={**headers, "Content-Type": "application/x-www-form-urlencoded"}, verify=False, timeout=10)
            r.raise_for_status()
            rd = r.json()
            if rd.get("Success") is False:
                # 检查是否为正常空数据（ErrorCode=0）
                error_code = rd.get("ErrorCode")
                if error_code == 0 or str(error_code) == "0":
                    pass # 视为正常，不记录 token_error
                else:
                    err = str(rd.get("FirstError", "") or "")
                    first_error_text = (first_error_text or err)
                    if any(k in err for k in ['Token', 'token', '凭证', 'passport', '未登录', '请登录', 'UToken', 'CToken', 'passportid', '权限']):
                        token_error = True
            if rd.get("Data", {}).get("AssetDetails"):
                response_data = rd
                break
        except requests.exceptions.RequestException as e:
            pass
    if response_data is None:
        logger.info("资产明细条数: 0", extra=extra)
        if with_meta:
            return [], {"token_error": token_error, "first_error": first_error_text}
        return []
    asset_details_list = []
    for asset in response_data.get("Data", {}).get("AssetDetails", []):
        asset_detail = AssetDetails()
        asset_detail.fund_name = asset.get("FundName")
        asset_detail.fund_code = asset.get("FundCode")
        asset_detail.fund_type = asset.get("FundType")
        hold_profit_str = asset.get("HoldProfit", 0)
        if hold_profit_str in ("--", "", None):
            asset_detail.hold_profit = 0.0
        else:
            # 处理带逗号的数字字符串
            hold_profit_str = str(hold_profit_str).replace(',', '')
            asset_detail.hold_profit = float(hold_profit_str)

        hold_profit_rate_str = asset.get("HoldProfitRate", "0").strip('%')
        if hold_profit_rate_str in ("--", "", None):
            asset_detail.hold_profit_rate = 0.0
        else:
            # 处理带逗号的百分比字符串
            hold_profit_rate_str = str(hold_profit_rate_str).replace(',', '')
            asset_detail.hold_profit_rate = float(hold_profit_rate_str)

        constant_profit_str = asset.get("ConstantProfit", 0)
        if constant_profit_str in ("--", "", None):
            asset_detail.constant_profit = 0.0
        else:
            # 处理带逗号的数字字符串
            constant_profit_str = str(constant_profit_str).replace(',', '')
            asset_detail.constant_profit = float(constant_profit_str)

        constant_profit_rate_str = asset.get("ConstantProfitRate", "0").strip('%')
        if constant_profit_rate_str in ("--", "", None):
            asset_detail.constant_profit_rate = 0.0
        else:
            # 处理带逗号的百分比字符串
            constant_profit_rate_str = str(constant_profit_rate_str).replace(',', '')
            asset_detail.constant_profit_rate = float(constant_profit_rate_str)
        asset_detail.profit_value = float(asset.get("ProfitValue", 0))
        asset_detail.daily_profit = float(asset.get("DailyProfit", 0))
        asset_detail.asset_value = float(asset.get("AssetValue", 0))
        asset_detail.available_vol = asset.get("AvailableVol", 0)
        asset_detail.on_way_transaction_count = asset.get("OnWayTransactionCount", 0)
        asset_details_list.append(asset_detail)
    logger.info(f"资产明细条数: {len(asset_details_list)}", extra=extra)
    if with_meta:
        return asset_details_list, {"token_error": token_error, "first_error": first_error_text}
    return asset_details_list
   
