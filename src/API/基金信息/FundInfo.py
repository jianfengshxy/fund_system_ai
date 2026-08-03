import json
import time
import random
from datetime import datetime

if __name__ == "__main__":
    import os
    import sys

    root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    if root_dir not in sys.path:
        sys.path.insert(0, root_dir)

from src.common.logger import get_logger
from src.common.errors import RetriableError, ValidationError
from src.common.constant import (
    IOS_CLIENT_INFO,
    DEFAULT_PAGE_INDEX_INT,
    DEFAULT_GTOKEN,
    MOBILE_KEY,
    MP_INSTANCE_ID_FUNDINFO,
    PHONE_TYPE,
    PRODUCT_EFUND,
    SERVER_VERSION,
    TRACEPARENT_FUNDINFO,
    TRACESTATE_FUNDINFO,
    IOS_USER_AGENT,
    VALIDMARK_FUNDINFO,
)

import requests
from typing import Optional
from src.common.requests_session import session
from src.domain.fund.fund_info import FundInfo

# 移除本地Session配置，使用全局共享Session


def _extract_date_part(date_text: Optional[str]) -> Optional[str]:
    """从日期/时间字符串中提取 `YYYY-MM-DD` 日期部分。"""
    if not date_text:
        return None
    candidate = str(date_text).strip()[:10]
    try:
        return datetime.strptime(candidate, "%Y-%m-%d").strftime("%Y-%m-%d")
    except ValueError:
        return None


def _sync_official_nav_fields(target: FundInfo, source: FundInfo) -> None:
    """
    用最新正式净值字段覆盖当前基金对象。

    当日正式净值已经出炉时，基础净值、收益率与交易状态应以正式数据为准，
    不再继续沿用盘中估算值。
    """
    target.nav = source.nav
    target.acc_nav = source.acc_nav
    target.nav_date = source.nav_date
    target.nav_change = source.nav_change
    target.week_return = source.week_return
    target.month_return = source.month_return
    target.three_month_return = source.three_month_return
    target.six_month_return = source.six_month_return
    target.year_return = source.year_return
    target.this_year_return = source.this_year_return
    target.max_purchase = source.max_purchase
    target.can_purchase = source.can_purchase
    target.can_redeem = source.can_redeem
    target.index_code = source.index_code
    target.tracking_error = source.tracking_error
    target.fund_sub_type = source.fund_sub_type


def _estimate_passed_close(estimated_time) -> bool:
    """估值时间是否已在 A 股收盘后 10 分钟（15:10）之外（复用公共判定，避免循环导入）。"""
    from src.service.公共服务.estimated_profit_service import _estimate_time_passed_close
    return _estimate_time_passed_close(estimated_time)


def _apply_estimated_or_official_nav(
    fund_info: FundInfo,
    estimate_payload: dict,
    user=None,
) -> None:
    """
    回填估值信息；若估算日期的正式净值已发布，则优先切回正式净值。

    业务规则：
    1. 盘中尚未出当日净值时，使用估算净值与估算涨跌幅；
    2. 一旦当日正式净值已经发布，则估算净值应等于当日净值，估算涨跌幅归零；
    3. 例外：若估值时间在 A 股收盘后 10 分钟（15:10）之外，视为当日定稿估值
       （如 QDII 海外指数收盘数据），即使与正式净值同日也保留估算涨跌幅作为
       有效增量。
    """
    estimated_value = float(estimate_payload.get('gsz', 0))
    estimated_change = float(estimate_payload.get('gszzl', 0))
    estimated_time = estimate_payload.get('gztime', '')
    estimated_date = _extract_date_part(estimated_time)
    official_nav_date = _extract_date_part(getattr(fund_info, "nav_date", None))

    index_code = getattr(fund_info, "index_code", None)
    is_overseas_index = bool(index_code) and any(ch.isalpha() for ch in str(index_code))

    # QDII 基金跨市场时差，指数估值日期与净值日期天然不同步，
    # 保留指数估算增量，不做"同日=正式净值已发布"的强制归零（与 _refresh_estimate 口径一致）。
    is_qdii = (getattr(fund_info, 'fund_type', '') == 'a'
               or ("QDII" in (getattr(fund_info, 'fund_name', '') or '').upper()))
    if is_qdii:
        fund_info.estimated_time = estimated_time
        return

    if is_overseas_index:
        fund_info.estimated_time = estimated_time
        fund_info.estimated_value = estimated_value
        fund_info.estimated_change = estimated_change
        return

    fund_info.estimated_time = estimated_time
    if estimated_date and official_nav_date == estimated_date and getattr(fund_info, "nav", None) is not None:
        if not _estimate_passed_close(estimated_time):
            fund_info.estimated_value = fund_info.nav
            fund_info.estimated_change = 0.0
        return

    if estimated_date and user is not None:
        latest_fund_info = getFundInfo(user, fund_info.fund_code)
        latest_nav_date = _extract_date_part(getattr(latest_fund_info, "nav_date", None)) if latest_fund_info else None
        if latest_fund_info and latest_nav_date == estimated_date and getattr(latest_fund_info, "nav", None) is not None:
            if not _estimate_passed_close(estimated_time):
                _sync_official_nav_fields(fund_info, latest_fund_info)
                fund_info.estimated_value = latest_fund_info.nav
                fund_info.estimated_change = 0.0
            return

    fund_info.estimated_value = estimated_value
    fund_info.estimated_change = estimated_change

def getFundInfo(user, fund_code) -> Optional[FundInfo]:
    """
    获取单只基金的基础资料与展示字段。

    该函数请求东财基金详情接口，返回项目内统一的 `FundInfo` 对象，
    主要用于后续的估值更新、收益率计算、止盈/加仓策略判断等场景。

    Args:
        user: 已完成登录和 passport 鉴权的用户对象，需包含 token、passport 等上下文。
        fund_code: 目标基金代码，例如 `021740`。

    Returns:
        `FundInfo`: 成功时返回基金对象；
        失败时抛出 `RetriableError` 或 `ValidationError`。
    """
    url = 'https://fundcomapi.tiantianfunds.com/mm/FundFavor/FundFavorInfo'
    
    headers = {
        'Accept': '*/*',
        'Accept-Encoding': 'gzip, deflate, br',
        'Connection': 'keep-alive',
        'Host': 'fundcomapi.tiantianfunds.com',
        # 移除包含中文的 Referer 头，这是导致编码错误的主要原因
        'User-Agent': IOS_USER_AGENT,
        'clientInfo': IOS_CLIENT_INFO,
        'forceLog': '1',
        'gtoken': DEFAULT_GTOKEN,
        'mp_instance_id': MP_INSTANCE_ID_FUNDINFO,
        'traceparent': TRACEPARENT_FUNDINFO,
        'tracestate': TRACESTATE_FUNDINFO,
        'Content-Type': 'application/x-www-form-urlencoded',
        'validmark': VALIDMARK_FUNDINFO,
    }
    
    # Referer 统一使用纯 ASCII，避免历史上出现过的中文编码兼容问题。
    referer = 'https://mpservice.com/770ddc37537896dae8ecd8160cb25336/release/pages/fundList/all-list/index'
    headers['Referer'] = referer
    
    data = {
        'FIELDS': 'MAXSG,FCODE,SHORTNAME,PDATE,NAV,ACCNAV,NAVCHGRT,NAVCHGRT100,GSZ,GSZZL,GZTIME,NEWPRICE,CHANGERATIO,ZJL,HQDATE,ISREDBAGS,SYL_Z,SYL_Y,SYL_3Y,SYL_6Y,SYL_JN,SYL_1N,SYL_2N,SYL_3N,SYL_5N,SYL_LN,RSBTYPE,RSFUNDTYPE,INDEXCODE,NEWINDEXTEXCH,TRKERROR1,ISBUY',
        'product': PRODUCT_EFUND,
        'APPID': 'FAVOR,FAVOR_ED,FAVOR_GS',
        'pageSize': 200,
        'passportctoken': user.passport_ctoken,
        'SortColumn': '',
        'passportutoken': user.passport_utoken,
        'deviceid': MOBILE_KEY,
        'userid': user.customer_no,
        'version': SERVER_VERSION,
        'ctoken': user.c_token,
        'uid': user.customer_no,
        'CODES': fund_code,
        'pageIndex': DEFAULT_PAGE_INDEX_INT,
        'utoken': user.u_token,
        'Sort': '',
        'plat': PHONE_TYPE,
        'passportid': user.passport_id
    }
    
    logger = get_logger("FundInfo")
    extra = {"account": getattr(user, 'mobile_phone', None) or getattr(user, 'account', None), "action": "get_fund_info", "fund_code": fund_code}
    try:
        # 共享 session 可复用连接，同时保持项目内统一的请求配置。
        response = session.post(
            url,
            data=data,
            headers=headers,
            verify=False,
            timeout=30
        )
        
        response.raise_for_status()

        # 接口偶发返回内容中带有非标准字符，显式按 UTF-8 解码更稳妥。
        response_text = response.content.decode('utf-8')
        
        try:
            json_data = json.loads(response_text)
        except json.JSONDecodeError as e:
            logger.error("JSON解析失败: %s, 响应内容: %s", str(e), response_text[:200], extra=extra)
            raise ValidationError(str(e))
            
        logger.debug("响应数据: %s", json.dumps(json_data, ensure_ascii=False))
        
        if not json_data.get('success', False):
            error_msg = json_data.get('firstError', '未知错误')
            logger.error("获取基金信息失败: %s", error_msg, extra=extra)
            raise ValidationError(error_msg)
            
        fund_data = json_data.get('data', [])
        if not fund_data:
            logger.error("未找到基金信息", extra=extra)
            raise ValidationError("DATA_EMPTY")
            
        try:
            fund_info_data = fund_data[0]
            fund_info = FundInfo.from_dict(fund_info_data)
            return fund_info
        except (IndexError, KeyError, TypeError) as e:
            logger.error("解析基金数据失败: %s", str(e), extra=extra)
            raise ValidationError(str(e))
            
    except requests.exceptions.RequestException as e:
        logger.error('请求失败: %s', str(e), extra=extra)
        raise RetriableError(str(e))
    except Exception as e:
        logger.error('处理过程发生异常: %s', str(e), extra=extra)
        import traceback
        logger.error('异常堆栈: %s', traceback.format_exc(), extra=extra)
        raise ValidationError(str(e))

def updateFundEstimatedValue(fund_info: FundInfo, user=None) -> Optional[FundInfo]:
    """
    获取并更新基金实时估值信息。

    内部调用 FundValuationLast 接口（由 基金估值信息.py 提供），
    将最新估算净值、估算涨跌幅、估值时间回填到传入的 `FundInfo` 对象。
    同时会基于最新估算涨跌，联动修正近一周、近一月、近三月、近六月、
    近一年和今年以来等区间收益字段，便于策略层直接消费。

    注意：旧的 fundgz.1234567.com.cn 接口已废弃（返回 404），
    现统一走 fundcomapi.tiantianfunds.com 的 FundValuationLast 接口。

    Args:
        fund_info: 已包含基础净值和收益字段的基金对象。
        user: 可选用户对象。传入时会在需要时主动刷新基金基础信息，
            用于判断估算日期对应的正式净值是否已经发布。

    Returns:
        `FundInfo`: 更新成功时返回原对象；
        连续重试失败时返回 `None`。
    """
    logger = get_logger("FundInfo")
    max_retries = 3
    retry_count = 0
    retry_delay = 2

    while retry_count < max_retries:
        try:
            if retry_count > 0:
                logger.debug(f"正在进行第 {retry_count} 次重试获取基金估值数据，基金代码: {fund_info.fund_code}")
                time.sleep(retry_delay)
                retry_delay *= 2

            # 调用 FundValuationLast 接口
            from src.API.基金信息.基金估值信息 import update_fund_estimated_value
            from src.common.constant import DEFAULT_USER
            local_user = user or DEFAULT_USER
            update_fund_estimated_value(local_user, fund_info)

            index_code = getattr(fund_info, 'index_code', None)
            if index_code:
                try:
                    from datetime import datetime
                    from src.common.third_party_index import is_third_party_index, fetch_valuation
                    if is_third_party_index(index_code):
                        tv = fetch_valuation(index_code)
                        if tv.success and tv.change_pct is not None:
                            chg = float(tv.change_pct)
                            nav = fund_info.nav or 0.0
                            fund_info.estimated_change = chg
                            fund_info.estimated_value = round(nav * (1 + chg / 100), 4) if nav > 0 else None
                            if tv.update_time:
                                s = str(tv.update_time).strip()
                                if len(s) >= 19 and ":" in s[11:]:
                                    fund_info.estimated_time = s[:19]
                                else:
                                    fund_info.estimated_time = f"{s[:10]} {datetime.now().strftime('%H:%M:%S')}"
                            else:
                                fund_info.estimated_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                            logger.info(
                                f"基金{fund_info.fund_code}第三方指数估值: "
                                f"[{tv.source}]({index_code}) "
                                f"涨幅={chg}%, 净值={fund_info.estimated_value}, 时间={fund_info.estimated_time}"
                            )
                except Exception as e:
                    logger.warning(f"第三方指数估值查询失败({index_code}): {e}")

            # ── 指数型（type=000）：用跟踪指数的实际涨跌幅替代重仓股估算 ──
            #   type=000 包括 A 股指数基金和 QDII。对于此类基金，FundValuationLast
            #   返回的是重仓股估算（可能不准），而指数详情返回的是指数真实涨跌幅。
            is_index_fund = getattr(fund_info, 'fund_type', '') == '000'
            if is_index_fund:
                if index_code:
                    # 裸接口 update_fund_estimated_value 已回填有效估值（如第三方回退）时跳过，避免重复请求
                    already_estimated = (getattr(fund_info, 'estimated_change', None) or 0) != 0
                    index_chg = None
                    index_date = ""
                    index_name = index_code

                    if not already_estimated:
                        try:
                            from src.API.市场指数.指数详情 import get_index_detail
                            detail = get_index_detail(local_user, index_code)
                            index_chg = detail.get('NEWCHG')
                            index_date = detail.get('NEWPRICEDATE') or detail.get('PDATE', '')
                            index_name = detail.get('BKNAME') or detail.get('INDEXNAME', index_code) or index_code
                            if index_chg is not None:
                                index_chg = float(index_chg)
                        except Exception as e:
                            logger.warning(f"指数估值查询失败({index_code}): {e}")

                    if index_chg is not None:
                        chg = float(index_chg)
                        nav = fund_info.nav or 0.0
                        from datetime import datetime
                        now_time = datetime.now().strftime("%H:%M:%S")
                        if index_date:
                            index_date_str = str(index_date).strip()
                            if len(index_date_str) >= 19 and ":" in index_date_str[11:]:
                                index_date = index_date_str[:19]
                            else:
                                index_date = f"{index_date_str[:10]} {now_time}"
                        else:
                            index_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        fund_info.estimated_change = chg
                        fund_info.estimated_value = round(nav * (1 + chg / 100), 4) if nav > 0 else None
                        fund_info.estimated_time = index_date
                        logger.info(
                            f"基金{fund_info.fund_code}指数估值: "
                            f"[{index_name}]({index_code}) "
                            f"涨幅={chg}%, 净值={fund_info.estimated_value}, 日期={index_date}"
                        )

            # 将获取后的估值数据注入收益率基线修正逻辑
            _apply_estimated_or_official_nav(
                fund_info,
                {
                    "gsz": fund_info.estimated_value,
                    "gszzl": fund_info.estimated_change,
                    "gztime": fund_info.estimated_time,
                    "fundcode": fund_info.fund_code,
                },
                user=local_user,
            )

            # 当基础净值日期变化时，刷新一次收益率基线，避免重复叠加估算值
            baseline_nav_date = getattr(fund_info, "_baseline_nav_date", None)
            if baseline_nav_date != getattr(fund_info, "nav_date", None):
                fund_info._baseline_nav_date = getattr(fund_info, "nav_date", None)
                fund_info._baseline_week_return = fund_info.week_return
                fund_info._baseline_month_return = fund_info.month_return
                fund_info._baseline_three_month_return = fund_info.three_month_return
                fund_info._baseline_six_month_return = fund_info.six_month_return
                fund_info._baseline_year_return = fund_info.year_return
                fund_info._baseline_this_year_return = fund_info.this_year_return

            # 在静态收益率基线之上叠加实时估算涨跌
            est = fund_info.estimated_change or 0.0
            base_week = getattr(fund_info, "_baseline_week_return", None)
            base_month = getattr(fund_info, "_baseline_month_return", None)
            base_three = getattr(fund_info, "_baseline_three_month_return", None)
            base_six = getattr(fund_info, "_baseline_six_month_return", None)
            base_year = getattr(fund_info, "_baseline_year_return", None)
            base_this_year = getattr(fund_info, "_baseline_this_year_return", None)

            if base_week is not None:
                fund_info.week_return = base_week + est
            if base_month is not None:
                fund_info.month_return = base_month + est
            if base_three is not None:
                fund_info.three_month_return = base_three + est
            if base_six is not None:
                fund_info.six_month_return = base_six + est
            if base_year is not None:
                fund_info.year_return = base_year + est
            if base_this_year is not None:
                fund_info.this_year_return = base_this_year + est

            if retry_count > 0:
                logger.debug(f"重试成功，已获取基金 {fund_info.fund_code} 的估值数据")
            return fund_info

        except Exception as e:
            logger.error(f"获取估值数据失败: {str(e)}")
            retry_count += 1
            if retry_count >= max_retries:
                logger.error(f"基金 {fund_info.fund_code} 估值数据获取失败，已重试 {max_retries} 次")
                return None
            continue

    return None



if __name__ == "__main__":
    import logging
    from src.common.constant import DEFAULT_USER, FUND_CODE
    from src.API.基金信息.FundRank import get_fund_growth_rate, get_fund_volatility, get_nav_rank
    
    logger = get_logger("FundInfo")
    
    # 配置日志
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    try:
        # 直接运行本文件时，使用默认用户与默认基金代码做一次只读调试调用。
        fund_info = getFundInfo(DEFAULT_USER, "024726")
        
        if fund_info:
            print(f"基础信息获取成功: {fund_info.fund_name}")
            
            # 在基础信息上继续拉取实时估值，观察字段是否正确回填。
            print("正在获取实时估值...")
            updateFundEstimatedValue(fund_info, DEFAULT_USER)

            # 指数型基金：打印跟踪指数行情
            if getattr(fund_info, 'fund_type', '') == '000':
                index_code = getattr(fund_info, 'index_code', None)
                if index_code:
                    try:
                        from src.API.市场指数.指数详情 import get_index_detail
                        from src.API.市场指数.证券日线K线行情数据 import get_security_day_kline, guess_secid_from_code
                        detail = get_index_detail(DEFAULT_USER, index_code)
                        iname = detail.get('BKNAME') or detail.get('INDEXNAME', index_code)
                        ichg = detail.get('NEWCHG', '?')
                        iprice = detail.get('NEWPRICE', '?')
                        idate = detail.get('NEWPRICEDATE') or detail.get('PDATE', '?')
                        # 查K线拿开盘价
                        secid = guess_secid_from_code(index_code)
                        open_price = '?'
                        if secid:
                            kl = get_security_day_kline(DEFAULT_USER, secid=secid, lmt=1)
                            if kl.success and kl.data and kl.data.items:
                                open_price = kl.data.items[-1].OPEN
                        print("\n── 跟踪指数行情 ──")
                        print(f"  指数: {iname}({index_code})")
                        print(f"  日期: {idate}")
                        print(f"  开盘: {open_price}")
                        print(f"  收盘: {iprice}")
                        print(f"  涨幅: {ichg}%")
                    except Exception as e:
                        print(f"  (查询指数行情失败: {e})")

            print("正在获取历史净值衍生指标...")
            nav_rank_30 = get_nav_rank(DEFAULT_USER, fund_info, 30, fund_info.estimated_value or fund_info.nav)
            mean_30, variance_30, volatility_30 = get_fund_volatility(DEFAULT_USER, fund_info, 30)
            nav_rank_100 = get_nav_rank(DEFAULT_USER, fund_info, 100, fund_info.estimated_value or fund_info.nav)
            mean_100, variance_100, volatility_100 = get_fund_volatility(DEFAULT_USER, fund_info, 100)
            growth_week, rank_week, total_week = get_fund_growth_rate(fund_info, "Z")
            growth_month, rank_month, total_month = get_fund_growth_rate(fund_info, "Y")
            growth_three_month, rank_three_month, total_three_month = get_fund_growth_rate(fund_info, "3Y")
            
            print("\n最终基金信息:")
            print(f"基金代码: {fund_info.fund_code}")
            print(f"基金名称: {fund_info.fund_name}")
            print(f"基金类型: {fund_info.fund_type}")
            print(f"当前净值: {fund_info.nav}")
            print(f"净值日期: {fund_info.nav_date}")
            print(f"日涨跌幅: {fund_info.nav_change}%")
            print(f"估算时间: {fund_info.estimated_time}")
            print(f"估算净值: {fund_info.estimated_value or '暂无'}")
            print(f"估算涨跌: {fund_info.estimated_change or '暂无'}%")
            print(f"近一周收益: {fund_info.week_return or '暂无'}%")
            print(f"近一月收益: {fund_info.month_return or '暂无'}%")
            print(f"近三月收益: {fund_info.three_month_return or '暂无'}%")
            print(f"今年收益: {fund_info.this_year_return or '暂无'}%")
            print(f"是否可购买: {'是' if fund_info.can_purchase else '否'}")

            print("\n历史净值衍生指标:")
            print(f"近30日净值排名: {nav_rank_30}  (数值越小表示当前净值在样本中越低)")
            print(f"近30日平均净值: {mean_30:.6f}")
            print(f"近30日净值方差: {variance_30:.8f}")
            print(f"近30日净值波动率: {volatility_30:.8f}")
            print(f"近100日净值排名: {nav_rank_100}  (数值越小表示当前净值在样本中越低)")
            print(f"近100日平均净值: {mean_100:.6f}")
            print(f"近100日净值方差: {variance_100:.8f}")
            print(f"近100日净值波动率: {volatility_100:.8f}")

            print("\n区间增长率与同类排名:")
            print(f"近一周(Z): 增长率={growth_week:.2f}%, 排名={rank_week}/{total_week}")
            print(f"近一月(Y): 增长率={growth_month:.2f}%, 排名={rank_month}/{total_month}")
            print(f"近三月(3Y): 增长率={growth_three_month:.2f}%, 排名={rank_three_month}/{total_three_month}")
        else:
            print("\n获取基金信息失败")
            
    except Exception as e:
        print(f"\n程序执行出错: {str(e)}")
