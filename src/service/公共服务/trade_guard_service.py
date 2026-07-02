from __future__ import annotations
import datetime
from typing import Optional, Set
import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# 导入所有需要的模块
try:
    from src.API.交易管理.trade import get_trades_list
    from src.API.基金信息.FundInfo import getFundInfo
    from src.API.资产管理.getAssetListOfSub import get_asset_list_of_sub
    from src.API.组合管理.SubAccountMrg import getSubAccountNoByName
    from src.domain.user.User import User
    from src.common.logger import get_logger
    from src.service.基金信息.基金信息 import get_all_fund_info
except ImportError as e:
    print(f"导入错误: {e}")
    print(f"PROJECT_ROOT: {PROJECT_ROOT}")
    print(f"sys.path: {sys.path}")
    raise

# 创建本地 DEFAULT_USER 用于测试
DEFAULT_USER = User(
    account="13918199137",
    password="sWX15706"  # 测试用密码
)
DEFAULT_USER.customer_no = "cd0b7906b53b43ffa508a99744b4055b"
DEFAULT_USER.mobile_phone = "13918199137"

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

def _get_trade_datetime(t) -> Optional[datetime.datetime]:
    """
    获取交易的完整日期时间（包括时间部分）
    """
    cand = (
        getattr(t, "apply_work_day", None)
        or getattr(t, "strike_start_date", None)
        or getattr(t, "cash_bag_app_time", None)
    )
    dt = _parse_dt(cand)
    if dt:
        return dt
    raw = getattr(t, "raw", None) if isinstance(getattr(t, "raw", None), dict) else None
    if raw:
        for k in ("ApplyWorkDay", "StrikeStartDate", "CashBagAppTime", "ApplyTime", "PayFinishTime", "CreateTime"):
            dt = _parse_dt(raw.get(k))
            if dt:
                return dt
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

def has_buy_submission_on_dates(user: User, sub_account_no: str, fund_code: str, trans_date: datetime.date):
    """
    查询同一基金在指定日期是否存在“有效买入/定投提交”记录（排除撤单）。
    命中则返回该条交易对象，否则返回 None。
    """
    try:
        trades = get_trades_list(user, sub_account_no=sub_account_no,fund_code=fund_code, date_type="5") 
        logger.info(f"守卫查询: fund={fund_code}, scope={'子账户'}, 记录数={len(trades)}")
        # 打印所有交易信息（按日期倒序）
        try:
            sorted_trades = sorted(
                trades,
                key=lambda x: (_get_trade_date(x) or datetime.date.min),
                reverse=True
            )
            for i, tt in enumerate(sorted_trades, start=1):
                d = _get_trade_date(tt)
                _log_trade_full(tt, title=f"最近一周交易#{i} (date={d})")
        except Exception as e:
            logger.warning(f"打印交易记录失败: {e}")
    except Exception as e:
        logger.warning(f"查询基金 {fund_code} 交易记录失败（不连续守卫跳过）：{e}")
        return None

    # 过滤出在 trans_date 日期0点到15:00点之间发生的交易（排除已撤单）
    filtered_trades = []
    for t in trades:
        trade_dt = _get_trade_datetime(t)
        if not trans_date or not trade_dt:
            continue
        if trade_dt.date() == trans_date:
            if trade_dt.time() >= datetime.time(0, 0, 0) and trade_dt.time() <= datetime.time(15, 0, 0):
                if not _is_canceled_trade(t):
                    filtered_trades.append(t)
    
    logger.info(f"时间过滤后: trans_date={trans_date}, 0:00-15:00时间段内的有效交易记录数={len(filtered_trades)}") 
    
    if not filtered_trades:
        return None
    return filtered_trades[0]

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

if __name__ == "__main__":
    import datetime as dt
    fund_code = "008706"
    sub_account_name = "海外基金组合"
    fund_info = getFundInfo(DEFAULT_USER, fund_code)
    # 打印 fund_info 所有属性
    # if fund_info:
    #     for attr in dir(fund_info):
    #         if not attr.startswith("_") and not callable(getattr(fund_info, attr)):
    #             try:
    #                 logger.info(f"fund_info.{attr} = {getattr(fund_info, attr)}")
    #             except Exception:
    #                 pass
    #     raw = getattr(fund_info, "raw", None)
    #     if isinstance(raw, dict):
    #         logger.info(f"fund_info.raw 原始字段({len(raw)}项):")
    #         for k, v in raw.items():
    #             logger.info(f"  raw.{k} = {v}")
    # else:
    #     logger.error("fund_info 为空")
    # 通过组合名称获取组合ID
    sub_account_no = getSubAccountNoByName(DEFAULT_USER, sub_account_name)
    if not sub_account_no:
        logger.error(f"未找到组合 '{sub_account_name}' 的ID")
        sub_account_no = ""
    else:
        logger.info(f"组合 '{sub_account_name}' 的ID为: {sub_account_no}")
    nav_date_str = getattr(fund_info, "nav_date", None)
    logger.info(f"nav_date_str 原始值: '{nav_date_str}', 类型: {type(nav_date_str)}")
    if nav_date_str:
        try:
            prev_trade_day = datetime.datetime.strptime(str(nav_date_str), "%Y-%m-%d").date()
        except Exception as e:
            logger.error(f"解析 nav_date 失败: {e}, 值: '{nav_date_str}'")
            prev_trade_day = None
    else:
        prev_trade_day = None
    logger.info(f"上日期prev_trade_day为: {prev_trade_day}")
    result = has_buy_submission_on_dates(DEFAULT_USER, sub_account_no, fund_code, prev_trade_day)
    # result = has_buy_submission_on_dates(DEFAULT_USER, sub_account_no, fund_code, datetime.date(2026, 6, 24))

    if result:
        logger.info(f"找到符合条件的交易: {getattr(result, 'product_name', 'Unknown')}")
    else:
        logger.info("未找到符合条件的交易")