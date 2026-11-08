"""
市场主题领域模型。

对齐 FundRSBKRealTime 接口返回的 BK 主题/板块实时数据。
默认可返回“主题+行业”全量 BK 板块池，也可按 TYPE_CODE 过滤。
"""

from dataclasses import dataclass, field
from typing import Any, List, Optional


@dataclass
class MarketThemeItem:
    """单条主题实时数据。"""

    INDEXCODE: str = ""
    INDEXNAME: str = ""
    TYPE_CODE: str = ""
    TYPE_NAME: str = ""
    PETTM: float = 0.0
    PEP100: float = 0.0
    PB: float = 0.0
    PBP100: float = 0.0
    INDEXVALUE: float = 0.0
    ISUSEPBP: str = ""
    DEALTIME: str = ""
    W: float = 0.0
    M: float = 0.0
    Q: float = 0.0
    Y: float = 0.0
    SY: float = 0.0
    UPDAYS: int = 0
    DOWNDAYS: int = 0
    INFLOWDAYS: int = 0
    OUTFLOWDAYS: int = 0
    MAX_60D: float = 0.0
    AVG_20D: float = 0.0
    FLOW: float = 0.0
    MAIN_FLOW_IN: float = 0.0
    MAIN_FLOW_OUT: float = 0.0
    RETAIL_FLOW_IN: float = 0.0
    RETAIL_FLOW_OUT: float = 0.0
    FLOW_W: float = 0.0
    FLOW_M: float = 0.0
    FLOW_Q: float = 0.0
    MFLOW_W: float = 0.0
    SUMFLOW_W: float = 0.0
    SUMFLOW_M: float = 0.0
    SUMFLOW_Q: float = 0.0
    CHGRT: float = 0.0
    PERCENTPRICE: float = 0.0
    SCOREDATE: str = ""
    CHANCE_ALL: float = 0.0
    CHANCE_JQD: float = 0.0
    CHANCE_ZJRD: float = 0.0
    CHANCE_SZQS: float = 0.0
    RISK_ALL: float = 0.0
    RISK_YJD: float = 0.0
    RISK_JZD: float = 0.0
    RISK_GLL: float = 0.0
    ISSHOWSCORE: str = ""
    ISFUNDLINK: str = ""
    INDEXDESC: Optional[str] = None
    REAPROFILE: Optional[str] = None
    FUNDINFO: Any = None
    SELFABOUTCOUNT: Any = None
    MAIN_FLOW_IN_PERCENT: str = ""
    MAIN_FLOW_OUT_PERCENT: str = ""
    RETAIL_FLOW_IN_PERCENT: str = ""
    RETAIL_FLOW_OUT_PERCENT: str = ""

    @classmethod
    def from_dict(cls, d: dict) -> "MarketThemeItem":
        """从原始 dict 构造 MarketThemeItem。"""
        clean = {}
        for field_name in cls.__dataclass_fields__:
            raw = d.get(field_name)
            field_type = cls.__dataclass_fields__[field_name].type
            if raw is None or raw == "" or raw == "--":
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
        if tp is Optional[str]:
            return None
        return None


@dataclass
class MarketThemeResponse:
    """获取所有主题的响应对象。"""

    items: List[MarketThemeItem] = field(default_factory=list)
    total_count: int = 0
    error_code: int = 0
    first_error: Optional[str] = None
    success: bool = False
    expansion: Any = None
