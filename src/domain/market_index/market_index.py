"""
市场指数领域模型。

定义指数宝接口的请求参数与响应数据结构。
此处仅做字段声明与类型注解，不包含业务逻辑。
该模型由 API 层负责填充，后续 service 层按需组合存储。
"""

from dataclasses import dataclass, field
from typing import Optional, List, Any


# ── 请求参数 ──────────────────────────────────────────────────────────────────

# type_code 的取值说明
MARKET_INDEX_TYPE_MAP = {
    "0":       "全部指数",
    "001001":  "宽基指数",
    "001002":  "行业指数",
    "001003":  "主题指数",
    "001004":  "策略指数",
    "003":     "海外指数",
}

# sort_name 的常用取值
MARKET_INDEX_SORT_NAME_MAP = {
    "NEWCHG":  "涨跌幅",
    "D":       "日涨跌幅",
    "W":       "周涨跌幅",
    "M":       "月涨跌幅",
    "Q":       "季涨跌幅",
}

# sort_type 的取值
MARKET_INDEX_SORT_TYPE_MAP = {
    "DESC": "降序",
    "ASC":  "升序",
}


# ── 响应数据项（单条指数） ────────────────────────────────────────────────────

@dataclass
class MarketIndexItem:
    """
    单条指数数据，对应响应 data[] 中的每个元素。

    ┌──────────────┬────────┬──────────────────────────────────────────┐
    │ 字段          │ 类型   │ 说明                                     │
    ├──────────────┼────────┼──────────────────────────────────────────┤
    │ SEC_NAME     │ str    │ 主题/行业名称（如 "煤炭,煤炭开采"）       │
    │ SEC_CODE     │ str    │ 主题/行业代码（如 "BK000177,BK000178"）   │
    │ TYPE_NAME    │ str    │ 指数分类名称（如 "行业"）                 │
    │ TYPE_CODE    │ str    │ 指数分类代码（如 "001002"）               │
    │ INDEXCODE    │ str    │ 指数代码（如 "399998"）                   │
    │ INDEXNAME    │ str    │ 指数简称（如 "中证煤炭"）                 │
    │ FULLINDEXNAME│ str    │ 指数全称（如 "中证煤炭指数"）             │
    │ INDEXTYPE    │ str    │ 指数类型码（如 "02"）                     │
    │ NEWPRICE     │ float  │ 最新点位                                   │
    │ NEWCHG       │ float  │ 日涨跌幅（%）                              │
    │ PDATE        │ str    │ 最新行情日期（如 "2026-07-20"）          │
    │ PERCENTPRICE │ float  │ 精确最新点位                               │
    │ D            │ float  │ 日涨跌幅（%），与 NEWCHG 同义             │
    │ W            │ float  │ 周涨跌幅（%）                              │
    │ M            │ float  │ 月涨跌幅（%）                              │
    │ Q            │ float  │ 季涨跌幅（%）                              │
    │ HY           │ float  │ 半年涨跌幅（%，HY=Half Year）             │
    │ Y            │ float  │ 1 年涨跌幅（%）                            │
    │ TWY          │ float  │ 2 年涨跌幅（%）                            │
    │ TRY          │ float  │ 3 年涨跌幅（%）                            │
    │ FY           │ float  │ 5 年涨跌幅（%）                            │
    │ SY           │ float  │ 今年以来涨跌幅（%）                        │
    │ ISSHOWEV    │ str    │ 是否显示事件（"1"=是）                   │
    │ INDEXVALUE   │ str    │ -                                          │
    │ HOTSALE      │ Any    │ 热门销售数据（目前为 null）                │
    │ WEEKTOTALSALE│ int    │ 本周交易量                                 │
    │ NEWINDEXTEXCH│ str    │ -                                          │
    │ MAKERNAME    │ str    │ 指数编制公司（如 "中证指数有限公司"）     │
    │ REAPROFILE   │ str    │ 指数描述/说明文本                          │
    │ TOPICJJBID   │ int    │ 主题基金页面 ID                            │
    │ ISQUOT       │ str    │ 是否有实时行情（"1"=有，"0"=无）          │
    │ ISUSEPBP     │ str    │ 是否有 PBP（"1"=有，"0"=无）              │
    │ PETTM        │ float  │ 滚动市盈率 PE-TTM                          │
    │ PEP100       │ float  │ PE 在历史区间中的百分位                    │
    │ PB           │ float  │ 市净率 PB                                   │
    │ PBP100       │ float  │ PB 在历史区间中的百分位                    │
    │ GXL          │ float  │ 静态股息率（%）                            │
    │ ROE          │ float  │ 净资产收益率（%）                          │
    │ GXL_RS       │ float  │ 股息率在历史区间中的百分位 (RS=RankScore) │
    │ XLFLOW_SCORE │ float  │ 指数资金热度评分                           │
    │ AVGSYL_TRY   │ float  │ 持有3年平均收益率                         │
    └──────────────┴────────┴──────────────────────────────────────────┘
    """
    # ── 基础信息 ──
    SEC_NAME: str = ""
    SEC_CODE: str = ""
    TYPE_NAME: str = ""
    TYPE_CODE: str = ""
    INDEXCODE: str = ""
    INDEXNAME: str = ""
    FULLINDEXNAME: str = ""
    INDEXTYPE: str = ""

    # ── 行情数据 ──
    NEWPRICE: float = 0.0
    NEWCHG: float = 0.0
    PDATE: str = ""
    PERCENTPRICE: float = 0.0

    # ── 各周期涨跌幅 ──
    D: float = 0.0
    W: float = 0.0
    M: float = 0.0
    Q: float = 0.0
    HY: float = 0.0
    Y: float = 0.0
    TWY: float = 0.0
    TRY: float = 0.0
    FY: float = 0.0
    SY: float = 0.0

    # ── 展示控制 ──
    ISSHOWEV: str = ""
    INDEXVALUE: str = ""
    HOTSALE: Any = None
    WEEKTOTALSALE: int = 0
    NEWINDEXTEXCH: str = ""

    # ── 指数说明 ──
    MAKERNAME: str = ""
    REAPROFILE: str = ""
    TOPICJJBID: int = 0

    # ── 行情/数据开关 ──
    ISQUOT: str = ""
    ISUSEPBP: str = ""

    # ── 估值指标 ──
    PETTM: float = 0.0
    PEP100: float = 0.0
    PB: float = 0.0
    PBP100: float = 0.0
    GXL: float = 0.0
    ROE: float = 0.0
    GXL_RS: float = 0.0

    # ── 资金热度 ──
    XLFLOW_SCORE: float = 0.0

    # ── 股息率 ──
    AVGSYL_TRY: float = 0.0


    @classmethod
    def from_dict(cls, d: dict) -> "MarketIndexItem":
        """从原始 dict 构造 MarketIndexItem。"""
        clean = {}
        for field_name in cls.__dataclass_fields__:
            raw = d.get(field_name)
            field_type = cls.__dataclass_fields__[field_name].type
            if raw is None:
                clean[field_name] = cls._default_for_type(field_type)
            elif field_type is float:
                clean[field_name] = float(raw)
            elif field_type is int:
                clean[field_name] = int(raw)
            else:
                clean[field_name] = raw
        return cls(**clean)

    @staticmethod
    def _default_for_type(tp) -> Any:
        if tp is float:
            return 0.0
        if tp is int:
            return 0
        if tp is str:
            return ""
        return None


# ── 响应元信息 ────────────────────────────────────────────────────────────────

@dataclass
class MarketIndexResponse:
    """
    指数宝接口的完整响应。

    ┌─────────────┬──────────────────────────────────────┐
    │ 字段         │ 说明                                 │
    ├─────────────┼──────────────────────────────────────┤
    │ items       │ 指数数据列表（MarketIndexItem[]）    │
    │ total_count │ 总记录数（仅当 type=0 时返回）       │
    │ error_code  │ 错误码（0=正常）                     │
    │ first_error │ 错误描述（成功时为 null）             │
    │ success     │ 是否成功                             │
    │ expansion   │ 扩展字段（目前未使用）                │
    └─────────────┴──────────────────────────────────────┘
    """
    items: List[MarketIndexItem] = field(default_factory=list)
    total_count: int = 0
    error_code: int = 0
    first_error: Optional[str] = None
    success: bool = False
    expansion: Any = None
