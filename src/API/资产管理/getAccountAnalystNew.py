import logging
from typing import Any, Dict, Optional

if __name__ == "__main__":
    import os
    import sys

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
    MP_VERSION_ACCOUNT_ANALYST_NEW,
    PHONE_TYPE,
    SERVER_VERSION,
    TRACEPARENT_ACCOUNT_ANALYST_NEW,
    TRACESTATE_ACCOUNT_ANALYST_NEW,
)
from src.domain.user.api_response import ApiResponse
from src.API.登录接口.login import ensure_user_fresh


# DateRange 的取值用于控制收益分析图表的时间跨度。
# 下面这组映射已按真实接口返回结果校验过：
# - 0: 当月
# - 1: 今年以来
# - 2: 最近3个月
# - 3: 最近6个月
# - 4: 最近1年
# - 7: 成立以来
DATE_RANGE_CURRENT_MONTH = 0
DATE_RANGE_YEAR_TO_DATE = 1
DATE_RANGE_3M = 2
DATE_RANGE_6M = 3
DATE_RANGE_1Y = 4
DATE_RANGE_ALL = 7

DATE_RANGE_DESCRIPTIONS = {
    DATE_RANGE_CURRENT_MONTH: "当月",
    DATE_RANGE_YEAR_TO_DATE: "今年以来",
    DATE_RANGE_3M: "最近3个月",
    DATE_RANGE_6M: "最近6个月",
    DATE_RANGE_1Y: "最近1年",
    DATE_RANGE_ALL: "成立以来",
}

TOKEN_ERROR_KEYWORDS = (
    "Token",
    "token",
    "凭证",
    "passport",
    "未登录",
    "请登录",
    "UToken",
    "CToken",
    "passportid",
    "权限",
)


def describe_date_range(date_range: int) -> str:
    """
    返回 DateRange 对应的人类可读说明。

    Args:
        date_range: 接口字段 DateRange 的整数值

    Returns:
        str: 对应的时间范围说明；未知值返回“未知范围”
    """
    return DATE_RANGE_DESCRIPTIONS.get(date_range, "未知范围")


def _normalize_date_range(date_range: Any) -> int:
    """
    将传入的 DateRange 统一转换为 int，并做白名单校验。
    这样可以在真正发请求之前尽早暴露调用错误，减少无效联调成本。
    """
    if isinstance(date_range, bool):
        raise ValueError("DateRange 不能是布尔值")

    try:
        normalized = int(date_range)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"DateRange 必须是整数，当前值为: {date_range!r}") from exc

    if normalized not in DATE_RANGE_DESCRIPTIONS:
        supported = ", ".join(str(value) for value in DATE_RANGE_DESCRIPTIONS)
        raise ValueError(f"DateRange 仅支持: {supported}，当前值为: {normalized}")

    return normalized


def _build_headers(index: Any, extra_headers: Optional[Dict[str, str]] = None) -> Dict[str, str]:
    """
    组装请求头。

    这里默认沿用用户提供的 iPhone 抓包风格请求头，因为该接口已通过真实 curl 验证。
    如果未来抓到新的请求头，可通过 extra_headers 局部覆盖，不需要改函数主体。
    """
    headers = {
        "Accept": "*/*",
        "Accept-Encoding": "gzip, deflate, br",
        "Accept-Language": "zh-Hans-CN;q=1",
        "Connection": "keep-alive",
        "Content-Type": "application/x-www-form-urlencoded",
        "GTOKEN": DEFAULT_GTOKEN,
        "Host": f"tradeapilvs{index}.1234567.com.cn",
        "MP-VERSION": MP_VERSION_ACCOUNT_ANALYST_NEW,
        "Referer": "https://mpservice.com/fund89ea636d829242/release/pages/home/index",
        "User-Agent": IOS_USER_AGENT,
        "clientInfo": IOS_CLIENT_INFO,
        "traceparent": TRACEPARENT_ACCOUNT_ANALYST_NEW,
        "tracestate": TRACESTATE_ACCOUNT_ANALYST_NEW,
    }
    if extra_headers:
        headers.update(extra_headers)
    return headers


def _build_payload(
    user,
    date_range: int,
    *,
    mobile_key: Optional[str] = None,
    phone_type: Optional[str] = None,
    server_version: Optional[str] = None,
) -> Dict[str, str]:
    """
    组装表单参数。

    默认优先使用项目里的公共常量，保证和现有登录态保持一致；
    若调用方需要完全复刻抓包环境，也可以通过参数覆盖。
    """
    resolved_server_version = server_version or SERVER_VERSION
    return {
        "AppType": "ttjj",
        "CToken": user.c_token,
        "DateRange": str(date_range),
        "MobileKey": mobile_key or MOBILE_KEY,
        "PhoneType": phone_type or PHONE_TYPE,
        "ServerVersion": resolved_server_version,
        "UToken": user.u_token,
        "UserId": user.customer_no,
        "Version": resolved_server_version,
    }


def _is_token_error(json_data: Dict[str, Any]) -> bool:
    """
    判断失败是否由登录态失效引起。
    """
    error_text = str(json_data.get("FirstError") or json_data.get("Message") or "")
    return any(keyword in error_text for keyword in TOKEN_ERROR_KEYWORDS)


def _extract_date_span(json_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    从响应里抽取曲线时间区间，便于日志和测试快速确认 DateRange 是否生效。
    """
    data = json_data.get("Data") or {}

    # 常规区间（0/1/2/3/4）主要看 AssetTrend.AssetPoints。
    points = ((data.get("AssetTrend") or {}).get("AssetPoints") or [])
    dates = [item.get("Date") for item in points if item.get("Date")]
    if dates:
        return {"points": len(dates), "start_date": dates[0], "end_date": dates[-1]}

    # 成立以来（7）没有 AssetTrend，而是按年度聚合到 DailyProfits。
    yearly_points = data.get("DailyProfits") or []
    yearly_dates = [item.get("Date") for item in yearly_points if item.get("Date")]
    if yearly_dates:
        return {"points": len(yearly_dates), "start_date": yearly_dates[0], "end_date": yearly_dates[-1]}

    return {"points": 0, "start_date": None, "end_date": None}


def _format_value(value: Any) -> str:
    """将接口字段转成适合终端阅读的字符串。"""
    if value is None:
        return "None"
    if isinstance(value, list):
        return f"list[{len(value)}]"
    if isinstance(value, dict):
        return f"dict[{len(value)}]"
    if isinstance(value, float):
        return f"{value:.6f}".rstrip("0").rstrip(".")
    return str(value)


def _print_mapping(title: str, mapping: Optional[Dict[str, Any]], keys: list[str]) -> None:
    """按给定键顺序打印一个字典块。"""
    print(title)
    if not mapping:
        print("  无数据")
        return
    for key in keys:
        print(f"  {key}: {_format_value(mapping.get(key))}")


def _print_points_preview(title: str, points: list[Dict[str, Any]], fields: list[str], limit: int = 3) -> None:
    """打印列表型时间序列的前后样本，便于快速判断数据是否合理。"""
    print(title)
    if not points:
        print("  无数据")
        return

    print(f"  总条数: {len(points)}")
    preview_items = points[:limit]
    tail_items = points[-limit:] if len(points) > limit else []

    print("  前几条:")
    for item in preview_items:
        print("   - " + ", ".join(f"{field}={_format_value(item.get(field))}" for field in fields))

    if tail_items:
        print("  后几条:")
        for item in tail_items:
            print("   - " + ", ".join(f"{field}={_format_value(item.get(field))}" for field in fields))


def _print_account_analyst_detail(result: ApiResponse, current_date_range: int) -> None:
    """将 GetAccountAnalystNew 的关键返回字段按业务含义展开打印。"""
    span = _extract_date_span({"Data": result.Data} if result.Data else {})
    print(
        f"DateRange={current_date_range} ({describe_date_range(current_date_range)}) | "
        f"Success={result.Success} | points={span['points']} | "
        f"start={span['start_date']} | end={span['end_date']} | error={result.FirstError}"
    )

    data = result.Data or {}
    if not data:
        print("  Data: None")
        return

    print("  返回字段:")
    print("   - AccountPerformance: 账户整体收益表现摘要")
    print("   - AssetTrend: 资产随时间变化曲线与区间汇总")
    print("   - BehaviorInfo: 交易行为统计")
    print("   - DailyProfits: 按天汇总的收益序列")
    print("   - ProfitContribute: 盈利/亏损贡献分布")
    print("   - ProfitTrend: 买入卖出与收益率趋势")
    print("   - Report/Report2: 报表月份标识")

    _print_mapping(
        "  AccountPerformance:",
        data.get("AccountPerformance"),
        [
            "Date",
            "Asset",
            "Profit",
            "ProfitRate",
            "ExceedRate",
            "OpenDays",
            "OpenTime",
            "TodayUpdating",
            "ProfitRateWeight",
            "ExceedRateWeight",
        ],
    )
    _print_mapping(
        "  AssetTrend 汇总:",
        data.get("AssetTrend"),
        [
            "StartAsset",
            "EndAsset",
            "In",
            "Out",
            "NetIn",
            "Profit",
            "ProfitDiff",
            "InvestProfit",
            "HoldGdlc",
        ],
    )
    _print_mapping(
        "  BehaviorInfo 交易行为:",
        data.get("BehaviorInfo"),
        [
            "TotalCnt",
            "BuyCnt",
            "SellCnt",
            "DtCnt",
            "DtDays",
            "Charge",
            "AvgHoldDays",
            "MyAvgHoldDays",
            "IAConvertCnt",
            "IATransInCnt",
            "IATransOutCnt",
        ],
    )
    _print_mapping(
        "  ProfitContribute 盈亏贡献:",
        data.get("ProfitContribute"),
        [
            "PositiveCnt",
            "NegativeCnt",
            "HasSecondaryPage",
        ],
    )

    positive_profits = (data.get("ProfitContribute") or {}).get("PositiveProfits") or []
    negative_profits = (data.get("ProfitContribute") or {}).get("NegativeProfits") or []
    _print_points_preview("  PositiveProfits 贡献前几项:", positive_profits, ["FundCode", "FundName", "Profit", "ProfitRate"])
    _print_points_preview("  NegativeProfits 贡献前几项:", negative_profits, ["FundCode", "FundName", "Profit", "ProfitRate"])

    asset_points = ((data.get("AssetTrend") or {}).get("AssetPoints") or [])
    _print_points_preview("  AssetPoints 资产曲线样本:", asset_points, ["Date", "Asset", "Profit", "ProfitRate"])

    daily_profits = data.get("DailyProfits") or []
    _print_points_preview("  DailyProfits 日收益样本:", daily_profits, ["Date", "Profit", "ProfitRate", "ProfitRateWeight"])

    profit_trend = data.get("ProfitTrend") or {}
    _print_mapping(
        "  ProfitTrend 概览:",
        profit_trend,
        [
            "AvgProfitRates",
            "AvgProfitRatesWeight",
        ],
    )
    _print_points_preview("  ProfitTrend.Buys 样本:", profit_trend.get("Buys") or [], ["Date", "Value"])
    _print_points_preview("  ProfitTrend.Sells 样本:", profit_trend.get("Sells") or [], ["Date", "Value"])
    _print_points_preview("  ProfitTrend.ProfitRates 样本:", profit_trend.get("ProfitRates") or [], ["Date", "Value"])
    _print_points_preview("  ProfitTrend.ProfitRatesWeight 样本:", profit_trend.get("ProfitRatesWeight") or [], ["Date", "Value"])

    print(f"  FirstTradeDate: {_format_value(data.get('FirstTradeDate'))}")
    print(f"  HasTraded: {_format_value(data.get('HasTraded'))}")
    print(f"  CustomReportDefaultStart: {_format_value(data.get('CustomReportDefaultStart'))}")
    print(f"  CustomReportDefaultEnd: {_format_value(data.get('CustomReportDefaultEnd'))}")
    print(f"  DisplayCustomReport: {_format_value(data.get('DisplayCustomReport'))}")
    print(f"  Report: {_format_value(data.get('Report'))}")
    print(f"  Report2: {_format_value(data.get('Report2'))}")
    print(f"  Tips: {_format_value(data.get('Tips'))}")
    print(f"  Tips2: {_format_value(data.get('Tips2'))}")
    print()


def get_account_analyst_new(
    user,
    date_range: int = DATE_RANGE_3M,
    *,
    extra_headers: Optional[Dict[str, str]] = None,
    mobile_key: Optional[str] = None,
    phone_type: Optional[str] = None,
    server_version: Optional[str] = None,
    timeout: float = 10.0,
) -> ApiResponse:
    """
    获取账户收益分析数据（GetAccountAnalystNew）。

    这个接口返回的是“账户收益分析页”的原始数据源，适合做以下事情：
    1. 查看当前账户在不同时间区间下的资产变化和收益曲线；
    2. 提取账户整体收益摘要，如总资产、累计收益、收益率、跑赢基准情况；
    3. 分析交易行为统计，如买入/卖出/定投次数、平均持有天数；
    4. 查看按天收益序列、资产曲线、买卖行为曲线；
    5. 分析盈利贡献/亏损贡献最大的基金。

    返回的 `Data` 里常见关键字段含义如下：
    - `AccountPerformance`: 账户整体表现摘要
      - `Asset`: 当前区间末资产
      - `Profit`: 区间累计收益金额
      - `ProfitRate`: 区间累计收益率
      - `ExceedRate`: 相对基准的超额收益率
      - `OpenDays/OpenTime`: 开户天数/开户时间
      - `TodayUpdating`: 今天的收益是否仍在更新中
    - `AssetTrend`: 资产趋势与汇总
      - `AssetPoints`: 每个时间点的资产/收益曲线点
      - `StartAsset/EndAsset`: 区间起止资产
      - `In/Out/NetIn`: 区间流入、流出、净流入
      - `Profit/ProfitDiff/InvestProfit`: 区间收益及拆分指标
    - `BehaviorInfo`: 交易行为统计，如买入次数、卖出次数、定投次数、平均持有天数
    - `DailyProfits`: 按天聚合的收益序列；成立以来场景下尤其重要
    - `ProfitContribute`: 盈利基金/亏损基金的贡献分布
    - `ProfitTrend`: 买入、卖出、收益率等时间序列趋势
    - `FirstTradeDate`: 首次交易日期
    - `CustomReportDefaultStart/End`: 自定义报表默认起止时间
    - `Report/Report2`: 报表月份编号
    - `Tips/Tips2`: 服务端补充提示文案

    Args:
        user: 已登录用户对象，至少需要 customer_no / u_token / c_token / index
        date_range: 图表时间跨度
            - 0: 当月
            - 1: 今年以来
            - 2: 最近3个月
            - 3: 最近6个月
            - 4: 最近一年
            - 7: 成立以来
        extra_headers: 额外请求头，用于覆盖默认抓包头
        mobile_key: 可选，覆盖项目默认 MobileKey
        phone_type: 可选，覆盖项目默认 PhoneType
        server_version: 可选，覆盖项目默认 Version / ServerVersion
        timeout: 请求超时时间（秒）

    Returns:
        ApiResponse:
            - Success / ErrorCode / FirstError 保留原接口语义
            - Data 为接口返回的原始 Data，避免丢字段
    """
    logger = get_logger("AssetAPI")
    extra = {
        "account": getattr(user, "mobile_phone", None) or getattr(user, "account", None),
        "action": "get_account_analyst_new",
        "date_range": date_range,
    }

    try:
        normalized_date_range = _normalize_date_range(date_range)
    except ValueError as exc:
        logger.warning(f"DateRange 参数非法: {exc}", extra=extra)
        return ApiResponse(Success=False, ErrorCode=-1, Data=None, FirstError=str(exc), DebugError=None)

    try:
        fresh_user = ensure_user_fresh(user)
        index = getattr(fresh_user, "index", 5) or 5
        url = f"https://tradeapilvs{index}.1234567.com.cn/Business/Analysis/GetAccountAnalystNew"
        headers = _build_headers(index, extra_headers=extra_headers)
        payload = _build_payload(
            fresh_user,
            normalized_date_range,
            mobile_key=mobile_key,
            phone_type=phone_type,
            server_version=server_version,
        )

        response = session.post(url, data=payload, headers=headers, verify=False, timeout=timeout)
        response.raise_for_status()
        json_data = response.json()

        # 如果登录态过期，则强制刷新 token 后重试一次，减少上层调用方处理负担。
        if not json_data.get("Success", False) and _is_token_error(json_data):
            refreshed_user = ensure_user_fresh(fresh_user, force_refresh=True)
            retry_payload = _build_payload(
                refreshed_user,
                normalized_date_range,
                mobile_key=mobile_key,
                phone_type=phone_type,
                server_version=server_version,
            )
            retry_response = session.post(url, data=retry_payload, headers=headers, verify=False, timeout=timeout)
            retry_response.raise_for_status()
            json_data = retry_response.json()

        span = _extract_date_span(json_data)
        logger.info(
            "账户收益分析请求完成: "
            f"DateRange={normalized_date_range}({describe_date_range(normalized_date_range)}), "
            f"points={span['points']}, start={span['start_date']}, end={span['end_date']}",
            extra=extra,
        )

        return ApiResponse(
            Success=bool(json_data.get("Success", False)),
            ErrorCode=json_data.get("ErrorCode"),
            Data=json_data.get("Data"),
            FirstError=json_data.get("FirstError"),
            DebugError=json_data.get("DebugError"),
        )
    except Exception as exc:
        logger.error(f"获取账户收益分析失败: {exc}", extra=extra)
        return ApiResponse(Success=False, ErrorCode=-1, Data=None, FirstError=str(exc), DebugError=None)


if __name__ == "__main__":
    from src.common.constant import DEFAULT_USER

    logging.basicConfig(level=logging.INFO)

    print("Testing get_account_analyst_new...")
    for current_date_range in sorted(DATE_RANGE_DESCRIPTIONS):
        result = get_account_analyst_new(DEFAULT_USER, current_date_range)
        _print_account_analyst_detail(result, current_date_range)
