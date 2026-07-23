"""
查询跟踪指定指数的基金列表（天天基金 getTrackingFundV3 接口）。

在指数字段解析完成后（如指数详情页），调用此接口查询有哪些基金跟踪该指数。
费率字段提供 FIELDS 和 RFIELDS 两级字段支持，方便复用。

请求参数说明：
  INDEXCODES: 指数代码，多个用逗号分隔（如 "000699,000016"）
  ISEXCHG:   是否仅上市交易基金（0=否，1=是），默认 0
  FUNDTYPE:   基金类型筛选（1=全部）
  BUY:        是否仅可申购（1=是）
  pageIndex:  页码，从 1 开始
  pageSize:   每页数量
  sortColumn: 排序字段（如 "ENDNAV"=规模, "SYL_1N"=近1年收益等）
  sort:       排序方向（"DESC"=降序, "ASC"=升序）
  FIELDS:     基础字段列表（逗号分隔的字段名）
  RFIELDS:    费率字段列表（逗号分隔的字段名）

返回数据（TrackingFundItem）：
  基础信息：
    FCODE        - 基金代码
    SHORTNAME    - 基金简称
    ESTABDATE    - 成立日期
    ENDNAV       - 资产净值（万元）
    ISBUY        - 是否可申购
    ISCLASSC     - 是否为 C 类（1.0=C类）
    ISEXCHG      - 是否上市交易
    MAXSG        - 最大申购金额
    SHRATE7      - 7天赎回费率
    TRKERROR     - 跟踪误差
    TJDLIST      - 推荐等级
    FEATURE      - 特色标签

  收益率类：
    RZDF     - 日涨跌幅
    SYL_D/.../SYL_LN  - 日/周/月/季/半年/1年/2年/3年/5年/成立/今年 收益率

  费率类（基础）：
    RATECOST_Y/.../SUBRERATE_Y/.../CSSFEERATE_Y/... （各周期）

  费率类（折扣前原始费率）：
    RAW_RATECOST_Y/... （各周期）
"""

import os
import sys
from typing import List

# 兼容直接运行 `python xxx.py` 的场景
if __name__ == "__main__":
    root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    if root_dir not in sys.path:
        sys.path.insert(0, root_dir)

from src.common.logger import get_logger
from src.common.requests_session import session
from src.domain.user.User import User
from src.common.constant import DEFAULT_GTOKEN, DEVICE_ID, IOS_CLIENT_INFO, IOS_USER_AGENT, MP_VERSION_DEFAULT, PLATFORM, SERVER_VERSION
from src.domain.market_index.tracking_fund import TrackingFundItem, TrackingFundResponse

logger = get_logger("TrackingFund")


# ── 字段声明 ──────────────────────────────────────────────────────────────────

# 基础字段：基金基本信息和各周期收益率
DEFAULT_FIELDS = [
    "RZDF",
    "SYL_LN", "SYL_D", "SYL_Z", "SYL_Y", "SYL_3Y", "SYL_6Y",
    "SYL_1N", "SYL_2N", "SYL_3N", "SYL_5N", "SYL_JN",
    "ENDNAV", "TRKERROR", "SHORTNAME", "DISCOUNT",
    "SHRATE7", "ISCLASSC", "DTZT", "ISBUY",
    "TJDLIST", "FEATURE", "ESTABDATE", "INDEXCODE",
    "MAXSG", "ZERODISCOUNTFLAG", "ISEXCHG", "NEWTEXCH",
]

# 费率字段：各周期的管理费率/申购费率/销售服务费率/折扣前费率
DEFAULT_RFIELDS = [
    "RATECOST_Q", "SUBRERATE_Q", "CSSFEERATE_Q",
    "RATECOST_HY", "SUBRERATE_HY", "CSSFEERATE_HY",
    "RATECOST_Y", "SUBRERATE_Y", "CSSFEERATE_Y",
    "RATECOST_TRY", "SUBRERATE_TRY", "CSSFEERATE_TRY",
    "RATECOST_FY", "SUBRERATE_FY", "CSSFEERATE_FY",
    "RAW_RATECOST_Q", "RAW_RATECOST_HY", "RAW_RATECOST_Y",
    "RAW_RATECOST_TRY", "RAW_RATECOST_FY",
]


def get_tracking_funds(
    user: User,
    index_codes: List[str],
    *,
    is_exchg: str = "0",
    fund_type: str = "1",
    buy: str = "1",
    page_index: int = 1,
    page_size: int = 50,
    sort_column: str = "ENDNAV",
    sort: str = "DESC",
    fields: List[str] = None,
    rfields: List[str] = None,
) -> TrackingFundResponse:
    """
    查询跟踪指定指数的基金列表。

    费率字段说明：
      持有费率 = 管理费 + 托管费（由基金年报披露，年化值）
      申购费率 = 购买时的手续费
      销售服务费率 = C 类份额额外的年化费率
      折扣前持有费率 = 未打折的原始标准费率

    Args:
        user:        User 对象，包含用户认证信息
        index_codes: 指数代码列表（如 ["000699", "000016"]）
        is_exchg:    是否仅上市交易基金
                      "0" = 全部, "1" = 仅上市
        fund_type:   基金类型筛选，"1" = 全部
        buy:         是否仅可申购，"1" = 仅可申购
        page_index:  页码，从 1 开始
        page_size:   每页数量（建议 50，上限 100）
        sort_column: 排序字段，"ENDNAV"（规模降序）为默认
        sort:        "DESC"（降序）或 "ASC"（升序）
        fields:      基础字段列表，默认全量字段
        rfields:     费率字段列表，默认全量费率字段

    Returns:
        TrackingFundResponse，items 为 {index_code: [TrackingFundItem]} 结构
    """
    index_codes_str = ",".join(index_codes)
    logger.info(
        f"获取跟踪指数基金: codes={index_codes_str}, "
        f"page={page_index}, size={page_size}, "
        f"sort={sort_column} {sort}"
    )

    url = "https://fundcomapi.eastmoney.com/mm/FundIndex/getTrackingFundV3"

    headers = _build_headers()
    data = _build_request_data(
        user=user,
        index_codes=index_codes_str,
        is_exchg=is_exchg,
        fund_type=fund_type,
        buy=buy,
        page_index=page_index,
        page_size=page_size,
        sort_column=sort_column,
        sort=sort,
        fields=fields or DEFAULT_FIELDS,
        rfields=rfields or DEFAULT_RFIELDS,
    )

    try:
        response = session.post(url, headers=headers, data=data, verify=False, timeout=30)
        response.raise_for_status()
        result: dict = response.json()

        resp_obj = TrackingFundResponse.from_json(result)

        if resp_obj.success:
            total_funds = sum(len(v) for v in resp_obj.items.values())
            logger.info(
                f"成功获取 {len(resp_obj.items)} 个指数的跟踪基金, "
                f"共 {total_funds} 只"
            )
        else:
            logger.error(f"获取跟踪基金失败: {resp_obj.first_error}")

        return resp_obj

    except Exception as e:
        logger.error(f"获取跟踪基金异常: {e}")
        return TrackingFundResponse(success=False, error_code=-1, first_error=str(e))


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
        "validmark": "Li4RtWc+9LvmhgcBNN3qg3dzZjFUt4WiApOOGmkaVZL5BWm0DcGX9NZYIxjsAsZdSIrQ1Lx4ygfw5br2rQnUfMES8ernsO5lB/RKZKLdR3zMThxZ2ZX8G1uEXj73HzHkj4RnL0fUh8xQ7MADEom6wQ==",
    }


def _build_request_data(
    user: User,
    index_codes: str,
    is_exchg: str,
    fund_type: str,
    buy: str,
    page_index: int,
    page_size: int,
    sort_column: str,
    sort: str,
    fields: List[str],
    rfields: List[str],
) -> dict:
    """构建 POST 请求体。"""
    return {
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
        # ── 接口业务参数 ──
        "INDEXCODES": index_codes,
        "ISEXCHG": is_exchg,
        "FUNDTYPE": fund_type,
        "BUY": buy,
        "pageIndex": str(page_index),
        "pageSize": str(page_size),
        "sortColumn": sort_column,
        "sort": sort,
        "FIELDS": ",".join(fields),
        "RFIELDS": ",".join(rfields),
    }


# ── 直接运行入口（调试） ──────────────────────────────────────────────────────


if __name__ == "__main__":
    from src.common.constant import DEFAULT_USER
    from src.API.登录接口.login import ensure_user_fresh

    print("Refreshing user token...")
    user = ensure_user_fresh(DEFAULT_USER)

    # 测试：查询 000699（中证传媒）和 000016（上证50）的跟踪基金
    for code in ["000699", "000016", "399998"]:
        print(f"\n--- 指数 {code} 的跟踪基金 ---")
        resp = get_tracking_funds(user, [code], page_size=5)
        if not resp.success:
            print(f"  ❌ 请求失败: {resp.first_error}")
            continue
        fund_list = resp.items.get(code, [])
        print(f"  共 {len(fund_list)} 只基金:")
        for item in fund_list[:5]:
            buy_tag = "可购" if item.ISBUY == "1" else "不可购"
            cls_tag = "C类" if item.ISCLASSC == 1.0 else "A类"
            sy1n = f"{item.SYL_1N:+.2f}%" if item.SYL_1N is not None else "N/A"
            cost_y = f"{item.RATECOST_Y:.3f}%" if item.RATECOST_Y is not None else "N/A"
            print(f"    {item.FCODE} {item.SHORTNAME}: "
                  f"规模={item.ENDNAV:.1f}万, "
                  f"近1年={sy1n}, "
                  f"年费率={cost_y}, "
                  f"[{cls_tag}][{buy_tag}]")
