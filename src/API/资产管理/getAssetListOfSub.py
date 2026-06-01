"""
子账户持仓明细查询接口。

本文件封装的是“按组合/子账户查询基金持仓明细”的只读接口，适合做：
1. 获取某个组合当前持有哪些基金；
2. 查看每只基金的资产市值、持有收益、累计收益、当日收益；
3. 获取组合级汇总数据，例如总资产、总持有收益、总累计收益；
4. 配合策略服务判断是否持仓、是否存在在途交易、当前盈亏情况。

实现上做了两层兼容：
1. 依次尝试 `GetFundAssetListOfSubV2` 和 `GetFundAssetListOfSub` 两个接口路径；
2. 每个路径同时尝试 JSON 请求体和 form 请求体。

这样做的原因是：不同账号、不同接口版本或服务端发布阶段，可能只接受其中一种组合。
调用方不需要感知这些差异，只需要拿到统一的 `AssetDetails` 列表即可。
"""

import logging

if __name__ == "__main__":
    import os
    import sys

    root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    if root_dir not in sys.path:
        sys.path.insert(0, root_dir)

from src.common.logger import get_logger
import requests
from src.common.requests_session import session

from src.common.constant import (
    IOS_CLIENT_INFO,
    DEFAULT_GTOKEN,
    DEFAULT_USER,
    MOBILE_KEY,
    MP_INSTANCE_ID_ASSET_LIST_OF_SUB,
    PHONE_TYPE,
    PLATFORM,
    SERVER_VERSION,
    TRACEPARENT_ASSET_LIST_OF_SUB,
    TRACESTATE_ASSET_LIST_OF_SUB,
    IOS_USER_AGENT,
    describe_asset_fund_type,
    format_type_with_label,
)
from src.domain.asset.asset_details import AssetDetails


def _safe_float(value, default: float = 0.0) -> float:
    """将接口返回的金额/收益字段安全转换为浮点数。"""
    if value in ("--", "", None):
        return default
    try:
        return float(str(value).replace(",", "").replace("%", ""))
    except (TypeError, ValueError):
        return default


def _print_asset_detail_preview(asset_details_list, limit: int = 10) -> None:
    """打印持仓明细样本，便于直接运行本文件时做人工核对。"""
    print("持仓明细:")
    if not asset_details_list:
        print("  无持仓")
        return

    print(f"  总条数: {len(asset_details_list)}")
    for index, asset in enumerate(asset_details_list[:limit], start=1):
        print(
            f"  #{index}: fund={asset.fund_name}({asset.fund_code}), "
            f"type={format_type_with_label(asset.fund_type, describe_asset_fund_type(asset.fund_type))}, "
            f"nav={asset.fund_nav}, nav_date={asset.nav_date}, "
            f"asset_value={asset.asset_value}, hold_profit={asset.hold_profit}, "
            f"hold_profit_rate={asset.hold_profit_rate}%, constant_profit={asset.constant_profit}, "
            f"constant_profit_rate={asset.constant_profit_rate}%, daily_profit={asset.daily_profit}, "
            f"available_vol={asset.available_vol}, on_way_transaction_count={asset.on_way_transaction_count}"
        )

    if len(asset_details_list) > limit:
        print(f"  ... 其余 {len(asset_details_list) - limit} 条未展开")


def get_asset_list_of_sub(user, sub_account_no, with_meta: bool = False):
    """
    获取指定子账户的基金持仓明细。

    Args:
        user: 已登录用户对象，至少需要 `index/customer_no/u_token/c_token/passport_id`。
        sub_account_no: 子账户编号，即组合编号。
        with_meta: 是否额外返回元信息。
            - `False`: 仅返回 `list[AssetDetails]`
            - `True`: 返回 `(asset_details_list, meta)` 二元组

    Returns:
        list[AssetDetails] | tuple[list[AssetDetails], dict]:
        - `AssetDetails` 中的核心字段含义：
          - `fund_name/fund_code/fund_type`: 基金名称、代码、类型
          - `fund_nav/nav_date`: 当前展示净值及净值日期
          - `asset_value`: 当前持仓市值
          - `hold_profit/hold_profit_rate`: 持有收益及持有收益率
          - `constant_profit/constant_profit_rate`: 累计收益及累计收益率
          - `daily_profit`: 当日收益
          - `available_vol`: 可用份额
          - `on_way_transaction_count`: 在途交易数量
        - `meta` 中的核心字段含义：
          - `token_error`: 是否疑似登录态失效
          - `first_error`: 服务端返回的首个错误信息
          - `summary`: 组合级汇总信息
            - `TotalAssetValue`: 组合总资产
            - `TotalHoldProfit`: 组合总持有收益
            - `TotalConstantProfit`: 组合总累计收益
            - `TotalDailyProfit`: 组合当日收益
            - `TotalProfitValue`: 组合总收益金额
            - `SubAssetPreview`: 服务端返回的组合摘要补充信息

    Notes:
        - 这个函数是只读查询，不会修改账户状态。
        - 当接口返回空持仓时，会返回空列表；若 `with_meta=True`，可通过 `token_error`
          与 `first_error` 判断是“真的没有持仓”还是“登录态可能已失效”。
    """
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
        "User-Agent": IOS_USER_AGENT,
        "clientInfo": IOS_CLIENT_INFO,
        "gtoken": DEFAULT_GTOKEN,
        "mp_instance_id": MP_INSTANCE_ID_ASSET_LIST_OF_SUB,
        "traceparent": TRACEPARENT_ASSET_LIST_OF_SUB,
        "tracestate": TRACESTATE_ASSET_LIST_OF_SUB,
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
        "plat": PLATFORM,
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
            r = session.post(url, json=data_json, headers=headers, verify=False, timeout=30)
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
        except requests.exceptions.RequestException:
            pass
        try:
            r = session.post(url, data=data_form, headers={**headers, "Content-Type": "application/x-www-form-urlencoded"}, verify=False, timeout=30)
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
        except requests.exceptions.RequestException:
            pass
    if response_data is None:
        logger.info("资产明细条数: 0", extra=extra)
        if with_meta:
            return [], {"token_error": token_error, "first_error": first_error_text}
        return []

    # Extract summary info from Data
    data_obj = response_data.get("Data", {})
    summary_info = {
        "TotalAssetValue": data_obj.get("TotalAssetValue"),
        "TotalHoldProfit": data_obj.get("TotalHoldProfit"),
        "TotalConstantProfit": data_obj.get("TotalConstantProfit"),
        "TotalDailyProfit": data_obj.get("TotalDailyProfit"),
        "TotalProfitValue": data_obj.get("TotalProfitValue"),
        "SubAssetPreview": data_obj.get("SubAssetPreview", {})
    }

    asset_details_list = []
    for asset in data_obj.get("AssetDetails", []):
        asset_detail = AssetDetails()
        asset_detail.fund_name = asset.get("FundName")
        asset_detail.fund_code = asset.get("FundCode")
        asset_detail.fund_type = asset.get("FundType")
        asset_detail.fund_nav = asset.get("FundNav")
        asset_detail.nav_date = asset.get("Navdate")
        asset_detail.hold_profit = _safe_float(asset.get("HoldProfit", 0))
        asset_detail.hold_profit_rate = _safe_float(asset.get("HoldProfitRate", "0"))
        asset_detail.constant_profit = _safe_float(asset.get("ConstantProfit", 0))
        asset_detail.constant_profit_rate = _safe_float(asset.get("ConstantProfitRate", "0"))
        asset_detail.profit_value = _safe_float(asset.get("ProfitValue", 0))
        asset_detail.daily_profit = _safe_float(asset.get("DailyProfit", 0))
        asset_detail.asset_value = _safe_float(asset.get("AssetValue", 0))
        asset_detail.available_vol = asset.get("AvailableVol", 0)
        asset_detail.on_way_transaction_count = asset.get("OnWayTransactionCount", 0)
        asset_details_list.append(asset_detail)
    logger.info(f"资产明细条数: {len(asset_details_list)}", extra=extra)
    if with_meta:
        return asset_details_list, {
            "token_error": token_error, 
            "first_error": first_error_text,
            "summary": summary_info
        }
    return asset_details_list


def _print_group_summary(meta: dict) -> None:
    """打印单个组合的汇总信息。"""
    print("组合级汇总:")
    print(f"  token_error: {meta.get('token_error')}")
    print(f"  first_error: {meta.get('first_error')}")
    summary = meta.get("summary") or {}
    print(f"  TotalAssetValue: {summary.get('TotalAssetValue')}")
    print(f"  TotalHoldProfit: {summary.get('TotalHoldProfit')}")
    print(f"  TotalConstantProfit: {summary.get('TotalConstantProfit')}")
    print(f"  TotalDailyProfit: {summary.get('TotalDailyProfit')}")
    print(f"  TotalProfitValue: {summary.get('TotalProfitValue')}")
    print(f"  SubAssetPreview: {summary.get('SubAssetPreview')}")


def _print_asset_type_summary(type_samples: dict) -> None:
    """打印遍历所有非空组合后观测到的资产基金类型。"""
    print("\n观测到的 Asset.FundType 类型:")
    for fund_type in sorted(type_samples):
        label = describe_asset_fund_type(fund_type)
        samples = ", ".join(
            f"{code} {name}" for code, name in type_samples[fund_type][:8]
        )
        print(
            f"  {format_type_with_label(fund_type, label)}: "
            f"样本数={len(type_samples[fund_type])}, 示例={samples}"
        )


if __name__ == "__main__":
    from src.API.组合管理.SubAccountMrg import getSubAccountList

    logging.basicConfig(level=logging.INFO)

    print("Testing get_asset_list_of_sub...")
    sub_account_response = getSubAccountList(DEFAULT_USER)
    if not sub_account_response.Success or not sub_account_response.Data:
        print(f"获取子账户列表失败: {sub_account_response.FirstError}")
        raise SystemExit(1)

    print("\n所有子账户信息:")
    print(f"  总数量: {len(sub_account_response.Data)}")
    for index, sub_account in enumerate(sub_account_response.Data, start=1):
        print(
            f"  #{index}: name={getattr(sub_account, 'sub_account_name', None)}, "
            f"sub_account_no={getattr(sub_account, 'sub_account_no', None)}, "
            f"total_amount={getattr(sub_account, 'total_amount', None)}, "
            f"asset_value={getattr(sub_account, 'asset_value', None)}, "
            f"total_profit={getattr(sub_account, 'total_profit', None)}, "
            f"total_profit_rate={getattr(sub_account, 'total_profit_rate', None)}, "
            f"daily_profit={getattr(sub_account, 'daily_profit', None)}, "
            f"hold_profit={getattr(sub_account, 'hold_profit', None)}, "
            f"constant_profit={getattr(sub_account, 'constant_profit', None)}, "
            f"on_way_trade_count={getattr(sub_account, 'on_way_trade_count', None)}"
        )

    non_empty_groups = []
    type_samples = {}
    for sub_account in sub_account_response.Data:
        sub_account_no = getattr(sub_account, "sub_account_no", None)
        if not sub_account_no:
            continue
        asset_details_list, meta = get_asset_list_of_sub(
            DEFAULT_USER,
            sub_account_no,
            with_meta=True,
        )
        if not asset_details_list:
            continue
        non_empty_groups.append((sub_account, asset_details_list, meta))
        for asset in asset_details_list:
            fund_type = str(getattr(asset, "fund_type", ""))
            type_samples.setdefault(fund_type, [])
            sample = (asset.fund_code, asset.fund_name)
            if sample not in type_samples[fund_type]:
                type_samples[fund_type].append(sample)

    if not non_empty_groups:
        print("没有有持仓的子账户")
        raise SystemExit(1)

    print("\n函数功能说明:")
    print("  - 查询指定子账户当前持仓的基金列表")
    print("  - 返回每只基金的净值、资产市值、持有收益、累计收益、当日收益等字段")
    print("  - 返回组合级汇总数据，便于上层策略快速判断整体资产和盈亏")
    print("  - 当 with_meta=True 时，还会返回 token_error / first_error / summary")
    print(f"\n有持仓的子账户数量: {len(non_empty_groups)}")

    for index, (sub_account, asset_details_list, meta) in enumerate(non_empty_groups, start=1):
        print("\n" + "=" * 80)
        print(
            f"组合 #{index}: name={sub_account.sub_account_name}, "
            f"sub_account_no={sub_account.sub_account_no}, 持仓条数={len(asset_details_list)}"
        )
        _print_group_summary(meta)
        print()
        _print_asset_detail_preview(asset_details_list, limit=20)

    _print_asset_type_summary(type_samples)
