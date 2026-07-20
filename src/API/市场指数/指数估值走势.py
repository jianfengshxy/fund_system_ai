"""
指数估值走势接口（查询 PB / PETTM 历史数据）。

调用天天基金 FundIndex/indexValueTrend 接口获取指定指数在时间范围内的 PB 或 PE-TTM
历史序列数据。单次仅返回一种估值类型（PETTM 或 PB），后续 service 层可按 PDATE join。

请求参数说明：
  index_code:       指数代码，如 "399998"（中证煤炭）
  index_value_type: 估值类型
    "PETTM"  - 滚动市盈率 PE-TTM
    "PB"     - 市净率 PB
  range:      时间范围
    "1n"  - 近 1 年
    "3n"  - 近 3 年
    "5n"  - 近 5 年
    "10n" - 近 10 年
  point_count: 返回数据点数（接口实际返回受 range 限制，可不指定使用默认值）

返回字段（ValuationPoint）：
  PDATE   - 估值日期（如 "2026-07-20"）
  PETTM   - 滚动市盈率（当查询类型为 PETTM 时返回）
  PB      - 市净率（当查询类型为 PB 时返回）

响应元信息：
  total_count - 数据点总数
  expansion   - [最小值, 下均值/中位数, 上均值/平均数, 最大值]
                用于图表辅助线绘制
  jf          - 平台标识（"ali" = 阿里云）
"""

import os
import sys
from typing import Optional

# 兼容直接运行 `python xxx.py` 的场景
if __name__ == "__main__":
    root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    if root_dir not in sys.path:
        sys.path.insert(0, root_dir)

from src.common.logger import get_logger
from src.common.requests_session import session
from src.domain.user.User import User
from src.common.constant import DEFAULT_GTOKEN, DEVICE_ID, IOS_CLIENT_INFO, IOS_USER_AGENT, MP_VERSION_DEFAULT, PLATFORM, SERVER_VERSION
from src.domain.market_index.market_index_valuation_trend import (
    ValuationPoint,
    ValuationTrendResponse,
    VALUATION_TYPE_MAP,
    VALUATION_RANGE_MAP,
)

logger = get_logger("IndexValuationTrend")


def get_index_valuation_trend(
    user: User,
    index_code: str,
    index_value_type: str = "PETTM",
    range_param: str = "10n",
    point_count: Optional[int] = None,
) -> ValuationTrendResponse:
    """
    获取指定指数的估值走势数据（PB 或 PE-TTM 历史序列）。

    Args:
        user:             User 对象，包含用户认证信息
        index_code:       指数代码，如 "399998"（中证煤炭）
        index_value_type: 估值类型，"PETTM" 或 "PB"
        range_param:      时间范围，如 "1n"/"3n"/"5n"/"10n"
        point_count:      返回点数（可选，接口默认按 range 分配，不传则用默认值）

    Returns:
        ValuationTrendResponse，包含 items（ValuationPoint 列表）与辅助线数据
    """
    type_label = VALUATION_TYPE_MAP.get(index_value_type, index_value_type)
    range_label = VALUATION_RANGE_MAP.get(range_param, range_param)
    logger.info(
        f"获取指数估值走势: index_code={index_code}, "
        f"type={index_value_type}({type_label}), "
        f"range={range_param}({range_label})"
    )

    url = "https://fundcomapi.tiantianfunds.com/mm/FundIndex/indexValueTrend"

    headers = _build_headers()
    params = _build_query_params(
        user=user,
        index_code=index_code,
        index_value_type=index_value_type,
        range_param=range_param,
        point_count=point_count,
    )

    try:
        response = session.get(url, headers=headers, params=params, verify=False, timeout=30)
        response.raise_for_status()
        result: dict = response.json()

        response_obj = ValuationTrendResponse(
            total_count=int(result.get("totalCount", 0)),
            error_code=int(result.get("errorCode", -1)),
            first_error=result.get("firstError"),
            success=bool(result.get("success", False)),
            expansion=result.get("expansion", []),
            jf=result.get("jf", ""),
        )

        if response_obj.success:
            raw_items: list = result.get("data", []) or []
            response_obj.items = [
                ValuationPoint.from_dict(item, index_value_type)
                for item in raw_items
            ]
            logger.info(
                f"成功获取 {len(response_obj.items)} 条估值数据, "
                f"总计 {response_obj.total_count}, expansion={response_obj.expansion}"
            )
        else:
            logger.error(f"获取指数估值走势失败: {response_obj.first_error}")

        return response_obj

    except Exception as e:
        logger.error(f"获取指数估值走势异常: {e}")
        return ValuationTrendResponse(success=False, error_code=-1, first_error=str(e))


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
        "Host": "fundcomapi.tiantianfunds.com",
        "MP-VERSION": MP_VERSION_DEFAULT,
        "Referer": "https://mpservice.com/7d7b3460cd40444ba58cdabdfae34442/release/pages/index-detail/sub-pages/common/index",
        "User-Agent": IOS_USER_AGENT,
        "clientInfo": IOS_CLIENT_INFO,
        "traceparent": "00-872f53346a2345339597c325183fcffa-0000000000000000-01",
        "tracestate": "pid=0x105032130,taskid=0x16e566ca0",
        "validmark": "Li4RtWc+9LvmhgcBNN3qg3dzZjFUt4WiApOOGmkaVZL5BWm0DcGX9NZYIxjsAsZdSIrQ1Lx4ygfw5br2rQnUfMES8ernsO5lB/RKZKLdR3y0j30EL+Ew6rLFgl+jpgiBrksrA9NNLJ97Phr21uXMnQ==",
    }


def _build_query_params(
    user: User,
    index_code: str,
    index_value_type: str,
    range_param: str,
    point_count: Optional[int],
) -> dict:
    """构建 GET 查询参数。"""
    params = {
        "ctoken": user.c_token,
        "deviceid": DEVICE_ID,
        "indexCode": index_code,
        "indexValueType": index_value_type,
        "passportctoken": user.passport_ctoken or user.c_token,
        "passportid": user.passport_id,
        "passportutoken": user.passport_utoken or user.u_token,
        "plat": PLATFORM,
        "product": "EFund",
        "range": range_param,
        "uid": user.customer_no,
        "userid": user.customer_no,
        "utoken": user.u_token,
        "version": SERVER_VERSION,
    }
    if point_count is not None:
        params["pointCount"] = str(point_count)
    return params


# ── 直接运行入口（调试） ──────────────────────────────────────────────────────


if __name__ == "__main__":
    from src.common.constant import DEFAULT_USER
    from src.API.登录接口.login import ensure_user_fresh

    print("Refreshing user token...")
    user = ensure_user_fresh(DEFAULT_USER)

    # 中证煤炭（399959）作为演示
    test_index_code = "399959"
    test_index_name = "中证煤炭"

    for value_type, label in [("PETTM", "PE-TTM"), ("PB", "PB")]:
        print(f"\n--- {test_index_name} - {label} 历史走势 ---")
        resp = get_index_valuation_trend(
            user,
            index_code=test_index_code,
            index_value_type=value_type,
            range_param="10n",
        )
        if not resp.success:
            print(f"  ❌ 请求失败: {resp.first_error}")
            continue
        print(f"  共 {resp.total_count} 条数据")
        print(f"  辅助线 [min, low_avg, high_avg, max] = {resp.expansion}")
        print(f"  前 5 条:")
        for point in resp.items[:5]:
            val = point.PETTM if value_type == "PETTM" else point.PB
            print(f"    {point.PDATE}  →  {val:.4f}")
        print(f"  最后 1 条:")
        last = resp.items[-1]
        val = last.PETTM if value_type == "PETTM" else last.PB
        print(f"    {last.PDATE}  →  {val:.4f}")
