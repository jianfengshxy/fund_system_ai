from __future__ import annotations
import datetime
from typing import Optional, Set
import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.API.交易管理.trade import get_trades_list
from src.API.资产管理.getAssetListOfSub import get_asset_list_of_sub
from src.domain.user.User import User
from src.common.logger import get_logger

logger = get_logger(__name__)

def _parse_dt(s: Optional[str]) -> Optional[datetime.datetime]:
    if not s:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%Y/%m/%d %H:%M:%S", "%Y/%m/%d"):
        try:
            return datetime.datetime.strptime(s, fmt)
        except Exception:
            continue
    # 兼容 ISO 字符串与带毫秒
    try:
        s2 = s.replace("T", " ").replace("Z", "")
        # 截断到秒，去掉毫秒部分
        s2 = s2.split(".")[0]
        return datetime.datetime.strptime(s2, "%Y-%m-%d %H:%M:%S")
    except Exception:
        pass
    # 兜底：仅取日期部分前10位
    try:
        return datetime.datetime.strptime(s[:10], "%Y-%m-%d")
    except Exception:
        return None

def _is_buy_trade(t) -> bool:
    raw = getattr(t, "raw", None) if isinstance(getattr(t, "raw", None), dict) else None
    display = (getattr(t, "display_business_code", "") or "")
    biz_type = (getattr(t, "business_type", "") or "")
    if raw:
        display = display or str(raw.get("DisPlayBusinessCode") or raw.get("DisplayBusinessCode") or "")
        biz_type = biz_type or str(raw.get("BusinessType") or "")
    text = " ".join([display, biz_type]).strip()

    # 仅按文案识别买入/定投/转入基金，不再使用业务码过滤
    buy_phrases = (
        "买入", "买", "定投", "扣款",
        "申购", "认购",
        "转入基金", "活期宝转入基金", "转入",
        "购买", "充值"
    )
    return any(p in text for p in buy_phrases)

def _is_canceled_trade(t) -> bool:
    state = (getattr(t, "app_state_text", None) or getattr(t, "status", None) or "")
    remark = (getattr(t, "remark", None) or getattr(t, "busin_remark", None) or "")
    text = f"{state}{remark}"
    return ("撤单" in text) or ("撤销" in text) or ("已撤" in text) or ("撤" in text)

def _get_trade_date(t) -> Optional[datetime.date]:
    cand = (
        getattr(t, "apply_work_day", None)
        or getattr(t, "strike_start_date", None)
        or getattr(t, "cash_bag_app_time", None)
    )
    dt = _parse_dt(cand)
    if dt:
        return dt.date()
    raw = getattr(t, "raw", None) if isinstance(getattr(t, "raw", None), dict) else None
    if raw:
        for k in ("ApplyWorkDay", "StrikeStartDate", "CashBagAppTime", "ApplyTime", "PayFinishTime", "CreateTime"):
            dt = _parse_dt(raw.get(k))
            if dt:
                return dt.date()
    return None

def _get_on_way_trade_count(t) -> int:
    """
    从交易对象中尽量提取“在途交易个数/在途标记”。

    背景：
    - 有些活期宝转基金订单是在收盘后提交，交易记录展示时间还是前一自然日；
    - 但实际会顺延到下一交易日处理，单纯靠 today/nav_date 做日期匹配会漏掉；
    - 这类情况下如果交易对象自身已经带有在途标记，就应直接视为在途。
    """
    candidates = [
        getattr(t, "on_way_trade_count", None),
        getattr(t, "on_way_transaction_count", None),
        getattr(t, "is_stay_on_way", None),
    ]
    raw = getattr(t, "raw", None) if isinstance(getattr(t, "raw", None), dict) else None
    if raw:
        candidates.extend(
            [
                raw.get("OnWayTradeCount"),
                raw.get("OnWayTransactionCount"),
                raw.get("IsStayOnWay"),
                raw.get("StayOnWayCount"),
            ]
        )

    for value in candidates:
        if value is None or value == "":
            continue
        try:
            return int(float(value))
        except Exception:
            text = str(value).strip().lower()
            if text in {"true", "yes", "y"}:
                return 1
            if text in {"false", "no", "n"}:
                return 0
    return 0

def _find_sub_account_asset(user: User, sub_account_no: str, fund_code: str):
    """
    在子账户资产列表里查找指定基金。

    优先使用资产接口判断是否存在在途交易，因为交易记录接口可能有同步延迟，
    或者盘后买入场景下日期落在前一自然日，导致交易记录守卫漏判。
    """
    if not sub_account_no:
        return None
    try:
        assets = get_asset_list_of_sub(user, sub_account_no) or []
    except Exception as e:
        logger.warning(f"查询子账户资产失败（资产守卫降级为交易守卫）: fund={fund_code}, sub_account_no={sub_account_no}, err={e}")
        return None

    for asset in assets:
        if str(getattr(asset, "fund_code", "") or "") == str(fund_code):
            return asset
    return None

def has_buy_submission_on_dates(user: User, sub_account_no: str, fund_code: str, dates: Set[datetime.date]):
    """
    查询同一基金在指定日期集合是否存在“有效买入/定投提交”记录（排除撤单）。
    命中则返回该条交易对象，否则返回 None。
    """
    asset = _find_sub_account_asset(user, sub_account_no, fund_code)
    if asset is not None:
        on_way_transaction_count = int(getattr(asset, "on_way_transaction_count", 0) or 0)
        asset_value = float(getattr(asset, "asset_value", 0) or 0)
        available_vol = float(getattr(asset, "available_vol", 0) or 0)
        if on_way_transaction_count > 0:
            logger.info(
                f"资产守卫命中在途交易: fund={fund_code}, sub_account_no={sub_account_no}, "
                f"on_way_transaction_count={on_way_transaction_count}, asset_value={asset_value}, available_vol={available_vol}"
            )
            return asset
        if asset_value > 0 and available_vol <= 0:
            logger.info(
                f"资产守卫命中疑似在途持仓: fund={fund_code}, sub_account_no={sub_account_no}, "
                f"asset_value={asset_value}, available_vol={available_vol}"
            )
            return asset

    try:
        trades = get_trades_list(user, sub_account_no=sub_account_no or "", fund_code=fund_code) or []
        if (not trades) and sub_account_no:
            extra = get_trades_list(user, sub_account_no="", fund_code=fund_code) or []
            trades = extra
        logger.info(f"守卫查询: fund={fund_code}, scope={'子账户' if sub_account_no else '全账户'}, 记录数={len(trades)}")

        # 打印最近两个交易的所有信息（按日期倒序）
        # try:
        #     sorted_trades = sorted(
        #         trades,
        #         key=lambda x: (_get_trade_date(x) or datetime.date.min),
        #         reverse=True
        #     )
        #     for i, tt in enumerate(sorted_trades[:2], start=1):
        #         d = _get_trade_date(tt)
        #         _log_trade_full(tt, title=f"最近交易#{i} (date={d})")
        # except Exception as e:
        #     logger.warning(f"打印最近交易失败: {e}")
    except Exception as e:
        logger.warning(f"查询基金 {fund_code} 交易记录失败（不连续守卫跳过）：{e}")
        return None

    for t in trades:
        if not _is_buy_trade(t):
            continue
        if _is_canceled_trade(t):
            # logger.info(f"忽略已撤单记录: {getattr(t, 'product_name','') or ''}({fund_code}) 状态={getattr(t, 'app_state_text', None) or getattr(t, 'status', None)}")
            continue
        on_way_trade_count = _get_on_way_trade_count(t)
        if on_way_trade_count > 0:
            logger.info(
                f"守卫命中在途标记: fund={fund_code}, on_way_trade_count={on_way_trade_count}, "
                f"status={getattr(t, 'app_state_text', None) or getattr(t, 'status', None)}"
            )
            return t
        d = _get_trade_date(t)
        if d and d in dates:
            return t

    return None

def _log_trade_full(t, title: str):
    summary = {
        "product_name": getattr(t, "product_name", None),
        "fund_code": getattr(t, "fund_code", None),
        "display_business_code": getattr(t, "display_business_code", None),
        "business_type": getattr(t, "business_type", None),
        "business_code": getattr(t, "business_code", None),
        "status/app_state_text": getattr(t, "app_state_text", None) or getattr(t, "status", None),
        "amount": getattr(t, "amount", None),
        "apply_work_day": getattr(t, "apply_work_day", None),
        "strike_start_date": getattr(t, "strike_start_date", None),
        "cash_bag_app_time": getattr(t, "cash_bag_app_time", None),
        "busin_serial_no/id": getattr(t, "busin_serial_no", None) or getattr(t, "id", None),
        "is_stay_on_way": getattr(t, "is_stay_on_way", None),
    }
    logger.info(f"{title} 概览: {summary}")

    try:
        attrs = []
        for attr in dir(t):
            if not attr.startswith("_") and not callable(getattr(t, attr)):
                try:
                    attrs.append((attr, getattr(t, attr)))
                except Exception:
                    pass
        logger.info(f"{title} 对象属性({len(attrs)}项):")
        for k, v in attrs:
            logger.info(f"{title} obj.{k} = {v}")
    except Exception as e:
        logger.warning(f"{title} 打印对象属性失败: {e}")

    raw = getattr(t, "raw", None)
    if isinstance(raw, dict):
        try:
            logger.info(f"{title} 原始字段({len(raw)}项):")
            for k, v in raw.items():
                logger.info(f"{title} raw.{k} = {v}")
        except Exception as e:
            logger.warning(f"{title} 打印原始字段失败: {e}")
