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
    统计某基金在上一个交易日（以基金的 nav_date 为准）及当天的未回撤交易数量。
    判定规则：
    - 交易时间：取 StrikeStartDate 的日期部分（YYYY-MM-DD），与 nav_date 完全匹配或为当天日期
    - 包含所有未回撤交易：无论交易是否已确认完成
    """
    logger = logging.getLogger("TradeQuery")

    # 1) 获取该基金的 nav_date（作为"上一个交易日"）
    fi = get_all_fund_info(user, fund_code)
    if not fi or not getattr(fi, "nav_date", None):
        logger.warning(f"获取基金 {fund_code} 的 nav_date 失败，返回 0")
        return 0
    nav_date_str = str(fi.nav_date)  # 形如 'YYYY-MM-DD'
    fund_name = getattr(fi, "fund_name", fund_code)
    
    # 获取当天日期
    today_date_str = datetime.now().strftime("%Y-%m-%d")
    
    # 开始统计时输出基金名+代码
    logger.info(f"统计基金 {fund_name}({fund_code}) 在上一个交易日({nav_date_str})及当天({today_date_str})的未回撤交易数量")


    # 2) 拉取该基金的交易列表（不过滤状态，统一在本地筛选）
    trades = get_trades_list(user, sub_account_no, fund_code, "", "")
    # 只取前5条记录
    trades = trades[:5] if len(trades) > 5 else trades
    logger.info(f"获取到 {len(trades)} 条交易记录，开始筛选（排除状态文本为'已撤单(已支付)'且日期匹配 {nav_date_str} 或 {today_date_str}）")
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

    # # 打印所有交易记录的原始信息
    # logger.info("\n" + "=" * 100)
    # logger.info("原始交易记录详情：")
    
    count = 0
    for idx, trade in enumerate(trades, start=1):
        # 获取关键字段
        statu_icon = _get(trade, "statu_icon", "StatuIcon")
        strike_start = _get(trade, "strike_start_date", "StrikeStartDate", "apply_work_day")
        strike_date = str(strike_start)[:10] if strike_start else None
        status_text = _get(trade, "app_state_text", "APPStateText", "status")
        serial_no = _get(trade, "busin_serial_no", "ID", "id")
        amount = _get(trade, "amount", "Amount")
        business_type = _get(trade, "business_type", "BusinessType")
        product_name = _get(trade, "product_name", "ProductName", "fund_name")
        
        # 打印原始记录的完整信息
        # logger.info(f"\n[交易记录 {idx}/{len(trades)}]")
        # logger.info("-" * 80)
        
        # 尝试将对象转为字典并格式化打印所有字段
        try:
            if isinstance(trade, dict):
                # 如果是字典，直接格式化打印
                for key, value in trade.items():
                    # logger.info(f"{key:30}: {value}")
                    pass
            else:
                # 如果是对象，获取所有非私有、非方法属性
                for attr in dir(trade):
                    if not attr.startswith("_") and not callable(getattr(trade, attr)):
                        value = getattr(trade, attr)
                        # logger.info(f"{attr:30}: {value}")
        except Exception as e:
            logger.info(f"打印原始记录失败: {e}")
        
        # 打印关键信息摘要
        # logger.info("-" * 80)
        # logger.info(f"交易序列号: {serial_no}")
        # logger.info(f"状态码(StatuIcon): {statu_icon}")
        # logger.info(f"状态文本: {status_text}")
        # logger.info(f"交易日期: {strike_date}")
        # logger.info(f"金额: {amount}")
        # logger.info(f"业务类型: {business_type}")
        # logger.info(f"基金名称: {product_name}")
        
        # 统计日期匹配 nav_date 或 当天 且 非撤回 的交易
        date_match_prev = strike_date == nav_date_str
        date_match_today = strike_date == today_date_str
        date_match = date_match_prev or date_match_today
        is_withdrawn = status_text == "已撤单(已支付)"
        
    #     if date_match and not is_withdrawn:
    #         count += 1
    #         logger.info(f"统计结果: 此交易被统计为未回撤交易 (日期匹配={'上一交易日' if date_match_prev else '当天'})")
    #     else:
    #         logger.info(f"统计结果: 此交易未被统计 (日期匹配上一交易日={date_match_prev}, 日期匹配当天={date_match_today}, 是否撤回={is_withdrawn})")
    
    # logger.info("=" * 100)
    logger.info(f"基金 {fund_name}({fund_code}) 在上一个交易日({nav_date_str})及当天({today_date_str})未回撤交易数量: {count}")
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