"""
基金详情页综合数据接口。

调用天天基金的 `dgs.tiantianfunds.com/merge/m/api/jjxqy1_2` 接口，
一次返回基金的多维度数据，包括：
  1. 基础信息（baseInfo）
  2. 关联主题与相关性（fundRelateTheme）
  3. 主题风险与机会评分（fundRelateThemeInfo）
  4. 各周期收益与基准对比（FundPeriodIncrease）
  5. 独立风险指标（uniqueInfo）
  6. 持有人结构（fundHolderStructure）
  7. 基金公司信息（companyInfo）
  8. 基金经理信息（FundManagerInformation）

使用方法：
  from src.API.基金信息.基金详情页 import get_fund_detail_page
  resp = get_fund_detail_page(user, "011707")
"""

from typing import Optional

if __name__ == "__main__":
    import sys
    import os

    root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    if root_dir not in sys.path:
        sys.path.insert(0, root_dir)

from src.common.logger import get_logger
from src.common.requests_session import session
from src.common.constant import (
    DEFAULT_GTOKEN,
    DEFAULT_USER,
    IOS_CLIENT_INFO,
    IOS_USER_AGENT,
    IOS_OS_VERSION,
    MOBILE_KEY,
    MP_VERSION_DEFAULT,
    PHONE_TYPE,
    PLATFORM,
    PRODUCT_EFUND,
    SERVER_VERSION,
)
from src.domain.fund.fund_detail import FundDetailResponse

logger = get_logger("FundDetailPage")


# ── 字段列表常量（参考 curl 的 fields 参数） ─────────────────────────────────

_BASEINFO_FIELDS = (
    "BENCH,ESTDIFF,INDEXNAME,LINKZSB,INDEXCODE,NEWTEXCH,FTYPE,FCODE,"
    "BAGTYPE,RISKLEVEL,TTYPENAME,PTDT_FY,PTDT_TRY,PTDT_TWY,PTDT_Y,"
    "DWDT_FY,DWDT_TRY,DWDT_TWY,DWDT_Y,MBDT_FY,MBDT_TRY,MBDT_TWY,MBDT_Y,"
    "YDDT_FY,YDDT_TRY,YDDT_TWY,YDDT_Y,BFUNDTYPE,YMATCHCODEA,"
    "RLEVEL_SZ,RLEVEL_CX,ESTABDATE,JJGS,JJGSID,ENDNAV,FEGMRQ,"
    "SHORTNAME,TTYPE,FUNDEXCHG,LISTTEXCHMARK,FSRQ,ISSBDATE,ISSEDATE,"
    "FEATURE,DWJZ,LJJZ,MINRG,RZDF,PERIODNAME,SYL_1N,SYL_LN,SYL_Z,"
    "SOURCERATE,RATE,TSRQ,BTYPE,BUY,BENCHCODE,BENCH_CORR,TRKERROR,"
    "BENCHRATIO,NEWINDEXTEXCH,BESTDT_STRATEGY,BESTDT_Y,BESTDT_TWY,"
    "BESTDT_TRY,BESTDT_FY,TJDLIST,TJDIN,RSFUNDTYPE,RSBTYPE,MAXSG,"
    "ETFCODE,CYCLE,SHRATE7,SHRATE30,MAXRGINVESTED,DISCOUNT,ISZHDT,"
    "ISABNORMAL_NDATE,ABNORMALDATE"
)

_UNIQUEINFO_FIELDS = (
    "FCODE,STDDEV1,STDDEV_1NRANK,STDDEV_1NFSC,STDDEV3,STDDEV_3NRANK,"
    "STDDEV_3NFSC,STDDEV5,STDDEV_5NRANK,STDDEV_5NFSC,"
    "SHARP1,SHARP_1NRANK,SHARP_1NFSC,SHARP3,SHARP_3NRANK,SHARP_3NFSC,"
    "SHARP5,SHARP_5NRANK,SHARP_5NFSC,"
    "MAXRETRA_SE,MAXRETRA1,MAXRETRA_1NRANK,MAXRETRA_1NFSC,"
    "MAXRETRA3,MAXRETRA_3NRANK,MAXRETRA_3NFSC,"
    "MAXRETRA5,MAXRETRA_5NRANK,MAXRETRA_5NFSC,"
    "TRKERROR1,TRKERROR_1NRANK,TRKERROR_1NFSC,"
    "TRKERROR3,TRKERROR_3NRANK,TRKERROR_3NFSC,"
    "TRKERROR5,TRKERROR_5NRANK,TRKERROR_5NFSC,,"
    "MAXRETRA_SDATE_SE,MAXRETRA_EDATE_SE,JGBL"
)


def get_fund_detail_page(user, fcode: str) -> FundDetailResponse:
    """
    获取基金详情页综合数据。

    一次请求包含基础信息/关联主题/各周期收益/风险指标/持有人结构/
    基金公司/基金经理等维度。

    Args:
        user:  User 对象，提供鉴权上下文。
        fcode: 基金代码（如 "011707"）。

    Returns:
        FundDetailResponse，各字段按 section 结构化。
    """
    url = "https://dgs.tiantianfunds.com/merge/m/api/jjxqy1_2"

    headers = _build_headers()
    data = _build_request_data(user, fcode)

    try:
        response = session.post(url, headers=headers, data=data, verify=False, timeout=30)
        response.raise_for_status()
        raw: dict = response.json()
        result = FundDetailResponse.from_api_response(raw)
        if result.success:
            logger.info(
                f"基金 {fcode} 详情获取成功: "
                f"主题数={len(result.relate_themes)}, "
                f"周期段={len(result.period_increases)}, "
                f"风险指标={'有' if result.risk_metrics else '无'}"
            )
        else:
            logger.error(f"基金 {fcode} 详情获取失败: {result.first_error}")
        return result
    except Exception as e:
        logger.error(f"基金 {fcode} 详情获取异常: {e}")
        return FundDetailResponse(success=False, error_code=-1, first_error=str(e))


# ── 内部构建 ──────────────────────────────────────────────────────────────────


def _build_headers() -> dict:
    """构建请求头。"""
    return {
        "Accept": "*/*",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Host": "dgs.tiantianfunds.com",
        "Referer": (
            "https://mpservice.com/fundb5035dd2ee584a/release/pages/"
            "public-offer-fund/index?fundCode=011707&isSimulation=false"
        ),
        "User-Agent": "okhttp/3.12.13",
        "clientInfo": IOS_CLIENT_INFO,
        "gtoken": DEFAULT_GTOKEN,
        "mp_instance_id": "36",
        "traceparent": "00-0000000046aa4cae00000196718a918a-0000000000000000-01",
        "tracestate": "pid=0x2c131c6,taskid=0x8e65308",
        "validmark": (
            "Li4RtWc+9LvmhgcBNN3qg3dzZjFUt4WiApOOGmkaVZL5BWm0DcGX9"
            "NZYIxjsAsZdVcHJ8J2NdZhXTNMQR9BMpxG3EMlqXyJoFeiMLZWZZtJ1"
            "DXqiIOSu/kLYsAt37vKDxwCpFLoaBa3neQcP+w1EDszlvkKkemR1sBvj"
            "em3Iu98="
        ),
    }


def _build_request_data(user, fcode: str) -> dict:
    """构建 POST 请求体。"""
    return {
        "appVersion": SERVER_VERSION,
        "version": SERVER_VERSION,
        "fcode": fcode,
        "uid": user.customer_no,
        "userid": user.customer_no,
        "utoken": user.u_token,
        "ctoken": user.c_token,
        "passportid": user.passport_id,
        "passportctoken": user.passport_ctoken or user.c_token,
        "passportutoken": user.passport_utoken or user.u_token,
        "deviceid": MOBILE_KEY,
        "plat": PLATFORM,
        "product": PRODUCT_EFUND,
        "serverversion": SERVER_VERSION,
        "ISRG": "0",
        "BusinessTypeList": "1,4",
        "fields": _BASEINFO_FIELDS,
        # 各子 section 字段
        "fundTagFields": "APPID,FEATYPE",
        "fundUniqueInfo_fIELDS": _UNIQUEINFO_FIELDS,
        "fundUniqueInfo_fLFIELDS": "FCODE,BUSINESSTYPE,BUSINESSTEXT,BUSINESSCODE,BUSINESSSUBTYPE,MARK",
        "rateFields": "FIRSTCODE,MINDATE,MAXDATE,ACTYPE",
        "infoFields": "FCODE,ACTYPE,ISRG,AFSTMAX",
        "cfhFundFInfo_fields": "INVESTMENTIDEAR,INVESTMENTIDEARIMG",
        "relateThemeFields": "FCODE,SEC_CODE,SEC_NAME,CORR_1Y,OL2TOP",
        "themeFields": "SEC_CODE,SEC_NAME,RISK_ALL,CHANCE_ALL,ISSHOW,ISSHOWSCORE,CORR_1Y",
        "themeSort": "desc",
        "themeSortFields": "CORR_1Y",
        "indexfields": "_id,INDEXCODE,BKID,INDEXNAME,INDEXVALUA,NEWINDEXTEXCH,PEP100",
        "companyFields": "TOTALSCALE,ESTABDATE",
    }


# ── 直接运行入口（调试） ──────────────────────────────────────────────────────


if __name__ == "__main__":
    from src.API.登录接口.login import ensure_user_fresh
    from src.API.市场指数.基金主题详情 import get_fund_theme_detail

    codes = ["021540"]
    user = ensure_user_fresh(DEFAULT_USER)

    for code in codes:
        print(f"\n{'='*60}")
        print(f"基金代码: {code}")
        print(f"{'='*60}")
        resp = get_fund_detail_page(user, code)
        if not resp.success:
            print(f"  ❌ 请求失败: {resp.first_error}")
            continue

        print(f"  基础信息: {'有' if resp.base_info_raw else '无'}")

        print(f"  ── 关联主题 ──")
        for t in resp.relate_themes:
            chg = None
            td = get_fund_theme_detail(user, t.sec_code)
            if td.success and td.data and td.data.realTimeList:
                chg = td.data.realTimeList[0].CHGRT
            chg_str = f"{chg:.2f}%" if chg is not None else "暂无数据"
            print(f"    {t.sec_name} ({t.sec_code}): 相关性={t.corr_1y}%, 重叠度={t.ol2top}%, 涨幅={chg_str}")

        print(f"  ── 主题风险机会 ──")
        for ti in resp.theme_infos:
            chg = None
            td = get_fund_theme_detail(user, ti.sec_code)
            if td.success and td.data and td.data.realTimeList:
                chg = td.data.realTimeList[0].CHGRT
            chg_str = f"{chg:.2f}%" if chg is not None else "暂无数据"
            print(f"    {ti.sec_name}({ti.sec_code}): 风险={ti.risk_all}, 机会={ti.chance_all}, 涨幅={chg_str}, 展示={ti.isshow}")

        print(f"  ── 各周期收益（含基准对比） ──")
        for p in resp.period_increases:
            title_map = {
                "Z": "近1周", "Y": "近1月", "3Y": "近3月", "6Y": "近6月",
                "1N": "近1年", "2N": "近2年", "3N": "近3年", "5N": "近5年",
                "JN": "今年以来", "LN": "成立以来",
            }
            label = title_map.get(p.title, p.title)
            print(f"    {label}: 基金={p.syl}%, 同类平均={p.avg}%, 沪深300={p.hs300}%, "
                  f"基准={p.benchmark}%, 排名={p.rank}/{p.sc}")

        rm = resp.risk_metrics
        if rm:
            print(f"  ── 风险指标 ──")
            print(f"    夏普比率: 1年={rm.sharp1}, 3年={rm.sharp3}, 5年={rm.sharp5}")
            print(f"    年化标准差: 1年={rm.stddev1}%, 3年={rm.stddev3}%, 5年={rm.stddev5}%")
            print(f"    最大回撤: 1年={rm.maxretra1}%, 3年={rm.maxretra3}%, 5年={rm.maxretra5}%")
            print(f"    最大回撤区间: {rm.maxretra_sdate} ~ {rm.maxretra_edate}")
            print(f"    机构持有比例: {rm.jgbl}%")

        hs = resp.holder_structure
        if hs:
            print(f"  ── 持有人结构 ({hs.fsrq}) ──")
            print(f"    个人={hs.grbl}%, 机构={hs.jgbl}%, 员工持有={hs.employe_hold:.2f}份, "
                  f"总份额={hs.zfe:.2f}, 内部持有={hs.nbbl}%")

        ci = resp.company_info
        if ci:
            print(f"  ── 基金公司 ──")
            print(f"    公司代码={ci.company_code}, 管理规模={ci.total_scale}亿, 成立={ci.estab_date}")

        if resp.current_managers:
            print(f"  ── 现任基金经理 ──")
            for m in resp.current_managers:
                print(f"    {m.mgr_name}({m.mgr_id}): 任职{m.days}天, "
                      f"任职回报={m.penav_growth}%, 从业{m.total_days}天, "
                      f"年均回报={m.yield_se}%")
                if m.investment_idea:
                    print(f"    投资理念: {m.investment_idea[:80]}...")
