"""
东方财富证券日线 K 线行情数据查询接口（含资金流向 + 筹码获利比例）。

接口地址：
  https://push2his.eastmoney.com/api/qt/stock/kline/get

该接口来自东方财富行情体系（push2his），返回单只证券的日线 K 线数据，并混入：
1) 资金流向字段（主力/大单/中单/小单净流入）
2) 筹码获利比例（f53：Profit Ratio / 获利盘占比）

本项目的“市场指数”模块通常用于指数数据，但这里的接口同时适用于：
- 指数（沪深/中证跨市场）
- 个股（沪深/创业板/科创/北交所）

因此将其放在 src/API/市场指数 目录，供后续 service 层统一组合使用。


一、secid 规则（非常重要）

接口以 secid 作为唯一标识，格式：{market}.{code}

代码前缀   market 前缀  标的类型                         示例      正确 secid
000xxxx    1           上交所指数（000001 等）            000001    1.000001
399xxxx    0           深交所指数（399998 中证煤炭）      399998    0.399998
930/931/H  2           中证沪港深跨市场指数              H11059    2.H11059 / 2.931238
30xxxx     2           创业板个股                         300750    2.300750
60/68xxxx  1           沪主板 / 科创板个股                600030    1.600030
00xxxx     0           深主板个股                         000063    0.000063
83/87xxxx  8           北交所个股                         831000    8.831000
BKxxxx     90          东财自定义板块（fflow 不可用）     BK000177  90.BK000177

注意：本文件提供 guess_secid_from_code()，用于“尽力推断” market 前缀。
如遇到无法准确判定的标的（例如跨市场指数/特殊代码），建议直接传入 secid。


二、关键请求参数

常用参数（与抓包示例一致）：
- klt=101:K线数据周期类型，101对应日线级别的个股资金流数据，用于指定获取的资金流数据周期
- fqt=0:  复权类型。0=不复权，1=前复权，2=后复权
- lmt:    返回条数限制（默认可取 1/100/200 等）
- end:    截止日期（yyyyMMdd），例如 20260721

fields1 / fields2 控制返回字段：
- fields1: 证券基础信息（code/name/market 等）
- fields2: K 线字段序列（f51-f67），由 data.klines 以字符串数组返回


三、fields2（K 线/资金/筹码）字段映射（f51-f67）

示例返回行（data.klines 的单条）：
  "2026-06-26,3149.32,3035.80,3154.47,3034.64,13888986,11647167818.93,3.81,-3.43,-107.81,1.22,0,0,0,0.00,0,0"

字段解释（综合用户提供说明 + 实测返回）：
- f51: 交易日期（YYYY-MM-DD）
- f52: 实测更符合"开盘价"（open）
- f53: 实测更符合"收盘价"（close）
- f54: 最高价
- f55: 最低价
- f56: 成交量
- f57: 成交额
- f58: 振幅
- f59: 涨跌幅
- f60: 涨跌额
- f61: 换手率
- f62: 主力净流入金额
- f63: 小单净流入金额
- f64: 中单净流入金额
- f65: 大单/特大单净流入金额
- f66/f67: 未在说明中给出（保留）

关于"筹码获利比例"：
用户提供的说明将 f53 标注为"筹码获利比例"，但在本仓库实测数据中 f53 更符合"收盘价"。
因此本实现：
1) 明确提供 OPEN/CLOSE/HIGH/LOW 等 K 线字段，确保可直接用于价格分析。
2) 对"筹码获利比例"字段保留 CHIP_PROFIT_RATIO（当前尝试映射到 f66；若为 0 或明显异常，说明该 secid 未返回该字段或需要其它字段配置）。

本文件会解析上述字段，并将无法解析的数值置为 None。


四、资金流 K 线端点（fflow 系列）

本文件实现了两个 fflow 子端点，用于获取证券的资金流向数据：

1. fflow/daykline/get — 历史日线资金流（已实现 get_security_day_flow_kline）
   用途：获取昨日及历史每日的资金净流入明细（含占比/收盘价/涨跌幅）。
   特点：数据完整（15 列），但当日数据尚未收录（滞后一天）。
   URL: https://push2his.eastmoney.com/api/qt/stock/fflow/daykline/get

2. fflow/kline/get — 当日实时资金流（get_security_today_flow_kline）
   用途：获取当日的资金净流入累计数据（盘中实时、盘后最终）。
   特点：仅返回日期 + 5 个净额字段（无占比/收盘价），但当日可用。
   URL: https://push2his.eastmoney.com/api/qt/stock/fflow/kline/get

注意：两个端点的 klines 行内字段布局不同（一个是 15 列，一个是 6 列），
解析时需使用各自对应的 Dataclass 和 from_kline_str 方法。
"""

import os
import sys
from dataclasses import dataclass, field
from typing import List, Optional, Any, Dict

# 兼容直接运行 `python xxx.py` 的场景
if __name__ == "__main__":
    root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    if root_dir not in sys.path:
        sys.path.insert(0, root_dir)

from src.common.logger import get_logger
from src.common.requests_session import session
from src.domain.user.User import User
from src.common.constant import IOS_CLIENT_INFO, IOS_USER_AGENT, MP_VERSION_DEFAULT, DEFAULT_GTOKEN

logger = get_logger("SecurityDayKline")


_DEFAULT_UT = "a7202e6f901554f7cfadffa430c882bf"

FIELDS1_DEFAULT = "f1,f2,f3,f4,f5,f6,f7,f8,f13"
FIELDS2_DEFAULT = "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61,f62,f63,f64,f65,f66,f67"


def guess_secid_from_code(code: str) -> str:
    """
    根据证券代码尽力推断 secid（market.code）。

    说明：
    - 该推断仅覆盖用户给出的常见规则。
    - 对于跨市场指数（如 H11059/931238）或特殊代码，建议直接传入 secid。

    Args:
        code: 证券代码，例如 "399998" / "600030" / "300750" / "H11059"

    Returns:
        secid 字符串，例如 "0.399998" / "1.600030" / "2.H11059"
    """
    code = (code or "").strip()
    if not code:
        return ""

    u = code.upper()
    if u.startswith("BK"):
        return f"90.{code}"

    if u.startswith(("H", "930", "931")):
        return f"2.{code}"

    if len(code) >= 2 and code[:2] in ("83", "87"):
        return f"8.{code}"

    if len(code) >= 2 and code[:2] == "30":
        return f"2.{code}"

    if len(code) >= 2 and code[:2] in ("60", "68"):
        return f"1.{code}"

    if len(code) >= 2 and code[:2] == "00":
        return f"0.{code}"

    if len(code) >= 2 and code[:2] == "97":
        return f"0.{code}"

    if len(code) >= 3 and code[:3] == "399":
        return f"0.{code}"

    if len(code) >= 3 and code[:3] == "000":
        return f"1.{code}"

    return code


def _to_float(v: Any) -> Optional[float]:
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).strip()
    if s == "" or s == "--":
        return None
    try:
        return float(s)
    except (ValueError, TypeError):
        return None


def _to_int(v: Any) -> Optional[int]:
    if v is None:
        return None
    if isinstance(v, int):
        return int(v)
    if isinstance(v, float):
        return int(v)
    s = str(v).strip()
    if s == "" or s == "--":
        return None
    try:
        return int(float(s))
    except (ValueError, TypeError):
        return None


@dataclass
class SecurityDayKlinePoint:
    """
    日线 K 线数据点（含资金流 + 筹码获利比例）。

    字段含义对齐 fields2（f51-f67），便于按需扩展。
    """

    PDATE: str = ""
    OPEN: Optional[float] = None
    CLOSE: Optional[float] = None
    CHIP_PROFIT_RATIO: Optional[float] = None
    HIGH: Optional[float] = None
    LOW: Optional[float] = None
    VOLUME: Optional[int] = None
    AMOUNT: Optional[float] = None
    AMPLITUDE: Optional[float] = None
    CHG_PCT: Optional[float] = None
    CHG: Optional[float] = None
    TURNOVER: Optional[float] = None
    MAIN_INFLOW: Optional[float] = None
    SMALL_INFLOW: Optional[float] = None
    MEDIUM_INFLOW: Optional[float] = None
    LARGE_INFLOW: Optional[float] = None
    F66: Optional[float] = None
    F67: Optional[float] = None

    @classmethod
    def from_kline_str(cls, kline: str) -> "SecurityDayKlinePoint":
        parts = (kline or "").split(",")
        point = cls(PDATE=parts[0] if parts else "")

        def get(i: int) -> Optional[str]:
            if i < 0 or i >= len(parts):
                return None
            return parts[i]

        point.OPEN = _to_float(get(1))
        point.CLOSE = _to_float(get(2))
        point.HIGH = _to_float(get(3))
        point.LOW = _to_float(get(4))
        point.VOLUME = _to_int(get(5))
        point.AMOUNT = _to_float(get(6))
        point.AMPLITUDE = _to_float(get(7))
        point.CHG_PCT = _to_float(get(8))
        point.CHG = _to_float(get(9))
        point.TURNOVER = _to_float(get(10))
        # kline/get 端点 f62-f65 恒为 0（该端点不返回资金流）
        point.F66 = _to_float(get(15))
        point.F67 = _to_float(get(16))
        point.CHIP_PROFIT_RATIO = point.F66

        return point


# ── 接口 2: 日线资金流 K 线（fflow/daykline/get） ──────────────────────────────


@dataclass
class SecurityDayFlowKlinePoint:
    """
    日线资金流 K 线数据点。

    字段布局对应 fflow/daykline/get 端点（与 kline/get 完全不同）。

    说明：fflow/daykline/get 的 data.klines 会返回 15 列（索引 0-14），对应字段如下：
    - f51: 日期
    - f52: 主力净流入（= 大单净流入 + 超大单净流入）
    - f53: 小单净流入
    - f54: 中单净流入
    - f55: 大单净流入
    - f56: 超大单净流入
    - f57: 主力净流入占比(%)
    - f58: 小单净流入占比(%)
    - f59: 中单净流入占比(%)
    - f60: 大单净流入占比(%)
    - f61: 超大单净流入占比(%)
    - f62: 收盘价
    - f63: 涨跌幅(%)
    - f64/f65: 扩展保留（常见为 0）
    """
    PDATE: str = ""
    MAIN_NET_INFLOW: Optional[float] = None
    SMALL_NET_INFLOW: Optional[float] = None
    MEDIUM_NET_INFLOW: Optional[float] = None
    LARGE_NET_INFLOW: Optional[float] = None
    SUPER_LARGE_NET_INFLOW: Optional[float] = None
    MAIN_NET_INFLOW_RATIO: Optional[float] = None
    SMALL_NET_INFLOW_RATIO: Optional[float] = None
    MEDIUM_NET_INFLOW_RATIO: Optional[float] = None
    LARGE_NET_INFLOW_RATIO: Optional[float] = None
    SUPER_LARGE_NET_INFLOW_RATIO: Optional[float] = None
    CLOSE: Optional[float] = None
    CHG_PCT: Optional[float] = None
    F64: Optional[float] = None
    F65: Optional[float] = None

    @classmethod
    def from_kline_str(cls, kline: str) -> "SecurityDayFlowKlinePoint":
        parts = (kline or "").split(",")
        point = cls(PDATE=parts[0] if parts else "")
        def g(i: int) -> Optional[str]:
            if i < 0 or i >= len(parts): return None
            return parts[i]
        point.MAIN_NET_INFLOW = _to_float(g(1))
        point.SMALL_NET_INFLOW = _to_float(g(2))
        point.MEDIUM_NET_INFLOW = _to_float(g(3))
        point.LARGE_NET_INFLOW = _to_float(g(4))
        point.SUPER_LARGE_NET_INFLOW = _to_float(g(5))
        point.MAIN_NET_INFLOW_RATIO = _to_float(g(6))
        point.SMALL_NET_INFLOW_RATIO = _to_float(g(7))
        point.MEDIUM_NET_INFLOW_RATIO = _to_float(g(8))
        point.LARGE_NET_INFLOW_RATIO = _to_float(g(9))
        point.SUPER_LARGE_NET_INFLOW_RATIO = _to_float(g(10))
        point.CLOSE = _to_float(g(11))
        point.CHG_PCT = _to_float(g(12))
        point.F64 = _to_float(g(13))
        point.F65 = _to_float(g(14))
        return point


def _split_in_out_by_net(net_amount: Optional[float]) -> tuple[float, float]:
    if net_amount is None:
        return 0.0, 0.0
    if net_amount >= 0:
        return float(net_amount), 0.0
    return 0.0, float(-net_amount)


def build_today_main_retail_flow_summary(flow_point: SecurityDayFlowKlinePoint) -> dict:
    """
    生成“当日主力/散户资金”摘要（基于净流入数据）。

    说明：
    - 东财 fflow/daykline/get 提供的是“净流入”，不提供“流入/流出”原始拆分。
    - 这里将净流入按方向拆成“流入/流出”展示：净流入>0 视为流入，净流入<0 视为流出。
    - 若你要实现截图中的“主力流入/主力流出/散户流入/散户流出”（同时有两边的绝对金额），需要额外接口返回总流入/总流出。
    """
    main_net = flow_point.MAIN_NET_INFLOW or 0.0
    retail_net = (flow_point.SMALL_NET_INFLOW or 0.0) + (flow_point.MEDIUM_NET_INFLOW or 0.0)

    main_in, main_out = _split_in_out_by_net(main_net)
    retail_in, retail_out = _split_in_out_by_net(retail_net)

    return {
        "date": flow_point.PDATE,
        "main_net": main_net,
        "main_in": main_in,
        "main_out": main_out,
        "retail_net": retail_net,
        "retail_in": retail_in,
        "retail_out": retail_out,
        "close": flow_point.CLOSE,
        "chg_pct": flow_point.CHG_PCT,
        "main_net_ratio": flow_point.MAIN_NET_INFLOW_RATIO,
    }


@dataclass
class SecurityDayFlowKlineData:
    """fflow/daykline/get 端点 data 节点。"""
    code: str = ""
    market: int = 0
    name: str = ""
    decimal: int = 2
    dktotal: int = 0
    items: List[SecurityDayFlowKlinePoint] = field(default_factory=list)


@dataclass
class SecurityDayFlowKlineResponse:
    """fflow/daykline/get 端点响应结构。"""
    success: bool = False
    rc: int = -1
    data: Optional[SecurityDayFlowKlineData] = None
    first_error: Optional[str] = None


def get_security_day_flow_kline(
    user: User,
    secid: str,
    end: Optional[str] = None,
    lmt: int = 120,
    klt: int = 101,
) -> SecurityDayFlowKlineResponse:
    """
    获取指定证券的日线资金流 K 线（分单净流入 + 收盘价 + 涨跌幅）。

    调用 fflow/daykline/get 端点，返回的分单净流入字段对个股有效。
    指数端点也会返回数据（总净流入等），但分单数据可能为 0。

    Args:
        user:   User 对象
        secid:  证券标识 market.code
        end:    截止日期（yyyyMMdd），默认取最新数据
        lmt:    返回条数限制，默认 120，最大 120
        klt:    K 线类型，101=日线

    Returns:
        SecurityDayFlowKlineResponse，成功时 data.items 为 SecurityDayFlowKlinePoint 列表
    """
    if not secid:
        return SecurityDayFlowKlineResponse(success=False, rc=-1, first_error="secid 不能为空")

    lmt = min(max(lmt, 1), 120)
    logger.info(f"获取证券日线资金流K线: secid={secid}, end={end or ''}, lmt={lmt}")

    url = "https://push2his.eastmoney.com/api/qt/stock/fflow/daykline/get"
    headers = _build_headers()
    params = _build_query_params(
        secid=secid, end=end, lmt=lmt, klt=klt, fqt=0,
        fields1=FIELDS1_DEFAULT, fields2=FIELDS2_DEFAULT, ut=_DEFAULT_UT,
    )
    params.pop("fqt", None)

    try:
        response = session.get(url, headers=headers, params=params, verify=False, timeout=30)
        response.raise_for_status()
        result: Dict[str, Any] = response.json() or {}

        rc = int(result.get("rc", -1))
        resp = SecurityDayFlowKlineResponse(
            success=rc == 0 and bool(result.get("data")),
            rc=rc,
        )

        if not resp.success:
            resp.first_error = f"请求失败: rc={resp.rc}"
            logger.error(resp.first_error)
            return resp

        raw_data = result.get("data") or {}
        data_obj = SecurityDayFlowKlineData(
            code=str(raw_data.get("code", "") or ""),
            market=_to_int(raw_data.get("market")) or 0,
            name=str(raw_data.get("name", "") or ""),
            decimal=_to_int(raw_data.get("decimal")) or 2,
            dktotal=_to_int(raw_data.get("dktotal")) or 0,
        )
        raw_klines = raw_data.get("klines", []) or []
        data_obj.items = [SecurityDayFlowKlinePoint.from_kline_str(k) for k in raw_klines]
        resp.data = data_obj

        logger.info(
            f"成功获取 {len(data_obj.items)} 条资金流K线, code={data_obj.code}, name={data_obj.name}"
        )
        return resp

    except Exception as e:
        logger.error(f"获取证券日线资金流K线异常: {e}")
        return SecurityDayFlowKlineResponse(success=False, rc=-1, first_error=str(e))


# ── 接口 3: 当日实时资金流 K 线（fflow/kline/get） ──────────────────────────


@dataclass
class SecurityTodayFlowKlinePoint:
    """
    当日实时资金流 K 线数据点。

    字段布局对应 fflow/kline/get 端点（与 fflow/daykline/get 不同）。
    klines 返回 6 列（索引 0-5），仅含净额，无占比/收盘价。

    - f51: 日期
    - f52: 主力净流入（= 大单净流入 + 超大单净流入）
    - f53: 小单净流入
    - f54: 中单净流入
    - f55: 大单净流入
    - f56: 超大单净流入
    """
    PDATE: str = ""
    MAIN_NET_INFLOW: Optional[float] = None
    SMALL_NET_INFLOW: Optional[float] = None
    MEDIUM_NET_INFLOW: Optional[float] = None
    LARGE_NET_INFLOW: Optional[float] = None
    SUPER_LARGE_NET_INFLOW: Optional[float] = None

    @classmethod
    def from_kline_str(cls, kline: str) -> "SecurityTodayFlowKlinePoint":
        parts = (kline or "").split(",")
        point = cls(PDATE=parts[0] if parts else "")
        def g(i: int) -> Optional[str]:
            if i < 0 or i >= len(parts): return None
            return parts[i]
        point.MAIN_NET_INFLOW = _to_float(g(1))
        point.SMALL_NET_INFLOW = _to_float(g(2))
        point.MEDIUM_NET_INFLOW = _to_float(g(3))
        point.LARGE_NET_INFLOW = _to_float(g(4))
        point.SUPER_LARGE_NET_INFLOW = _to_float(g(5))
        return point


@dataclass
class SecurityTodayFlowKlineData:
    """fflow/kline/get 端点 data 节点（不含 code/name 字段）。"""
    dktotal: int = 0
    items: List[SecurityTodayFlowKlinePoint] = field(default_factory=list)


@dataclass
class SecurityTodayFlowKlineResponse:
    """fflow/kline/get 端点响应结构。"""
    success: bool = False
    rc: int = -1
    data: Optional[SecurityTodayFlowKlineData] = None
    first_error: Optional[str] = None


def get_security_today_flow_kline(
    user: User,
    secid: str,
    lmt: int = 1,
    klt: int = 101,
) -> SecurityTodayFlowKlineResponse:
    """
    获取指定证券的当日实时资金流 K 线（盘中累计/盘后最终）。

    调用 fflow/kline/get 端点，仅返回核心净额字段（6 列），无占比/收盘价。
    与 get_security_day_flow_kline（历史日线，滞后一天）互补：
    - 历史查询用 daykline/get（15 列，含占比/收盘价）
    - 当日数据用 kline/get（6 列，仅净额）

    Args:
        user:   User 对象
        secid:  证券标识 market.code
        lmt:    返回条数限制，默认 1（当日数据放在最近一条）
        klt:    K 线类型，仅支持 101（日线），无分钟级支持

    Returns:
        SecurityTodayFlowKlineResponse，成功时 data.items 为 SecurityTodayFlowKlinePoint 列表
    """
    if not secid:
        return SecurityTodayFlowKlineResponse(success=False, rc=-1, first_error="secid 不能为空")

    logger.info(f"获取当日资金流K线: secid={secid}, lmt={lmt}")

    url = "https://push2his.eastmoney.com/api/qt/stock/fflow/kline/get"
    headers = _build_headers()
    params = _build_query_params(
        secid=secid, end="", lmt=lmt, klt=klt, fqt=0,
        fields1=FIELDS1_DEFAULT,
        fields2="f51,f52,f53,f54,f55,f56",
        ut=_DEFAULT_UT,
    )
    params.pop("fqt", None)

    try:
        response = session.get(url, headers=headers, params=params, verify=False, timeout=30)
        response.raise_for_status()
        result: Dict[str, Any] = response.json() or {}

        rc = int(result.get("rc", -1))
        resp = SecurityTodayFlowKlineResponse(
            success=rc == 0 and bool(result.get("data")),
            rc=rc,
        )

        if not resp.success:
            resp.first_error = f"请求失败: rc={resp.rc}"
            logger.error(resp.first_error)
            return resp

        raw_data = result.get("data") or {}
        data_obj = SecurityTodayFlowKlineData(
            dktotal=_to_int(raw_data.get("dktotal")) or 0,
        )
        raw_klines = raw_data.get("klines", []) or []
        data_obj.items = [SecurityTodayFlowKlinePoint.from_kline_str(k) for k in raw_klines]
        resp.data = data_obj

        logger.info(
            f"成功获取 {len(data_obj.items)} 条当日资金流K线"
        )
        return resp

    except Exception as e:
        logger.error(f"获取当日资金流K线异常: {e}")
        return SecurityTodayFlowKlineResponse(success=False, rc=-1, first_error=str(e))


@dataclass
class SecurityDayKlineData:
    """data 节点的结构化映射。"""

    code: str = ""
    market: int = 0
    name: str = ""
    decimal: int = 2
    dktotal: int = 0
    preKPrice: Optional[float] = None
    prePrice: Optional[float] = None
    qtMiscType: Optional[int] = None
    version: Optional[int] = None
    items: List[SecurityDayKlinePoint] = field(default_factory=list)


@dataclass
class SecurityDayKlineResponse:
    """
    东方财富 push2his K 线接口响应结构。

    顶层字段：
    - rc: 0 表示成功
    - rt/svr/lt/full/dlmkts/dsc: 由东财服务返回的元信息，业务上一般不依赖，但保留以便排障
    """

    success: bool = False
    rc: int = -1
    rt: Optional[int] = None
    svr: Optional[int] = None
    lt: Optional[int] = None
    full: Optional[int] = None
    dlmkts: str = ""
    dsc: str = ""
    data: Optional[SecurityDayKlineData] = None
    first_error: Optional[str] = None


def get_security_day_kline(
    user: User,
    secid: str,
    end: Optional[str] = None,
    lmt: int = 120,
    klt: int = 101,
    fqt: int = 0,
    fields1: str = FIELDS1_DEFAULT,
    fields2: str = FIELDS2_DEFAULT,
    ut: str = _DEFAULT_UT,
) -> SecurityDayKlineResponse:
    """
    获取指定证券的日线 K 线（含资金流向与筹码获利比例）。

    Args:
        user:   User 对象（与项目其它 API 保持一致；本接口通常不依赖登录态，但保留参数以兼容调用链）
        secid: 证券标识 market.code，例如 "0.399998" / "1.600030" / "2.H11059"
        end:   截止日期（yyyyMMdd）。不传时默认使用 20500101 以获取“最新可用数据”
        lmt:   返回条数限制，默认 120，最大 120（超出自动截断）
        klt:   K 线类型，101=日线
        fqt:   复权类型，0=不复权
        fields1/fields2: 字段控制，默认使用抓包中常用字段集
        ut:    东财接口固定参数（抓包值），一般无需变更

    Returns:
        SecurityDayKlineResponse，成功时 data.items 为 SecurityDayKlinePoint 列表
    """
    if not secid:
        return SecurityDayKlineResponse(success=False, rc=-1, first_error="secid 不能为空")

    # lmt 上限 120
    lmt = min(max(lmt, 1), 120)

    logger.info(f"获取证券日线K线: secid={secid}, end={end or ''}, lmt={lmt}, klt={klt}, fqt={fqt}")

    url = "https://push2his.eastmoney.com/api/qt/stock/kline/get"
    headers = _build_headers()
    params = _build_query_params(
        secid=secid,
        end=end,
        lmt=lmt,
        klt=klt,
        fqt=fqt,
        fields1=fields1,
        fields2=fields2,
        ut=ut,
    )

    try:
        response = session.get(url, headers=headers, params=params, verify=False, timeout=30)
        response.raise_for_status()
        result: Dict[str, Any] = response.json() or {}

        rc = int(result.get("rc", -1))
        resp = SecurityDayKlineResponse(
            success=rc == 0 and bool(result.get("data")),
            rc=rc,
            rt=_to_int(result.get("rt")),
            svr=_to_int(result.get("svr")),
            lt=_to_int(result.get("lt")),
            full=_to_int(result.get("full")),
            dlmkts=str(result.get("dlmkts", "") or ""),
            dsc=str(result.get("dsc", "") or ""),
        )

        if not resp.success:
            resp.first_error = f"请求失败: rc={resp.rc}"
            logger.error(resp.first_error)
            return resp

        raw_data: Dict[str, Any] = result.get("data") or {}
        data_obj = SecurityDayKlineData(
            code=str(raw_data.get("code", "") or ""),
            market=_to_int(raw_data.get("market")) or 0,
            name=str(raw_data.get("name", "") or ""),
            decimal=_to_int(raw_data.get("decimal")) or 2,
            dktotal=_to_int(raw_data.get("dktotal")) or 0,
            preKPrice=_to_float(raw_data.get("preKPrice")),
            prePrice=_to_float(raw_data.get("prePrice")),
            qtMiscType=_to_int(raw_data.get("qtMiscType")),
            version=_to_int(raw_data.get("version")),
        )

        raw_klines = raw_data.get("klines", []) or []
        data_obj.items = [SecurityDayKlinePoint.from_kline_str(k) for k in raw_klines]
        resp.data = data_obj

        logger.info(
            f"成功获取 {len(data_obj.items)} 条日线K线, code={data_obj.code}, name={data_obj.name}, "
            f"dktotal={data_obj.dktotal}"
        )
        return resp

    except Exception as e:
        logger.error(f"获取证券日线K线异常: {e}")
        return SecurityDayKlineResponse(success=False, rc=-1, first_error=str(e))


def _build_headers() -> dict:
    """
    构建请求头。

    说明：
    - push2his 接口通常不需要 Cookie/登录态；抓包示例中的 Cookie 可省略
    - 为了减少被风控概率，保留 TTJJ 客户端的常见头（与其它 API 一致）
    """
    return {
        "Accept": "*/*",
        "Accept-Encoding": "gzip, deflate, br",
        "Accept-Language": "zh-Hans-CN;q=1",
        "Connection": "keep-alive",
        "GTOKEN": DEFAULT_GTOKEN,
        "MP-VERSION": MP_VERSION_DEFAULT,
        "Referer": "https://mpservice.com/7d7b3460cd40444ba58cdabdfae34442/release/pages/index-detail/index",
        "User-Agent": IOS_USER_AGENT,
        "clientInfo": IOS_CLIENT_INFO,
        "Host": "push2his.eastmoney.com",
    }


def _build_query_params(
    secid: str,
    end: Optional[str],
    lmt: int,
    klt: int,
    fqt: int,
    fields1: str,
    fields2: str,
    ut: str,
) -> dict:
    params = {
        "authorityType": "fa",
        "dpt": "ttjj.xtb",
        "end": end or "20500101",
        "fields1": fields1,
        "fields2": fields2,
        "fqt": str(fqt),
        "klt": str(klt),
        "lmt": str(lmt),
        "secid": secid,
        "ut": ut,
    }
    return params


if __name__ == "__main__":
    from src.common.constant import DEFAULT_USER
    from src.API.登录接口.login import ensure_user_fresh

    print("Refreshing user token...")
    user = ensure_user_fresh(DEFAULT_USER)

    test_code = "399998"
    test_secid = guess_secid_from_code(test_code)
    print(f"secid guess: code={test_code} -> secid={test_secid}")

    # 获取 K 线数据
    resp = get_security_day_kline(user, secid=test_secid, lmt=5, klt=101, fqt=0)
    if not resp.success or not resp.data:
        print(f"❌ K线请求失败: {resp.first_error}")
        raise SystemExit(1)

    # 获取历史资金流数据 (fflow/daykline/get)
    flow_resp = get_security_day_flow_kline(user, secid=test_secid, lmt=5)
    if not flow_resp.success or not flow_resp.data:
        print(f"❌ 历史资金流请求失败: {flow_resp.first_error}")
        raise SystemExit(1)

    # 获取当日资金流数据 (fflow/kline/get)
    today_flow_resp = get_security_today_flow_kline(user, secid=test_secid, lmt=5)
    if not today_flow_resp.success or not today_flow_resp.data:
        print(f"⚠️ 当日资金流请求失败: {today_flow_resp.first_error}")

    # 合并资金流数据：历史日线 + 当日
    flow_by_date = {p.PDATE: p for p in flow_resp.data.items}
    if today_flow_resp.success and today_flow_resp.data:
        for tp in today_flow_resp.data.items:
            if tp.PDATE not in flow_by_date:
                flow_by_date[tp.PDATE] = tp

    print(f"\n{'='*60}")
    print(f"{resp.data.name}({resp.data.code}) - K线与资金流合并数据")
    print(f"{'='*60}")

    kline_fields = [
        ("OPEN", "开盘"),
        ("CLOSE", "收盘"),
        ("HIGH", "最高"),
        ("LOW", "最低"),
        ("VOLUME", "成交量"),
        ("AMOUNT", "成交额"),
        ("AMPLITUDE", "振幅%"),
        ("CHG_PCT", "涨跌幅%"),
        ("CHG", "涨跌额"),
        ("TURNOVER", "换手率%"),
    ]

    for i, kp in enumerate(resp.data.items[:5]):
        date = kp.PDATE
        print(f"\n  --- #{i+1} {date} ---")

        # K 线指标
        kline_parts = []
        for attr, label in kline_fields:
            v = getattr(kp, attr)
            if v is None:
                kline_parts.append(f"{label}=None")
            elif isinstance(v, float):
                kline_parts.append(f"{label}={v:.2f}")
            else:
                kline_parts.append(f"{label}={v}")
        for j in range(0, len(kline_parts), 4):
            print("    " + "  ".join(kline_parts[j:j+4]))

        # 资金流指标（兼容 SecurityDayFlowKlinePoint 和 SecurityTodayFlowKlinePoint）
        fp = flow_by_date.get(date)
        if fp:
            # 判断是否为历史日线点（含 RATIO 字段）
            has_ratio = hasattr(fp, 'MAIN_NET_INFLOW_RATIO') and fp.MAIN_NET_INFLOW_RATIO is not None

            main_net = fp.MAIN_NET_INFLOW or 0.0
            super_large = getattr(fp, 'SUPER_LARGE_NET_INFLOW', None)
            large = getattr(fp, 'LARGE_NET_INFLOW', None)
            medium = getattr(fp, 'MEDIUM_NET_INFLOW', None)
            small = getattr(fp, 'SMALL_NET_INFLOW', None)

            flow_parts = [
                f"主力净流入={main_net:,.2f}",
            ]
            if has_ratio:
                flow_parts.append(f"净占比={fp.MAIN_NET_INFLOW_RATIO}%")
            flow_parts += [
                f"超大单={super_large:,.2f}" if super_large is not None else "超大单=None",
                f"大单={large:,.2f}" if large is not None else "大单=None",
                f"中单={medium:,.2f}" if medium is not None else "中单=None",
                f"小单={small:,.2f}" if small is not None else "小单=None",
            ]
            print("    资金流: " + "  ".join(flow_parts[:3]))
            print("            " + "  ".join(flow_parts[3:]))

            # 净流入汇总（主力/散户）
            main_net = fp.MAIN_NET_INFLOW or 0.0
            retail_net = (fp.SMALL_NET_INFLOW or 0.0) + (fp.MEDIUM_NET_INFLOW or 0.0)
            print(f"    主力净={main_net:+,.2f}  散户净={retail_net:+,.2f}  总计净={main_net+retail_net:+,.2f}")
        else:
            print("    资金流: 无(fflow 无此日期数据)")


