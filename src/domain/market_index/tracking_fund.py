"""
指数跟踪基金领域模型。

定义 getTrackingFundV3 接口的响应数据结构。
该接口用于查询跟踪指定指数的所有基金产品及其费率信息。
"""

from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any


@dataclass
class TrackingFundItem:
    """
    单只跟踪基金数据，对应响应 data[index_code][] 中的每个元素。

    ┌────────────────┬────────┬──────────────────────────────────────────────┐
    │ 字段           │ 类型   │ 说明                                         │
    ├────────────────┼────────┼──────────────────────────────────────────────┤
    │ FCODE          │ str    │ 基金代码                                     │
    │ SHORTNAME      │ str    │ 基金简称                                     │
    │ ESTABDATE      │ str    │ 成立日期 (YYYY-MM-DD)                       │
    │ ENDNAV         │ float  │ 基金资产净值 (万元)                          │
    │ INDEXCODE      │ str    │ 跟踪的指数代码                               │
    │ DISCOUNT       │ float  │ 费率折扣 (0.0 = 不打折, 1.0 = 全折扣)      │
    │ DTZT           │ str    │ 基金类型标签 (1=普通, 2=ETF联接等)          │
    │ ISBUY          │ str    │ 是否可申购 (1=是, 0=否)                     │
    │ ISCLASSC       │ float  │ 是否为 C 类份额 (1.0=C类, 0.0=A类)         │
    │ ISEXCHG        │ str    │ 是否上市交易 (0=否, 1=是)                   │
    │ MAXSG          │ float  │ 单日最大申购金额 (元)                       │
    │ SHRATE7        │ float  │ 7天内赎回费率 (%)                          │
    │ TRKERROR       │ str    │ 跟踪误差 (%)                                 │
    │ TJDLIST        │ str    │ 推荐等级标签 (逗号分隔)                      │
    │ FEATURE        │ str    │ 基金特色标签 (逗号分隔编码)                  │
    │ NEWTEXCH       │ str    │ 新交易场所标识                               │
    │ ZERODISCOUNTFLAG│ str   │ 零折扣标识                                   │
    ├────────────────┼────────┼──────────────────────────────────────────────┤
    │ 收益率字段     │        │ (空字符串或 "-" 表示数据不可用)               │
    │ SYL_D          │ float  │ 日收益率 (%)                                 │
    │ SYL_Z          │ float  │ 周收益率 (%)                                 │
    │ SYL_Y          │ float  │ 近1月收益率 (%)                              │
    │ SYL_3Y         │ float  │ 近3月收益率 (%)                              │
    │ SYL_6Y         │ float  │ 近6月收益率 (%)                              │
    │ SYL_1N         │ float  │ 近1年收益率 (%)                              │
    │ SYL_2N         │ float  │ 近2年收益率 (%)                              │
    │ SYL_3N         │ float  │ 近3年收益率 (%)                              │
    │ SYL_5N         │ float  │ 近5年收益率 (%)                              │
    │ SYL_JN         │ float  │ 今年以来收益率 (%)                           │
    │ SYL_LN         │ float  │ 成立以来收益率 (%)                           │
    │ RZDF           │ float  │ 日涨跌幅 (%) - 同 SYL_D                      │
    ├────────────────┼────────┼──────────────────────────────────────────────┤
    │ 费率字段       │        │ (以下各周期管理费率/申购费率/销售服务费率)   │
    │ RATECOST_Q     │ float  │ 季度持有费率 (%)                             │
    │ RATECOST_HY    │ float  │ 半年度持有费率 (%)                           │
    │ RATECOST_Y     │ float  │ 年度持有费率 (%)                             │
    │ RATECOST_TRY   │ float  │ 近3年平均持有费率 (%)                        │
    │ RATECOST_FY    │ float  │ 近5年平均持有费率 (%)                        │
    │ SUBRERATE_Q    │ float  │ 季度申购费率 (%)                             │
    │ SUBRERATE_HY   │ float  │ 半年度申购费率 (%)                           │
    │ SUBRERATE_Y    │ float  │ 年度申购费率 (%)                             │
    │ SUBRERATE_TRY  │ float  │ 近3年平均申购费率 (%)                        │
    │ SUBRERATE_FY   │ float  │ 近5年平均申购费率 (%)                        │
    │ CSSFEERATE_Q   │ float  │ 季度销售服务费率 (%)                         │
    │ CSSFEERATE_HY  │ float  │ 半年度销售服务费率 (%)                       │
    │ CSSFEERATE_Y   │ float  │ 年度销售服务费率 (%)                         │
    │ CSSFEERATE_TRY │ float  │ 近3年平均销售服务费率 (%)                    │
    │ CSSFEERATE_FY  │ float  │ 近5年平均销售服务费率 (%)                    │
    │ RAW_RATECOST_Q │ float  │ 季度原始持有费率 (折扣前) (%)               │
    │ RAW_RATECOST_HY│ float  │ 半年度原始持有费率 (折扣前) (%)             │
    │ RAW_RATECOST_Y │ float  │ 年度原始持有费率 (折扣前) (%)               │
    │ RAW_RATECOST_TRY│ float │ 近3年平均原始持有费率 (折扣前) (%)          │
    │ RAW_RATECOST_FY│ float  │ 近5年平均原始持有费率 (折扣前) (%)          │
    └────────────────┴────────┴──────────────────────────────────────────────┘
    """
    # ── 基金基础信息 ──
    FCODE: str = ""
    SHORTNAME: str = ""
    ESTABDATE: str = ""
    ENDNAV: float = 0.0
    INDEXCODE: str = ""
    DISCOUNT: float = 0.0
    DTZT: str = ""
    ISBUY: str = ""
    ISCLASSC: float = 0.0
    ISEXCHG: str = ""
    MAXSG: float = 0.0
    SHRATE7: float = 0.0
    TRKERROR: str = ""
    TJDLIST: str = ""
    FEATURE: str = ""
    NEWTEXCH: str = ""
    ZERODISCOUNTFLAG: str = ""

    # ── 各周期收益率 ──
    SYL_D: Optional[float] = None
    SYL_Z: Optional[float] = None
    SYL_Y: Optional[float] = None
    SYL_3Y: Optional[float] = None
    SYL_6Y: Optional[float] = None
    SYL_1N: Optional[float] = None
    SYL_2N: Optional[float] = None
    SYL_3N: Optional[float] = None
    SYL_5N: Optional[float] = None
    SYL_JN: Optional[float] = None
    SYL_LN: Optional[float] = None
    RZDF: Optional[float] = None

    # ── 各周期持有费率 (管理费+托管费) ──
    RATECOST_Q: Optional[float] = None
    RATECOST_HY: Optional[float] = None
    RATECOST_Y: Optional[float] = None
    RATECOST_TRY: Optional[float] = None
    RATECOST_FY: Optional[float] = None

    # ── 各周期申购费率 ──
    SUBRERATE_Q: Optional[float] = None
    SUBRERATE_HY: Optional[float] = None
    SUBRERATE_Y: Optional[float] = None
    SUBRERATE_TRY: Optional[float] = None
    SUBRERATE_FY: Optional[float] = None

    # ── 各周期销售服务费率 (C类特有) ──
    CSSFEERATE_Q: Optional[float] = None
    CSSFEERATE_HY: Optional[float] = None
    CSSFEERATE_Y: Optional[float] = None
    CSSFEERATE_TRY: Optional[float] = None
    CSSFEERATE_FY: Optional[float] = None

    # ── 各周期原始持有费率 (折扣前) ──
    RAW_RATECOST_Q: Optional[float] = None
    RAW_RATECOST_HY: Optional[float] = None
    RAW_RATECOST_Y: Optional[float] = None
    RAW_RATECOST_TRY: Optional[float] = None
    RAW_RATECOST_FY: Optional[float] = None

    @classmethod
    def from_dict(cls, d: dict) -> "TrackingFundItem":
        """从原始 dict 构造 TrackingFundItem。"""
        clean = {}
        for field_name in cls.__dataclass_fields__:
            raw = d.get(field_name)
            field_type = cls.__dataclass_fields__[field_name].type
            if raw is None or raw == "" or raw == "-":
                clean[field_name] = None if field_type is not str else ""
            elif field_type is float:
                clean[field_name] = float(raw)
            elif field_type is int:
                clean[field_name] = int(raw)
            else:
                clean[field_name] = raw
        return cls(**clean)


@dataclass
class TrackingFundResponse:
    """
    指数跟踪基金接口的完整响应。

    ┌────────────┬──────────────────────────────────────────────────┐
    │ 字段       │ 说明                                              │
    ├────────────┼──────────────────────────────────────────────────┤
    │ success    │ 是否成功                                         │
    │ error_code │ 错误码 (0=正常)                                  │
    │ first_error│ 错误描述 (成功时为 None)                         │
    │ total_count│ 请求的指数数量                                    │
    │ items      │ {index_code: [TrackingFundItem]} 的字典           │
    │ expansion  │ 扩展字段 (目前未使用)                             │
    │ jf         │ 环境标识 (prod/dev)                              │
    └────────────┴──────────────────────────────────────────────────┘
    """
    success: bool = False
    error_code: int = 0
    first_error: Optional[str] = None
    total_count: int = 0
    items: Dict[str, List[TrackingFundItem]] = field(default_factory=dict)
    expansion: Any = None
    jf: str = ""

    @classmethod
    def from_json(cls, result: dict) -> "TrackingFundResponse":
        """从接口返回的 JSON dict 构造响应。"""
        resp = cls(
            success=bool(result.get("success", False)),
            error_code=int(result.get("errorCode", -1)),
            first_error=result.get("firstError"),
            total_count=int(result.get("totalCount", 0)),
            expansion=result.get("expansion"),
            jf=result.get("jf", ""),
        )
        if resp.success:
            raw_data: dict = result.get("data", {}) or {}
            for index_code, fund_list in raw_data.items():
                resp.items[index_code] = [
                    TrackingFundItem.from_dict(item) for item in (fund_list or [])
                ]
        return resp
