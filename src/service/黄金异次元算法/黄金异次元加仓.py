import logging
import sys
import os
import datetime
from typing import Optional

# 获取项目根目录路径
root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# 如果项目根目录不在Python路径中，则添加
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from src.common.logger import get_logger
from src.domain.user.User import User
from src.API.组合管理.SubAccountMrg import getSubAccountNoByName
from src.service.交易管理.购买基金 import commit_order
from src.service.公共服务.trade_guard_service import has_buy_submission_on_dates
from src.service.基金信息.基金信息 import get_all_fund_info
from src.service.资产管理.get_fund_asset_detail import get_sub_account_asset_by_name

logger = get_logger(__name__)

TARGET_FUND_CODE = "021740"  # 前海开源黄金ETF联接C

def increase_gold_dimension_funds(user: User, sub_account_name: str, amount: float = 50000.0) -> bool:
    """
    黄金异次元组合加仓逻辑：
    周一到周五 下午2:53分执行。
    
    逻辑总结：
    1. 检查在途交易：如果有针对 021740 的在途买入，直接跳过。
    2. 获取持仓信息：
       - 无持仓：视为初始化建仓，直接买入 50000。
       - 有持仓：
         - 如果当前盈利 (Rate >= -1.0)，不加仓。
         - 如果当前亏损 (Rate < -1.0)，进行严格检查：
           a. 排名检查：
              - 30日排名 >= 5 (拒绝极低位)
              - 20 <= 100日排名 <= 90 (拒绝极低和极高位，处于震荡区间)
           b. 趋势检查 (短期向好)：
              - 如果近三月收益 < 0：要求 近一月 >= 0 且 近一周 >= 0
              - 如果近三月收益 > 0 且 近一月 < 0：要求 近一周 >= 0
           c. 满足以上条件后，根据亏损幅度计算买入金额：
              - 基础金额: 50000
              - 亏损 > 3% (Rate < -3.0): +50000
              - 亏损 > 5% (Rate < -5.0): +50000
              - 最大单笔可能买入 150000
    """
    logger.info(f"开始执行黄金异次元组合加仓检查，组合: {sub_account_name}", extra={"account": user.account, "sub_account_name": sub_account_name, "action": "gold_dimension_increase"})

    # 1. 获取子账户编号
    sub_account_no = getSubAccountNoByName(user, sub_account_name)
    if not sub_account_no:
        logger.error(f"未找到组合 {sub_account_name} 的账号")
        return False

    # 2. 检查在途交易
    if check_pending_trade(user, sub_account_no, TARGET_FUND_CODE):
        logger.info(f"目标基金 {TARGET_FUND_CODE} 存在在途交易，跳过加仓")
        return True

    # 3. 获取基金详细信息 (排名、收益率等)
    fi = get_all_fund_info(user, TARGET_FUND_CODE)
    if not fi:
        logger.error(f"无法获取基金 {TARGET_FUND_CODE} 的详细信息，跳过加仓")
        return False

    # 4. 获取持仓情况
    user_assets = get_sub_account_asset_by_name(user, sub_account_name)
    target_asset = None
    if user_assets:
        for asset in user_assets:
            if asset.fund_code == TARGET_FUND_CODE:
                target_asset = asset
                break
    
    # 5. 决策逻辑
    final_amount = 0.0
    
    # 检查是否有有效持仓 (份额 > 0)
    has_position = False
    if target_asset:
        try:
            vol = float(getattr(target_asset, 'available_vol', 0) or 0)
            val = float(getattr(target_asset, 'asset_value', 0) or 0)
            if vol > 0.01 or val > 1.0: # 稍微给点容差，避免浮点数0.000001的情况
                has_position = True
        except:
            pass

    if not has_position:
        # Case 1: 无持仓（或份额为0），初始化建仓
        logger.info(f"组合无 {TARGET_FUND_CODE} 有效持仓，执行初始化建仓")
        final_amount = amount
            
    else:
        # Case 2: 有持仓
        current_profit_rate = float(getattr(target_asset, "constant_profit_rate", 0.0) or 0.0)
        
        # 计算预估收益率
        estimated_change = fi.estimated_change if fi.estimated_change is not None else 0.0
        estimated_profit_rate = current_profit_rate + estimated_change
        
        logger.info(f"当前持仓收益率: {current_profit_rate}%, 估值变动: {estimated_change}%, 预估收益率: {estimated_profit_rate:.2f}%")
        
        if estimated_profit_rate >= -1.0:
            logger.info(f"预估收益率 ({estimated_profit_rate:.2f}%) >= -1.0%，不触发加仓")
            return True
            
        # 亏损状态，进行严格检查
        
        # a. 排名检查
        # 30日排名 >= 5
        if fi.rank_30day is not None and fi.rank_30day < 5:
            logger.info(f"30日排名过低 ({fi.rank_30day} < 5)，不满足加仓条件")
            return True
            
        # 20 <= 100日排名 <= 90
        if fi.rank_100day is not None and not (20 <= fi.rank_100day <= 90):
            logger.info(f"100日排名不在区间 [20, 90] 内 ({fi.rank_100day})，不满足加仓条件")
            return True
            
        # b. 趋势检查
        season_syl = fi.three_month_return if fi.three_month_return is not None else 0.0
        month_syl = fi.month_return if fi.month_return is not None else 0.0
        week_syl = fi.week_return if fi.week_return is not None else 0.0
        
        logger.info(f"趋势指标: 季={season_syl}%, 月={month_syl}%, 周={week_syl}%")
        
        trend_ok = True
        if season_syl < 0:
            if month_syl < 0 or week_syl < 0:
                logger.info("趋势不佳 (季<0, 且 月<0 或 周<0)，不满足加仓条件")
                trend_ok = False
        elif season_syl > 0:
            if month_syl < 0 and week_syl < 0:
                logger.info("趋势不佳 (季>0, 但 月<0 且 周<0)，不满足加仓条件")
                trend_ok = False
        
        if not trend_ok:
            return True
            
        # c. 计算金额
        final_amount = amount
        logger.info(f"基础加仓条件满足，初始金额: {final_amount}")
        
        if estimated_profit_rate < -3.0:
            final_amount += amount
            logger.info(f"预估收益率 < -3.0%，追加 {amount}，当前: {final_amount}")
            
        if estimated_profit_rate < -5.0:
            final_amount += amount
            logger.info(f"预估收益率 < -5.0%，追加 {amount}，当前: {final_amount}")

    # 6. 执行交易
    if final_amount > 0:
        logger.info(f"准备买入 {TARGET_FUND_CODE}，金额: {final_amount}")
        res = commit_order(user, sub_account_no, TARGET_FUND_CODE, final_amount)
        if res:
            logger.info(f"加仓提交成功: 订单号 {res.busin_serial_no}")
            return True
        else:
            logger.error(f"加仓提交失败")
            return False
            
    return True

def check_pending_trade(user: User, sub_account_no: str, fund_code: str) -> bool:
    """检查是否有在途买入交易"""
    # 获取昨日净值日期
    try:
        fi = get_all_fund_info(user, fund_code)
        nav_date_str = getattr(fi, "nav_date", None)
        prev_trade_day = datetime.datetime.strptime(nav_date_str, "%Y-%m-%d").date() if nav_date_str else None
    except Exception:
        prev_trade_day = None
    
    today = datetime.date.today()
    check_dates = {today}
    if prev_trade_day:
        check_dates.add(prev_trade_day)

    return has_buy_submission_on_dates(user, sub_account_no, fund_code, check_dates)

if __name__ == "__main__":
    from src.common.constant import DEFAULT_USER
    try:
        # 1. 构造测试用户
        test_user = DEFAULT_USER
        
        # 2. 设置测试参数
        test_sub_account = "黄金异次元"
        test_amount = 50000.0

        print(f"--- 开始测试黄金异次元加仓 ---")
        print(f"用户: {test_user.customer_name}")
        print(f"组合: {test_sub_account}")
        
        # 3. 调用加仓函数
        increase_gold_dimension_funds(test_user, test_sub_account, test_amount)
        
        print(f"--- 测试结束 ---")

    except Exception as e:
        logger.error(f"测试执行失败: {e}")
