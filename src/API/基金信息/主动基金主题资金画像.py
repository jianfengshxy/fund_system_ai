"""
主动基金主题资金画像接口。

目标：
1. 针对没有直接指数代码的主动型基金，先通过基金详情页拿到关联主题；
2. 再拉取主题的当前资金热度、净流入和最近一段价格/热度序列；
3. 明确标记“是否支持主题级逐日净流入历史”。

当前结论：
- 对 BK 主题代码，可以通过 `基金主题详情` 获取当前资金热度、当日/周/月/季净流入。
- 可以通过 `指数资金热度与价格走势` 获取近一段价格序列。
- 但 BK 主题无法通过东财 `fflow/daykline/get` 取得逐日净流入历史，实测返回 rc=100。
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Optional, Any
import os
import sys

if __name__ == "__main__":
    root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    if root_dir not in sys.path:
        sys.path.insert(0, root_dir)

from src.common.logger import get_logger
from src.domain.user.User import User
from src.API.基金信息.基金详情页 import get_fund_detail_page
from src.API.市场指数.基金主题详情 import get_fund_theme_detail
from src.API.市场指数.指数资金热度与价格走势 import get_index_price_flow
from src.API.市场指数.证券日线K线行情数据 import (
    get_security_day_flow_kline,
    get_security_today_flow_kline,
    guess_secid_from_code,
)

logger = get_logger("ActiveFundThemeFlowProfile")


@dataclass
class ThemeCandidate:
    sec_code: str
    sec_name: str
    corr_1y: float = 0.0
    ol2top: float = 0.0
    chance_all: Optional[float] = None
    risk_all: Optional[float] = None
    isshow: Optional[bool] = None


@dataclass
class ThemeFlowSnapshot:
    sec_code: str = ""
    sec_name: str = ""
    chgrt: Optional[float] = None
    chance_all: Optional[float] = None
    chance_zjrd: Optional[float] = None
    chance_jqd: Optional[float] = None
    flow: Optional[float] = None
    flow_w: Optional[float] = None
    flow_m: Optional[float] = None
    flow_q: Optional[float] = None
    sumflow_w: Optional[float] = None
    sumflow_m: Optional[float] = None
    sumflow_q: Optional[float] = None
    rm_netflowxl: Optional[float] = None
    rm_netflowxl_pct: Optional[float] = None
    fct_xlflow: Optional[float] = None
    inflowdays: Optional[int] = None
    outflowdays: Optional[int] = None


@dataclass
class ThemeHeatPoint:
    date: str
    price: Optional[float] = None
    chg_pct: Optional[float] = None
    heat_score: Optional[float] = None


@dataclass
class ThemeDailyFlowAvailability:
    supported: bool = False
    secid: str = ""
    day_flow_error: Optional[str] = None
    today_flow_error: Optional[str] = None
    day_flow_samples: list[dict[str, Any]] = field(default_factory=list)
    today_flow_samples: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class ActiveFundThemeFlowProfile:
    success: bool
    fund_code: str
    selected_theme: Optional[ThemeCandidate] = None
    candidates: list[ThemeCandidate] = field(default_factory=list)
    snapshot: Optional[ThemeFlowSnapshot] = None
    recent_heat_series: list[ThemeHeatPoint] = field(default_factory=list)
    daily_flow_availability: ThemeDailyFlowAvailability = field(default_factory=ThemeDailyFlowAvailability)
    notes: list[str] = field(default_factory=list)
    first_error: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def analyze_active_fund_theme_flow(
    user: User,
    fund_code: str,
    top_n: int = 5,
    range_type: str = "y",
    heat_tail_size: int = 10,
) -> ActiveFundThemeFlowProfile:
    """
    给主动基金生成主题资金画像。

    Args:
        user: 用户鉴权上下文
        fund_code: 基金代码，例如 "011707"
        top_n: 输出前 N 个关联主题
        range_type: 热度序列范围，默认近 1 月
        heat_tail_size: 仅保留热度序列最后 N 条
    """
    fund_resp = get_fund_detail_page(user, fund_code)
    if not fund_resp.success:
        return ActiveFundThemeFlowProfile(
            success=False,
            fund_code=fund_code,
            first_error=fund_resp.first_error,
        )

    theme_info_map = {item.sec_code: item for item in fund_resp.theme_infos}
    candidates: list[ThemeCandidate] = []
    for item in fund_resp.relate_themes[:max(top_n, 1)]:
        info = theme_info_map.get(item.sec_code)
        candidates.append(
            ThemeCandidate(
                sec_code=item.sec_code,
                sec_name=item.sec_name,
                corr_1y=item.corr_1y,
                ol2top=item.ol2top,
                chance_all=getattr(info, "chance_all", None),
                risk_all=getattr(info, "risk_all", None),
                isshow=getattr(info, "isshow", None),
            )
        )

    if not candidates and fund_resp.theme_infos:
        info = fund_resp.theme_infos[0]
        candidates.append(
            ThemeCandidate(
                sec_code=info.sec_code,
                sec_name=info.sec_name,
                chance_all=info.chance_all,
                risk_all=info.risk_all,
                isshow=info.isshow,
            )
        )

    if not candidates:
        return ActiveFundThemeFlowProfile(
            success=False,
            fund_code=fund_code,
            first_error="基金详情未返回关联主题",
        )

    selected = candidates[0]
    profile = ActiveFundThemeFlowProfile(
        success=True,
        fund_code=fund_code,
        selected_theme=selected,
        candidates=candidates,
    )

    theme_resp = get_fund_theme_detail(user, selected.sec_code)
    if theme_resp.success and theme_resp.data:
        rt = theme_resp.data.realTimeList[0] if theme_resp.data.realTimeList else None
        bi = theme_resp.data.themeBaseInfo[0] if theme_resp.data.themeBaseInfo else None
        if rt or bi:
            profile.snapshot = ThemeFlowSnapshot(
                sec_code=selected.sec_code,
                sec_name=selected.sec_name,
                chgrt=getattr(rt, "CHGRT", None) if rt else None,
                chance_all=getattr(rt, "CHANCE_ALL", None) if rt else getattr(bi, "CHANCE_ALL", None),
                chance_zjrd=getattr(rt, "CHANCE_ZJRD", None) if rt else getattr(bi, "CHANCE_ZJRD", None),
                chance_jqd=getattr(rt, "CHANCE_JQD", None) if rt else getattr(bi, "CHANCE_JQD", None),
                flow=getattr(rt, "FLOW", None) if rt else None,
                flow_w=getattr(rt, "FLOW_W", None) if rt else None,
                flow_m=getattr(rt, "FLOW_M", None) if rt else None,
                flow_q=getattr(rt, "FLOW_Q", None) if rt else None,
                sumflow_w=getattr(rt, "SUMFLOW_W", None) if rt else getattr(bi, "SUMFLOW_W", None),
                sumflow_m=getattr(rt, "SUMFLOW_M", None) if rt else getattr(bi, "SUMFLOW_M", None),
                sumflow_q=getattr(rt, "SUMFLOW_Q", None) if rt else getattr(bi, "SUMFLOW_Q", None),
                rm_netflowxl=getattr(bi, "RM_NETFLOWXL", None) if bi else None,
                rm_netflowxl_pct=getattr(bi, "RM_NETFLOWXL_PCT", None) if bi else None,
                fct_xlflow=getattr(bi, "FCT_XLFLOW", None) if bi else None,
                inflowdays=getattr(rt, "INFLOWDAYS", None) if rt else None,
                outflowdays=getattr(rt, "OUTFLOWDAYS", None) if rt else None,
            )
    else:
        profile.notes.append(f"主题详情获取失败: {theme_resp.firstError}")

    heat_resp = get_index_price_flow(user, selected.sec_code, range_type=range_type)
    if heat_resp.success and heat_resp.items:
        tail_items = heat_resp.items[-max(heat_tail_size, 1):]
        profile.recent_heat_series = [
            ThemeHeatPoint(
                date=item.PDATE,
                price=item.PERCENTPRICE,
                chg_pct=item.CHGRT,
                heat_score=item.XLFLOW_SCORE,
            )
            for item in tail_items
        ]
        if all(point.heat_score is None for point in profile.recent_heat_series):
            profile.notes.append(
                "近段主题价格序列可获取，但该主题在历史序列接口中未返回每日 heat_score。"
            )
    else:
        profile.notes.append(f"主题价格/热度序列获取失败: {heat_resp.first_error}")

    secid = guess_secid_from_code(selected.sec_code)
    availability = ThemeDailyFlowAvailability(secid=secid)
    day_flow_resp = get_security_day_flow_kline(user, secid=secid, lmt=5)
    if day_flow_resp.success and day_flow_resp.data:
        availability.supported = True
        availability.day_flow_samples = [
            {
                "date": item.PDATE,
                "main_net_inflow": item.MAIN_NET_INFLOW,
                "small_net_inflow": item.SMALL_NET_INFLOW,
                "medium_net_inflow": item.MEDIUM_NET_INFLOW,
                "large_net_inflow": item.LARGE_NET_INFLOW,
                "close": item.CLOSE,
                "chg_pct": item.CHG_PCT,
            }
            for item in day_flow_resp.data.items[-5:]
        ]
    else:
        availability.day_flow_error = day_flow_resp.first_error

    today_flow_resp = get_security_today_flow_kline(user, secid=secid, lmt=3)
    if today_flow_resp.success and today_flow_resp.data:
        availability.supported = True
        availability.today_flow_samples = [
            {
                "date": item.PDATE,
                "main_net_inflow": item.MAIN_NET_INFLOW,
                "small_net_inflow": item.SMALL_NET_INFLOW,
                "medium_net_inflow": item.MEDIUM_NET_INFLOW,
                "large_net_inflow": item.LARGE_NET_INFLOW,
                "super_large_net_inflow": item.SUPER_LARGE_NET_INFLOW,
            }
            for item in today_flow_resp.data.items
        ]
    else:
        availability.today_flow_error = today_flow_resp.first_error

    if selected.sec_code.upper().startswith("BK") and not availability.supported:
        profile.notes.append(
            "BK 主题当前可获取快照级资金数据，但无法通过现有 EastMoney fflow 接口取得逐日净流入历史。"
        )

    profile.daily_flow_availability = availability
    logger.info(
        "主动基金主题资金画像完成: fund=%s, theme=%s, day_flow_supported=%s",
        fund_code,
        selected.sec_code,
        availability.supported,
    )
    return profile


if __name__ == "__main__":
    import json
    from src.common.constant import DEFAULT_USER
    from src.API.登录接口.login import ensure_user_fresh

    user = ensure_user_fresh(DEFAULT_USER)
    profile = analyze_active_fund_theme_flow(user, "011707")
    print(json.dumps(profile.to_dict(), ensure_ascii=False, indent=2))
