"""
基金详情页领域模型。

对应 `dgs.tiantianfunds.com/merge/m/api/jjxqy1_2` 返回的多维度数据，
包含基础信息/关联主题/各周期收益/风险指标/持有人结构/基金经理/费率等。

此处仅做字段声明与类型注解，不包含业务逻辑。
"""

from dataclasses import dataclass, field
from typing import Optional, List, Any


# ── 关联主题 ──────────────────────────────────────────────────────────────────

@dataclass
class FundRelateTheme:
    """
    基金关联主题（fundRelateTheme[]）。

    ┌──────────┬────────┬──────────────────────────────┐
    │ 字段     │ 类型   │ 说明                         │
    ├──────────┼────────┼──────────────────────────────┤
    │ sec_code │ str    │ 主题代码（如 BK000441）      │
    │ sec_name │ str    │ 主题名称（如 高端装备）       │
    │ fcode    │ str    │ 基金代码                     │
    │ corr_1y  │ float  │ 近 1 年相关性（%）           │
    │ ol2top   │ float  │ 与主题 TOP 基金的重叠度（%） │
    └──────────┴────────┴──────────────────────────────┘
    """
    sec_code: str = ""
    sec_name: str = ""
    fcode: str = ""
    corr_1y: float = 0.0
    ol2top: float = 0.0

    @classmethod
    def from_dict(cls, d: dict) -> "FundRelateTheme":
        return cls(
            sec_code=d.get("SEC_CODE", ""),
            sec_name=d.get("SEC_NAME", ""),
            fcode=d.get("FCODE", ""),
            corr_1y=_safe_float(d.get("CORR_1Y")),
            ol2top=_safe_float(d.get("OL2TOP")),
        )


# ── 主题风险机会 ──────────────────────────────────────────────────────────────

@dataclass
class FundThemeInfo:
    """
    主题风险与机会评分（fundRelateThemeInfo[]）。

    ┌──────────────┬────────┬────────────────────────────────┐
    │ 字段         │ 类型   │ 说明                           │
    ├──────────────┼────────┼────────────────────────────────┤
    │ sec_code     │ str    │ 主题代码                       │
    │ sec_name     │ str    │ 主题名称                       │
    │ risk_all     │ float  │ 综合风险评分                   │
    │ chance_all   │ float  │ 综合机会评分                   │
    │ isshow       │ bool   │ 是否在前端展示                 │
    │ isshow_score │ bool   │ 是否展示评分数字               │
    └──────────────┴────────┴────────────────────────────────┘
    """
    sec_code: str = ""
    sec_name: str = ""
    risk_all: float = 0.0
    chance_all: float = 0.0
    isshow: bool = False
    isshow_score: bool = False

    @classmethod
    def from_dict(cls, d: dict) -> "FundThemeInfo":
        return cls(
            sec_code=d.get("SEC_CODE", ""),
            sec_name=d.get("SEC_NAME", ""),
            risk_all=_safe_float(d.get("RISK_ALL")),
            chance_all=_safe_float(d.get("CHANCE_ALL")),
            isshow=d.get("ISSHOW", "0") == "1",
            isshow_score=d.get("ISSHOWSCORE", "0") == "1",
        )


# ── 各周期收益（含基准对比） ──────────────────────────────────────────────────

@dataclass
class FundPeriodIncrease:
    """
    各周期收益数据（FundPeriodIncrease[]）。

    ┌───────────┬────────┬───────────────────────────────┐
    │ 字段      │ 类型   │ 说明                          │
    ├───────────┼────────┼───────────────────────────────┤
    │ title     │ str    │ 周期标识                       │
    │           │        │ Z/Y/3Y/6Y/1N/2N/3N/5N/JN/LN  │
    │ syl       │ float  │ 基金收益率（%）                │
    │ avg       │ float  │ 同类平均（%）                  │
    │ hs300     │ float  │ 沪深 300（%）                  │
    │ benchmark │ float  │ 基准收益率（%）                │
    │ rank      │ int    │ 排名                           │
    │ sc        │ int    │ 同类总数                       │
    └───────────┴────────┴───────────────────────────────┘
    """
    title: str = ""
    syl: float = 0.0
    avg: float = 0.0
    hs300: float = 0.0
    benchmark: float = 0.0
    rank: int = 0
    sc: int = 0

    @classmethod
    def from_dict(cls, d: dict) -> "FundPeriodIncrease":
        return cls(
            title=d.get("title", ""),
            syl=_safe_float(d.get("syl")),
            avg=_safe_float(d.get("avg")),
            hs300=_safe_float(d.get("hs300")),
            benchmark=_safe_float(d.get("benchmark")),
            rank=_safe_int(d.get("rank")),
            sc=_safe_int(d.get("sc")),
        )


# ── 风险指标 ──────────────────────────────────────────────────────────────────

@dataclass
class FundRiskMetrics:
    """
    基金独立风险指标（uniqueInfo[]）。

    ┌──────────────┬────────┬──────────────────────────────┐
    │ 字段         │ 类型   │ 说明                         │
    ├──────────────┼────────┼──────────────────────────────┤
    │ sharp1/3/5   │ float  │ 夏普比率（近 1/3/5 年）     │
    │ stddev1/3/5  │ float  │ 年化标准差（近 1/3/5 年）   │
    │ maxretra1/3/5│ float  │ 最大回撤（%）（近 1/3/5 年）│
    │ maxretra_sd  │ str    │ 最大回撤开始日期             │
    │ maxretra_ed  │ str    │ 最大回撤结束日期             │
    │ trkerror1/3/5│ str    │ 跟踪误差（-- 表示无数据）    │
    │ jgbl         │ float  │ 机构持有比例（%）             │
    └──────────────┴────────┴──────────────────────────────┘
    """
    sharp1: float = 0.0
    sharp3: float = 0.0
    sharp5: float = 0.0
    stddev1: float = 0.0
    stddev3: float = 0.0
    stddev5: float = 0.0
    maxretra1: float = 0.0
    maxretra3: float = 0.0
    maxretra5: float = 0.0
    maxretra_se: float = 0.0
    maxretra_sdate: str = ""
    maxretra_edate: str = ""
    trkerror1: str = ""
    trkerror3: str = ""
    trkerror5: str = ""
    jgbl: float = 0.0

    @classmethod
    def from_dict(cls, d: dict) -> "FundRiskMetrics":
        return cls(
            sharp1=_safe_float(d.get("SHARP1")),
            sharp3=_safe_float(d.get("SHARP3")),
            sharp5=_safe_float(d.get("SHARP5")),
            stddev1=_safe_float(d.get("STDDEV1")),
            stddev3=_safe_float(d.get("STDDEV3")),
            stddev5=_safe_float(d.get("STDDEV5")),
            maxretra1=_safe_float(d.get("MAXRETRA1")),
            maxretra3=_safe_float(d.get("MAXRETRA3")),
            maxretra5=_safe_float(d.get("MAXRETRA5")),
            maxretra_se=_safe_float(d.get("MAXRETRA_SE")),
            maxretra_sdate=d.get("MAXRETRA_SDATE_SE", ""),
            maxretra_edate=d.get("MAXRETRA_EDATE_SE", ""),
            trkerror1=d.get("TRKERROR1", ""),
            trkerror3=d.get("TRKERROR3", ""),
            trkerror5=d.get("TRKERROR5", ""),
            jgbl=_safe_float(d.get("JGBL")),
        )


# ── 持有人结构 ────────────────────────────────────────────────────────────────

@dataclass
class FundHolderStructure:
    """
    基金持有人结构（fundHolderStructure[]）。

    ┌──────────────┬────────┬──────────────────────────────┐
    │ 字段         │ 类型   │ 说明                         │
    ├──────────────┼────────┼──────────────────────────────┤
    │ fsrq         │ str    │ 数据日期                     │
    │ grbl         │ float  │ 个人持有比例（%）             │
    │ jgbl         │ float  │ 机构持有比例（%）             │
    │ employe_hold │ float  │ 员工持有份额                 │
    │ zfe          │ float  │ 总份额                       │
    │ nbbl         │ float  │ 内部持有比例（%）             │
    └──────────────┴────────┴──────────────────────────────┘
    """
    fsrq: str = ""
    grbl: float = 0.0
    jgbl: float = 0.0
    employe_hold: float = 0.0
    zfe: float = 0.0
    nbbl: float = 0.0

    @classmethod
    def from_dict(cls, d: dict) -> "FundHolderStructure":
        return cls(
            fsrq=d.get("FSRQ", ""),
            grbl=_safe_float(d.get("GRBL")),
            jgbl=_safe_float(d.get("JGBL")),
            employe_hold=_safe_float(d.get("EMPLOYEHOLD")),
            zfe=_safe_float(d.get("ZFE")),
            nbbl=_safe_float(d.get("NBBL")),
        )


# ── 公司信息 ──────────────────────────────────────────────────────────────────

@dataclass
class FundCompanyInfo:
    """
    基金公司信息（companyInfo[]）。

    ┌──────────────┬────────┬──────────────────────────────┐
    │ 字段         │ 类型   │ 说明                         │
    ├──────────────┼────────┼──────────────────────────────┤
    │ company_code │ str    │ 公司代码                     │
    │ total_scale  │ float  │ 管理总规模（亿元）           │
    │ estab_date   │ str    │ 成立日期                     │
    └──────────────┴────────┴──────────────────────────────┘
    """
    company_code: str = ""
    total_scale: float = 0.0
    estab_date: str = ""

    @classmethod
    def from_dict(cls, d: dict) -> "FundCompanyInfo":
        return cls(
            company_code=d.get("COMPANYCODE", ""),
            total_scale=_safe_float(d.get("TOTALSCALE")),
            estab_date=d.get("ESTABDATE", ""),
        )


# ── 基金经理简要 ──────────────────────────────────────────────────────────────

@dataclass
class FundManagerBrief:
    """
    基金经理简要信息（FundManagerInformation > currentManagerInfos）。

    ┌──────────────┬────────┬──────────────────────────────┐
    │ 字段         │ 类型   │ 说明                         │
    ├──────────────┼────────┼──────────────────────────────┤
    │ mgr_name     │ str    │ 基金经理姓名                 │
    │ mgr_id       │ str    │ 基金经理 ID                  │
    │ days         │ int    │ 任职天数                     │
    │ penav_growth │ float  │ 任职回报（%）                 │
    │ total_days   │ int    │ 从业天数                     │
    │ yield_se     │ float  │ 从业年均回报（%）             │
    │ investment   │ str    │ 投资理念                     │
    └──────────────┴────────┴──────────────────────────────┘
    """
    mgr_name: str = ""
    mgr_id: str = ""
    days: int = 0
    penav_growth: float = 0.0
    total_days: int = 0
    yield_se: float = 0.0
    investment_idea: str = ""


# ── 完整响应 ──────────────────────────────────────────────────────────────────

@dataclass
class FundDetailResponse:
    """
    基金详情页 v1.2 完整响应。

    ┌──────────────────┬──────────────┬────────────────────────────────┐
    │ 字段             │ 类型         │ 说明                           │
    ├──────────────────┼──────────────┼────────────────────────────────┤
    │ success          │ bool         │ 是否成功                       │
    │ error_code       │ int          │ 错误码                         │
    │ first_error      │ str/None     │ 错误描述                       │
    │ base_info_raw    │ dict/None    │ 原始基础信息                   │
    │ relate_themes    │ list         │ 关联主题列表                   │
    │ theme_infos      │ list         │ 主题风险机会列表               │
    │ period_increases │ list         │ 各周期收益（含基准对比）       │
    │ risk_metrics     │ FundRiskMetrics/None │ 风险指标               │
    │ holder_structure │ FundHolderStructure/None │ 持有人结构         │
    │ company_info     │ FundCompanyInfo/None    │ 基金公司信息        │
    │ current_managers │ list         │ 当前基金经理列表               │
    │ raw_data         │ dict/None    │ 完整原始响应（备用）           │
    └──────────────────┴──────────────┴────────────────────────────────┘
    """
    success: bool = False
    error_code: int = -1
    first_error: Optional[str] = None
    base_info_raw: Optional[dict] = None
    relate_themes: List[FundRelateTheme] = field(default_factory=list)
    theme_infos: List[FundThemeInfo] = field(default_factory=list)
    period_increases: List[FundPeriodIncrease] = field(default_factory=list)
    risk_metrics: Optional[FundRiskMetrics] = None
    holder_structure: Optional[FundHolderStructure] = None
    company_info: Optional[FundCompanyInfo] = None
    current_managers: List[FundManagerBrief] = field(default_factory=list)
    raw_data: Optional[dict] = None

    @classmethod
    def from_api_response(cls, raw: dict) -> "FundDetailResponse":
        """从 API 返回的完整 dict 构造 FundDetailResponse。"""
        resp = cls(
            success=bool(raw.get("success", False)),
            error_code=int(raw.get("errorCode", -1)),
            first_error=raw.get("firstError"),
            raw_data=raw,
        )

        data = raw.get("data") or {}

        # baseInfo
        base_list = data.get("baseInfo") or []
        if base_list:
            resp.base_info_raw = base_list[0]

        # fundRelateTheme
        theme_list = data.get("fundRelateTheme") or []
        resp.relate_themes = [FundRelateTheme.from_dict(t) for t in theme_list]

        # fundRelateThemeInfo
        info_list = data.get("fundRelateThemeInfo") or []
        resp.theme_infos = [FundThemeInfo.from_dict(t) for t in info_list]

        # FundPeriodIncrease
        period_list = data.get("FundPeriodIncrease") or []
        resp.period_increases = [FundPeriodIncrease.from_dict(p) for p in period_list]

        # uniqueInfo → risk_metrics
        unique_list = data.get("uniqueInfo") or []
        if unique_list:
            resp.risk_metrics = FundRiskMetrics.from_dict(unique_list[0])

        # fundHolderStructure
        holder_list = data.get("fundHolderStructure") or []
        if holder_list:
            resp.holder_structure = FundHolderStructure.from_dict(holder_list[0])

        # companyInfo
        company_list = data.get("companyInfo") or []
        if company_list:
            resp.company_info = FundCompanyInfo.from_dict(company_list[0])

        # FundManagerInformation → currentManagerInfos
        mgr_info = data.get("FundManagerInformation") or {}
        current_list = mgr_info.get("currentManagerInfos") or []
        for cm in current_list:
            sinfo = cm.get("SINFO") or {}
            pinfo_list = cm.get("PINFO") or []
            yield_se = 0.0
            idea = ""
            if pinfo_list:
                yield_se = _safe_float(pinfo_list[0].get("YIELDSE"))
                idea = pinfo_list[0].get("INVESTMENTIDEAR", "")
            resp.current_managers.append(FundManagerBrief(
                mgr_name=sinfo.get("MGRNAME", ""),
                mgr_id=sinfo.get("MGRID", ""),
                days=_safe_int(sinfo.get("DAYS")),
                penav_growth=_safe_float(sinfo.get("PENAVGROWTH")),
                total_days=_safe_int(sinfo.get("TOTALDAYS")),
                yield_se=yield_se,
                investment_idea=idea,
            ))

        return resp


# ── 内部工具 ──────────────────────────────────────────────────────────────────

def _safe_float(value, default: float = 0.0) -> float:
    """安全转 float，处理 None / '' / '--' 等异常值。"""
    if value is None:
        return default
    if isinstance(value, (int, float)):
        return float(value)
    s = str(value).strip()
    if not s or s == "--":
        return default
    try:
        return float(s)
    except (ValueError, TypeError):
        return default


def _safe_int(value, default: int = 0) -> int:
    """安全转 int，处理 None / '' / '--' 等异常值。"""
    if value is None:
        return default
    if isinstance(value, (int, float)):
        return int(value)
    s = str(value).strip()
    if not s or s == "--":
        return default
    try:
        return int(float(s))
    except (ValueError, TypeError):
        return default
