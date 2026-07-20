"""
指数价格走势与资金热度领域模型。

对应天天基金 FundIndex/FundIndexPrice 接口。
返回指定指数每日的收盘点位、涨跌幅与资金热度评分序列。
"""

from dataclasses import dataclass, field
from typing import Optional, List, Any


# ── 请求参数 ──────────────────────────────────────────────────────────────────

# RANGE 取值说明
MONEY_FLOW_RANGE_MAP = {
    "n":   "近 1 年",
    "3n":  "近 3 年",
    "y":   "近 1 月",
    "w":   "近 1 周",
}


# ── 单日点位数据 ──────────────────────────────────────────────────────────────

@dataclass
class IndexPriceFlowPoint:
    """
    单日指数价格走势与资金热度数据。

    ┌───────────────┬────────┬──────────────────────────────────────────┐
    │ 字段           │ 类型   │ 说明                                     │
    ├───────────────┼────────┼──────────────────────────────────────────┤
    │ PDATE         │ str    │ 日期（如 "2026-07-20"）                  │
    │ PERCENTPRICE  │ float  │ 指数收盘点位（行情数据经处理后的精确值） │
    │ CHGRT         │ float  │ 日涨跌幅（%），首次数据点可能为空        │
    │ XLFLOW_SCORE  │ float  │ 指数资金热度评分（0-100），              │
    │               │        │ "--" 表示当日暂无数据（非交易/未更新）   │
    └───────────────┴────────┴──────────────────────────────────────────┘
    """
    PDATE: str = ""
    PERCENTPRICE: float = 0.0
    CHGRT: Optional[float] = None
    XLFLOW_SCORE: Optional[float] = None

    @classmethod
    def from_dict(cls, d: dict) -> "IndexPriceFlowPoint":
        """从原始 dict 构造。"""
        point = cls(PDATE=str(d.get("PDATE", "")))

        raw_price = d.get("PERCENTPRICE")
        if raw_price is not None:
            point.PERCENTPRICE = float(raw_price)

        raw_chgrt = d.get("CHGRT")
        if raw_chgrt is not None and raw_chgrt != "":
            try:
                point.CHGRT = float(raw_chgrt)
            except (ValueError, TypeError):
                point.CHGRT = None

        raw_score = d.get("XLFLOW_SCORE")
        if raw_score is not None and raw_score != "" and raw_score != "--":
            try:
                point.XLFLOW_SCORE = float(raw_score)
            except (ValueError, TypeError):
                point.XLFLOW_SCORE = None

        return point


# ── 完整响应 ──────────────────────────────────────────────────────────────────

@dataclass
class IndexPriceFlowResponse:
    """
    指数价格走势与资金热度接口的完整响应。

    ┌─────────────┬──────────────────────────────────────────────┐
    │ 字段         │ 说明                                         │
    ├─────────────┼──────────────────────────────────────────────┤
    │ items       │ 每日点位与热度数据列表（IndexPriceFlowPoint） │
    │ total_count │ 总记录数                                      │
    │ error_code  │ 错误码（0 = 正常）                           │
    │ first_error │ 错误描述（成功时为 null）                     │
    │ success     │ 是否成功                                     │
    │ has_wrong_token │ token 是否异常（null 或 bool）           │
    │ expansion   │ 扩展字段（本接口不使用）                      │
    │ jf          │ 平台标识（"ali" = 阿里云）                   │
    └─────────────┴──────────────────────────────────────────────┘
    """
    items: List[IndexPriceFlowPoint] = field(default_factory=list)
    total_count: int = 0
    error_code: int = 0
    first_error: Optional[str] = None
    success: bool = False
    has_wrong_token: Any = None
    expansion: Any = None
    jf: str = ""
