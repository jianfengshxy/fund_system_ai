"""
基础账户资产明细查询接口。

这个文件封装的是 `GetFundAssetListOfBaseV3`，用于查询“基础账户”层面的基金资产，
与“按子账户/组合查询”的 `getAssetListOfSub` 不同，这里返回的是基础账户维度下的持仓列表。

适用场景：
1. 想看用户在基础账户里持有哪些基金；
2. 想获取每只基金的基础账户市值、持有收益、累计收益、当日收益；
3. 需要和子账户资产分开展示或做汇总校验；
4. 需要判断基础账户是否有可用份额、是否存在在途交易。

返回结果会统一映射成 `AssetDetails`，这样上层服务在处理“基础账户资产”和“子账户资产”时
可以复用同一套字段：
- `fund_name/fund_code/fund_type`: 基金名称、基金代码、基金类型
- `asset_value`: 当前持仓市值
- `hold_profit/hold_profit_rate`: 持有收益与持有收益率
- `constant_profit/constant_profit_rate`: 累计收益与累计收益率
- `profit_value`: 总收益金额
- `daily_profit`: 当日收益
- `available_vol`: 可用份额
- `on_way_transaction_count`: 在途交易数量
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
    IOS_CLIENT_INFO,
    DEFAULT_GTOKEN,
    MOBILE_KEY,
    MP_INSTANCE_ID_ASSET_LIST_OF_BASE_V3,
    MP_VERSION_ASSET,
    PHONE_TYPE,
    SERVER_VERSION,
    IOS_USER_AGENT,
    describe_asset_fund_type,
    format_type_with_label,
)
from src.domain.asset.asset_details import AssetDetails
from typing import List, Tuple, Optional

def format_asset_value(key: str, value) -> str:
    """将调试输出里的字段值格式化为更可读的字符串。"""
    if key == "fund_type":
        return format_type_with_label(value, describe_asset_fund_type(value))
    if key == "asset_rank" and value is None:
        return "接口未返回"
    return str(value)


def get_fund_asset_list_of_base_v3(user, with_meta: bool = False) -> Tuple[Optional[List[AssetDetails]], Optional[dict]]:
    """
    获取基础账户资产列表（GetFundAssetListOfBaseV3）。

    这个函数查询的是“基础账户”层面的基金持仓，不区分具体子账户/组合。
    如果你的业务目标是：
    - 查看用户基础账户下直接持有的基金；
    - 展示基础账户总资产里的基金明细；
    - 对比基础账户资产和子账户资产；
    那么应该使用本函数。

    Args:
        user: 已登录用户对象，至少需要：
            - `index`: 用于拼接交易域名 `tradeapilvs{index}.1234567.com.cn`
            - `customer_no`: 用户编号
            - `u_token`: 用户登录态 UToken
            - `c_token`: 用户登录态 CToken
        with_meta: 是否额外返回元信息。
            - `False`: 返回 `(asset_list, None)`
            - `True`: 返回 `(asset_list, meta)`

    Returns:
        Tuple[Optional[List[AssetDetails]], Optional[dict]]:
        - 第 1 个值 `asset_list`:
          - 成功且有数据时：`list[AssetDetails]`
          - 成功但无数据时：`[]`
          - 请求失败时：`None`
        - 第 2 个值 `meta`:
          - `token_error`: 是否疑似为 token/登录态失效
          - `first_error`: 服务端返回或异常捕获到的首个错误信息

    Notes:
        - 这是只读接口，不会修改账户状态。
        - 当前实现直接请求 `GetFundAssetListOfBaseV3`，不像子账户资产接口那样做多路径兼容。
        - 若未来服务端返回结构扩展，可继续在 `AssetDetails` 映射处补充字段。
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
        "User-Agent": IOS_USER_AGENT,
        "clientInfo": IOS_CLIENT_INFO,
        "gtoken": DEFAULT_GTOKEN,
        "mp_instance_id": MP_INSTANCE_ID_ASSET_LIST_OF_BASE_V3,
        "MP-VERSION": MP_VERSION_ASSET,
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
        r = session.post(url, json=data_json, headers=headers, verify=False, timeout=30)
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
        
        # 服务端很多金额/收益字段可能是 "--"、带逗号字符串或百分号字符串，
        # 这里统一做一次清洗，保证上层拿到的都是可直接计算的 float。
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
            asset.fund_nav = item.get("FundNav")
            asset.nav_date = item.get("Navdate")
            
            asset.hold_profit = clean_num(item.get("HoldProfit"))
            asset.hold_profit_rate = clean_num(item.get("HoldProfitRate"))
            asset.constant_profit = clean_num(item.get("ConstantProfit"))
            asset.constant_profit_rate = clean_num(item.get("ConstantProfitRate"))
            asset.profit_value = clean_num(item.get("ProfitValue")) # Accumulated Profit
            asset.daily_profit = clean_num(item.get("DailyProfit"))
            asset.asset_value = clean_num(item.get("AssetValue"))
            asset.available_vol = clean_num(item.get("AvailableVol"))
            asset.on_way_transaction_count = int(item.get("OnWayTransactionCount") or 0)
            asset.asset_rank = item.get("AssetRank")
            
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
    
    logging.basicConfig(level=logging.INFO)
    
    print("Testing get_fund_asset_list_of_base_v3...")
    print("函数功能说明:")
    print("  - 查询基础账户维度下的全部基金持仓列表")
    print("  - 适合做基础账户总览页、列表页和汇总校验")
    print("  - 返回 list[AssetDetails]，每条对应一只基金")
    print("  - 与 get_fund_asset_details_of_base_sub_hdt 的区别：这里是全量列表，不是单基金详情")
    
    assets, meta = get_fund_asset_list_of_base_v3(DEFAULT_USER, with_meta=True)
    
    if assets is not None:
        print(f"\nFound {len(assets)} assets in Base Account:")
        print(f"Meta: {meta}")
        print("="*50)
        for index, asset in enumerate(assets, start=1):
            print(f"Asset #{index}:")
            for key, value in asset.to_dict().items():
                print(f"  {key}: {format_asset_value(key, value)}")
            print("-" * 30)
        print("="*50 + "\n")
    else:
        print(f"Failed to get assets. Error: {meta.get('first_error') if meta else 'Unknown'}")
