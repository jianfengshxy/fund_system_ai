"""
基金主题详情领域模型。

定义天天基金 fundThemeDetail 接口的响应数据结构。
该接口用于查询板块/主题的综合详情，包含实时行情、资金流、
评分排名、相似主题、投资热点与研究报告等。

接口地址: https://dgs.tiantianfunds.com/merge/m/api/fundThemeDetail
"""

from dataclasses import dataclass, field
from typing import Optional, List, Any


# ── 实时行情（realTimeList[0]） ──────────────────────────────────────────────

@dataclass
class FundThemeRealTimeItem:
    """
    realTimeList 单条实时行情。

    ┌──────────────────┬────────┬───────────────────────────────────────┐
    │ 字段              │ 类型   │ 说明                                  │
    ├──────────────────┼────────┼───────────────────────────────────────┤
    │ INDEXCODE         │ str    │ 主题代码（如 BK000441）               │
    │ INDEXNAME         │ str    │ 主题名称（如 "高端装备"）             │
    │ CHGRT             │ float  │ 当日涨跌幅（%）                       │
    │ PERCENTPRICE      │ float  │ 最新点位                              │
    │ DEALTIME          │ str    │ 行情时间                              │
    │ TYPE_CODE         │ str    │ 指数分类（如 001003=主题）            │
    │ TYPE_NAME         │ str    │ 分类名称                              │
    │ CHANCE_ALL        │ float  │ 机会综合评分                          │
    │ CHANCE_ZJRD       │ float  │ 资金热度评分                          │
    │ CHANCE_JQD        │ float  │ 景气度评分                            │
    │ CHANCE_SZQS       │ float  │ 指数趋势评分                          │
    │ RISK_ALL          │ float  │ 风险综合评分                          │
    │ RISK_GLL          │ float  │ 概率风险                              │
    │ RISK_JZD          │ float  │ 阶段风险                              │
    │ RISK_YJD          │ float  │ 阶段风险                              │
    │ W/M/Q/Y/SY        │ float  │ 周/月/季/年/今年 涨跌幅             │
    │ PB/PETTM          │ float  │ 市净率 / 滚动市盈率                   │
    │ PBP100/PEP100     │ float  │ PB/PE 历史百分位                      │
    │ FLOW/FLOW_W/      │ float  │ 当日/周/月/季 资金净流入             │
    │ FLOW_M/FLOW_Q     │ float  │                                       │
    │ SUMFLOW_W/        │ float  │ 累计周/月/季 资金净流入               │
    │ SUMFLOW_M/        │ float  │                                       │
    │ SUMFLOW_Q         │ float  │                                       │
    │ MFLOW_W           │ float  │ 周主力净流入                          │
    │ MAIN_FLOW_IN/     │ float  │ 主力资金流入/流出                     │
    │ MAIN_FLOW_OUT     │ float  │                                       │
    │ RETAIL_FLOW_IN/   │ float  │ 散户资金流入/流出                     │
    │ RETAIL_FLOW_OUT   │ float  │                                       │
    │ MAIN_FLOW_IN_PCT  │ str    │ 主力流入占比（%）                     │
    │ MAIN_FLOW_OUT_PCT │ str    │ 主力流出占比（%）                     │
    │ MAX_60D           │ float  │ 60 日最高点位                         │
    │ AVG_20D           │ float  │ 20 日均线点位                         │
    │ UPDAYS/DOWNDAYS   │ int    │ 连涨/连跌天数                        │
    │ INFLOWDAYS/       │ int    │ 资金连续流入/流出天数                │
    │ OUTFLOWDAYS       │ int    │                                       │
    │ REAPROFILE        │ str    │ 板块简介                              │
    │ SCOREDATE         │ str    │ 评分日期                              │
    │ ISSHOWSCORE       │ str    │ 是否显示评分（"0"/"1"）              │
    │ ISUSEPBP          │ int    │ 是否使用 PBP（0/1）                  │
    │ ISFUNDLINK        │ str    │ 是否有基金链接（"0"/"1"）            │
    └──────────────────┴────────┴───────────────────────────────────────┘
    """
    INDEXCODE: str = ""
    INDEXNAME: str = ""
    CHGRT: float = 0.0
    PERCENTPRICE: float = 0.0
    DEALTIME: str = ""
    TYPE_CODE: str = ""
    TYPE_NAME: str = ""
    REAPROFILE: str = ""

    # ── 机会/风险评分 ──
    CHANCE_ALL: float = 0.0
    CHANCE_ZJRD: float = 0.0
    CHANCE_JQD: float = 0.0
    CHANCE_SZQS: float = 0.0
    RISK_ALL: float = 0.0
    RISK_GLL: float = 0.0
    RISK_JZD: float = 0.0
    RISK_YJD: float = 0.0
    SCOREDATE: str = ""
    ISSHOWSCORE: str = ""
    ISUSEPBP: int = 0

    # ── 各周期涨跌幅 ──
    W: float = 0.0
    M: float = 0.0
    Q: float = 0.0
    Y: float = 0.0
    SY: float = 0.0

    # ── 估值指标 ──
    PB: float = 0.0
    PETTM: float = 0.0
    PBP100: float = 0.0
    PEP100: float = 0.0

    # ── 资金流向 ──
    FLOW: float = 0.0
    FLOW_W: float = 0.0
    FLOW_M: float = 0.0
    FLOW_Q: float = 0.0
    SUMFLOW_W: float = 0.0
    SUMFLOW_M: float = 0.0
    SUMFLOW_Q: float = 0.0
    MFLOW_W: float = 0.0
    MAIN_FLOW_IN: float = 0.0
    MAIN_FLOW_OUT: float = 0.0
    RETAIL_FLOW_IN: float = 0.0
    RETAIL_FLOW_OUT: float = 0.0
    MAIN_FLOW_IN_PERCENT: str = ""
    MAIN_FLOW_OUT_PERCENT: str = ""
    RETAIL_FLOW_IN_PERCENT: str = ""
    RETAIL_FLOW_OUT_PERCENT: str = ""

    # ── 技术指标 ──
    MAX_60D: float = 0.0
    AVG_20D: float = 0.0
    UPDAYS: int = 0
    DOWNDAYS: int = 0
    INFLOWDAYS: int = 0
    OUTFLOWDAYS: int = 0

    # ── 其他 ──
    ISFUNDLINK: str = ""
    FUNDINFO: Any = None
    SELFABOUTCOUNT: Any = None

    @classmethod
    def from_dict(cls, d: dict) -> "FundThemeRealTimeItem":
        clean = {}
        for fn in cls.__dataclass_fields__:
            raw = d.get(fn)
            ft = cls.__dataclass_fields__[fn].type
            if raw is None:
                clean[fn] = None if ft in (Any, Optional) else _default(ft)
            elif ft is float:
                clean[fn] = float(raw)
            elif ft is int:
                clean[fn] = int(raw)
            else:
                clean[fn] = raw
        return cls(**clean)


# ── 相似主题（similarTheme[]） ──────────────────────────────────────────────

@dataclass
class FundThemeSimilarItem:
    """相似主题条目。"""
    SEC_CODE: str = ""
    SEC_NAME: str = ""
    SCORE: float = 0.0
    CORRELATION: float = 0.0
    OVERLAP_SCORE: float = 0.0
    W: float = 0.0

    @classmethod
    def from_dict(cls, d: dict) -> "FundThemeSimilarItem":
        clean = {}
        for fn in cls.__dataclass_fields__:
            raw = d.get(fn)
            ft = cls.__dataclass_fields__[fn].type
            if raw is None:
                clean[fn] = _default(ft)
            elif ft is float:
                clean[fn] = float(raw)
            elif ft is int:
                clean[fn] = int(raw)
            else:
                clean[fn] = raw
        return cls(**clean)


# ── 主题基本信息（themeBaseInfo[0]） ────────────────────────────────────────

@dataclass
class FundThemeBaseInfoItem:
    """
    主题基本信息，包含各类评分与排名。

    ┌───────────────┬────────┬───────────────────────────────────────┐
    │ 字段           │ 类型   │ 说明                                  │
    ├───────────────┼────────┼───────────────────────────────────────┤
    │ SEC_CODE      │ str    │ 主题代码                              │
    │ SCOREDATE     │ str    │ 评分日期                              │
    │ TYPE_CODE     │ str    │ 类型代码                              │
    │ WSC/MSC/QSC/  │ int    │ 周/月/季/年/半年 评分               │
    │ YSC/SYSC      │ int    │                                       │
    │ FWSC/FMSC/FQSC│ int    │ 财务周/月/季 评分                    │
    │ RANKW/RANKM/  │ int    │ 周/月/季/年/半年 排名                │
    │ RANKQ/RANKY/  │ int    │                                       │
    │ RANKSY        │ int    │                                       │
    │ FRANKW/FRANKM/│ int    │ 财务周/月/季 排名                    │
    │ FRANKQ        │ int    │                                       │
    │ CHANCE_ALL    │ float  │ 机会综合评分                          │
    │ CHANCE_ZJRD   │ float  │ 资金热度评分                          │
    │ CHANCE_JQD    │ float  │ 景气度评分                            │
    │ RISK_GLL/RISK_│ float  │ 风险评分（概率/阶段）                 │
    │ JZD/RISK_YJD  │ float  │                                       │
    │ PB/PETTM      │ float  │ 市净率 / 滚动市盈率                   │
    │ PBP100/PEP100 │ float  │ PB/PE 历史百分位                      │
    │ ROE/SUE       │ float  │ 净资产收益率 / 超预期因子             │
    │ RM_NETFLOWXL  │ float  │ 主力资金净流入                        │
    │ RM_NETFLOWXL_ │ float  │ 主力资金净流入占比（%）               │
    │ PCT           │ float  │                                       │
    │ FCT_XLFLOW    │ float  │ 资金流因子值                          │
    │ SUMFLOW_W/    │ float  │ 累计周/月/季 资金净流入               │
    │ SUMFLOW_M/    │ float  │                                       │
    │ SUMFLOW_Q     │ float  │                                       │
    └───────────────┴────────┴───────────────────────────────────────┘
    """
    SEC_CODE: str = ""
    SCOREDATE: str = ""
    TYPE_CODE: str = ""

    # ── 评分 ──
    WSC: int = 0
    MSC: int = 0
    QSC: int = 0
    YSC: int = 0
    SYSC: int = 0
    FWSC: int = 0
    FMSC: int = 0
    FQSC: int = 0

    # ── 排名 ──
    RANKW: int = 0
    RANKM: int = 0
    RANKQ: int = 0
    RANKY: int = 0
    RANKSY: int = 0
    FRANKW: int = 0
    FRANKM: int = 0
    FRANKQ: int = 0

    # ── 机会/风险评分 ──
    CHANCE_ALL: float = 0.0
    CHANCE_ZJRD: float = 0.0
    CHANCE_JQD: float = 0.0
    RISK_GLL: float = 0.0
    RISK_JZD: float = 0.0
    RISK_YJD: float = 0.0

    # ── 估值指标 ──
    PB: float = 0.0
    PETTM: float = 0.0
    PBP100: float = 0.0
    PEP100: float = 0.0

    # ── 财务指标 ──
    ROE: float = 0.0
    SUE: float = 0.0

    # ── 资金流 ──
    RM_NETFLOWXL: float = 0.0
    RM_NETFLOWXL_PCT: float = 0.0
    FCT_XLFLOW: float = 0.0
    SUMFLOW_W: float = 0.0
    SUMFLOW_M: float = 0.0
    SUMFLOW_Q: float = 0.0

    @classmethod
    def from_dict(cls, d: dict) -> "FundThemeBaseInfoItem":
        clean = {}
        for fn in cls.__dataclass_fields__:
            raw = d.get(fn)
            ft = cls.__dataclass_fields__[fn].type
            if raw is None:
                clean[fn] = _default(ft)
            elif ft is float:
                clean[fn] = float(raw)
            elif ft is int:
                clean[fn] = int(raw)
            else:
                clean[fn] = raw
        return cls(**clean)


# ── 投资热点 ─────────────────────────────────────────────────────────────────

@dataclass
class FundThemeSectorHotspot:
    """板块投资热点条目。"""
    summary: str = ""
    date: str = ""
    topicId: str = ""
    secName: Optional[str] = None
    secCode: str = ""
    outline: Optional[str] = None
    title: Optional[str] = None
    url: Optional[str] = None
    content: Optional[str] = None
    question: Optional[str] = None
    references: Optional[Any] = None

    @classmethod
    def from_dict(cls, d: dict) -> "FundThemeSectorHotspot":
        return cls(
            summary=d.get("summary", ""),
            date=d.get("date", ""),
            topicId=d.get("topicId", ""),
            secName=d.get("secName"),
            secCode=d.get("secCode", ""),
            outline=d.get("outline"),
            title=d.get("title"),
            url=d.get("url"),
            content=d.get("content"),
            question=d.get("question"),
            references=d.get("references"),
        )


# ── 研究报告 ─────────────────────────────────────────────────────────────────

@dataclass
class FundThemeResearchReport:
    """板块研究报告。"""
    secName: str = ""
    secCode: str = ""
    shortSummary: str = ""
    viewpoint: List[str] = field(default_factory=list)
    title: List[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, d: dict) -> "FundThemeResearchReport":
        return cls(
            secName=d.get("secName", ""),
            secCode=d.get("secCode", ""),
            shortSummary=d.get("shortSummary", ""),
            viewpoint=d.get("viewpoint", []) or [],
            title=d.get("title", []) or [],
        )


# ── 板块信息 ─────────────────────────────────────────────────────────────────

@dataclass
class FundThemeSectorInfo:
    """板块综合信息（sectorByCodeOrTheme）。"""
    sectorCode: str = ""
    sectorName: str = ""
    updateTime: Optional[str] = None
    sectorHotspotVOS: List[FundThemeSectorHotspot] = field(default_factory=list)
    researchReportVO: Optional[FundThemeResearchReport] = None

    @classmethod
    def from_dict(cls, d: dict) -> "FundThemeSectorInfo":
        hotspots_raw = d.get("sectorHotspotVOS", []) or []
        hotspots = [FundThemeSectorHotspot.from_dict(h) for h in hotspots_raw]
        report_raw = d.get("researchReportVO")
        report = FundThemeResearchReport.from_dict(report_raw) if report_raw else None
        return cls(
            sectorCode=d.get("sectorCode", ""),
            sectorName=d.get("sectorName", ""),
            updateTime=d.get("updateTime"),
            sectorHotspotVOS=hotspots,
            researchReportVO=report,
        )


# ── 关联主题 ─────────────────────────────────────────────────────────────────

@dataclass
class FundThemeRelativeInfo:
    """关联主题信息（relativeTheme）。"""
    datas: List[Any] = field(default_factory=list)
    relativeIndCode: str = ""
    relativeIndName: str = ""

    @classmethod
    def from_dict(cls, d: dict) -> "FundThemeRelativeInfo":
        return cls(
            datas=d.get("datas", []) or [],
            relativeIndCode=d.get("relativeIndCode", ""),
            relativeIndName=d.get("relativeIndName", ""),
        )


# ── 响应数据 ─────────────────────────────────────────────────────────────────

@dataclass
class FundThemeDetailData:
    """fundThemeDetail 接口 data 字段。"""
    realTimeList: List[FundThemeRealTimeItem] = field(default_factory=list)
    similarTheme: List[FundThemeSimilarItem] = field(default_factory=list)
    themeBaseInfo: List[FundThemeBaseInfoItem] = field(default_factory=list)
    sectorByCodeOrTheme: Optional[FundThemeSectorInfo] = None
    relativeTheme: FundThemeRelativeInfo = field(default_factory=FundThemeRelativeInfo)
    fundMangerInfos: Any = None
    getReviewList: List[Any] = field(default_factory=list)

    @classmethod
    def from_dict(cls, d: dict) -> "FundThemeDetailData":
        return cls(
            realTimeList=[FundThemeRealTimeItem.from_dict(it) for it in (d.get("realTimeList") or [])],
            similarTheme=[FundThemeSimilarItem.from_dict(it) for it in (d.get("similarTheme") or [])],
            themeBaseInfo=[FundThemeBaseInfoItem.from_dict(it) for it in (d.get("themeBaseInfo") or [])],
            sectorByCodeOrTheme=FundThemeSectorInfo.from_dict(d["sectorByCodeOrTheme"])
                if d.get("sectorByCodeOrTheme") else None,
            relativeTheme=FundThemeRelativeInfo.from_dict(d.get("relativeTheme") or {}),
            fundMangerInfos=d.get("fundMangerInfos"),
            getReviewList=d.get("getReviewList", []) or [],
        )


# ── 完整响应 ─────────────────────────────────────────────────────────────────

@dataclass
class FundThemeDetailResponse:
    """fundThemeDetail 接口完整响应。"""
    success: bool = False
    errorCode: int = -1
    firstError: Optional[str] = None
    data: Optional[FundThemeDetailData] = None
    totalCount: int = 0
    expansion: Any = None

    @classmethod
    def from_json(cls, j: dict) -> "FundThemeDetailResponse":
        data_raw = j.get("data")
        data_obj = FundThemeDetailData.from_dict(data_raw) if data_raw else None
        return cls(
            success=bool(j.get("success", False)),
            errorCode=int(j.get("errorCode", -1)),
            firstError=j.get("firstError"),
            data=data_obj,
            totalCount=int(j.get("totalCount", 0)),
            expansion=j.get("expansion"),
        )


# ── 工具 ─────────────────────────────────────────────────────────────────────

def _default(tp) -> Any:
    if tp is float:
        return 0.0
    if tp is int:
        return 0
    if tp is str:
        return ""
    return None
