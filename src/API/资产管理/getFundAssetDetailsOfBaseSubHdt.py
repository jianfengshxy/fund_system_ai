"""
基础账户单基金持仓详情查询接口。

这个文件封装的是 `GetFundAssetDetailsOfBaseSubHdt`，用于查询“某一只基金”在整个账户维度下的
持有详情。它和 `getFundAssetListOfBaseV3` 的关系是：

1. `getFundAssetListOfBaseV3` 负责“列出基础账户里有哪些基金”；
2. `getFundAssetDetailsOfBaseSubHdt` 负责“把某一只基金的汇总持仓再展开看”。

适用场景：
1. 已经知道基金代码，想查看这只基金在账户里的整体持有情况；
2. 想看单基金的持有收益、累计收益、总资产、可用份额；
3. 想把基金列表页和基金详情页串起来使用。
"""

import logging
import sys
import os

# Add root dir to sys.path
root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from src.common.logger import get_logger
from src.common.requests_session import session
from src.common.constant import (
    DEFAULT_GTOKEN,
    IOS_CLIENT_INFO,
    IOS_USER_AGENT,
    MOBILE_KEY,
    PHONE_TYPE,
    SERVER_VERSION,
    describe_asset_fund_type,
    format_type_with_label,
)
from src.API.基金信息.FundInfo import getFundInfo
from src.domain.asset.asset_details import AssetDetails


def _clean_num(val):
    """统一清洗金额、收益率、净值等数字字段。"""
    if val in ("--", "", None):
        return 0.0
    if isinstance(val, (int, float)):
        return float(val)
    try:
        return float(str(val).replace(',', '').strip('%'))
    except ValueError:
        return 0.0


def format_asset_value(key: str, value) -> str:
    """将调试输出里的字段值格式化为更可读的字符串。"""
    if key == "fund_type":
        return format_type_with_label(value, describe_asset_fund_type(value))
    if key == "asset_rank" and value is None:
        return "接口未返回"
    return str(value)



def get_fund_asset_details_of_base_sub_hdt(user, fund_code: str, with_meta: bool = False):
    """
    获取某个基金在整个账户上的持有详情（GetFundAssetDetailsOfBaseSubHdt）。

    这是“单基金详情接口”，查询粒度比 `getFundAssetListOfBaseV3` 更细。
    当你已经知道基金代码，并希望继续查看这只基金在账户里的整体持仓情况时，
    应该使用本函数。

    Args:
        user: 已登录用户对象，至少需要：
            - `index`: 用于拼接交易域名
            - `customer_no`: 用户编号
            - `u_token`: 用户登录态 UToken
            - `c_token`: 用户登录态 CToken
            - `passport_id`: 登录关联的 PassportId
        fund_code: 目标基金代码，例如 `017204`
        with_meta: 是否返回额外元信息
            - `False`: 仅返回 `AssetDetails | None`
            - `True`: 返回 `(AssetDetails | None, meta)`

    Returns:
        AssetDetails | tuple[AssetDetails | None, dict] | None:
        - 成功时返回单个 `AssetDetails`
        - 无数据或失败时返回 `None`
        - `with_meta=True` 时额外返回：
          - `token_error`: 是否疑似登录态失效
          - `first_error`: 首个错误信息

    Notes:
        - 这是只读接口，不会修改账户状态。
        - 返回的是“单基金汇总视角”，不是基础账户全部基金列表。
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
        "User-Agent": IOS_USER_AGENT,
        "clientInfo": IOS_CLIENT_INFO,
        "gtoken": DEFAULT_GTOKEN,
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
        r = session.post(url, json=data_json, headers=headers, verify=False, timeout=30)
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
        
        asset_detail.hold_profit = _clean_num(data.get("HoldProfit"))
        asset_detail.hold_profit_rate = _clean_num(data.get("HoldProfitRate"))
        asset_detail.constant_profit = _clean_num(data.get("ConstantProfit"))
        asset_detail.constant_profit_rate = _clean_num(data.get("ConstantProfitRate"))
        
        # Fields mapping based on response example and AssetDetails model
        # The response has "DailyProfit"
        asset_detail.daily_profit = _clean_num(data.get("DailyProfit"))
        
        # Mapping TotalProfit to profit_value (Accumulated Profit)
        asset_detail.profit_value = _clean_num(data.get("TotalProfit"))
        
        # "TotalAmount" seems to correspond to AssetValue in other contexts? 
        # Or "ShareValue"?
        # In response: "ShareValue": 32077.62, "TotalAmount": 38226.9, "HoldAmount": "38226.90"
        # Usually asset_value is the total market value.
        asset_detail.asset_value = _clean_num(data.get("TotalAmount")) 
        
        # AvailableShare / AvailableVol
        asset_detail.available_vol = _clean_num(data.get("AvailableShare"))
        
        # FundNav and NavDate
        asset_detail.fund_nav = _clean_num(data.get("UnitNav") or data.get("FundNav"))
        asset_detail.nav_date = data.get("NavDate") or data.get("FDate")
        if asset_detail.fund_nav and not asset_detail.nav_date:
            latest_fund_info = getFundInfo(user, fund_code)
            asset_detail.nav_date = getattr(latest_fund_info, "nav_date", None) or asset_detail.nav_date

        # OnWayTransactionCount is not explicitly in the top level Data, maybe 0 default
        asset_detail.on_way_transaction_count = 0 
        asset_detail.asset_rank = data.get("AssetRank")
        
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
    from src.API.资产管理.getFundAssetListOfBaseV3 import get_fund_asset_list_of_base_v3
    
    logging.basicConfig(level=logging.INFO)

    print("Testing get_fund_asset_details_of_base_sub_hdt...")
    print("函数功能说明:")
    print("  - 查询某一只基金在整个账户维度下的汇总持仓情况")
    print("  - 适合从基金列表页点进某只基金后查看详情")
    print("  - 返回单个 AssetDetails，对应单基金的收益、市值、可用份额、净值等信息")
    print("  - 与 get_fund_asset_list_of_base_v3 的区别：前者是单基金详情，这里不是全量列表")

    base_assets, base_meta = get_fund_asset_list_of_base_v3(DEFAULT_USER, with_meta=True)
    if not base_assets:
        print(f"无法从基础账户列表挑选测试基金，错误: {base_meta.get('first_error') if base_meta else 'Unknown'}")
        raise SystemExit(1)

    print(f"\n基础账户基金总数: {len(base_assets)}")
    for index, test_asset in enumerate(base_assets, start=1):
        test_fund_code = test_asset.fund_code
        print("\n" + "=" * 80)
        print(f"基金 #{index}: {test_asset.fund_name} ({test_fund_code})")

        result, meta = get_fund_asset_details_of_base_sub_hdt(DEFAULT_USER, test_fund_code, with_meta=True)

        if result is not None:
            print("Meta:")
            print(f"  token_error: {meta.get('token_error')}")
            print(f"  first_error: {meta.get('first_error')}")
            print("Asset Detail:")
            for key, value in result.to_dict().items():
                print(f"  {key}: {format_asset_value(key, value)}")
        else:
            print(f"Failed to get asset details. Error: {meta.get('first_error') if meta else 'Unknown'}")
