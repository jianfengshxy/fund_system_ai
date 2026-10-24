# -*- coding: utf-8 -*-
"""
第三方指数估值查询模块。

当天天基金 API 不支持的指数（如海外 S&P 指数、MSCI 指数等）需要查询估值时，
通过本模块从第三方数据源获取价格、涨跌幅等实时数据。

## 数据源

| source      | 说明                                        | 可达性            |
|-------------|---------------------------------------------|-------------------|
| eastmoney   | 东方财富全球指数行情（海外指数为主）        | 国内环境稳定       |
| tencent_us  | 腾讯证券行情接口（美股/ETF）                | 国内环境稳定       |
| sina_us     | 新浪财经行情接口（美股/ETF）                | 国内环境稳定       |
| yahoo_finance | Yahoo Finance v8 Chart API（美股/ETF/指数）| 海外环境，FC 会 403 |
| investing_com | investing.com 页面解析（备用）              | 反爬严格，不推荐   |

## 扩展方式

在 `THIRD_PARTY_INDEX_CONFIG` 中新增条目即可添加新的指数/数据源：

    THIRD_PARTY_INDEX_CONFIG["NEW_CODE"] = {
        "name": "指数名称",
        "source": "eastmoney",       # 首选数据源
        "secid": "100.GDAXI",        # 东财行情代码（market.code），eastmoney 源使用
        "symbol": "^GDAXI",          # Yahoo Finance 代码（备用源，eastmoney 时也需填写）
        "currency": "EUR",
        "fallback_sources": ["yahoo_finance"],  # 备用源，按顺序尝试
    }

如需支持新的数据源，只需添加对应的 parser 函数并在 `_FETCHERS` 中注册即可。
"""

import re
import os
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional, Dict, List
from urllib.parse import quote

import requests

# 兼容直接运行 `python xxx.py` 的场景
if __name__ == "__main__":
    root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    if root_dir not in sys.path:
        sys.path.insert(0, root_dir)

from src.common.logger import get_logger
from src.common.requests_session import session as shared_session

logger = get_logger(__name__)


# ── 数据模型 ──────────────────────────────────────────────────────────────────


@dataclass
class ThirdPartyValuation:
    """第三方指数估值结果。"""

    index_code: str                          # 指数代码
    price: float                             # 当前价格
    change_amount: float = 0                 # 涨跌额
    change_pct: float = 0                    # 涨跌幅（%）
    update_time: str = ""                    # 更新时间
    currency: str = ""                       # 货币单位
    source: str = ""                         # 数据源标识
    day_high: Optional[float] = None         # 当日最高
    day_low: Optional[float] = None          # 当日最低
    prev_close: Optional[float] = None       # 前收盘价
    success: bool = True
    error: str = ""


# ── 第三方指数配置注册表 ──────────────────────────────────────────────────────
#
# 新增指数/数据源只需在此字典中添加条目。
#  key:      指数代码（与基金 INDEXCODE 字段一致）
#  value:    { name, source, symbol, currency, fallback_sources }
#
# 说明：`source` 为首选数据源，`fallback_sources` 为按顺序尝试的备用源。
#       各源优先使用国内可达的腾讯/新浪行情，避免 FC 环境访问海外源被 403。

THIRD_PARTY_INDEX_CONFIG: Dict[str, dict] = {
    "SPCDSSI": {
        "name": "标普美国品质消费股票",
        "source": "tencent_us",
        "symbol": "XLY",                       # 美股 XLY ETF 跟踪该指数
        "currency": "USD",
        "fallback_sources": ["sina_us", "yahoo_finance"],
    },
}


# ── 对外接口 ──────────────────────────────────────────────────────────────────


def is_third_party_index(index_code: str) -> bool:
    """判断指数代码是否在第三方数据源配置中。"""
    return index_code in THIRD_PARTY_INDEX_CONFIG


def get_index_config(index_code: str) -> Optional[dict]:
    """获取指数的第三方数据源配置，不存在返回 None。"""
    return THIRD_PARTY_INDEX_CONFIG.get(index_code)


def fetch_valuation(index_code: str) -> ThirdPartyValuation:
    """
    根据指数代码从第三方数据源查询估值数据。

    按配置顺序依次尝试数据源（首选 + fallback），返回第一个成功的结果。

    Args:
        index_code: 指数代码（如 "SPCDSSI"）。

    Returns:
        ThirdPartyValuation，success=True 表示查询成功。
    """
    config = THIRD_PARTY_INDEX_CONFIG.get(index_code)
    if not config:
        return ThirdPartyValuation(
            index_code=index_code,
            price=0,
            success=False,
            error="未找到该指数的第三方数据源配置",
        )

    # 组装有序数据源列表：首选 + 备用
    sources: List[str] = [config["source"]] + config.get("fallback_sources", [])
    currency = config.get("currency", "")

    errors = []
    for source in sources:
        fetch_func = _FETCHERS.get(source)
        if not fetch_func:
            errors.append(f"不支持的数据源类型: {source}")
            continue
        try:
            result = fetch_func(config)
        except Exception as e:
            logger.warning(f"[{index_code}] 数据源[{source}]查询异常: {e}")
            errors.append(f"{source}: {e}")
            continue

        result.index_code = index_code
        result.source = source
        result.currency = result.currency or currency
        if result.success:
            logger.info(
                f"[{index_code}] {config['name']} 第三方估值(来源={source}): "
                f"价格={result.price}, 涨跌={result.change_pct:+.2f}%, "
                f"时间={result.update_time}"
            )
            return result
        errors.append(f"{source}: {result.error}")

    return ThirdPartyValuation(
        index_code=index_code,
        price=0,
        source=sources[0] if sources else "",
        success=False,
        error="; ".join(errors) if errors else "所有数据源均失败",
    )


# ── 数据源解析器 ──────────────────────────────────────────────────────────────


def _fetch_tencent_us(config: dict) -> ThirdPartyValuation:
    """
    腾讯证券行情接口（美股/ETF）。

    URL: https://qt.gtimg.cn/q=us{XLY}
    返回（GBK 编码，按 ~ 分隔）：
      [0] 200, [1] 名称, [2] 代码, [3] 最新价, [4] 昨收, [5] 今开,
      [30] 时间, [31] 涨跌额, [32] 涨跌幅(%), [33] 最高, [34] 最低, [35] 货币
    """
    symbol = config.get("symbol")
    if not symbol:
        return ThirdPartyValuation(index_code="", price=0, success=False,
                                    error="配置缺少 symbol 字段")

    url = f"https://qt.gtimg.cn/q=us{symbol}"
    headers = {"User-Agent": "Mozilla/5.0", "Referer": "https://gu.qq.com/"}
    try:
        resp = shared_session.get(url, headers=headers, timeout=15, verify=False)
        resp.raise_for_status()
        resp.encoding = "gbk"
        text = resp.text
    except requests.RequestException as e:
        return ThirdPartyValuation(index_code="", price=0, success=False, error=str(e))

    m = re.search(r'v_us\w+="([^"]+)"', text)
    if not m:
        return ThirdPartyValuation(index_code="", price=0, success=False,
                                    error=f"响应格式异常: {text[:100]}")
    fields = m.group(1).split("~")
    try:
        price = float(fields[3])
        prev_close = float(fields[4]) if fields[4] else None
        change_amount = float(fields[31]) if fields[31] else None
        change_pct = float(fields[32]) if fields[32] else None
        day_high = float(fields[33]) if fields[33] else None
        day_low = float(fields[34]) if fields[34] else None
        update_time = fields[30] if len(fields) > 30 else ""
        currency = fields[35] if len(fields) > 35 else ""
    except (ValueError, IndexError) as e:
        return ThirdPartyValuation(index_code="", price=0, success=False,
                                    error=f"字段解析失败: {e}")

    return ThirdPartyValuation(
        index_code="",
        price=price,
        change_amount=change_amount or 0,
        change_pct=change_pct or 0,
        update_time=update_time,
        currency=currency,
        day_high=day_high,
        day_low=day_low,
        prev_close=prev_close,
    )


def _fetch_eastmoney(config: dict) -> ThirdPartyValuation:
    """
    东方财富全球指数行情接口（海外指数为主，国内环境稳定可达）。

    URL: https://push2.eastmoney.com/api/qt/stock/get
    参数: secid={market}.{code}  (如 100.GDAXI / 100.FCHI / 100.FTSE / 100.NDX100)
    返回 JSON（fltt=2 时为浮点）：
      data.f43   最新价
      data.f60   昨收
      data.f86   更新时间（unix 秒）
      data.f170  涨跌幅（%）
    """
    secid = config.get("secid")
    if not secid:
        return ThirdPartyValuation(index_code="", price=0, success=False,
                                    error="配置缺少 secid 字段")

    url = "https://push2.eastmoney.com/api/qt/stock/get"
    params = {
        "ut": "fa5fd1943c7b386f172d6893dbfba10b",
        "invt": "2",
        "fltt": "2",
        "fields": "f43,f57,f58,f60,f86,f170",
        "secid": secid,
    }
    try:
        resp = shared_session.get(url, params=params, timeout=15, verify=False)
        resp.raise_for_status()
        data = resp.json()
    except (requests.RequestException, ValueError) as e:
        return ThirdPartyValuation(index_code="", price=0, success=False, error=str(e))

    d = (data or {}).get("data") or {}
    price = d.get("f43")
    if price is None:
        return ThirdPartyValuation(index_code="", price=0, success=False,
                                    error=f"响应缺少价格字段: {str(data)[:120]}")

    change_pct = d.get("f170")
    prev_close = d.get("f60")

    update_time = ""
    ts = d.get("f86")
    if ts:
        try:
            update_time = datetime.fromtimestamp(int(ts), tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        except (ValueError, OSError, OverflowError):
            update_time = ""

    change_amount = None
    if prev_close:
        try:
            change_amount = float(price) - float(prev_close)
        except (ValueError, TypeError):
            change_amount = None

    return ThirdPartyValuation(
        index_code="",
        price=float(price),
        change_amount=change_amount,
        change_pct=float(change_pct or 0),
        update_time=update_time,
        currency=config.get("currency", ""),
        prev_close=float(prev_close) if prev_close else None,
    )


def _fetch_sina_us(config: dict) -> ThirdPartyValuation:
    """
    新浪财经行情接口（美股/ETF）。

    URL: https://hq.sinajs.cn/list=gb_{symbol.lower()}
    返回（GB18030 编码，按 , 分隔）：
      [0] 名称, [1] 最新价, [2] 涨跌幅(%), [3] 时间, [4] 涨跌额,
      [5] 今开, [6] 最高, [7] 最低, [8] 52周最高, [9] 52周最低, [26] 昨收
    """
    symbol = config.get("symbol")
    if not symbol:
        return ThirdPartyValuation(index_code="", price=0, success=False,
                                    error="配置缺少 symbol 字段")

    url = f"https://hq.sinajs.cn/list=gb_{symbol.lower()}"
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Referer": "https://finance.sina.com.cn",
    }
    try:
        resp = shared_session.get(url, headers=headers, timeout=15, verify=False)
        resp.raise_for_status()
        resp.encoding = "gb18030"
        text = resp.text
    except requests.RequestException as e:
        return ThirdPartyValuation(index_code="", price=0, success=False, error=str(e))

    m = re.search(r'="([^"]*)"', text)
    if not m or not m.group(1):
        return ThirdPartyValuation(index_code="", price=0, success=False,
                                    error=f"响应为空或格式异常: {text[:100]}")
    fields = m.group(1).split(",")
    try:
        price = float(fields[1])
        change_pct = float(fields[2]) if fields[2] else None
        update_time = fields[3]
        change_amount = float(fields[4]) if fields[4] else None
        day_high = float(fields[6]) if fields[6] else None
        day_low = float(fields[7]) if fields[7] else None
        prev_close = float(fields[26]) if len(fields) > 26 and fields[26] else None
    except (ValueError, IndexError) as e:
        return ThirdPartyValuation(index_code="", price=0, success=False,
                                    error=f"字段解析失败: {e}")

    return ThirdPartyValuation(
        index_code="",
        price=price,
        change_amount=change_amount or 0,
        change_pct=change_pct or 0,
        update_time=update_time,
        day_high=day_high,
        day_low=day_low,
        prev_close=prev_close,
    )


def _fetch_sina_global(config: dict) -> ThirdPartyValuation:
    """
    新浪全球指数行情（国内可达、适合 FC 环境兜底）。

    URL: https://hq.sinajs.cn/list=b_{CODE}

    返回示例：
      var hq_str_b_DAX="德国DAX指数,26015.0600,385.82,1.51,9/26/2025,2025-09-26,2026-08-03,19:43:51,...";

    字段（逗号分隔）常见含义：
      [0] 名称
      [1] 最新价
      [2] 涨跌额
      [3] 涨跌幅(%)
      [6] 日期(YYYY-MM-DD)
      [7] 时间(HH:MM:SS)
    """
    symbol = config.get("sina_code") or config.get("symbol")
    if not symbol:
        return ThirdPartyValuation(index_code="", price=0, success=False, error="配置缺少 sina_code 字段")

    url = f"https://hq.sinajs.cn/list=b_{str(symbol).upper()}"
    headers = {"User-Agent": "Mozilla/5.0", "Referer": "https://finance.sina.com.cn"}
    try:
        resp = shared_session.get(url, headers=headers, timeout=10, verify=False)
        resp.raise_for_status()
        resp.encoding = "gbk"
        text = resp.text
    except requests.RequestException as e:
        return ThirdPartyValuation(index_code="", price=0, success=False, error=str(e))

    m = re.search(r'="([^"]*)"', text)
    if not m or not m.group(1):
        return ThirdPartyValuation(index_code="", price=0, success=False, error=f"响应为空或格式异常: {text[:120]}")

    fields = m.group(1).split(",")
    if len(fields) < 4:
        return ThirdPartyValuation(index_code="", price=0, success=False, error=f"字段数量不足: {fields}")

    try:
        price = float(fields[1])
        change_amount = float(fields[2]) if fields[2] else None
        change_pct = float(fields[3]) if fields[3] else None
    except ValueError as e:
        return ThirdPartyValuation(index_code="", price=0, success=False, error=f"字段解析失败: {e}")

    update_time = ""
    if len(fields) >= 8 and fields[6] and fields[7]:
        update_time = f"{fields[6]} {fields[7]}"
    elif len(fields) >= 6 and fields[5]:
        update_time = fields[5]

    prev_close = None
    day_high = None
    day_low = None
    if len(fields) >= 12:
        try:
            prev_close = float(fields[8]) if fields[8] else None
            day_high = float(fields[10]) if fields[10] else None
            day_low = float(fields[11]) if fields[11] else None
        except ValueError:
            pass

    return ThirdPartyValuation(
        index_code="",
        price=price,
        change_amount=change_amount or 0,
        change_pct=change_pct or 0,
        update_time=update_time,
        currency=config.get("currency", ""),
        day_high=day_high,
        day_low=day_low,
        prev_close=prev_close,
    )


def _fetch_yahoo_finance(config: dict) -> ThirdPartyValuation:
    """
    Yahoo Finance v8 Chart API（备用，FC 环境可能 403）。

    返回数据示例：
      {"chart": {"result": [{"meta": {
          "symbol": "XLY", "currency": "USD",
          "regularMarketPrice": 116.045, "chartPreviousClose": 112.39,
          "regularMarketDayHigh": 116.125, "regularMarketDayLow": 114.97,
          "regularMarketTime": 1785519262
      }}]}}
    """
    symbol = config.get("symbol")
    if not symbol:
        return ThirdPartyValuation(
            index_code="", price=0, success=False,
            error="配置缺少 symbol 字段",
        )

    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{quote(symbol, safe='')}"
    params = {"interval": "1d", "range": "1d"}
    headers = {"User-Agent": "Mozilla/5.0"}

    try:
        resp = shared_session.get(url, params=params, headers=headers, timeout=15, verify=False)
        resp.raise_for_status()
        data = resp.json()
    except requests.RequestException as e:
        return ThirdPartyValuation(index_code="", price=0, success=False, error=str(e))
    except ValueError as e:
        return ThirdPartyValuation(index_code="", price=0, success=False, error=f"JSON 解析失败: {e}")

    try:
        result = data["chart"]["result"][0]
        meta = result["meta"]
    except (KeyError, IndexError) as e:
        return ThirdPartyValuation(index_code="", price=0, success=False,
                                    error=f"响应结构异常: {e}")

    price = meta.get("regularMarketPrice", 0)
    prev_close = meta.get("chartPreviousClose", price)
    change_amount = price - prev_close
    change_pct = (change_amount / prev_close * 100) if prev_close else 0

    unixtime = meta.get("regularMarketTime")
    if unixtime:
        update_time = datetime.fromtimestamp(unixtime, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    else:
        update_time = ""

    return ThirdPartyValuation(
        index_code="",
        price=price,
        change_amount=round(change_amount, 4),
        change_pct=round(change_pct, 4),
        update_time=update_time,
        currency=meta.get("currency", ""),
        day_high=meta.get("regularMarketDayHigh"),
        day_low=meta.get("regularMarketDayLow"),
        prev_close=prev_close,
    )


def _fetch_investing_com(config: dict) -> ThirdPartyValuation:
    """
    investing.com 页面解析（备用，反爬严格）。

    investing.com 对非浏览器请求有严格的反爬策略，可能会返回 403。
    """
    url = config.get("url")
    if not url:
        return ThirdPartyValuation(
            index_code="", price=0, success=False,
            error="配置缺少 url 字段",
        )

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Referer": "https://www.google.com/",
    }

    try:
        resp = shared_session.get(url, headers=headers, timeout=30, verify=False)
        resp.raise_for_status()
        html = resp.text
    except requests.RequestException as e:
        return ThirdPartyValuation(index_code="", price=0, success=False, error=str(e))

    price = _extract_investing_price(html)
    if price is None:
        return ThirdPartyValuation(index_code="", price=0, success=False,
                                    error="未能从页面解析出价格信息")

    change_amount, change_pct = _extract_investing_change(html)
    update_time = _extract_investing_time(html)
    day_high, day_low = _extract_investing_day_range(html)

    return ThirdPartyValuation(
        index_code="",
        price=price,
        change_amount=change_amount or 0,
        change_pct=change_pct or 0,
        update_time=update_time,
        day_high=day_high,
        day_low=day_low,
    )


# ── investing.com 字段提取函数 ────────────────────────────────────────────────


def _extract_investing_price(html: str) -> Optional[float]:
    for pat in [
        r'data-test=["\']instrument-price-last["\'][^>]*>\s*([0-9,]+\.[0-9]+)',
        r'instrument-price-last[^>]*>\s*([0-9,]+\.[0-9]+)',
    ]:
        m = re.search(pat, html)
        if m:
            return float(m.group(1).replace(",", ""))
    return None


def _extract_investing_change(html: str) -> tuple:
    change_amount = None
    change_pct = None
    for pat_amt in [
        r'data-test=["\']instrument-price-change["\'][^>]*>\s*([+-][0-9,]+\.[0-9]+)',
        r'instrument-price-change["\']?[^>]*>\s*([+-][0-9,]+\.[0-9]+)',
    ]:
        m = re.search(pat_amt, html)
        if m:
            change_amount = float(m.group(1).replace(",", ""))
            break
    for pat_pct in [
        r'data-test=["\']instrument-price-change-percent["\'][^>]*>\s*\(?\s*([+-][0-9,.]+)%\s*\)?',
        r'instrument-price-change-percent[^>]*>\s*\(?\s*([+-][0-9,.]+)%\s*\)?',
    ]:
        m = re.search(pat_pct, html)
        if m:
            change_pct = float(m.group(1).replace(",", ""))
            break
    return change_amount, change_pct


def _extract_investing_time(html: str) -> str:
    m = re.search(r'<time[^>]*datetime=["\']([^"\']+)["\']', html)
    if m:
        return m.group(1)[:19].replace("T", " ")
    m = re.search(r'实时数据[·\s]*(\d{2}:\d{2}:\d{2})', html)
    if m:
        return m.group(1)
    return ""


def _extract_investing_day_range(html: str) -> tuple:
    m_low = re.search(r'data-test=["\']instrument-daily-low["\']>\s*([0-9,]+\.[0-9]+)', html)
    m_high = re.search(r'data-test=["\']instrument-daily-high["\']>\s*([0-9,]+\.[0-9]+)', html)
    day_low = float(m_low.group(1).replace(",", "")) if m_low else None
    day_high = float(m_high.group(1).replace(",", "")) if m_high else None
    return day_low, day_high


# ── 数据源注册表 ──────────────────────────────────────────────────────────────
# 每种数据源对应一个解析函数(frame)，便于扩展。

_FETCHERS = {
    "eastmoney": _fetch_eastmoney,
    "tencent_us": _fetch_tencent_us,
    "sina_us": _fetch_sina_us,
    "sina_global": _fetch_sina_global,
    "yahoo_finance": _fetch_yahoo_finance,
    "investing_com": _fetch_investing_com,
}


# ── 直接运行入口（调试） ──────────────────────────────────────────────────────
if __name__ == "__main__":
    import os as _os
    import sys as _sys
    _rd = _os.path.dirname(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
    if _rd not in _sys.path:
        _sys.path.insert(0, _rd)

    for code, cfg in THIRD_PARTY_INDEX_CONFIG.items():
        print(f"\n--- [{code}] {cfg['name']} (source={cfg['source']}) ---")
        result = fetch_valuation(code)
        if result.success:
            print(f"    来源: {result.source}")
            print(f"    价格: {result.price} {result.currency}")
            print(f"    涨跌: {result.change_pct:+.2f}% ({result.change_amount:+.2f})")
            print(f"    时间: {result.update_time}")
            if result.day_high:
                print(f"    当日区间: {result.day_low} - {result.day_high}")
        else:
            print(f"    失败: {result.error}")
