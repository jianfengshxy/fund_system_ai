import logging
from random import vonmisesvariate
import re
from typing import Optional
import threading
from concurrent.futures import ThreadPoolExecutor
import os
import sys
import math

# 获取项目根目录路径
root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# 如果项目根目录不在Python路径中，则添加
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from src.service.定投管理.定投查询.定投查询 import get_all_fund_plan_details
from src.domain.user.User import User
from src.domain.user.User import User  
from src.domain.fund_plan.fund_plan_detail import FundPlanDetail
from src.API.交易管理.sellMrg import super_transfer
from src.service.基金信息.基金信息 import get_all_fund_info
from src.API.交易管理.trade import get_trades_list
from src.API.交易管理.revokMrg import revoke_order
from src.service.交易管理.购买基金 import commit_order
from src.domain.trade.TradeResult import TradeResult
from src.common.constant import DEFAULT_USER
from src.API.资产管理.getAssetListOfSub import get_asset_list_of_sub
from src.service.资产管理.get_fund_asset_detail import get_fund_asset_detail
import datetime
from datetime import datetime
import math
from src.domain.fund_plan.fund_plan import FundPlan
from src.domain.fund_plan.fund_plan_detail import FundPlanDetail
from src.API.基金信息.FundRank import get_fund_growth_rate
from src.API.交易管理.trade import get_trades_list, get_bank_shares
from src.service.交易管理.交易查询 import count_success_trades_on_prev_nav_day
from src.service.公共服务.nav_gate_service import nav5_gate
from src.service.公共服务.risk_control_service import check_hqb_risk_allowed

logging.basicConfig(
    stream=sys.stdout,
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)    

from typing import Optional
from src.domain.asset.asset_details import AssetDetails

def increase(user: User, plan_detail: FundPlanDetail) -> bool:
    # 顶部导入片段
    import logging
    logger.info(f"========== 开始执行加仓算法 ==========")
    customer_name=user.customer_name
    logger.info(f"用户: {customer_name}")
    
    # 获取基金信息
    fund_code = plan_detail.rationPlan.fundCode
    fund_name = plan_detail.rationPlan.fundName
    logger.info(f"处理基金: {fund_name} {fund_code}")
    
    try:
        fund_info = get_all_fund_info(user, fund_code)
        fund_name = fund_info.fund_name
        logger.info(f"基金名称: {fund_name}")
        logger.info(f"基金估值增长率: {fund_info.estimated_change}")
        logger.info(f"基金100日排名: {fund_info.rank_100day}, 30日排名: {fund_info.rank_30day}")
    except Exception as e:
        logger.error(f"获取基金信息失败: {e}")
        return False
        
    sub_account_no = plan_detail.rationPlan.subAccountNo
    sub_account_name = plan_detail.rationPlan.subAccountName
    
    # 获取银行份额信息，添加异常处理
    try:
        shares = get_bank_shares(user, sub_account_no, fund_code)
    except Exception as e:
        logger.warning(f"获取银行份额信息失败，将使用空份额列表继续处理: {e}")
        return False
    
    period_type = plan_detail.rationPlan.periodType
    period_value = plan_detail.rationPlan.periodValue
    fund_amount = plan_detail.rationPlan.amount 
    plan_type = plan_detail.rationPlan.planType
    
    #获取当前日期
    current_date = datetime.now()
    # 提取当天的日期（即本月的第几天）
    day_of_month = current_date.day
    # 获取星期几的数字表示（0 表示周一，1 表示周二，依此类推）
    day_of_week_number = current_date.weekday()     
    logger.info(f"时间信息 - 当前日期: {current_date.strftime('%Y-%m-%d')}, 月份第{day_of_month}天, 星期{day_of_week_number + 1}")
  
    # 检查是否有可回撤的定投交易，4是定投业务类型，7是可以回撤交易状态
    try:
        trades = get_trades_list(user, sub_account_no=sub_account_no, fund_code = fund_code,bus_type="4", status="7")
        logger.info(f"{fund_name}({fund_code}) 查询可回撤交易 - 找到{len(trades) if trades else 0}笔可回撤的定投交易")
    except Exception as e:
        logger.error(f"查询可回撤交易失败: {e}")
        return False   

    if not trades:
            logger.info(f"{fund_name}({fund_code}) [均线风控] 无可撤回交易，跳过撤单")
            return True
    
    logger.info(f"计划详情 - 组合账号: {sub_account_no}, 组合名称: {sub_account_name}")
    logger.info(f"计划详情 - 周期类型: {period_type}, 周期值: {period_value}, 定投金额: {fund_amount}, 计划类型: {plan_type}")
    
    #这里最强风控处理极端情况
    # Strict Bear Protection (Triple Circuit Breaker)
    # 逻辑: 如果年收益率 <= 0 或 半年收益率 <= 0 或 季度收益率 <= 0, 停止一切加仓.
    
    # 1. 获取收益率数据 (Handle None values safely)
    season_return = getattr(fund_info, "three_month_return", None)
    half_year_return = getattr(fund_info, "six_month_return", None)
    year_return = getattr(fund_info, "year_return", None)
    
    # Convert to float or None if not valid
    season_val = float(season_return) if isinstance(season_return, (int, float)) else None
    half_year_val = float(half_year_return) if isinstance(half_year_return, (int, float)) else None
    year_val = float(year_return) if isinstance(year_return, (int, float)) else None
    
    # 获取活期宝占比 (新风控 - 统一调用公共服务)
    # 使用 check_hqb_risk_allowed 获取布尔值结果，如果返回 False，说明余额不足（< 阈值）
    # 但此处逻辑是：如果 check_hqb_risk_allowed(user, threshold=10.0) 返回 False，则 hqb_ratio_ok 为 False
    hqb_risk_passed = check_hqb_risk_allowed(user, threshold=20.0)
    
    # 注意：check_hqb_risk_allowed 内部已经打日志了，这里主要为了拿到状态用于后续 stop_reason 判断
    # 如果 hqb_risk_passed 为 False，说明 占比 < 10%
    
    try:
        asset_detail = get_fund_asset_detail(user, sub_account_no, fund_code)
    except Exception as e:
        logger.error(f"{fund_name}({fund_code}) 获取资产详情失败: {e}")
        return False
    asset_available_vol = float(getattr(asset_detail, "available_vol", 0.0) or 0.0) if asset_detail else 0.0
    asset_asset_value = float(getattr(asset_detail, "asset_value", 0.0) or 0.0) if asset_detail else 0.0

    if asset_asset_value == 0:
        logger.info(f"{fund_name}({fund_code}) 资产为0，直接跳过加仓逻辑，返回成功")
        return True

    bank_available_vol = 0.0
    try:
        bank_available_vol = sum(float(getattr(s, "availableVol", 0.0) or 0.0) for s in (shares or []))
    except Exception:
        bank_available_vol = 0.0
    has_position = (asset_asset_value > 1.0) or (asset_available_vol > 0.01) or (bank_available_vol > 0.01)
    
    # 新增：当活期宝占比不足，且当前有效份额≈0（未确认/在途），统一执行防守撤单（避免余额不足还继续开网格）
    if (not hqb_risk_passed) and (asset_available_vol <= 0.01):
        logger.info(f"[资金风控] 活期宝占比不足 20% 且 有效份额≈0，仅撤回可撤交易 - {fund_name}({fund_code})")
        if not trades:
            logger.info(f"[资金风控] 当日无可撤回定投记录，跳过撤单 - {fund_name}({fund_code})")
            return True
        for i, trade in enumerate(trades):
            logger.info(f"  -> 执行回撤 {i+1}/{len(trades)}: 序列号={trade.busin_serial_no}, 金额={trade.amount}")
            try:
                res = revoke_order(user, trade.busin_serial_no, trade.business_code, plan_detail.rationPlan.fundCode, trade.amount, sub_account_no=sub_account_no)
                if res.get("Success"):
                    logger.info("     回撤成功")
                else:
                    logger.error(f"     回撤失败: {res.get('Message')}")
            except Exception as e:
                logger.error(f"     回撤失败: {e}")
        return True

    stop_reason = None
    
    if half_year_val is not None and half_year_val <= 0:
        stop_reason = f"半年收益率({half_year_val}%) <= 0"
    elif year_val is not None and year_val <= 0:
        stop_reason = f"年收益率({year_val}%) <= 0"
    # HQB占比不足且无持仓的撤回已在上方统一处理，这里不再设置 stop_reason
    
    # 趋势豁免逻辑：虽然长期指标走弱，但如果短期趋势强劲，允许豁免拦截
    if stop_reason:
        # 1. 计算 20日均线 (使用 30日均线近似或从 fund_info 获取)
        # 简单使用 估算净值 > 5日均线 且 涨幅 > 1.0% 作为强趋势信号
        # 这里复用已有的 nav5_gate 逻辑判断是否站上5日线，并额外要求今日涨幅显著
        
        # 重新获取 5日均线状态 (前面可能没调用)
        is_trend_strong = False
        try:
            ma5_ok = nav5_gate(fund_info, fund_name, fund_code, logger)
            estimated_change = fund_info.estimated_change if fund_info.estimated_change is not None else 0.0
            
            # 豁免条件: 站上5日线 且 (今日大涨 > 1.5% 或 虽然长期弱但短期3个月已转正)
            season_positive = (season_val is not None and season_val > 0)
            
            if ma5_ok and (estimated_change > 1.5 or season_positive):
                is_trend_strong = True
                logger.info(f"{fund_name}({fund_code}) [趋势豁免] 触发豁免条件 - 长期弱势({stop_reason}) 但短期强势(站上5日线 且 (涨幅{estimated_change}%>1.5% 或 季度转正))，允许继续加仓")
                stop_reason = None # 清除拦截原因
        except Exception as e:
            logger.warning(f"趋势豁免判断异常: {e}")
        
    if stop_reason:
        logger.info(f"[风控拦截] 最强风控触发 - {fund_name}({fund_code}) 触发原因: {stop_reason}")
        # 回撤所有交易
        for i, trade in enumerate(trades):
            logger.info(f"  -> 执行回撤 {i+1}/{len(trades)}: 序列号={trade.busin_serial_no}, 金额={trade.amount}")
            try:
                revoke_order(user, trade.busin_serial_no, trade.business_code, plan_detail.rationPlan.fundCode, trade.amount, sub_account_no=sub_account_no)
                logger.info("     回撤成功")
            except Exception as e:
                logger.error(f"     回撤失败: {e}")
        logger.info(f"[风控拦截] 处理完毕，已跳过后续加仓")
        return True
    
    if asset_detail is not None:
        constant_profit_rate = asset_detail.constant_profit_rate
        logger.info(f"[资产快照] {fund_name}({fund_code}) 持仓市值: {asset_detail.asset_value:.2f}, 收益率: {constant_profit_rate}%, 估值变动: {fund_info.estimated_change}%")
    else:
        logger.info(f"[资产快照] {fund_name}({fund_code}) 无持仓资产，视为首次建仓/空仓")
        return True
        
    plan_assets = asset_detail.asset_value
    constant_profit_rate = asset_detail.constant_profit_rate  # 移除 * 100
    on_way_transaction_count = asset_detail.on_way_transaction_count
    times = round(plan_assets / fund_amount, 2)
    logger.info(f"[资产倍数] 当前资产/定投金额 = {plan_assets:.2f}/{fund_amount} = {times}倍")
    
    # 获取当前收益率和估值增长率
    current_profit_rate = constant_profit_rate if constant_profit_rate is not None else 0.0
    estimated_change = fund_info.estimated_change if fund_info.estimated_change is not None else 0.0
    estimated_profit_rate = current_profit_rate + estimated_change
    
    logger.info(f"[收益率预估] 预估收益率 = 当前({current_profit_rate}%) + 估值({estimated_change}%) = {estimated_profit_rate:.2f}%")

      #判断是否是月定投延期交易
    if period_type == 3 and  period_value != day_of_month: 
        logger.info(f"{fund_name}({fund_code}) [时间风控] 月定投延期拦截 - 计划日:{period_value} vs 今日:{day_of_month}，不匹配，撤回交易")
        #回撤所有交易   
        for i, trade in enumerate(trades):
            logger.info(f"  -> 执行回撤 {i+1}/{len(trades)}: 序列号={trade.busin_serial_no}, 金额={trade.amount}")
            try:
                revoke_order(user, trade.busin_serial_no, trade.business_code, plan_detail.rationPlan.fundCode, trade.amount, sub_account_no=sub_account_no)
                logger.info(f"     回撤成功")
            except Exception as e:
                logger.error(f"     回撤失败: {e}")
        return  True
                  
    # 5日均线守卫：对所有可回撤的买入/定投交易生效
    # 如果是周定投(1)或月定投(3)，即使是第一次(times<=1)也要检查；其他类型第一次不检查
    bypass_ma5 = (period_type not in [1, 3]) and (times <= 1)
    gate_ok = True if bypass_ma5 else bool(nav5_gate(fund_info, fund_name, fund_code, logger))
    if not gate_ok:
        logger.info(f"{fund_name}({fund_code}) [均线风控] 5日均线守卫未通过（估算净值≤5日均值）：撤回当天所有可回撤交易。资产={plan_assets:.2f} 定投金额={fund_amount:.2f}")
        for i, trade in enumerate(trades):
            logger.info(f"{fund_name}({fund_code})  -> 执行回撤 {i+1}/{len(trades)}: 序列号={trade.busin_serial_no}, 金额={trade.amount}")
            try:
                res = revoke_order(user, trade.busin_serial_no, trade.business_code, plan_detail.rationPlan.fundCode, trade.amount, sub_account_no=sub_account_no)
                if res and res.get("Success"):
                    logger.info("     回撤成功")
                else:
                    logger.error(f"     回撤失败: {res.get('Message') if res else 'Unknown error'}")
            except Exception as e:
                logger.error(f"     回撤失败: {e}")
        return True
    else:
        if bypass_ma5:
            logger.info(f"{fund_name}({fund_code}) [均线风控] 豁免：首次定投/资产积累期 (倍数{times}<=1)，跳过均线检查")
            return True  # 口子开启时直接通过并早停
        else:
            logger.info(f"{fund_name}({fund_code}) [均线风控] 通过：估算净值 > 5日均值，趋势向上")
            if period_type in [1, 3] and times <= 1:
                # 首次定投额外检查：避免追高 (Rank过低代表排名靠前，净值低，没有摆脱底部)
                rank_100 = getattr(fund_info, "rank_100day", None)
                rank_30 = getattr(fund_info, "rank_30day", None)
                
                should_revoke = False
                revoke_reason = ""
                
                if isinstance(rank_100, (int, float)) and rank_100 < 20:
                    should_revoke = True
                    revoke_reason = f"100日排名过低({rank_100} < 20)"
                elif isinstance(rank_30, (int, float)) and rank_30 < 5:
                    should_revoke = True
                    revoke_reason = f"30日排名过低({rank_30} < 5)"
                    
                if should_revoke:
                    logger.info(f"{fund_name}({fund_code}) [排名风控] 首次定投位置不佳 - {revoke_reason}，执行防守撤单")
                    if not trades:
                        logger.info(f"[排名风控] 无可撤回交易，跳过撤单")
                    for i, trade in enumerate(trades):
                        logger.info(f"  -> 执行回撤 {i+1}/{len(trades)}: 序列号={trade.busin_serial_no}, 金额={trade.amount}")
                        try:
                            res = revoke_order(user, trade.busin_serial_no, trade.business_code, plan_detail.rationPlan.fundCode, trade.amount, sub_account_no=sub_account_no)
                            if res and res.get("Success"):
                                logger.info("     回撤成功")
                            else:
                                logger.error(f"     回撤失败: {res.get('Message') if res else 'Unknown error'}")
                        except Exception as e:
                            logger.error(f"     回撤失败: {e}")
                    return True

                # 首次定投需同时满足活期宝占比阈值（不足则不新开仓）
                if not hqb_risk_passed and not has_position:
                    logger.info(f"{fund_name}({fund_code}) [资金风控] 活期宝占比不足 20% 且 无持仓资产，直接跳过，不开新仓")
                    for i, trade in enumerate(trades):
                        logger.info(f"{fund_name}({fund_code})  -> 执行回撤 {i+1}/{len(trades)}: 序列号={trade.busin_serial_no}, 金额={trade.amount}")
                        try:
                            revoke_order(user, trade.busin_serial_no, trade.business_code, plan_detail.rationPlan.fundCode, trade.amount, sub_account_no=sub_account_no)
                            logger.info("     回撤成功")
                        except Exception as e:
                            logger.error(f"     回撤失败: {e}")
                    return True

                logger.info(f"[首次风控] 通过：均线及排名检查均合格，继续持有")
                return True

    #判断是否是周定投延期交易
    if period_type == 1 and  period_value != day_of_week_number + 1:
        logger.info(f"{fund_name}({fund_code}) [时间风控] 周定投延期拦截 - 计划周:{period_value} vs 今日周:{day_of_week_number + 1}，不匹配，撤回交易")
        #回撤所有交易
        for i, trade in enumerate(trades):
            logger.info(f"{fund_name}({fund_code})  -> 执行回撤 {i+1}/{len(trades)}: 序列号={trade.busin_serial_no}, 金额={trade.amount}")
            try:
                revoke_order(user, trade.busin_serial_no, trade.business_code, plan_detail.rationPlan.fundCode, trade.amount, sub_account_no=sub_account_no)
                logger.info(f"     回撤成功")
            except Exception as e:
                logger.error(f"     回撤失败: {e}")
        return True
        
    # 使用“昨日净值日(nav_date)+今天”的守卫：任一天存在非撤的买入/定投则回撤并跳过
    from src.service.公共服务.trade_guard_service import has_buy_submission_on_dates
    nav_date_str = getattr(fund_info, "nav_date", None)
    try:
        prev_trade_day = datetime.strptime(nav_date_str, "%Y-%m-%d").date() if nav_date_str else None
    except Exception:
        prev_trade_day = None
    today = datetime.now().date()

    prev_trade_pre = has_buy_submission_on_dates(user, sub_account_no, fund_code, {d for d in [prev_trade_day] if d})
    today_trade_pre = has_buy_submission_on_dates(user, sub_account_no, fund_code, {today})
    
    if prev_trade_pre is not None:
        logger.info(f"{fund_name}({fund_code}) [频率风控] 交易过于频繁 - 昨日/今日已存在交易，避免重复加仓，撤回本次交易")
        # 撤回交易
        for i, trade in enumerate(trades):
            logger.info(f"  -> 执行回撤 {i+1}/{len(trades)}: 序列号={trade.busin_serial_no}, 金额={trade.amount}")
            try:
                revoke_order(user, trade.busin_serial_no, trade.business_code, plan_detail.rationPlan.fundCode, trade.amount, sub_account_no=sub_account_no)
                logger.info(f"     回撤成功")
            except Exception as e:
                logger.error(f"     回撤失败: {e}")
        return True
        

    logger.info(f"[加仓决策] 进入加仓逻辑判断...")
    
    # 首次定投例外：优先以计划执行次数判断，其次以资产倍数兜底
    is_first_investment = (times == 1.0)
    if is_first_investment:
        logger.info(f"{fund_name}({fund_code}) [加仓决策] 首次定投(times=1.0)，直接通过")
        return True

    if not is_first_investment and estimated_profit_rate > -1.0 :
        logger.info(f"{fund_name}({fund_code}) [加仓决策] 预估收益率({estimated_profit_rate:.2f}%) > -1.0%，不满足加仓条件，撤回交易")
        
        # 强制重新查询最新的可撤交易，防止缓存失效或状态不一致
        try:
            current_trades = get_trades_list(user, sub_account_no=sub_account_no, fund_code=fund_code, bus_type="4", status="7")
            logger.info(f"{fund_name}({fund_code}) [二次确认] 重新查询可撤交易，找到 {len(current_trades)} 笔")
            trades_to_revoke = current_trades
        except Exception as e:
            logger.warning(f"{fund_name}({fund_code}) [二次确认] 查询失败，使用原始列表: {e}")
            trades_to_revoke = trades

        #回撤所有交易
        for i, trade in enumerate(trades_to_revoke):
            logger.info(f"  -> 执行回撤 {i+1}/{len(trades_to_revoke)}: 序列号={trade.busin_serial_no}, 金额={trade.amount}")
            try:
                revoke_order(user, trade.busin_serial_no, trade.business_code, plan_detail.rationPlan.fundCode, trade.amount, sub_account_no=sub_account_no)
                logger.info(f"     回撤成功")
            except Exception as e:
                logger.error(f"     回撤失败: {e}")
        return  True  
        
    #判断shares数组里面的totalVol之和等于shares数组里面的availableVol之和不相等为True和上面操作一样撤回交易  
    totalVol = 0
    availableVol = 0
    for share in shares:
        totalVol += share.totalVol
        availableVol += share.availableVol
        
    if totalVol != availableVol:
        logger.info(f"{fund_name}({fund_code}) [状态风控] 份额异常 (Total:{totalVol} != Avail:{availableVol})，可能有在途卖出或冻结，撤回交易")
        # 撤回交易
        for i, trade in enumerate(trades):
            logger.info(f"  -> 执行回撤 {i+1}/{len(trades)}: 序列号={trade.busin_serial_no}, 金额={trade.amount}")
            try:
                revoke_order(user, trade.busin_serial_no, trade.business_code, plan_detail.rationPlan.fundCode, trade.amount, sub_account_no=sub_account_no)
                logger.info(f"     回撤成功")
            except Exception as e:
                logger.error(f"     回撤失败: {e}")
        return True
        
    #计算当前可以回撤的交易数量 
    try:
        revoke_count = len(get_trades_list(user, sub_account_no=sub_account_no, fund_code = fund_code,bus_type="", status="7"))
    except Exception as e:
        logger.error(f"统计可回撤交易失败: {e}")
        return False
        
    if  revoke_count == 1:
        logger.info(f"[单笔加仓] 当前仅有一笔可撤回交易，进行详细风控检查")
        if estimated_profit_rate < -1.0 :
            # 提取并校验排名字段，缺失时给出跳过原因并不参与阈值判断
            fund_name = plan_detail.rationPlan.fundName
            fund_code = plan_detail.rationPlan.fundCode
            rank_100 = getattr(fund_info, "rank_100day", None)
            rank_30 = getattr(fund_info, "rank_30day", None)
            
            if isinstance(rank_100, (int, float)) and isinstance(rank_30, (int, float)):
                if rank_100 < 20:
                    logger.info(f"[排名风控] 100日排名过低 ({rank_100} < 20)，执行撤单")
                    # 回撤交易
                    for i, trade in enumerate(trades):
                        logger.info(f"{fund_name}({fund_code})  -> 执行回撤 {i+1}/{len(trades)}: 序列号={trade.busin_serial_no}, 金额={trade.amount}")
                        try:
                            revoke_order(user, trade.busin_serial_no, trade.business_code, plan_detail.rationPlan.fundCode, trade.amount, sub_account_no=sub_account_no)
                            logger.info("     回撤成功")
                        except Exception as e:
                            logger.error(f"     回撤失败: {e}")
                    return True
                if rank_100 > 90:
                    logger.info(f"[排名风控] 100日排名过高 ({rank_100} > 90)，风险过大，执行撤单")
                    for i, trade in enumerate(trades):
                        logger.info(f"  -> 执行回撤 {i+1}/{len(trades)}: 序列号={trade.busin_serial_no}, 金额={trade.amount}")
                        try:
                            revoke_order(user, trade.busin_serial_no, trade.business_code, plan_detail.rationPlan.fundCode, trade.amount, sub_account_no=sub_account_no)
                            logger.info("     回撤成功")
                        except Exception as e:
                            logger.error(f"     回撤失败: {e}")
                    return True
                if rank_30 < 5:
                    logger.info(f"[排名风控] 30日排名过低 ({rank_30} < 5)，执行撤单")
                    for i, trade in enumerate(trades):
                        logger.info(f"  -> 执行回撤 {i+1}/{len(trades)}: 序列号={trade.busin_serial_no}, 金额={trade.amount}")
                        try:
                            revoke_order(user, trade.busin_serial_no, trade.business_code, plan_detail.rationPlan.fundCode, trade.amount, sub_account_no=sub_account_no)
                            logger.info("     回撤成功")
                        except Exception as e:
                            logger.error(f"     回撤失败: {e}")
                    return True

            # 收益率字段防空与类型兜底（缺失时按0.0处理并打印原因）
            week_growth_raw = getattr(fund_info, "week_return", None)
            month_growth_raw = getattr(fund_info, "month_return", None)
            season_growth_raw = getattr(fund_info, "three_month_return", None)
            
            week_growth_rate = float(week_growth_raw) if isinstance(week_growth_raw, (int, float)) else 0.0
            month_growth_rate = float(month_growth_raw) if isinstance(month_growth_raw, (int, float)) else 0.0
            season_growth_rate = float(season_growth_raw) if isinstance(season_growth_raw, (int, float)) else 0.0

            logger.info(f"[周期收益] 周:{week_growth_rate}%, 月:{month_growth_rate}%, 季:{season_growth_rate}%")

            if  week_growth_rate <  0.0 and month_growth_rate < 0.0 and season_growth_rate < 0.0:
                logger.info(f"[趋势风控] 全部周期收益率为负 (周/月/季 < 0)，下跌趋势确立，执行撤单")
                # 回撤所有交易  
                for i, trade in enumerate(trades):
                    logger.info(f"  -> 执行回撤 {i+1}/{len(trades)}: 序列号={trade.busin_serial_no}, 金额={trade.amount}")
                    try:
                        revoke_order(user, trade.busin_serial_no, trade.business_code, plan_detail.rationPlan.fundCode, trade.amount, sub_account_no=sub_account_no)
                        logger.info("     回撤成功")
                    except Exception as e:
                        logger.error(f"     回撤失败: {e}")
                return  True    

            if  season_growth_rate < 0.0 and (month_growth_rate < 0.0 or week_growth_rate < 0.0 ):
                logger.info(f"[趋势风控] 季度为负且(月或周)为负，跳过加仓")
                return  True

            if  season_growth_rate > 0.0 and (month_growth_rate < 0.0 and week_growth_rate < 0.0 ):
                logger.info(f"[趋势风控] 季度为正但(月和周)均为负，跳过加仓")
                return  True

            # 月/季排名比例防空（仅在可计算时参与判断）
            month_rank_rate = None
            season_rank_rate = None
            try:
                _, month_item_rank, month_item_sc = get_fund_growth_rate(fund_info, 'Y')
                if month_item_rank is not None and month_item_sc not in (None, 0):
                    month_rank_rate = float(month_item_rank) / float(month_item_sc)
            except Exception as e:
                logger.info(f"获取月度排名数据异常: {e}")
            try:
                _, season_item_rank, season_item_sc = get_fund_growth_rate(fund_info, 'S')
                if season_item_rank is not None and season_item_sc not in (None, 0):
                    season_rank_rate = float(season_item_rank) / float(season_item_sc)
            except Exception as e:
                logger.info(f"获取季度排名数据异常: {e}")

            if (month_rank_rate is not None and month_rank_rate > 0.75) or (season_rank_rate is not None and season_rank_rate > 0.75):
                logger.info(f"[排名风控] 月/季排名比例过高 (月:{month_rank_rate:.2f}, 季:{season_rank_rate:.2f} > 0.75)，执行撤单")
                for i, trade in enumerate(trades):
                    logger.info(f"  -> 执行回撤 {i+1}/{len(trades)}: 序列号={trade.busin_serial_no}, 金额={trade.amount}")
                    try:
                        revoke_order(user, trade.busin_serial_no, trade.business_code, plan_detail.rationPlan.fundCode, trade.amount, sub_account_no=sub_account_no)
                        logger.info("     回撤成功")
                    except Exception as e:
                        logger.error(f"     回撤失败: {e}")
                return True

            logger.info(f"[加仓确认] 所有风控检查通过，确认加仓") 
            
            # 3倍逻辑检查
            if estimated_profit_rate < -5.0 and times > 15 :
                logger.info(f"[加仓执行] 触发3倍暴击! 预估收益率:{estimated_profit_rate}% < -5.0% 且 资产倍数:{times} > 15")
                try:
                    commit_order(user, sub_account_no, fund_code, fund_amount * 3.0)
                    logger.info(f"  -> 3倍加仓提交成功: 金额 {fund_amount * 3.0}")
                except Exception as e:
                    logger.error(f"  -> 3倍加仓提交失败: {e}")
                return True 
                
            # 基础加仓
            try:
                logger.info(f"[加仓执行] 基础加仓: 金额 {fund_amount}")
                commit_order(user, sub_account_no, fund_code, fund_amount )
                logger.info(f"  -> 基础加仓提交成功")
            except Exception as e:
                logger.error(f"  -> 基础加仓提交失败: {e}")
                
            # -3.0%额外加仓
            if estimated_profit_rate < -3.0 :
                try:
                    logger.info(f"[加仓执行] 触发-3%额外加仓: 金额 {fund_amount}")
                    commit_order(user, sub_account_no, fund_code, fund_amount )
                    logger.info(f"  -> 额外加仓提交成功")
                except Exception as e:
                    logger.error(f"  -> 额外加仓提交失败: {e}")
                    
            # -5.0%额外加仓
            if estimated_profit_rate < -5.0 :
                try:
                    logger.info(f"[加仓执行] 触发-5%额外加仓: 金额 {fund_amount}")
                    commit_order(user, sub_account_no, fund_code, fund_amount )
                    logger.info(f"  -> 额外加仓提交成功")
                except Exception as e:
                    logger.error(f"  -> 额外加仓提交失败: {e}")
                    
    logger.info(f"========== 加仓算法执行完成 ==========")
    return True

def increase_all_fund_plans(user: User):
    logger.info(f"========== 开始执行全部基金计划加仓 ==========")
    logger.info(f"用户: {user.customer_name}")
    
    try:
        fund_plan_details = get_all_fund_plan_details(user)
        logger.info(f"获取到{len(fund_plan_details)}个基金计划")
    except Exception as e:
        logger.error(f"获取基金计划详情失败: {e}")
        return
    
    # 3. 执行加仓逻辑
    with ThreadPoolExecutor(max_workers=1) as executor:
        futures = []
        for plan_detail in fund_plan_details:
            # 直接调用 increase，不做预取优化
            futures.append(executor.submit(increase, user, plan_detail))
        
        results = []
        for i, future in enumerate(futures):
            try:
                results.append(future.result())
            except Exception as e:
                logger.error(f"定投计划线程执行异常（index={i}）: {e}")
                results.append(False)
        
        success_count = sum(1 for result in results if result)
        logger.info(f"{user.customer_name}有{len(results)}个定投计划执行加仓操作，成功{success_count}个，失败{len(results) - success_count}个")
        
    logger.info(f"========== 全部基金计划加仓执行完成 ==========")


if __name__ == "__main__":
    increase_all_fund_plans(DEFAULT_USER)
