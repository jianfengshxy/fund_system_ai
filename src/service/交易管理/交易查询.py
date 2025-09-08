import requests
import json
import logging
import sys
import os
import re
from datetime import datetime, date

# 获取项目根目录路径
root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# 如果项目根目录不在Python路径中，则添加
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from src.domain.trade.TradeResult import TradeResult
from src.domain.user.User import User
from typing import List, Optional
from src.common.constant import DEFAULT_USER, MOBILE_KEY
from src.API.交易管理.trade import get_trades_list
from src.service.基金信息.基金信息 import get_all_fund_info

def get_withdrawable_trades(user, sub_account_no="", fund_code="", bus_type="", status="7"):
    """
    获取可撤单交易列表
    Args:
        user: User对象，包含用户认证信息
        sub_account_no: 子账户编号，默认为空
        fund_code: 基金代码，默认为空
        bus_type: 业务类型，默认为空
        status: 状态，默认为"7"表示可撤单
    Returns:
        List[TradeResult]: 可撤单交易结果列表
    """
    logger = logging.getLogger("TradeQuery")
    logger.info("开始获取可撤单交易列表")
    
    # 调用API层的get_trades_list函数，传入状态参数"7"表示可撤单
    trades = get_trades_list(user, sub_account_no, fund_code, bus_type, status)
    
    logger.info(f"获取到 {len(trades)} 条可撤单交易记录")
    return trades

def count_success_trades_on_prev_nav_day(user: User, fund_code: str, sub_account_no: str = "") -> int:
    """
    统计某基金在上一个交易日（以基金的 nav_date 为准）及当天的成功交易数量。
    判定规则：
    - 排除撤回：StatuIcon == 3 的交易不计入
    - 交易时间：取 StrikeStartDate 的日期部分（YYYY-MM-DD），与 nav_date 完全匹配或为当天日期
    """
    logger = logging.getLogger("TradeQuery")

    # 1) 获取该基金的 nav_date（作为"上一个交易日"）
    fi = get_all_fund_info(user, fund_code)
    if not fi or not getattr(fi, "nav_date", None):
        logger.warning(f"获取基金 {fund_code} 的 nav_date 失败，返回 0")
        return 0
    nav_date_str = str(fi.nav_date)  # 形如 'YYYY-MM-DD'
    
    # 获取当天日期
    today_date_str = datetime.now().strftime("%Y-%m-%d")
    
    logger.info(f"统计基金 {fund_code} 在上一个交易日({nav_date_str})及当天({today_date_str})的成功交易数量（排除撤回）")

    # 2) 拉取该基金的交易列表（不过滤状态，统一在本地筛选）
    trades = get_trades_list(user, sub_account_no, fund_code, "", "")
    logger.info(f"获取到 {len(trades)} 条交易记录，开始筛选（排除 StatuIcon==3 且日期匹配 {nav_date_str} 或 {today_date_str}）")

    def _get(obj, *keys):
        # 兼容对象属性和字典键
        for k in keys:
            if hasattr(obj, k):
                v = getattr(obj, k)
                if v is not None:
                    return v
            if isinstance(obj, dict) and k in obj and obj[k] is not None:
                return obj[k]
        return None

    count = 0
    for idx, trade in enumerate(trades, start=1):
        # 撤回标记（StatuIcon == 3 表示已撤回，需要排除）
        statu_icon = _get(trade, "statu_icon", "StatuIcon")
        # 交易时间（取 StrikeStartDate 的日期部分）
        strike_start = _get(trade, "strike_start_date", "StrikeStartDate", "apply_work_day")
        strike_date = str(strike_start)[:10] if strike_start else None

        # 额外打印：其他可能出现的时间字段，基金代码相关字段，业务字段，序列号以便排查
        extra_cash_bag_time = _get(trade, "cash_bag_app_time", "CashBagAppTime")
        extra_apply_work_day = _get(trade, "ApplyWorkDay", "applyWorkDay")
        code_fund_code = _get(trade, "fund_code", "FundCode")
        code_product_code = _get(trade, "ProductCode")
        code_org_fund_code = _get(trade, "OrgFundCode")
        product_name = _get(trade, "product_name", "ProductName", "fund_name")
        business_type = _get(trade, "business_type", "BusinessType")
        serial_no = _get(trade, "busin_serial_no", "ID", "id")

        # 打印调试摘要信息（INFO）
        logger.info(
            f"[{idx}/{len(trades)}] 序列号={serial_no} "
            f"状态(StatuIcon)={statu_icon} "
            f"StrikeStartDate={_get(trade, 'StrikeStartDate', 'strike_start_date')} "
            f"CashBagAppTime={extra_cash_bag_time} "
            f"ApplyWorkDay={_get(trade, 'apply_work_day')} / {extra_apply_work_day} "
            f"归一化日期={strike_date} "
            f"基金代码(fund_code)={code_fund_code} ProductCode={code_product_code} OrgFundCode={code_org_fund_code} "
            f"产品名={product_name} 业务类型={business_type}"
        )

        # 打印是否命中过滤条件（INFO）
        date_match = strike_date == nav_date_str or strike_date == today_date_str
        logger.info(
            f"    -> 过滤判断: 日期匹配上一交易日={strike_date == nav_date_str}, 日期匹配当天={strike_date == today_date_str}, "
            f"总日期匹配={date_match}, 排除撤回(StatuIcon==3)={statu_icon == 3 or str(statu_icon) == '3'}"
        )

        # 可选：打印完整记录（DEBUG，默认 INFO 级别下不会刷屏）
        try:
            if isinstance(trade, dict):
                logger.debug(f"    原始记录(完整): {json.dumps(trade, ensure_ascii=False, default=str)}")
            else:
                # 尝试将对象转字典打印
                obj_dict = {k: getattr(trade, k) for k in dir(trade) if not k.startswith("_") and not callable(getattr(trade, k))}
                logger.debug(f"    原始记录(完整): {json.dumps(obj_dict, ensure_ascii=False, default=str)}")
        except Exception as e:
            logger.debug(f"    原始记录(完整)打印失败: {e}")

        # 统计日期匹配 nav_date 或当天日期，且 非撤回 的交易
        if (strike_date == nav_date_str or strike_date == today_date_str) and statu_icon != 3 and str(statu_icon) != "3":
            count += 1

    logger.info(f"基金 {fund_code} 在上一个交易日({nav_date_str})及当天({today_date_str})成功交易数量（排除撤回）: {count}")
    return count

if __name__ == "__main__":
    # 配置日志
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    logger = logging.getLogger("TradeQuery")
    
    # 调用函数获取可撤单交易列表
    trades = get_withdrawable_trades(DEFAULT_USER)
    
    # 打印结果
    for i, trade in enumerate(trades):
        logger.info(f"\n{'='*50}")
        logger.info(f"可撤单交易记录 {i+1} 详细信息:")
        logger.info(f"{'-'*50}")
        logger.info(f"交易ID(busin_serial_no): {trade.busin_serial_no}")
        logger.info(f"业务类型(business_type): {trade.business_type}")
        logger.info(f"申请工作日(apply_work_day): {trade.apply_work_day}")
        logger.info(f"申请金额/份额(amount): {trade.amount}")
        logger.info(f"交易状态(status): {trade.status}")
        logger.info(f"显示属性(show_com_prop): {trade.show_com_prop}")
        logger.info(f"基金代码(fund_code): {trade.fund_code}")
        # 新增：打印基金名称（优先从对象取，兜底调用基金信息服务）
        try:
            fund_name = getattr(trade, 'product_name', None) or getattr(trade, 'fund_name', None)
            if not fund_name and getattr(trade, 'fund_code', None):
                fi = get_all_fund_info(DEFAULT_USER, trade.fund_code)
                fund_name = fi.fund_name if fi else None
            logger.info(f"基金名称(fund_name): {fund_name or '未知'}")
        except Exception as e:
            logger.warning(f"获取基金名称失败: {e}")
        logger.info(f"{'='*50}")