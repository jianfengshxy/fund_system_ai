import logging
import sys
import os

# 获取项目根目录路径
root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# 如果项目根目录不在Python路径中，则添加
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from src.common.logger import get_logger
import datetime
from typing import Optional

from src.domain.user.User import User
from src.service.资产管理.get_fund_asset_detail import get_sub_account_asset_by_name
from src.API.组合管理.SubAccountMrg import getSubAccountNoByName
from src.service.交易管理.购买基金 import commit_order
from src.service.公共服务.trade_guard_service import has_buy_submission_on_dates
from src.service.基金信息.基金信息 import get_all_fund_info

logger = get_logger(__name__)

def increase_gold_funds(user: User, sub_account_name: str, amount: float = 10000.0) -> bool:
    """
    黄金多利组合加仓逻辑：
    只有收益率小于-1.0% 且 没有在途交易 就买入 前海开源黄金ETF联接C 021740 10000.0
    """
    logger.info(f"开始执行黄金多利组合加仓检查，组合: {sub_account_name}", extra={"account": user.account, "sub_account_name": sub_account_name, "action": "gold_increase"})

    # 获取子账户编号
    sub_account_no = getSubAccountNoByName(user, sub_account_name)
    if not sub_account_no:
        logger.error(f"未找到组合 {sub_account_name} 的账号")
        return False

    target_fund_code = "021740" # 前海开源黄金ETF联接C
    
    # 获取持仓
    user_assets = get_sub_account_asset_by_name(user, sub_account_name)
    if not user_assets:
        logger.info(f"组合 {sub_account_name} 中没有基金资产，视为初始化建仓")
        # 直接买入目标基金
        res = commit_order(user, sub_account_no, target_fund_code, amount)
        if res:
            logger.info(f"初始化建仓成功: {target_fund_code} - 金额: {amount} - 订单号: {res.busin_serial_no}")
            return True
        else:
            logger.error(f"初始化建仓失败: {target_fund_code}")
            return True

    buy_triggered = False

    # 检查持仓收益率
    for asset in user_assets:
        try:
            # 获取收益率
            current_profit_rate = float(getattr(asset, "constant_profit_rate", 0.0) or 0.0)
            fund_code = asset.fund_code
            fund_name = asset.fund_name

            # 获取基金估值信息
            fund_info = get_all_fund_info(user, fund_code)
            estimated_change = fund_info.estimated_change if fund_info and fund_info.estimated_change is not None else 0.0
            
            # 计算预估收益率 = 当前收益率 + 估值涨跌幅
            estimated_profit_rate = current_profit_rate + estimated_change
            
            logger.info(f"基金 {fund_name}({fund_code}) 当前收益率: {current_profit_rate}%, 估值变动: {estimated_change}%, 预估收益率: {estimated_profit_rate:.2f}%")

            if estimated_profit_rate < -1.0:
                logger.info(f"基金 {fund_name}({fund_code}) 预估收益率 {estimated_profit_rate:.2f}% < -1.0%，触发加仓判定")
                
                # 检查目标基金 021740 是否有在途交易
                # 只有没有在途交易时才买入
                
                # 获取昨日净值日期（为了检查 trade guard）
                # 这里简单起见，检查目标基金 021740 的在途情况
                fi = get_all_fund_info(user, target_fund_code)
                nav_date_str = getattr(fi, "nav_date", None)
                try:
                    prev_trade_day = datetime.datetime.strptime(nav_date_str, "%Y-%m-%d").date() if nav_date_str else None
                except Exception:
                    prev_trade_day = None
                today = datetime.date.today()
                
                check_dates = {today}
                if prev_trade_day:
                    check_dates.add(prev_trade_day)

                pending_trade = has_buy_submission_on_dates(user, sub_account_no, target_fund_code, check_dates)
                
                if pending_trade:
                    logger.info(f"目标基金 {target_fund_code} 存在在途交易，跳过加仓")
                    continue
                
                # 执行买入
                logger.info(f"满足加仓条件，买入 {target_fund_code} {amount}元")
                res = commit_order(user, sub_account_no, target_fund_code, amount)
                if res:
                    logger.info(f"加仓成功: {target_fund_code} - 金额: {amount} - 订单号: {res.busin_serial_no}")
                    buy_triggered = True
                    break # 每次只加仓一笔，避免重复
                else:
                    logger.error(f"加仓提交失败: {target_fund_code}")
            else:
                logger.info(f"基金 {fund_name}({fund_code}) 预估收益率 {estimated_profit_rate:.2f}% >= -1.0%，不满足加仓条件")

            
        except Exception as e:
            logger.error(f"处理基金 {asset.fund_code} 时发生错误: {e}")
            continue

    if not buy_triggered:
        logger.info("本次检查未触发加仓操作")

    return True

if __name__ == "__main__":
    from src.common.constant import DEFAULT_USER
    try:
        # 1. 构造测试用户（或者使用默认用户）
        # 这里使用 DEFAULT_USER 进行测试，确保 s.yaml 中的账号密码配置正确
        test_user = DEFAULT_USER
        
        # 2. 设置测试参数
        test_sub_account = "黄金多利"
        test_amount = 10000.0

        print(f"--- 开始测试黄金多利加仓 ---")
        print(f"用户: {test_user.customer_name}")
        print(f"组合: {test_sub_account}")
        
        # 3. 调用加仓函数
        increase_gold_funds(test_user, test_sub_account, test_amount)
        
        print(f"--- 测试结束 ---")

    except Exception as e:
        logger.error(f"测试执行失败: {e}")
