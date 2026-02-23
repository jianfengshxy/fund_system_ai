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

def get_fund_history_success_trades(user: User, fund_code: str) -> List[TradeResult]:
    """
    获取指定基金的全量历史成功交易记录（优先使用新接口，失败回退）
    
    Args:
        user: User对象
        fund_code: 基金代码
        
    Returns:
        List[TradeResult]: 成功的交易记录列表
    """
    logger = get_logger("TradeQuery")
    extra = {"account": getattr(user, 'mobile_phone', None) or getattr(user, 'account', None), 
             "action": "get_fund_history_success_trades", 
             "fund_code": fund_code}
             
    logger.info(f"正在尝试使用 GetOneFundTranInfos 获取基金 {fund_code} 的全量历史交易记录...", extra=extra)
    
    try:
        from src.API.交易管理.trade import get_one_fund_tran_infos
        trades = get_one_fund_tran_infos(user, fund_code)
        
        # 如果新接口返回了数据，直接使用并过滤
        if trades:
            success_trades = [t for t in trades if "撤" not in (t.status or "") and "失败" not in (t.status or "")]
            logger.info(f"使用新接口成功获取 {len(success_trades)} 条有效记录", extra=extra)
            return success_trades
            
        logger.info(f"新接口返回空数据", extra=extra)
    except Exception as e:
        logger.error(f"新接口调用失败: {e}", extra=extra)
        # 根据用户要求，不进行回退，直接报错或返回空
        raise e
        
    return []

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
    
    fund_code = "016531"
    
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
    success_trades = get_fund_history_success_trades(DEFAULT_USER, fund_code)
    
    # 3. 整理交易数据并计算 Cashflows
    # 打印全部成功交易记录
    print(f"【交易记录明细】 (共 {len(success_trades)} 条，显示全部历史记录)")
    print("-" * 100)
    print(f"{'交易时间':<20} | {'业务类型':<15} | {'确认金额':<12} | {'确认份额':<12} | {'状态'}")
    print("-" * 100)
    
    # 辅助变量：计算最近一年的期初本金状态
    # 定义近1年窗口
    one_year_ago = datetime.now().replace(year=datetime.now().year - 1)
    one_year_ago_date = one_year_ago.date()
    
    # 核心数据结构：
    # 1. full_cashflows: 全量现金流（用于推导一年前的状态）
    # 2. recent_cashflows: 最近一年现金流（用于计算近1年收益率）
    # 3. initial_state_1y: 一年前那个时间点的持仓状态（投入本金、持仓市值等）
    
    initial_principal_1y = 0.0 # 一年前的剩余本金（总投入-总赎回，未考虑盈亏）
    initial_share_1y = 0.0 # 一年前的持有份额
    
    # 按时间正序排列（API通常返回倒序，需确认）
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
    
    recent_cashflows = [] # 仅包含最近1年的现金流
    recent_dates = []
    
    total_invest_recent = 0.0 # 最近1年投入
    total_redeem_recent = 0.0 # 最近1年赎回
    
    for t in parsed_trades:
        if not t['date']:
            continue
            
        is_recent = t['date'] >= one_year_ago
        
        # 打印控制：打印全部记录
        print(f"{t['date_str']:<20} | {t['type']:<15} | {t['amount']:<12,.2f} | {t['vol']:<12.2f} | {t['status']}")
        
        # 识别资金流向
        flow = 0.0
        
        if any(k in t['type'] for k in ['买入', '申购', '定投', '转入', '分红再投']):
            flow = -t['amount']
            
            # 累计数据
            if is_recent:
                total_invest_recent += t['amount']
            else:
                # 这是一个简化的假设：历史投入都算作本金积累
                # 实际上应该用份额来推导一年前的市值，但没有当时净值，只能估算资金占用
                initial_principal_1y += t['amount']
                initial_share_1y += t['vol']
                
        elif any(k in t['type'] for k in ['卖出', '赎回', '转出', '分红', '转换出', '强制赎回']):
            flow = t['amount']
            
            if is_recent:
                total_redeem_recent += t['amount']
            else:
                initial_principal_1y -= t['amount']
                initial_share_1y -= t['vol']
        else:
            # 其他类型，暂且忽略
            pass
            
        # 如果是最近一年的交易，加入现金流计算
        if is_recent and flow != 0:
            recent_cashflows.append(flow)
            recent_dates.append(t['date'])

    print("-" * 100)
    
    # 4. 构建近1年的完整现金流模型
    # 模型 = [初始状态] + [期间交易] + [期末状态]
    
    # 期末状态 (当前)
    current_asset = asset_detail.asset_value
    recent_cashflows.append(current_asset)
    recent_dates.append(datetime.now())
    
    # 推导期初状态 (一年前)
    # 这里的 initial_principal_1y 只是资金流水差额，不代表当时的市值。
    # 既然用户只关心最近1年的表现，我们可以把 "一年前的持有市值" 视为 "初始投入"。
    # 但是我们不知道一年前的净值，无法准确计算当时市值。
    # 变通方案：
    # 使用 "一年前剩余本金" (initial_principal_1y) 作为期初投入。
    # 这假设之前的盈亏已经结清，或者我们将之前的投入视为成本。
    # 如果 initial_principal_1y < 0，说明之前已经回本且盈利，期初成本为0（甚至可以视为负成本？XIRR通常处理不了负的期初值作为投入）
    
    initial_cost_for_xirr = max(0, initial_principal_1y)
    
    if initial_cost_for_xirr > 0:
        # 在 cashflows 开头插入一笔“期初投入”
        recent_cashflows.insert(0, -initial_cost_for_xirr)
        recent_dates.insert(0, one_year_ago)
        
    print("\n【近1年资金效率分析】")
    print("=" * 60)
    print(f"统计区间: {one_year_ago.strftime('%Y-%m-%d')} 至 {datetime.now().strftime('%Y-%m-%d')}")
    print("-" * 60)
    print(f"期初推导本金: {initial_cost_for_xirr:,.2f} (基于历史全量交易推算)")
    print(f"期间总投入: {total_invest_recent:,.2f}")
    print(f"期间总赎回: {total_redeem_recent:,.2f}")
    print(f"期末持仓市值: {current_asset:,.2f}")
    
    # 计算近1年净收益
    # Net Profit = (期末市值 + 期间赎回) - (期初本金 + 期间投入)
    net_profit_1y = (current_asset + total_redeem_recent) - (initial_cost_for_xirr + total_invest_recent)
    print(f"近1年净收益: {net_profit_1y:,.2f}")
    
    # 计算日均持有资产 (近1年)
    avg_daily_invested = 0.0
    if recent_dates:
        start_date = recent_dates[0] # 可能是 one_year_ago 或第一笔交易日
        end_date = datetime.now()
        total_days = (end_date - start_date).days + 1
        
        daily_sum = 0.0
        current_invested = initial_cost_for_xirr
        
        # 交易映射
        trade_map = {}
        for t in parsed_trades:
            if t['date'] and t['date'] >= start_date:
                d_str = t['date'].strftime("%Y-%m-%d")
                
                flow = 0.0
                if any(k in t['type'] for k in ['买入', '申购', '定投', '转入', '分红再投']):
                    flow = t['amount']
                elif any(k in t['type'] for k in ['卖出', '赎回', '转出', '分红', '转换出', '强制赎回']):
                    flow = -t['amount']
                trade_map[d_str] = trade_map.get(d_str, 0.0) + flow
        
        # 按天累加
        from datetime import timedelta
        for i in range(total_days):
            curr_d = start_date + timedelta(days=i)
            d_str = curr_d.strftime("%Y-%m-%d")
            
            if d_str in trade_map:
                current_invested += trade_map[d_str]
            
            daily_sum += max(0, current_invested)
            
        avg_daily_invested = daily_sum / total_days if total_days > 0 else 0.0
        
    print(f"近1年日均资金占用: {avg_daily_invested:,.2f}")

    # XIRR 计算函数
    def xirr(cashflows, dates):
        if not cashflows or not dates or len(cashflows) != len(dates):
            return None
        
        start_date = dates[0]
        days = [(d - start_date).days for d in dates]
        
        def npv(rate):
            if rate <= -1.0: return float('inf')
            total_npv = 0.0
            for i, flow in enumerate(cashflows):
                total_npv += flow / ((1 + rate) ** (days[i] / 365.0))
            return total_npv
            
        low, high = -0.9999, 10.0 
        for _ in range(100):
            mid = (low + high) / 2
            v = npv(mid)
            if abs(v) < 1e-5:
                return mid
            if v > 0:
                low = mid 
            else:
                high = mid
        return (low + high) / 2

    xirr_val = xirr(recent_cashflows, recent_dates)
    xirr_percent = xirr_val * 100 if xirr_val is not None else 0.0
    
    # 实际年化收益率 (简单版: 收益/日均占用)
    # 注意：这里的年化是简单的 (收益/本金) * (365/天数)
    days_held = (datetime.now() - one_year_ago).days
    simple_annualized = 0.0
    if avg_daily_invested > 0:
        simple_annualized = (net_profit_1y / avg_daily_invested) * (365 / days_held) * 100
        
    print(f"近1年实际资金回报率 (TotalProfit / Avg.Daily.Invested): {simple_annualized:.2f}%")
    print(f"近1年内部收益率 (XIRR): {xirr_percent:.2f}%")
    print("=" * 60)
