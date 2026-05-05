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
from src.common.constant import MOBILE_KEY, PHONE_TYPE, SERVER_VERSION
from src.domain.user.api_response import ApiResponse
from src.API.登录接口.login import ensure_user_fresh


# DateRange 的取值用于控制收益分析图表的时间跨度。
# 这里按照接口实测结果整理成常量，便于调用方直接查阅和 IDE 自动提示。
DATE_RANGE_1M = 0
DATE_RANGE_3M = 1
DATE_RANGE_6M = 2
DATE_RANGE_1Y = 3
DATE_RANGE_3Y = 4
DATE_RANGE_ALL = 5

DATE_RANGE_DESCRIPTIONS = {
    DATE_RANGE_1M: "近1个月",
    DATE_RANGE_3M: "近3个月",
    DATE_RANGE_6M: "近6个月",
    DATE_RANGE_1Y: "近1年",
    DATE_RANGE_3Y: "近3年",
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
        "GTOKEN": "03FC9273690F4DC4B71CB2247A0E4338",
        "Host": f"tradeapilvs{index}.1234567.com.cn",
        "MP-VERSION": "2.9.0",
        "Referer": "https://mpservice.com/fund89ea636d829242/release/pages/home/index",
        "User-Agent": "EMProjJijin/6.8.6 (iPhone; iOS 26.0.1; Scale/3.00)",
        "clientInfo": "ttjj-iPhone18,1-iOS-iOS26.0.1",
        "traceparent": "00-715f86be36b64be4956edbf671fb05f5-0000000000000000-01",
        "tracestate": "pid=0x104974860,taskid=0x13dd9eb80",
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
    points = (((json_data.get("Data") or {}).get("AssetTrend") or {}).get("AssetPoints") or [])
    dates = [item.get("Date") for item in points if item.get("Date")]
    if not dates:
        return {"points": 0, "start_date": None, "end_date": None}
    return {"points": len(dates), "start_date": dates[0], "end_date": dates[-1]}


def get_account_analyst_new(
    user,
    date_range: int = DATE_RANGE_6M,
    *,
    extra_headers: Optional[Dict[str, str]] = None,
    mobile_key: Optional[str] = None,
    phone_type: Optional[str] = None,
    server_version: Optional[str] = None,
    timeout: float = 10.0,
) -> ApiResponse:
    """
    获取账户收益分析数据（GetAccountAnalystNew）。

    Args:
        user: 已登录用户对象，至少需要 customer_no / u_token / c_token / index
        date_range: 图表时间跨度
            - 0: 近1个月
            - 1: 近3个月
            - 2: 近6个月
            - 3: 近1年
            - 4: 近3年
            - 5: 成立以来
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
        span = _extract_date_span({"Data": result.Data} if result.Data else {})
        print(
            f"DateRange={current_date_range} ({describe_date_range(current_date_range)}) | "
            f"Success={result.Success} | points={span['points']} | "
            f"start={span['start_date']} | end={span['end_date']} | error={result.FirstError}"
        )
