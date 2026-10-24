"""
基金主题详情查询接口。

调用天天基金 dgs 体系的 fundThemeDetail 接口获取板块/主题的综合详情，
包含实时行情、资金流向、评分排名、相似主题、投资热点与研究报告等数据。

接口地址: https://dgs.tiantianfunds.com/merge/m/api/fundThemeDetail
方法: GET

请求参数:
  code:         主题代码（如 BK000441）
  baseInfoFields: 基础信息字段列表（逗号分隔）

返回:
  FundThemeDetailResponse，包含完整嵌套结构。
"""

import os
import sys
from typing import Dict, Any

# 兼容直接运行 `python xxx.py` 的场景
if __name__ == "__main__":
    root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    if root_dir not in sys.path:
        sys.path.insert(0, root_dir)

from src.common.logger import get_logger
from src.common.requests_session import session
from src.domain.user.User import User
from src.common.constant import (
    DEFAULT_GTOKEN, DEVICE_ID, IOS_CLIENT_INFO, IOS_USER_AGENT,
    MP_VERSION_DEFAULT, PLATFORM, SERVER_VERSION,
)
from src.domain.market_index.fund_theme_detail import (
    FundThemeDetailResponse,
)

logger = get_logger("FundThemeDetail")

# 基础信息字段，对齐天天基金页面展示
_BASE_INFO_FIELDS = (
    "CHANCE_ALL,SCOREDATE,WSC,MSC,QSC,YSC,SYSC,"
    "FWSC,FMSC,FQSC,RANKW,RANKM,RANKQ,RANKY,RANKSY,"
    "FRANKW,FRANKM,FRANKQ,"
    "PETTM,PEP100,PB,PBP100,TYPE_CODE,RELATIVEINDNAME,"
    "BACKGROUNDPIC,SUE,ROE,RM_NETFLOWXL,FCT_XLFLOW,RM_NETFLOWXL_PCT,"
    "RISK_GLL,RISK_JZD,RISK_YJD,"
    "CHANCE_ALL_RANK,CHANCE_ALL_NUM,RISK_ALL_RANK,RISK_ALL_NUM,"
    "SUMFLOW_W,SUMFLOW_M,SUMFLOW_Q,CHANCE_ZJRD,CHANCE_JQD"
)
_RELATIVE_THEME_FIELDS = "W,SEC_NAME,SEC_CODE"
_SIMILAR_THEME_FIELDS = "W,SEC_NAME,SEC_CODE"


def get_fund_theme_detail(user: User, code: str) -> FundThemeDetailResponse:
    """
    获取基金主题详情。

    Args:
        user: User 对象，包含用户认证信息
        code: 主题代码，如 "BK000441"

    Returns:
        FundThemeDetailResponse，包含完整嵌套结构
    """
    logger.info(f"获取基金主题详情: code={code}")

    url = "https://dgs.tiantianfunds.com/merge/m/api/fundThemeDetail"

    headers = {
        "Accept": "*/*",
        "Accept-Encoding": "gzip, deflate, br",
        "Accept-Language": "zh-Hans-CN;q=1",
        "Connection": "keep-alive",
        "GTOKEN": DEFAULT_GTOKEN,
        "clientInfo": IOS_CLIENT_INFO,
        "content-type": "application/json",
        "mp-version": MP_VERSION_DEFAULT,
        "traceparent": "00-84a722bf4a0f4af7a918c718b1c20a37-0000000000000000-01",
        "tracestate": "pid=0x106ba9c80,taskid=0x17edcd440",
        "User-Agent": IOS_USER_AGENT,
        "priority": "u=3, i",
    }

    params: Dict[str, str] = {
        "code": code,
        "baseInfoFields": _BASE_INFO_FIELDS,
        "relativeThemeFields": _RELATIVE_THEME_FIELDS,
        "relativeThemeSortColumn": "W",
        "similarThemeFields": _SIMILAR_THEME_FIELDS,
        "similarThemeSortColumn": "W",
        "appVersion": SERVER_VERSION,
        "ctoken": user.c_token,
        "deviceid": DEVICE_ID,
        "passportctoken": user.passport_ctoken or user.c_token,
        "passportid": user.passport_id,
        "passportutoken": user.passport_utoken or user.u_token,
        "plat": PLATFORM,
        "product": "Fund",
        "uid": user.customer_no,
        "userid": user.customer_no,
        "utoken": user.u_token,
        "version": SERVER_VERSION,
    }

    try:
        response = session.get(url, headers=headers, params=params, verify=False, timeout=30)
        response.raise_for_status()
        result: dict = response.json()

        resp = FundThemeDetailResponse.from_json(result)
        if resp.success:
            rt = resp.data.realTimeList[0] if resp.data and resp.data.realTimeList else None
            if rt:
                logger.info(
                    f"主题详情获取成功: [{rt.INDEXNAME}]({rt.INDEXCODE}), "
                    f"涨跌幅={rt.CHGRT}%, 价格={rt.PERCENTPRICE}"
                )
            else:
                logger.info(f"主题详情获取成功: code={code}")
        else:
            logger.error(f"获取基金主题详情失败: {resp.firstError}")

        return resp

    except Exception as e:
        logger.error(f"获取基金主题详情异常: {e}")
        return FundThemeDetailResponse(success=False, firstError=str(e))


# ── 直接运行入口（调试） ──────────────────────────────────────────────────────

if __name__ == "__main__":
    from src.common.constant import DEFAULT_USER
    from src.API.登录接口.login import ensure_user_fresh

    print("Refreshing user token...")
    user = ensure_user_fresh(DEFAULT_USER)

    # 测试高端装备主题
    resp = get_fund_theme_detail(user, "BK000441")
    print(f"\n请求结果: success={resp.success}, errorCode={resp.errorCode}")
    if resp.firstError:
        print(f"错误信息: {resp.firstError}")

    if resp.data and resp.data.realTimeList:
        rt = resp.data.realTimeList[0]
        print(f"\n── 实时行情 ──")
        print(f"  主题: {rt.INDEXNAME}({rt.INDEXCODE})")
        print(f"  涨跌幅: {rt.CHGRT}%")
        print(f"  最新点位: {rt.PERCENTPRICE}")
        print(f"  行情时间: {rt.DEALTIME}")
        print(f"  机会评分: {rt.CHANCE_ALL}")
        print(f"  资金热度: {rt.CHANCE_ZJRD}")
        print(f"  周涨跌: {rt.W}% / 月涨跌: {rt.M}%")
        print(f"  PE: {rt.PETTM} / PB: {rt.PB}")
        print(f"  连涨: {rt.UPDAYS}天 / 连跌: {rt.DOWNDAYS}天")
        print(f"  资金流入: {rt.FLOW} / 流出: {rt.FLOW_W}")

    if resp.data and resp.data.similarTheme:
        print(f"\n── 相似主题 ──")
        for st in resp.data.similarTheme[:5]:
            print(f"  {st.SEC_NAME}({st.SEC_CODE}): 相似度={st.SCORE}, 相关系数={st.CORRELATION}%")

    if resp.data and resp.data.themeBaseInfo:
        bi = resp.data.themeBaseInfo[0]
        print(f"\n── 基本信息 ──")
        print(f"  周排名: {bi.RANKW} / 月排名: {bi.RANKM} / 季排名: {bi.RANKQ}")
        print(f"  综合机会: {bi.CHANCE_ALL} / 资金热度: {bi.CHANCE_ZJRD}")

    if resp.data and resp.data.sectorByCodeOrTheme:
        si = resp.data.sectorByCodeOrTheme
        print(f"\n── 板块信息 ──")
        print(f"  板块: {si.sectorName}({si.sectorCode})")
        if si.researchReportVO:
            print(f"  视点摘要: {si.researchReportVO.shortSummary}")
            print(f"  核心标题: {', '.join(si.researchReportVO.title)}")
