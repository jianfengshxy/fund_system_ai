"""
获取所有主题接口。

调用天天基金 `FundRSBKRealTime` 接口获取 BK 主题/板块实时列表。
默认不传 `TYPE_CODE`，返回“主题+行业”的全量 BK 板块池。
如果需要纯主题，可显式传 `type_code="001003"`。
"""

import os
import sys
from typing import Dict

# 兼容直接运行 `python xxx.py` 的场景
if __name__ == "__main__":
    root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    if root_dir not in sys.path:
        sys.path.insert(0, root_dir)

from src.common.constant import DEFAULT_GTOKEN, IOS_CLIENT_INFO, IOS_USER_AGENT, MP_VERSION_DEFAULT
from src.common.logger import get_logger
from src.common.requests_session import session
from src.domain.user.User import User
from src.domain.market_index.market_theme import (
    MarketThemeItem,
    MarketThemeResponse,
)

logger = get_logger("MarketTheme")


def get_all_market_themes(
    user: User,
    type_code: str = "",
    page_index: int = 1,
    page_size: int = 500,
    sort_type: str = "desc",
    sort_column: str = "CHGRT",
    is_show_score: str = "0",
) -> MarketThemeResponse:
    """
    获取所有主题。

    Args:
        user: User 对象，包含用户认证信息
        type_code: 板块类型，默认空字符串（返回主题+行业全量 BK 板块池）
        page_index: 页码，默认 1
        page_size: 每页数量，默认 500
        sort_type: 排序方向，默认 desc
        sort_column: 排序字段，默认 CHGRT
        is_show_score: 是否只显示有评分主题，默认 0

    Returns:
        MarketThemeResponse，items 为主题实时列表
    """
    logger.info(
        f"获取所有主题: type_code={type_code or 'ALL'}, page={page_index}, "
        f"size={page_size}, sort={sort_column} {sort_type}, is_show_score={is_show_score}"
    )

    url = "https://fundcomapi.tiantianfunds.com/mm/FundTheme/FundRSBKRealTime"
    headers = _build_headers()
    params = _build_params(
        user=user,
        type_code=type_code,
        page_index=page_index,
        page_size=page_size,
        sort_type=sort_type,
        sort_column=sort_column,
        is_show_score=is_show_score,
    )

    try:
        response = session.get(url, headers=headers, params=params, verify=False, timeout=30)
        response.raise_for_status()
        result: Dict = response.json()

        response_obj = MarketThemeResponse(
            total_count=int(result.get("totalCount", 0)),
            error_code=int(result.get("errorCode", -1)),
            first_error=result.get("firstError"),
            success=bool(result.get("success", False)),
            expansion=result.get("expansion"),
        )

        if response_obj.success:
            raw_items = result.get("data", []) or []
            response_obj.items = [MarketThemeItem.from_dict(item) for item in raw_items]
            logger.info(f"所有主题获取成功: {len(response_obj.items)} 条, 总计 {response_obj.total_count}")
        else:
            logger.error(f"获取所有主题失败: {response_obj.first_error}")

        return response_obj
    except Exception as e:
        logger.error(f"获取所有主题异常: {e}")
        return MarketThemeResponse(success=False, error_code=-1, first_error=str(e))


def _build_headers() -> dict:
    """构建请求头，使用应用的默认配置。"""
    return {
        "Accept": "*/*",
        "Accept-Encoding": "gzip, deflate, br",
        "Accept-Language": "zh-Hans-CN;q=1",
        "Connection": "keep-alive",
        "GTOKEN": DEFAULT_GTOKEN,
        "Host": "fundcomapi.tiantianfunds.com",
        "MP-VERSION": MP_VERSION_DEFAULT,
        "User-Agent": IOS_USER_AGENT,
        "clientInfo": IOS_CLIENT_INFO,
        "content-type": "application/json",
        "traceparent": "00-7331cef7d29b4c9da7e2bf2f588e6854-0000000000000000-01",
        "tracestate": "pid=0x10693b1f0,taskid=0x15ece0720",
        "priority": "u=3, i",
    }


def _build_params(
    user: User,
    type_code: str,
    page_index: int,
    page_size: int,
    sort_type: str,
    sort_column: str,
    is_show_score: str,
) -> dict:
    """构建请求参数。"""
    _ = user
    params = {
        "ISSHOWSCORE": is_show_score,
        "pageIndex": str(page_index),
        "pageSize": str(page_size),
        "sort": sort_type,
        "sortColumn": sort_column,
    }
    if type_code:
        params["TYPE_CODE"] = type_code
    return params


if __name__ == "__main__":
    from src.common.constant import DEFAULT_USER
    from src.API.登录接口.login import ensure_user_fresh

    print("Refreshing user token...")
    user = ensure_user_fresh(DEFAULT_USER)

    resp = get_all_market_themes(user)
    print(f"\n请求结果: success={resp.success}, errorCode={resp.error_code}")
    if resp.first_error:
        print(f"错误信息: {resp.first_error}")

    print(f"板块数量: {resp.total_count}")
    for idx, item in enumerate(resp.items[:20], 1):
        print(
            f"{idx}. {item.INDEXNAME}({item.INDEXCODE}) [{item.TYPE_NAME}] "
            f"涨跌幅={item.CHGRT:.2f}% 热度={item.CHANCE_ZJRD:.2f} "
            f"资金={item.FLOW:.2f}"
        )
