"""
指数资金热度与价格走势接口。

调用天天基金 FundIndex/FundIndexPrice 接口获取指定指数每日的价格（PERCENTPRICE）、
涨跌幅（CHGRT）与资金热度评分（XLFLOW_SCORE）序列。
用于在"指数详情"页面渲染价格走势图与资金热度辅助线。

请求参数说明：
  index_code:   指数代码，如 "930901" / "399959"
  range_type:   时间范围
    "n"   - 近 1 年（默认）
    "3n"  - 近 3 年
    "y"   - 近 1 月
    "w"   - 近 1 周


返回字段（IndexPriceFlowPoint）：
  PDATE         - 日期（如 "2026-07-20"）
  PERCENTPRICE  - 指数收盘点位（精确点位，非四舍五入）
  CHGRT         - 日涨跌幅（%），首次数据点通常为空（无前一日比较基准）
  XLFLOW_SCORE  - 指数资金热度评分（0-100），"--" 表示当日暂无数据

响应元信息：
  total_count    - 总记录数
  error_code     - 错误码（0 = 正常）
  has_wrong_token - token 是否异常（null 表示正常）
  expansion      - 扩展字段（本接口不使用，固定为 null）
  jf             - 平台标识（"ali" = 阿里云）
"""

import os
import sys


# 兼容直接运行 `python xxx.py` 的场景
if __name__ == "__main__":
    root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    if root_dir not in sys.path:
        sys.path.insert(0, root_dir)

from src.common.logger import get_logger
from src.common.requests_session import session
from src.domain.user.User import User
from src.common.constant import DEFAULT_GTOKEN, DEVICE_ID, IOS_CLIENT_INFO, IOS_USER_AGENT, MP_VERSION_DEFAULT, PLATFORM, SERVER_VERSION
from src.domain.market_index.market_index_price_flow import (
    IndexPriceFlowPoint,
    IndexPriceFlowResponse,
    MONEY_FLOW_RANGE_MAP,
)

logger = get_logger("IndexPriceFlow")


def get_index_price_flow(
    user: User,
    index_code: str,
    range_type: str = "n",
) -> IndexPriceFlowResponse:
    """
    获取指定指数的每日价格走势与资金热度数据。

    Args:
        user:        User 对象，包含用户认证信息
        index_code:  指数代码，如 "930901" / "399959"
        range_type:  时间范围，"n"(近1年) / "3n"(近3年) / "y"(近1月) / "w"(近一周)

    Returns:
        IndexPriceFlowResponse，包含 items（IndexPriceFlowPoint 列表）与元信息
    """
    range_label = MONEY_FLOW_RANGE_MAP.get(range_type, range_type)
    logger.info(
        f"获取指数价格与资金热度: index_code={index_code}, "
        f"range={range_type}({range_label})"
    )

    url = "https://fundcomapi.tiantianfunds.com/mm/FundIndex/FundIndexPrice"

    headers = _build_headers()
    data = _build_request_data(
        user=user,
        index_code=index_code,
        range_type=range_type,
    )

    try:
        response = session.post(url, headers=headers, data=data, verify=False, timeout=30)
        response.raise_for_status()
        result: dict = response.json()

        response_obj = IndexPriceFlowResponse(
            total_count=int(result.get("totalCount", 0)),
            error_code=int(result.get("errorCode", -1)),
            first_error=result.get("firstError"),
            success=bool(result.get("success", False)),
            has_wrong_token=result.get("hasWrongToken"),
            expansion=result.get("expansion"),
            jf=result.get("jf", ""),
        )

        if response_obj.success:
            raw_items: list = result.get("data", []) or []
            response_obj.items = [
                IndexPriceFlowPoint.from_dict(item)
                for item in raw_items
            ]
            logger.info(
                f"成功获取 {len(response_obj.items)} 条价格/热度数据, "
                f"总计 {response_obj.total_count}"
            )
        else:
            logger.error(f"获取指数价格与资金热度失败: {response_obj.first_error}")

        return response_obj

    except Exception as e:
        logger.error(f"获取指数价格与资金热度异常: {e}")
        return IndexPriceFlowResponse(success=False, error_code=-1, first_error=str(e))


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
        "Referer": "https://mpservice.com/7d7b3460cd40444ba58cdabdfae34442/release/pages/index-detail/sub-pages/capital/index",
        "User-Agent": IOS_USER_AGENT,
        "clientInfo": IOS_CLIENT_INFO,
        "traceparent": "00-daba033e0a1f4986b39426b61e0b3619-0000000000000000-01",
        "tracestate": "pid=0x105032130,taskid=0x157a9ef40",
        "validmark": "Li4RtWc+9LvmhgcBNN3qg3dzZjFUt4WiApOOGmkaVZL5BWm0DcGX9NZYIxjsAsZdSIrQ1Lx4ygfw5br2rQnUfMES8ernsO5lB/RKZKLdR3zD2KNQjemM+lwlJAhAHjbPa1Sl+8lg3dobsr1ny7eoGw==",
    }


def _build_request_data(
    user: User,
    index_code: str,
    range_type: str,
) -> dict:
    """构建 POST 请求体。"""
    return {
        "INDEXCODE": index_code,
        "RANGE": range_type,
        "ctoken": user.c_token,
        "deviceid": DEVICE_ID,
        "passportctoken": user.passport_ctoken or user.c_token,
        "passportid": user.passport_id,
        "passportutoken": user.passport_utoken or user.u_token,
        "plat": PLATFORM,
        "product": "EFund",
        "uid": user.customer_no,
        "userid": user.customer_no,
        "utoken": user.u_token,
        "version": SERVER_VERSION,
    }


# ── 直接运行入口（调试） ──────────────────────────────────────────────────────


if __name__ == "__main__":
    from src.common.constant import DEFAULT_USER
    from src.API.登录接口.login import ensure_user_fresh

    print("Refreshing user token...")
    user = ensure_user_fresh(DEFAULT_USER)

    test_index_code = "399998"
    test_index_name = "中证煤炭"

    for range_type, label in [("n", "近 1 年"), ("3n", "近 3 年"), ("y", "近 1 月")]:
        print(f"\n--- {test_index_name} - {label} ---")
        resp = get_index_price_flow(user, index_code=test_index_code, range_type=range_type)
        if not resp.success:
            print(f"  ❌ 请求失败: {resp.first_error}")
            continue
        print(f"  共 {resp.total_count} 条数据")
        print(f"  前 3 条:")
        for point in resp.items[:3]:
            chg = f"{point.CHGRT:+.4f}%" if point.CHGRT is not None else "N/A"
            score = f"{point.XLFLOW_SCORE:.2f}" if point.XLFLOW_SCORE is not None else "--"
            print(f"    {point.PDATE}  价格={point.PERCENTPRICE:.4f}  涨跌幅={chg}  热度={score}")
        print(f"  最后 3 条:")
        for point in resp.items[-3:]:
            chg = f"{point.CHGRT:+.4f}%" if point.CHGRT is not None else "N/A"
            score = f"{point.XLFLOW_SCORE:.2f}" if point.XLFLOW_SCORE is not None else "--"
            print(f"    {point.PDATE}  价格={point.PERCENTPRICE:.4f}  涨跌幅={chg}  热度={score}")
