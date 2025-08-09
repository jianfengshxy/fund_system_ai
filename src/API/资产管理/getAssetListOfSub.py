import sys
import os
import logging
import urllib.parse
import urllib3
import warnings
import requests
from typing import List

# 确保路径添加在导入之前
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# 使用绝对导入
from src.domain.fund_plan import ApiResponse
from src.common.constant import SERVER_VERSION, PHONE_TYPE, MOBILE_KEY
from src.domain.asset.asset_details import AssetDetails

def get_asset_list_of_sub(user, sub_account_no):
    url = f"https://tradeapilvs{user.index}.1234567.com.cn/User/Asset/GetFundAssetListOfSubV2"
    headers = {
        "Connection": "keep-alive",
        "Host": f"tradeapilvs{user.index}.1234567.com.cn",
        "Accept": "*/*",
        "GTOKEN": "4474AFD3E15F441E937647556C01C174",
        "clientInfo": "ttjj-iPhone12,3-iOS-iOS16.2",
        "MP-VERSION": "3.20.0",
        "Accept-Encoding": "gzip, deflate, br",
        "Accept-Language": "zh-Hans-CN;q=1",
        "Content-Type": "application/x-www-form-urlencoded",
        "User-Agent": "EMProjJijin/6.6.2 (iPhone; iOS 16.2; Scale/3.00)",
        "Referer": "https://mpservice.com/33cb2e2622954432b6073633f27149ba/release/pages/SubAccountDetail",
        "Content-Length": "787"
    }
    data = {
        "BankCardNo": "",
        "CustomerNo": user.customer_no,
        "MobileKey": MOBILE_KEY,
        "Passportid": user.passport_uid,
        "PhoneType": "IOS16.2.0",
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
    response = requests.post(url, headers=headers, data=data)
    response_data = response.json()
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
    return asset_details_list
   




