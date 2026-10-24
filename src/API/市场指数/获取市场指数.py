"""
市场指数排行查询接口（指数宝 API）。

调用天天基金的 FundZSBIndexRankV2 接口获取市场指数排行数据。
接口提供全量字段解析到 MarketIndexItem，返回 MarketIndexResponse。

请求参数说明：
  type_code: 指数类型
    "0"       - 全部指数
    "001001"  - 宽基指数
    "001002"  - 行业指数
    "001003"  - 主题指数
    "001004"  - 策略指数
    "003"     - 海外指数
  sort_name: 排序字段
    "NEWCHG"  - 涨跌幅
    "D"       - 日涨跌幅
    "W"       - 周涨跌幅
    "M"       - 月涨跌幅
    "Q"       - 季涨跌幅
  sort_type: 排序方向
    "DESC"    - 降序
    "ASC"     - 升序

返回数据字段（MarketIndexItem）：
  指标类：
    NEWPRICE   - 指数最新点位
    NEWCHG     - 日涨跌幅(%)
    D          - 日涨跌幅(%)（精确值）
    W          - 周涨跌幅(%)
    M          - 月涨跌幅(%)
    Q          - 季涨跌幅(%)
    HY         - 半年涨跌幅(%)（HY=Half Year）
    Y          - 1年涨跌幅(%)
    TWY        - 2年涨跌幅(%)
    TRY        - 3年涨跌幅(%)
    FY         - 5年涨跌幅(%)
    SY         - 今年以来涨跌幅(%)
  估值类：
    PETTM      - 滚动市盈率 PE-TTM
    PEP100     - PE 在历史区间中的百分位
    PB         - 市净率
    PBP100     - PB 在历史区间中的百分位
    GXL        - 静态股息率(%)
    ROE        - 净资产收益率(%)
    GXL_RS     - 股息率在历史区间中的百分位
  热度类：
    XLFLOW_SCORE - 指数资金热度评分
    AVGSYL_TRY   - 近3年平均股息率
"""

import os
import sys
from typing import Dict, Any, List

# 兼容直接运行 `python xxx.py` 的场景
if __name__ == "__main__":
    root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    if root_dir not in sys.path:
        sys.path.insert(0, root_dir)

from src.common.logger import get_logger
from src.common.requests_session import session
from src.domain.user.User import User
from src.common.constant import DEFAULT_GTOKEN, DEVICE_ID, IOS_CLIENT_INFO, IOS_USER_AGENT, MP_VERSION_DEFAULT, PLATFORM, SERVER_VERSION
from src.domain.market_index.market_index import (
    MarketIndexItem,
    MarketIndexResponse,
    MARKET_INDEX_TYPE_MAP,
)

logger = get_logger("MarketIndex")


def get_market_index(
    user: User,
    type_code: str = "0",
    page_index: int = 1,
    page_size: int = 30,
    sort_type: str = "DESC",
    sort_name: str = "NEWCHG",
    sec_code: str = "",
    index_value: str = "",
    valuation_type: str = "",
) -> MarketIndexResponse:
    """
    获取市场指数排行数据。

    Args:
        user:         User 对象，包含用户认证信息
        type_code:    指数类型代码，详见 MARKET_INDEX_TYPE_MAP
                      默认 "0"（全部指数），常用: 001001/001002/001003/001004/003
        page_index:   页码，从 1 开始
        page_size:    每页数量，默认 30，最大 30（超出自动截断）
        sort_type:    排序方向，"DESC"（降序）或 "ASC"（升序）
        sort_name:    排序字段，默认 "NEWCHG"（涨跌幅）
        sec_code:     行业/主题代码，空字符串表示不过滤
        index_value:  指数代码筛选，空字符串表示不过滤
        valuation_type: 估值类型筛选，空字符串表示不过滤

    Returns:
        MarketIndexResponse，包含 items（MarketIndexItem 列表）与元信息
    """
    type_name = MARKET_INDEX_TYPE_MAP.get(type_code, "未知类型")
    logger.info(
        f"获取市场指数: type={type_code}({type_name}), "
        f"page={page_index}, size={page_size}, "
        f"sort={sort_name} {sort_type}"
    )

    # page_size 上限 30
    page_size = min(max(page_size, 1), 30)

    url = "https://fundcomapi.eastmoney.com/mm/FundIndex/FundZSBIndexRankV2"

    headers = _build_headers()
    data = _build_request_data(
        user=user,
        type_code=type_code,
        page_index=page_index,
        page_size=page_size,
        sort_type=sort_type,
        sort_name=sort_name,
        sec_code=sec_code,
        index_value=index_value,
        valuation_type=valuation_type,
    )

    try:
        response = session.post(url, headers=headers, data=data, verify=False, timeout=30)
        response.raise_for_status()
        result: dict = response.json()

        response_obj = MarketIndexResponse(
            total_count=int(result.get("totalCount", 0)),
            error_code=int(result.get("errorCode", -1)),
            first_error=result.get("firstError"),
            success=bool(result.get("success", False)),
            expansion=result.get("expansion"),
        )

        if response_obj.success:
            raw_items: List[dict] = result.get("data", []) or []
            response_obj.items = [MarketIndexItem.from_dict(item) for item in raw_items]
            logger.info(f"成功获取 {len(response_obj.items)} 条指数数据, 总计 {response_obj.total_count}")
        else:
            logger.error(f"获取市场指数失败: {response_obj.first_error}")

        return response_obj

    except Exception as e:
        logger.error(f"获取市场指数异常: {e}")
        return MarketIndexResponse(success=False, error_code=-1, first_error=str(e))


# ── 内部辅助 ──────────────────────────────────────────────────────────────────


def _build_headers() -> dict:
    """构建请求头，使用应用的默认配置。"""
    return {
        "Accept": "*/*",
        "Accept-Encoding": "gzip, deflate, br",
        "Accept-Language": "zh-Hans-CN;q=1",
        "Connection": "keep-alive",
        "Content-Type": "application/x-www-form-urlencoded",
        "GTOKEN": DEFAULT_GTOKEN,
        "Host": "fundcomapi.eastmoney.com",
        "MP-VERSION": MP_VERSION_DEFAULT,
        "Referer": "https://mpservice.com/7d7b3460cd40444ba58cdabdfae34442/release/pages/rank",
        "User-Agent": IOS_USER_AGENT,
        "clientInfo": IOS_CLIENT_INFO,
        "traceparent": "00-b368e007d4eb4a6b9b833e67470de310-0000000000000000-01",
        "tracestate": "pid=0x105032130,taskid=0x16e672340",
        "validmark": "Li4RtWc+9LvmhgcBNN3qg3dzZjFUt4WiApOOGmkaVZL5BWm0DcGX9NZYIxjsAsZdSIrQ1Lx4ygfw5br2rQnUfMES8ernsO5lB/RKZKLdR3zMThZx2ZX8G1uEXj73HzHkj4RnL0fUh8xQ7MADEom6wQ==",
    }


def _build_request_data(
    user: User,
    type_code: str,
    page_index: int,
    page_size: int,
    sort_type: str,
    sort_name: str,
    sec_code: str,
    index_value: str,
    valuation_type: str,
) -> dict:
    """构建 POST 请求体。"""
    return {
        "ctoken": user.c_token,
        "deviceid": DEVICE_ID,
        "indexValue": index_value,
        "pageIndex": str(page_index),
        "pageSize": str(page_size),
        "passportctoken": user.passport_ctoken or user.c_token,
        "passportid": user.passport_id,
        "passportutoken": user.passport_utoken or user.u_token,
        "plat": PLATFORM,
        "product": "EFund",
        "secCode": sec_code,
        "sortName": sort_name,
        "sortType": sort_type,
        "type": type_code,
        "uid": user.customer_no,
        "userid": user.customer_no,
        "utoken": user.u_token,
        "valuationType": valuation_type,
        "version": SERVER_VERSION,
    }


# ── 直接运行入口（调试） ──────────────────────────────────────────────────────


if __name__ == "__main__":
    from src.common.constant import DEFAULT_USER
    from src.API.登录接口.login import ensure_user_fresh

    print("Refreshing user token...")
    user = ensure_user_fresh(DEFAULT_USER)

    for code, name in [("0", "全部"), ("001003", "主题"), ("001002", "行业"), ("001001", "宽基"), ("001004", "策略"), ("003", "海外")]:
        print(f"\n--- {name}指数 ({code}) ---")
        resp = get_market_index(user, type_code=code, page_size=5)
        if not resp.success:
            print(f"  ❌ 请求失败: {resp.first_error}")
            continue
        print(f"  共 {resp.total_count} 条, 返回 {len(resp.items)} 条")
        for item in resp.items[:5]:
            print(f"  {item.INDEXNAME or item.SEC_NAME}: "
                  f"NEWCHG={item.NEWCHG:+.2f}%, "
                  f"PE={item.PETTM:.2f}, PB={item.PB:.4f}, "
                  f"ROE={item.ROE:.2f}%, 热度={item.XLFLOW_SCORE:.2f}")
