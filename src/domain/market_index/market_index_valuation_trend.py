"""
指数估值走势领域模型（PB / PE-TTM 历史数据）。

对应天天基金 FundIndex/indexValueTrend 接口。
返回指定指数在指定时间范围内的 PB 或 PE-TTM 历史走势点。
"""

from dataclasses import dataclass, field
from typing import Optional, List


# ── 请求参数 ──────────────────────────────────────────────────────────────────

# indexValueType 取值
VALUATION_TYPE_MAP = {
    "PETTM": "滚动市盈率 PE-TTM",
    "PB":    "市净率 PB",
}

# range 取值范围
VALUATION_RANGE_MAP = {
    "1n":  "近 1 年",
    "3n":  "近 3 年",
    "5n":  "近 5 年",
    "10n": "近 10 年",
}


# ── 单个估值数据点 ────────────────────────────────────────────────────────────

@dataclass
class ValuationPoint:
    """
    单个估值数据点。

    ┌────────┬────────┬────────────────────────────────────┐
    │ 字段    │ 类型   │ 说明                               │
    ├────────┼────────┼────────────────────────────────────┤
    │ PDATE  │ str    │ 估值日期（如 "2026-07-20"）        │
    │ PETTM  │ float  │ 滚动市盈率（indexValueType=PETTM） │
    │ PB     │ float  │ 市净率（indexValueType=PB）        │
    └────────┴────────┴────────────────────────────────────┘

    注：对于同一只指数，PETTM 和 PB 分开查询（接口按 indexValueType 返回其一）。
        后续 service 层可将两者按 PDATE join 为完整记录后入库。
    """
    PDATE: str = ""
    PETTM: Optional[float] = None
    PB: Optional[float] = None

    @classmethod
    def from_dict(cls, d: dict, value_type: str) -> "ValuationPoint":
        """从原始 dict 构造。

        Args:
            d: 原始 dict，key 包含 "PDATE" 和 value_type（"PETTM" 或 "PB"）
            value_type: 当前查询的估值类型
        """
        point = cls(PDATE=str(d.get("PDATE", "")))
        raw = d.get(value_type)
        if raw is not None:
            parsed = float(raw)
            if value_type == "PETTM":
                point.PETTM = parsed
            elif value_type == "PB":
                point.PB = parsed
        return point


# ── 完整响应 ──────────────────────────────────────────────────────────────────

@dataclass
class ValuationTrendResponse:
    """
    指数估值走势接口的完整响应。

    ┌─────────────┬───────────────────────────────────────────────────┐
    │ 字段         │ 说明                                              │
    ├─────────────┼───────────────────────────────────────────────────┤
    │ items       │ 估值数据点列表（ValuationPoint[]）                 │
    │ total_count │ 数据点数量                                         │
    │ error_code  │ 错误码（0=正常）                                   │
    │ first_error │ 错误描述（成功时为 null）                          │
    │ success     │ 是否成功                                           │
    │ expansion   │ [最小值, 下均值/中位数, 上均值/平均数, 最大值]    │
    │              │ 用于图表辅助线绘制，顺序仅供参考                   │
    │ jf          │ 平台标识（"ali" = 阿里云）                         │
    └─────────────┴───────────────────────────────────────────────────┘
    """
    items: List[ValuationPoint] = field(default_factory=list)
    total_count: int = 0
    error_code: int = 0
    first_error: Optional[str] = None
    success: bool = False
    expansion: List[str] = field(default_factory=list)
    jf: str = ""
