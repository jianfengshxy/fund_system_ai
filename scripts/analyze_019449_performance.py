
import sys
import os
import logging
from datetime import datetime, timedelta
import pandas as pd
import numpy as np

# 添加项目根目录到 Python 路径
root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from src.common.constant import DEFAULT_USER
from src.API.交易管理.trade import get_trades_list
from src.service.资产管理.get_fund_asset_detail import get_fund_asset_detail
from src.service.基金信息.基金信息 import get_all_fund_info

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("Analysis")

FUND_CODE = "019449"

def calculate_xirr(cashflows, dates):
    """
    计算内部收益率 (XIRR)
    cashflows: 现金流列表 (负数为支出，正数为收入)
    dates: 对应的日期列表 (datetime对象)
    """
    if not cashflows or len(cashflows) != len(dates):
        return None
    
    # 确保按日期排序
    sorted_indices = np.argsort(dates)
    cashflows = np.array(cashflows)[sorted_indices]
    dates = np.array(dates)[sorted_indices]
    
    start_date = dates[0]
    # 将日期转换为天数差
    days = np.array([(d - start_date).days for d in dates])
    
    def npv(rate):
        if rate <= -1.0:
            return float('inf')
        return np.sum(cashflows / ((1 + rate) ** (days / 365.0)))
    
    # 使用二分法求解
    low = -0.99
    high = 100.0
    for _ in range(100):
        mid = (low + high) / 2
        v = npv(mid)
        if abs(v) < 1e-6:
            return mid
        if v > 0:
            low = mid
        else:
            high = mid
            
    return (low + high) / 2

def analyze_fund_performance(user, fund_code):
    logger.info(f"开始分析基金 {fund_code} 的交易记录与收益...")
    
    # 1. 获取最近一年的交易记录
    # 注意：get_trades_list 默认只返回第一页（100条），我们需要循环获取所有历史记录
    all_trades = []
    page_index = 1
    page_size = 100
    max_pages = 50 # 防止死循环
    
    while page_index <= max_pages:
        logger.info(f"正在获取第 {page_index} 页交易记录...")
        try:
            # 调用 API 获取单页数据
            page_trades = get_trades_list(user, fund_code=fund_code, page_index=page_index, page_size=page_size)
            
            if not page_trades:
                logger.info(f"第 {page_index} 页无数据，停止获取。")
                break
                
            all_trades.extend(page_trades)
            
            # 如果获取的数量少于 page_size，说明是最后一页
            if len(page_trades) < page_size:
                logger.info(f"第 {page_index} 页数据不满 {page_size} 条，已获取全部数据。")
                break
                
            page_index += 1
            
        except Exception as e:
            logger.error(f"获取第 {page_index} 页数据失败: {e}")
            break
            
    if not all_trades:
        logger.info(f"未找到基金 {fund_code} 的任何交易记录。")
        return

    # 过滤最近一年的记录
    one_year_ago = datetime.now() - timedelta(days=365)
    target_trades = []
    
    logger.info(f"找到 {len(all_trades)} 条原始交易记录，正在筛选最近一年...")
    
    # 用于计算 XIRR 的现金流
    cashflows = []
    dates = []
    
    total_buy = 0.0
    total_sell = 0.0
    buy_count = 0
    sell_count = 0
    
    trade_details = []

    for trade in all_trades:
        # 解析日期
        # TradeResult 中可能有 apply_work_day, strike_start_date 等字段
        # 优先使用确认日期或者申请日期
        date_str = getattr(trade, 'strike_start_date', None) or getattr(trade, 'apply_work_day', None)
        if not date_str:
            continue
            
        # 处理可能的日期格式
        try:
            if 'T' in date_str:
                trade_date = datetime.strptime(date_str.split('T')[0], "%Y-%m-%d")
            else:
                trade_date = datetime.strptime(str(date_str)[:10], "%Y-%m-%d")
        except Exception as e:
            logger.warning(f"日期解析失败: {date_str}, error: {e}")
            continue
            
        # 只要最近一年的
        if trade_date < one_year_ago:
            continue

        # 过滤掉撤单和失败的交易
        status_text = getattr(trade, 'app_state_text', "") or getattr(trade, 'status', "")
        if "撤" in status_text or "失败" in status_text:
            continue

        target_trades.append(trade)
        
        # 智能解析金额
        def clean_amount(val):
            if not val: return 0.0
            if isinstance(val, (int, float)): return float(val)
            s = str(val).replace('元', '').replace(',', '').replace('--', '').strip()
            if not s: return 0.0
            try:
                return float(s)
            except:
                return 0.0

        confirm_val = getattr(trade, 'confirm_count', None)
        # 注意：TradeResult 中 amount 属性已经被映射为 apply_amount 或 ApplyCount
        apply_val = getattr(trade, 'apply_count', None) or getattr(trade, 'amount', None)
        
        bus_type = getattr(trade, 'business_type', "") or getattr(trade, 'display_business_code', "") or "未知"
        is_sell = any(k in bus_type for k in ["卖出", "赎回", "转换出"])
        
        confirm_amount = clean_amount(confirm_val)
        apply_amount = clean_amount(apply_val)
        
        final_amount = 0.0
        if is_sell:
            # 卖出：优先取确认金额
            if confirm_amount > 0:
                final_amount = confirm_amount
            # 如果未确认且无金额，保持为 0 (仅在日志中体现，不计入现金流以免错误)
        else:
            # 买入：优先取确认金额，其次申请金额
            if confirm_amount > 0:
                final_amount = confirm_amount
            else:
                final_amount = apply_amount

        # 记录交易明细用于展示
        trade_details.append({
            "date": trade_date.strftime("%Y-%m-%d"),
            "type": bus_type,
            "amount": final_amount,
            "status": status_text
        })

        # 检查是否为"未确认"的买入（在途资金）
        # 状态如 "已受理"、"确认中" 等
        is_pending = "受理" in status_text or "确认中" in status_text or "提交" in status_text
        
        # 构建现金流
        if final_amount > 0:
            if "买" in bus_type or "申购" in bus_type or "定投" in bus_type or "转入" in bus_type:
                # 只有当这笔买入尚未确认时，我们才标记它，后续可能需要特殊处理
                # 但在现金流计算中，钱已经出去了，记为流出是正确的（因为计算XIRR时，这笔钱已经离开了钱包）
                # 关键在于期末资产是否包含这笔钱的价值
                cashflows.append(-final_amount)
                dates.append(trade_date)
                total_buy += final_amount
                buy_count += 1
                
                if is_pending:
                    logger.info(f"发现在途买入交易: {trade_date} {final_amount}，将在期末资产中加回")
                    # 我们需要一个变量来存储在途买入金额，稍后加到 current_asset_value 中
                    # 但由于 python 闭包限制，这里使用全局变量或者对象属性比较麻烦，我们简单地用一个列表收集
                    pass 

            elif "卖" in bus_type or "赎回" in bus_type or "转出" in bus_type:
                cashflows.append(final_amount)
                dates.append(trade_date)
                total_sell += final_amount
                sell_count += 1
            elif "分红" in bus_type:
                 # 如果是现金分红
                 if "现金" in bus_type or "红利" in bus_type: 
                     # 分红是收入，计入 cashflow
                     cashflows.append(final_amount)
                     dates.append(trade_date)
                     # 同时也应该计入 total_sell (作为广义的回款/收入)
                     total_sell += final_amount
    
    # 计算在途买入金额（未确认的买入）
    pending_buy_amount = 0.0
    for detail in trade_details:
        if detail['amount'] > 0 and ("买" in detail['type'] or "申购" in detail['type'] or "定投" in detail['type'] or "转入" in detail['type']):
             if "受理" in detail['status'] or "确认中" in detail['status'] or "提交" in detail['status']:
                 pending_buy_amount += detail['amount']

    if pending_buy_amount > 0:
        logger.info(f"在途买入总金额: {pending_buy_amount}")

    # 2. 获取当前持仓市值
    # 我们需要遍历所有子账户来找到这个基金的持仓，或者如果知道子账户可以直接查
    # 这里我们使用一个假设：尝试获取该基金的资产详情。
    # 由于 get_fund_asset_detail 需要 sub_account_no，我们可能需要先找到它所在的组合。
    # 或者，我们可以假设它可能在"普通账户"或者某个组合里。
    # 这里我们简化处理：假设 TradeResult 里没有 sub_account_no 信息，我们可能无法直接定位。
    # 但是，我们可以通过 get_trades_list 返回的信息看看有没有 sub_account 关联。
    # 如果找不到，我们尝试从所有组合中搜索。
    
    current_asset_value = 0.0
    current_hold_profit = 0.0
    
    # 尝试查找资产
    # 我们可以调用 get_asset_list_of_sub 遍历常见组合，或者直接利用 TradeResult 里的信息
    # 既然是分析，我们简单遍历一下几个主要组合，或者如果用户只有一个主账户。
    # 为了准确，我们打印一下提示，如果找不到当前持仓，可能导致收益率计算偏低（假设已清仓）。
    
    # 我们可以利用 get_fund_asset_detail 的逻辑，但是需要 sub_account_no。
    # 我们可以先调用 getSubAccountList 获取所有子账户，然后遍历查找。
    from src.API.组合管理.SubAccountMrg import getSubAccountList
    from src.API.资产管理.getAssetListOfSub import get_asset_list_of_sub
    
    sub_accounts_resp = getSubAccountList(user)
    found_asset = False
    
    if sub_accounts_resp.Success:
        for sub_acc in sub_accounts_resp.Data:
            assets = get_asset_list_of_sub(user, sub_acc.sub_account_no)
            for asset in assets:
                if asset.fund_code == fund_code:
                    current_asset_value = asset.asset_value
                    current_hold_profit = asset.hold_profit
                    found_asset = True
                    logger.info(f"在组合 '{sub_acc.sub_account_name}' 中找到持仓，当前市值: {current_asset_value}")
                    break
            if found_asset:
                break
    
    if not found_asset:
        logger.warning("未在任何组合中找到当前持仓，假设已清仓或市值为0。")

    # 修正：将在途买入金额加回期末资产（因为这部分钱虽然付出了，但变成了在途资产，价值还在）
    # 假设 get_asset_list_of_sub 返回的 asset_value 不包含在途交易（通常如此，除非是 T+1 确认后）
    final_asset_value = current_asset_value + pending_buy_amount

    # 添加终值现金流（当前市值 + 在途资产，视为在今天卖出）
    if final_asset_value > 0:
        cashflows.append(final_asset_value)
        dates.append(datetime.now())
        
    # 按日期排序打印交易明细
    trade_details.sort(key=lambda x: x['date'])
    
    print("\n" + "="*50)
    print(f"基金 {fund_code} 最近一年交易分析报告")
    print("="*50)
    print(f"统计区间: {one_year_ago.strftime('%Y-%m-%d')} 至 {datetime.now().strftime('%Y-%m-%d')}")
    print("-" * 50)
    print(f"{'日期':<15} {'类型':<10} {'金额':<10} {'状态'}")
    print("-" * 50)
    for detail in trade_details:
        print(f"{detail['date']:<15} {detail['type']:<10} {detail['amount']:<10.2f} {detail['status']}")
    print("-" * 50)
    
    # 3. 计算收益指标
    # 净利润 = (总卖出 + 分红) + (期末持仓 + 在途资产) - 总投入
    net_profit = total_sell + final_asset_value - total_buy
    roi = (net_profit / total_buy * 100) if total_buy > 0 else 0.0
    
    # 计算 XIRR
    xirr_value = calculate_xirr(cashflows, dates)
    xirr_percent = xirr_value * 100 if xirr_value is not None else 0.0
    
    print(f"\n【收益统计】")
    print(f"总买入金额: {total_buy:.2f} (含在途: {pending_buy_amount:.2f})")
    print(f"总卖出金额: {total_sell:.2f} (含分红)")
    print(f"当前持仓市值: {current_asset_value:.2f}")
    print(f"期末总资产: {final_asset_value:.2f} (含在途)")
    print(f"绝对收益额: {net_profit:.2f}")
    print(f"绝对收益率: {roi:.2f}%")
    print(f"内部收益率 (XIRR): {xirr_percent:.2f}% (年化)")
    
    # 4. 评价
    print(f"\n【投资评价】")
    
    # 频率评价
    freq_comment = ""
    if buy_count + sell_count > 24: # 平均每月超过2次
        freq_comment = "操作较为频繁，属于积极交易型。"
    elif buy_count + sell_count > 12: # 平均每月超过1次
        freq_comment = "操作频率适中，保持了一定的定投或调整节奏。"
    else:
        freq_comment = "操作频率较低，偏向长期持有或低频定投。"
        
    print(f"1. 操作风格: 近一年买入 {buy_count} 次，卖出 {sell_count} 次。{freq_comment}")
    
    # 收益评价
    score_comment = ""
    if xirr_percent > 20:
        score_comment = "收益表现非常优秀，远超市场平均水平。"
    elif xirr_percent > 10:
        score_comment = "收益表现良好，跑赢了大部分理财产品。"
    elif xirr_percent > 0:
        score_comment = "收益表现一般，实现了正收益但未显著跑赢通胀或基准。"
    elif xirr_percent > -10:
        score_comment = "出现小幅亏损，建议检视持仓成本和市场环境。"
    else:
        score_comment = "亏损幅度较大，建议重新评估该基金的投资逻辑或止损。"
        
    print(f"2. 收益表现: {score_comment}")
    
    # 结合当前持有收益的评价
    if current_asset_value > 0:
        if current_hold_profit > 0:
            print(f"3. 持仓现状: 当前持仓处于盈利状态，可以考虑根据止盈策略分批落袋为安。")
        else:
            print(f"3. 持仓现状: 当前持仓处于浮亏状态，如果基本面未变，可考虑低位补仓摊薄成本。")
    else:
        print(f"3. 持仓现状: 当前无持仓。")

    print("="*50 + "\n")

if __name__ == "__main__":
    analyze_fund_performance(DEFAULT_USER, FUND_CODE)
