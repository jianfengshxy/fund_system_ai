import logging
import sys
import os
from typing import Dict, List, Optional

# 获取项目根目录路径
root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# 如果项目根目录不在Python路径中，则添加
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from src.common.logger import get_logger
from src.common.constant import DEFAULT_USER
from src.API.基金信息.FundInfo import getFundInfo
from src.API.基金信息.FundRank import get_nav_rank, get_fund_volatility as get_fund_volatility_api
from src.API.基金信息.基金详情页 import get_fund_detail_page
from src.API.市场指数.获取市场指数 import get_market_index
from src.domain.fund.fund_info import FundInfo
from src.domain.fund.fund_detail import (
    FundDetailResponse,
    FundRelateTheme,
    FundRiskMetrics,
    FundHolderStructure,
    FundCompanyInfo,
    FundManagerBrief,
    FundPeriodIncrease,
)
from src.domain.user.User import User

logger = get_logger(__name__)


def _estimate_by_theme(fund_info: FundInfo, user: User) -> None:
    """
    通过基金详情页的关联主题，查询对应主题指数的涨跌幅作为估算涨跌幅。

    策略：
    1. 从 theme_infos 筛选展示（isshow=True）的主题，取第一个
    2. 若无可展示主题，退而使用 relate_themes，按 1 年相关性（CORR_1Y）降序取最高
    3. 将主题的 sec_code 作为查询条件，获取对应指数涨跌幅（NEWCHG）
    4. 估算净值 = 上一个交易日净值 × (1 + 涨跌幅/100)

    若找不到任何主题，则估算涨跌幅 = 0，估算净值 = 昨日净值。
    """
    # 优先从 theme_infos 筛选 isshow=True 的主题
    sec_code = None
    theme_name = None
    show_themes = [ti for ti in fund_info.theme_infos if ti.isshow]
    if show_themes:
        sec_code = show_themes[0].sec_code
        theme_name = show_themes[0].sec_name
        logger.debug(
            f"{fund_info.fund_name} 选取展示主题[{theme_name}]({sec_code})"
        )

    # 退而使用 relate_themes 按相关性降序
    if not sec_code and fund_info.relate_themes:
        theme = max(fund_info.relate_themes, key=lambda t: t.corr_1y)
        sec_code = theme.sec_code
        theme_name = theme.sec_name
        logger.debug(
            f"{fund_info.fund_name} 选取关联主题[{theme_name}]({sec_code}), "
            f"相关性={theme.corr_1y}%"
        )

    if not sec_code:
        logger.debug(f"{fund_info.fund_name} 无关联主题数据，估算涨跌幅默认为 0%")
        _set_estimate_zero(fund_info)
        return

    chg: Optional[float] = None
    date_str: Optional[str] = None
    if str(sec_code).upper().startswith("BK"):
        from src.API.市场指数.基金主题详情 import get_fund_theme_detail
        td = get_fund_theme_detail(user, sec_code)
        if td.success and td.data and td.data.realTimeList:
            rt = td.data.realTimeList[0]
            chg = rt.CHGRT
            date_str = rt.DEALTIME or rt.SCOREDATE
    else:
        resp = get_market_index(user, sec_code=sec_code, page_size=1, sort_name="NEWCHG")
        if resp.success and resp.items:
            it = resp.items[0]
            chg = float(it.NEWCHG)
            date_str = getattr(it, "DATE", None) or getattr(it, "PDATE", None) or getattr(it, "D", None)

    if chg is None:
        logger.debug(f"{fund_info.fund_name} 主题[{theme_name}]涨跌幅查询无结果，默认为 0%")
        _set_estimate_zero(fund_info)
        return

    nav = fund_info.nav or 0.0
    estimated_value = round(nav * (1 + chg / 100), 4) if nav > 0 else None

    fund_info.estimated_change = chg
    fund_info.estimated_value = estimated_value
    fund_info.estimated_time = str(date_str) if date_str else None
    logger.info(
        f"{fund_info.fund_name} 主题估值: [{theme_name}]({sec_code}), "
        f"板块涨跌幅={chg}%"
    )


def _set_estimate_zero(fund_info: FundInfo) -> None:
    """估算涨跌幅=0，估算净值=当日净值。"""
    fund_info.estimated_change = 0.0
    fund_info.estimated_value = fund_info.nav or 0.0
    fund_info.estimated_time = None


def _merge_fund_detail(fund_info: FundInfo, user: User) -> Optional[FundDetailResponse]:
    """
    获取基金详情页数据并合并到 FundInfo 对象中。

    注入的字段：
      relate_themes / theme_infos / period_increases / risk_metrics /
      holder_structure / company_info / current_managers
    """
    try:
        detail = get_fund_detail_page(user, fund_info.fund_code)
        if not detail.success:
            return None
        fund_info.relate_themes = detail.relate_themes
        fund_info.theme_infos = detail.theme_infos
        fund_info.period_increases = detail.period_increases
        fund_info.risk_metrics = detail.risk_metrics
        fund_info.holder_structure = detail.holder_structure
        fund_info.company_info = detail.company_info
        fund_info.current_managers = detail.current_managers
        return detail
    except Exception as e:
        logger.warning(f"{fund_info.fund_name} 合并详情页数据异常: {e}")
        return None

def _refresh_estimate(fund_info: FundInfo, user: User) -> None:
    """
    统一估值入口。

    优先级：
    1. type=000（指数型）：若有 index_code，用指数详情 NEWCHG（对齐天天基金指数涨幅）
    2. QDII（type='a' 或含 "QDII"）：若有 index_code，用指数详情 NEWCHG；否则 0.0
    3. 其他所有基金（混合/股票等）：用关联主题板块的实时涨跌幅（BK 代码 → fundThemeDetail）
    """
    fund_type = getattr(fund_info, 'fund_type', '')
    is_qdii = fund_type == 'a' or ("QDII" in (fund_info.fund_name or '').upper())
    index_code = getattr(fund_info, 'index_code', None)

    if index_code:
        try:
            from datetime import datetime
            from src.common.third_party_index import is_third_party_index, fetch_valuation
            if is_third_party_index(index_code):
                existing_chg = getattr(fund_info, "estimated_change", None)
                if existing_chg is not None and existing_chg != 0.0:
                    return
                tv = fetch_valuation(index_code)
                if tv.success and tv.change_pct is not None:
                    nav = fund_info.nav or 0.0
                    fund_info.estimated_change = float(tv.change_pct)
                    fund_info.estimated_value = round(nav * (1 + float(tv.change_pct) / 100), 4) if nav > 0 else None
                    if tv.update_time:
                        s = str(tv.update_time).strip()
                        if len(s) >= 19 and ":" in s[11:]:
                            fund_info.estimated_time = s[:19]
                        else:
                            fund_info.estimated_time = f"{s[:10]} {datetime.now().strftime('%H:%M:%S')}"
                    else:
                        fund_info.estimated_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    fund_info._baseline_nav_date = getattr(fund_info, "nav_date", None)
                    logger.info(
                        f"{fund_info.fund_name} 第三方估值: "
                        f"[{tv.source}]({index_code}) 涨幅={fund_info.estimated_change}%, 净值={fund_info.estimated_value}"
                    )
                    return
        except Exception as e:
            logger.warning(f"{fund_info.fund_name} 第三方估值查询失败({index_code}): {e}")

    # ── type=000 指数型 / QDII：优先用跟踪指数涨跌幅 ──
    if (fund_type == '000' or is_qdii) and index_code:
        # 如果 FundValuationLast 已返回有效估值，保留 API 结果，不做指数覆盖
        existing_chg = getattr(fund_info, "estimated_change", None)
        if existing_chg is not None and existing_chg != 0.0:
            logger.debug(
                f"{fund_info.fund_name} 已有 API 估值({existing_chg}%)，跳过指数覆盖"
            )
            return

        chg_val = None
        index_date = None
        index_name = index_code

        # 天天基金指数详情
        try:
            from src.API.市场指数.指数详情 import get_index_detail
            from datetime import datetime
            detail = get_index_detail(user, index_code)
            index_name = detail.get('BKNAME') or detail.get('INDEXNAME', index_code) or index_code
            index_date = detail.get('NEWPRICEDATE') or detail.get('PDATE', '')

            # 优先 NEWCHG，若无则尝试 D 字段（黄金 AU9999 等特殊指数用 D 表示日涨跌）
            chg = detail.get('NEWCHG')
            if chg is None:
                chg = detail.get('D')
            if chg is not None:
                chg_val = float(chg)
                now_time = datetime.now().strftime("%H:%M:%S")
                if index_date:
                    index_date_str = str(index_date).strip()
                    if len(index_date_str) >= 19 and ":" in index_date_str[11:]:
                        index_date = index_date_str[:19]
                    else:
                        index_date = f"{index_date_str[:10]} {now_time}"
                else:
                    index_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        except Exception as e:
            logger.warning(f"{fund_info.fund_name} 指数详情查询失败({index_code}): {e}")

        if chg_val is not None:
            nav = fund_info.nav or 0.0
            fund_info.estimated_change = chg_val
            fund_info.estimated_value = round(nav * (1 + chg_val / 100), 4) if nav > 0 else None
            fund_info.estimated_time = index_date
            fund_info._baseline_nav_date = getattr(fund_info, "nav_date", None)
            # QDII 基金有跨市场时差，指数日期与净值日期天然不同步，不做清零判断
            if not is_qdii:
                _clear_if_nav_matches_estimated(fund_info)
            tag = "QDII" if is_qdii else "指数"
            logger.info(
                f"{fund_info.fund_name} ({tag}) 指数估值: "
                f"[{index_name}]({index_code}) 涨幅={chg_val}%, 净值={fund_info.estimated_value}"
            )
            return

        # 回退：无数据则归零
        if fund_type == '000':
            # 非 QDII 的 type=000 指数型基金，指数查不到时归零
            fund_info.estimated_change = 0.0
            fund_info.estimated_value = fund_info.nav or 0.0
            fund_info.estimated_time = None
            fund_info._baseline_nav_date = getattr(fund_info, "nav_date", None)
            logger.debug(f"{fund_info.fund_name} 指数无数据，默认涨跌幅 0%")
            return
        if is_qdii:
            fund_info.estimated_change = 0.0
            fund_info.estimated_value = fund_info.nav or 0.0
            fund_info.estimated_time = None
            fund_info._baseline_nav_date = getattr(fund_info, "nav_date", None)
            logger.debug(f"{fund_info.fund_name} (QDII) 无指数代码，默认涨跌幅 0.0%")
            return

    # QDII 无 index_code → 归零
    if is_qdii:
        fund_info.estimated_change = 0.0
        fund_info.estimated_value = fund_info.nav or 0.0
        fund_info.estimated_time = None
        fund_info._baseline_nav_date = getattr(fund_info, "nav_date", None)
        logger.debug(f"{fund_info.fund_name} (QDII) 无指数代码，默认涨跌幅 0.0%")
        return

    # ── 其他基金（混合/股票等）：用关联主题板块涨跌幅 ──
    _estimate_by_theme(fund_info, user)

    # ── 后处理：若净值日期已是今天（自然日），说明当日净值已发布，估算值清零 ──
    _clear_if_nav_matches_estimated(fund_info)


def _clear_if_nav_matches_estimated(fund_info: FundInfo) -> None:
    """若净值日期已是今天（自然日），说明当日净值已发布，估算值清零。"""
    if fund_info.nav_date and fund_info.nav is not None:
        from datetime import datetime
        today = datetime.now().strftime("%Y-%m-%d")
        nav_date_str = fund_info.nav_date[:10]
        if nav_date_str == today:
            fund_info.estimated_change = 0.0
            fund_info.estimated_value = fund_info.nav
            fund_info.estimated_time = None
            logger.debug(
                f"{fund_info.fund_name} 净值日期[{nav_date_str}]已是当日，估算值清零"
            )


def get_all_fund_info(user: User, fund_code: str) -> Optional[FundInfo]:
    """
    获取基金的完整信息，包括基础信息、估值信息、排名信息和波动率
    """
    logger.debug(f"开始获取基金 {fund_code} 的完整信息")
    
    # 第1步：获取基金基础信息
    fund_info = getFundInfo(user, fund_code)
    if not fund_info:
        logger.error(f"获取基金基础信息失败: {fund_code}")
        return None
    
    logger.debug(
        f"{fund_info.fund_name}成功获取基金基础信息: {fund_info.fund_name}({fund_code})，"
        f"类型={getattr(fund_info, 'fund_type', '')}，子类型={getattr(fund_info, 'fund_sub_type', '')}"
    )

    # 第1.5步：获取基金详情页综合数据（关联主题/风险指标/持有人结构等）
    _merge_fund_detail(fund_info, user)
    
    # 第2步：获取基金估值信息
    try:
        _refresh_estimate(fund_info, user)
    except Exception as e:
        logger.error(f"{fund_info.fund_name}获取基金估值信息时发生异常: {str(e)}")
    
    # 第3步：获取基金30日排名信息
    try:
        rank_30 = get_nav_rank(user, fund_info, 30)
        if rank_30 is not None:
            fund_info.rank_30day = rank_30
            logger.debug(f"{fund_info.fund_name}成功获取基金30日排名信息: {rank_30}")
        else:
            logger.warning(f"{fund_info.fund_name}获取基金30日排名信息失败: {fund_code}")
    except Exception as e:
        logger.error(f"{fund_info.fund_name}获取基金30日排名信息时发生异常: {str(e)}")
    
    # 第4步：获取基金100日排名信息
    try:
        rank_100 = get_nav_rank(user, fund_info, 100)
        if rank_100 is not None:
            fund_info.rank_100day = rank_100
            logger.debug(f"{fund_info.fund_name}成功获取基金100日排名信息: {rank_100}")
        else:
            logger.warning(f"{fund_info.fund_name}获取基金100日排名信息失败: {fund_code}")
    except Exception as e:
        logger.error(f"{fund_info.fund_name}获取基金100日排名信息时发生异常: {str(e)}")
    
    # 第5步：获取基金30日波动率信息
    try:
        volatility_result = get_fund_volatility_api(user, fund_info, 30)
        if volatility_result is not None:
            _, _, volatility = volatility_result
            fund_info.volatility = volatility * 100
            logger.debug(f"{fund_info.fund_name}成功获取基金30日波动率信息: {volatility}")
        else:
            logger.warning(f"{fund_info.fund_name}获取基金30日波动率信息失败: {fund_code}")
    except Exception as e:
        logger.error(f"{fund_info.fund_name}获取基金30日波动率信息时发生异常: {str(e)}")
    
    # 新增：第5.1步 获取近5日平均净值（用于与当日估值净值比较）
    try:
        nav5_result = get_fund_volatility_api(user, fund_info, 5)
        if nav5_result is not None:
            mean_5d, _, _ = nav5_result
            fund_info.nav_5day_avg = mean_5d
            logger.debug(f"{fund_info.fund_name}成功获取近5日平均净值: {mean_5d}")
        else:
            logger.warning(f"{fund_info.fund_name}获取近5日平均净值失败: {fund_code}")
    except Exception as e:
        logger.error(f"{fund_info.fund_name}获取近5日平均净值时发生异常: {str(e)}")
    
    # 打印基金跟踪的指数信息
    if hasattr(fund_info, 'index_code') and fund_info.index_code:
        logger.debug(f"{fund_info.fund_name}跟踪指数代码: {fund_info.index_code}")
    else:
        logger.debug(f"{fund_info.fund_name}未跟踪任何指数或指数代码为空")
    
    # 返回基金信息对象
    return fund_info

if __name__ == '__main__':
    fund_info = get_all_fund_info(DEFAULT_USER, '009975')
    print(fund_info)
    pass
