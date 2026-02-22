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

from src.common.logger import get_logger

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
    logger = get_logger("TradeQuery")
    extra = {"account": getattr(user,'mobile_phone',None) or getattr(user,'account',None), "action": "get_withdrawable_trades", "sub_account_no": sub_account_no, "fund_code": fund_code}
    logger.info("开始获取可撤单交易列表", extra=extra)
    
    # 调用API层的get_trades_list函数，传入状态参数"7"表示可撤单
    trades = get_trades_list(user, sub_account_no, fund_code, bus_type, status)
    
    logger.info(f"获取到 {len(trades)} 条可撤单交易记录", extra=extra)
    return trades

def get_fund_success_trades(user: User, fund_code: str, date_type: str = "") -> List[TradeResult]:
    """
    获取指定基金的所有成功交易记录（排除撤单和失败）
    
    Args:
        user: User对象
        fund_code: 基金代码
        date_type: 时间范围类型，默认为"3" (近1年)。
                   "5": 近1周
                   "1": 近1月
                   "2": 近3月
                   "3": 近1年
    
    Returns:
        List[TradeResult]: 成功的交易记录列表
    """
    logger = get_logger("TradeQuery")
    extra = {"account": getattr(user, 'mobile_phone', None) or getattr(user, 'account', None), 
             "action": "get_fund_success_trades", 
             "fund_code": fund_code,
             "date_type": date_type}
    
    logger.info(f"开始获取基金 {fund_code} 的成功交易记录 (date_type={date_type})", extra=extra)
    
    # get_trades_list 现在已经内置了自动分页获取所有数据的逻辑
    try:
        all_trades = get_trades_list(user, fund_code=fund_code, page_index=1, page_size=50, date_type=date_type)
    except Exception as e:
        logger.error(f"获取交易记录失败: {e}", extra=extra)
        all_trades = []
            
    # 过滤成功的交易
    success_trades = []
    for trade in all_trades:
        # 获取状态文本
        status_text = getattr(trade, 'app_state_text', "") or getattr(trade, 'status', "") or ""
        
        # 排除撤单和失败
        if "撤" in status_text or "失败" in status_text:
            continue
            
        success_trades.append(trade)
        
    logger.info(f"共获取到 {len(all_trades)} 条记录，其中成功记录 {len(success_trades)} 条", extra=extra)
    return success_trades

def count_success_trades_on_prev_nav_day(user: User, fund_code: str, sub_account_no: str = "") -> int:
    """
    统计某基金在上一个交易日（以基金的 nav_date 为准）及当天的未回撤交易数量。
    判定规则：
    - 交易时间：取 StrikeStartDate 的日期部分（YYYY-MM-DD），与 nav_date 完全匹配或为当天日期
    - 包含所有未回撤交易：无论交易是否已确认完成
    """
    logger = get_logger("TradeQuery")

    # 1) 获取该基金的 nav_date（作为"上一个交易日"）
    fi = get_all_fund_info(user, fund_code)
    if not fi or not getattr(fi, "nav_date", None):
        logger.warning(f"获取基金 {fund_code} 的 nav_date 失败，返回 0", extra={"account": getattr(user,'mobile_phone',None) or getattr(user,'account',None), "action": "count_success_trades_on_prev_nav_day", "fund_code": fund_code})
        return 0
    nav_date_str = str(fi.nav_date)  # 形如 'YYYY-MM-DD'
    fund_name = getattr(fi, "fund_name", fund_code)
    
    # 获取当天日期
    today_date_str = datetime.now().strftime("%Y-%m-%d")
    
    # 开始统计时输出基金名+代码
    logger.info(f"统计基金 {fund_name}({fund_code}) 在上一个交易日({nav_date_str})及当天({today_date_str})的未回撤交易数量", extra={"account": getattr(user,'mobile_phone',None) or getattr(user,'account',None), "action": "count_success_trades_on_prev_nav_day", "fund_code": fund_code})


    # 2) 拉取该基金的交易列表（不过滤状态，统一在本地筛选）
    trades = get_trades_list(user, sub_account_no, fund_code, "", "")
    # 只取前5条记录
    trades = trades[:5] if len(trades) > 5 else trades
    logger.info(f"获取到 {len(trades)} 条交易记录，开始筛选（排除状态文本为'已撤单(已支付)'且日期匹配 {nav_date_str} 或 {today_date_str}）", extra={"account": getattr(user,'mobile_phone',None) or getattr(user,'account',None), "action": "count_success_trades_on_prev_nav_day", "fund_code": fund_code})
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
    logger.info(f"基金 {fund_name}({fund_code}) 在上一个交易日({nav_date_str})及当天({today_date_str})未回撤交易数量: {count}", extra={"account": getattr(user,'mobile_phone',None) or getattr(user,'account',None), "action": "count_success_trades_on_prev_nav_day", "fund_code": fund_code})
    return count

if __name__ == "__main__":
    # 配置日志
    logging.basicConfig(level=logging.INFO, format='%(message)s') # 简化日志格式，只输出message
    logger = logging.getLogger("TradeQuery")
    
    fund_code = "020516"
    
    # 1. 获取当前持仓资产详情
    from src.service.资产管理.get_fund_asset_detail import get_fund_total_asset_detail
    logger.info(f"正在获取基金 {fund_code} 的当前持仓详情...")
    asset_detail = get_fund_total_asset_detail(DEFAULT_USER, fund_code)
    
    if not asset_detail:
        logger.error("未找到资产详情，无法计算收益率。")
        sys.exit(1)
        
    # 打印资产详情摘要
    print("\n" + "="*60)
    print(f"【当前持仓详情】 基金: {asset_detail.fund_name} ({asset_detail.fund_code})")
    print("-" * 60)
    print(f"资产/市值: {asset_detail.asset_value:,.2f}")
    print(f"持有收益: {asset_detail.hold_profit:,.2f} (收益率: {asset_detail.hold_profit_rate}%)")
    print(f"累计收益: {asset_detail.profit_value:,.2f}")
    print(f"可用份额: {asset_detail.available_vol:,.2f}")
    print("="*60 + "\n")

    # 2. 获取历史交易记录
    logger.info(f"正在获取基金 {fund_code} 的历史成功交易记录(date_type='3' 获取近1年)...")
    success_trades = get_fund_success_trades(DEFAULT_USER, fund_code, date_type="3")
    
    # 3. 整理交易数据并计算 Cashflows
    print(f"【交易记录明细】 (共 {len(success_trades)} 条)")
    print("-" * 100)
    print(f"{'交易时间':<20} | {'业务类型':<15} | {'确认金额':<12} | {'确认份额':<12} | {'状态'}")
    print("-" * 100)
    
    cashflows = []
    dates = []
    total_invest = 0.0  # 总投入
    total_redeem = 0.0  # 总赎回/分红
    
    # 按时间正序排列（API通常返回倒序，需确认）
    # get_trades_list 并没有明确排序，通常是时间倒序。我们需要正序来打印和计算XIRR
    # 先尝试解析日期
    parsed_trades = []
    for trade in success_trades:
        # 获取日期
        date_str = getattr(trade, 'strike_start_date', None) or getattr(trade, 'apply_work_day', None)
        trade_date = None
        if date_str:
            try:
                # 处理 '2025-05-28 09:33:56' 格式
                trade_date = datetime.strptime(str(date_str)[:19], "%Y-%m-%d %H:%M:%S")
            except:
                try:
                    trade_date = datetime.strptime(str(date_str)[:10], "%Y-%m-%d")
                except:
                    pass
        
        # 获取金额 (解析 "1,000.00元" 这种格式)
        raw_amount = getattr(trade, 'confirm_count', None) or getattr(trade, 'amount', None)
        amount = 0.0
        if raw_amount:
            try:
                s = str(raw_amount).replace(',', '').replace('元', '').replace('--', '').strip()
                if s:
                    amount = float(s)
            except:
                pass
                
        # 获取份额
        raw_vol = getattr(trade, 'confirm_vol', None) # TradeResult 可能没有这个字段，需检查 raw
        vol = 0.0
        if hasattr(trade, 'raw') and isinstance(trade.raw, dict):
             # 有些接口返回 ConfirmVol
             v = trade.raw.get('ConfirmVol')
             if v:
                 try:
                     vol = float(str(v).replace(',', ''))
                 except:
                     pass
        
        bus_type = getattr(trade, 'business_type', '未知')
        status = getattr(trade, 'app_state_text', '成功')
        
        parsed_trades.append({
            'date': trade_date,
            'date_str': date_str,
            'type': bus_type,
            'amount': amount,
            'vol': vol,
            'status': status
        })
        
    # 按日期正序排序
    parsed_trades.sort(key=lambda x: x['date'] if x['date'] else datetime.min)
    
    for t in parsed_trades:
        print(f"{t['date_str']:<20} | {t['type']:<15} | {t['amount']:<12,.2f} | {t['vol']:<12.2f} | {t['status']}")
        
        if not t['date']:
            continue
            
        # 构建现金流
        # 买入/定投/申购 -> 现金流出 (-)
        # 卖出/赎回/分红 -> 现金流入 (+)
        # 转换入 -> 流出, 转换出 -> 流入
        
        flow = 0.0
        is_inflow = False # 是否为流入（回到口袋）
        
        if any(k in t['type'] for k in ['买入', '申购', '定投', '转入']):
            flow = -t['amount']
            total_invest += t['amount']
        elif any(k in t['type'] for k in ['卖出', '赎回', '转出', '分红', '转换出']):
            flow = t['amount']
            total_redeem += t['amount']
            is_inflow = True
        else:
            # 其他类型，暂且忽略或按正负判断
            pass
            
        if flow != 0:
            cashflows.append(flow)
            dates.append(t['date'])

    print("-" * 100)
    
    # 4. 加入期末资产作为最后一笔现金流
    current_asset = asset_detail.asset_value
    cashflows.append(current_asset)
    dates.append(datetime.now())
    
    # 5. 计算收益率指标
    # 尝试推导缺失的初始成本 (Implied Initial Cost)
    # 逻辑: TotalInvest_Lifetime = TotalRedeem_Lifetime + CurrentAsset - TotalProfit_Lifetime
    # 我们假设 TotalRedeem_Lifetime ≈ total_redeem (窗口内的赎回), 这在只最近一年有大额卖出的情况下成立
    # 如果用户在更早之前也有大额卖出，这个推导会偏小，但总比没有好。
    
    total_invest_lifetime_derived = total_redeem + current_asset - asset_detail.profit_value
    missing_initial_cost = total_invest_lifetime_derived - total_invest
    
    print("\n【收益分析 (基于APP数据校正)】")
    print("=" * 60)
    print(f"当前持仓市值: {current_asset:,.2f}")
    print(f"APP显示累计收益: {asset_detail.profit_value:,.2f}")
    print(f"窗口内总投入: {total_invest:,.2f}")
    print(f"窗口内总赎回: {total_redeem:,.2f}")
    
    if missing_initial_cost > 100:
        print(f"推导缺失初始成本: {missing_initial_cost:,.2f} (将作为期初投入参与XIRR计算)")
        # 添加一笔期初现金流
        start_date = dates[0] if dates else datetime.now()
        # 设为第一笔交易前一天
        from datetime import timedelta
        initial_date = start_date - timedelta(days=1)
        
        cashflows.insert(0, -missing_initial_cost)
        dates.insert(0, initial_date)
        
        # 修正用于显示的净收益
        net_profit_calc = current_asset + total_redeem - (total_invest + missing_initial_cost)
        print(f"校正后计算净收益: {net_profit_calc:,.2f} (与APP一致)")
    else:
        print(f"计算净收益: {net_profit:,.2f}")

    # 简单收益率 (基于推导的总投入)
    total_principal = total_invest + max(0, missing_initial_cost)
    simple_return = (asset_detail.profit_value / total_principal * 100) if total_principal > 0 else 0.0
    
    # XIRR 计算函数
    def xirr(cashflows, dates):
        if not cashflows or not dates or len(cashflows) != len(dates):
            return None
        
        # 将日期转换为距首日的天数
        start_date = dates[0]
        days = [(d - start_date).days for d in dates]
        
        # 定义净现值函数
        def npv(rate):
            # 避免除零和复数
            if rate <= -1.0: return float('inf')
            total_npv = 0.0
            for i, flow in enumerate(cashflows):
                total_npv += flow / ((1 + rate) ** (days[i] / 365.0))
            return total_npv
            
        # 二分法求解 rate
        low, high = -0.9999, 10.0 # -99.99% 到 1000%
        for _ in range(100):
            mid = (low + high) / 2
            v = npv(mid)
            if abs(v) < 1e-5:
                return mid
            if v > 0:
                low = mid # 需要更高的折现率来降低NPV
            else:
                high = mid
        return (low + high) / 2

    xirr_val = xirr(cashflows, dates)
    xirr_percent = xirr_val * 100 if xirr_val is not None else 0.0
    
    print(f"简单收益率 (TotalProfit / Est.Principal): {simple_return:.2f}%")
    print(f"年化收益率 (XIRR): {xirr_percent:.2f}%")
    print("=" * 60)
