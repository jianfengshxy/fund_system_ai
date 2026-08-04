import sys
import os
import datetime
from typing import Optional, List, Dict

# 获取项目根目录路径
root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# 如果项目根目录不在Python路径中，则添加
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from src.common.logger import get_logger
from src.domain.user.User import User
from src.service.资产管理.get_fund_asset_detail import get_sub_account_asset_by_name
from src.API.组合管理.SubAccountMrg import getSubAccountNoByName
from src.service.交易管理.赎回基金 import sell_0_fee_shares, sell_low_fee_shares
from src.service.基金信息.基金信息 import get_all_fund_info
from src.API.交易管理.trade import get_bank_shares
from src.service.公共服务.estimated_profit_service import calc_estimated_change, calc_estimated_profit_rate
from src.service.公共服务.trade_guard_service import has_buy_submission_on_dates

logger = get_logger(__name__)

def redeem_gold_funds(
    user: User,
    sub_account_name: str,
    fund_list: Optional[List[Dict]] = None,
    stop_rate: Optional[float] = None,
) -> bool:
    """
    黄金多利止盈逻辑：
    收益率大于1.0% 就买出0费率份额
    """
    logger.info(f"开始执行黄金多利止盈检查，组合: {sub_account_name}", extra={"account": user.account, "sub_account_name": sub_account_name, "action": "gold_redeem"})

    # 获取子账户编号
    sub_account_no = getSubAccountNoByName(user, sub_account_name)
    if not sub_account_no:
        logger.error(f"未找到组合 {sub_account_name} 的账号")
        return False

    # 获取持仓
    user_assets = get_sub_account_asset_by_name(user, sub_account_name)
    if not user_assets:
        logger.info(f"组合 {sub_account_name} 中没有基金资产")
        return True

    def _safe_float(v, default=0.0):
        try:
            if v is None:
                return default
            return float(v)
        except Exception:
            return default

    def _get_default_stop_rate(fund_info) -> float:
        fund_type = getattr(fund_info, "fund_type", None)
        volatility = _safe_float(getattr(fund_info, "volatility", None), 0.0)
        if fund_type == "000":
            return min(max(volatility, 5.0), 10.0)
        return min(max(volatility, 5.0), 15.0)

    portfolio_stop_rate = None
    if stop_rate is not None:
        try:
            portfolio_stop_rate = float(stop_rate)
        except Exception:
            portfolio_stop_rate = None

    fund_stop_rate = None
    if isinstance(fund_list, list) and fund_list:
        m = {}
        for item in fund_list:
            if not isinstance(item, dict):
                continue
            code = item.get("fund_code") or item.get("fundcode") or item.get("FundCode") or item.get("code")
            if not code:
                continue
            raw_stop_rate = item.get("stop_rate")
            try:
                item_stop_rate = float(raw_stop_rate) if raw_stop_rate is not None else None
            except Exception:
                item_stop_rate = None
            m[str(code)] = item_stop_rate
        if m:
            fund_stop_rate = m

    redeem_count = 0

    for asset in user_assets:
        try:
            current_profit_rate = float(getattr(asset, "constant_profit_rate", 0.0) or 0.0)
            fund_code = asset.fund_code
            fund_name = asset.fund_name
            fund_code_str = str(fund_code)

            # 获取基金估值信息
            fund_info = get_all_fund_info(user, fund_code)

            nav_date_str = getattr(fund_info, "nav_date", None) if fund_info else None
            if nav_date_str:
                try:
                    prev_trade_day = datetime.datetime.strptime(str(nav_date_str)[:10], "%Y-%m-%d").date()
                except Exception:
                    prev_trade_day = None
            else:
                prev_trade_day = None

            estimated_change, label_est = calc_estimated_change(fund_info)
            
            # 获取波动率和基金类型以供日志输出
            volatility = _safe_float(getattr(fund_info, "volatility", None), 0.0) if fund_info else 0.0
            fund_type = getattr(fund_info, "fund_type", "未知") if fund_info else "未知"
            
            default_stop_rate = _get_default_stop_rate(fund_info) if fund_info else 5.0
            configured_stop_rate = fund_stop_rate.get(fund_code_str) if fund_stop_rate is not None else None
            resolved_stop_rate = None
            stop_rate_source = None
            if configured_stop_rate is not None:
                resolved_stop_rate = configured_stop_rate
                stop_rate_source = "基金级配置"
            elif portfolio_stop_rate is not None:
                resolved_stop_rate = portfolio_stop_rate
                stop_rate_source = "组合级配置"
            else:
                resolved_stop_rate = default_stop_rate
                stop_rate_source = "默认动态计算"
            
            # 计算预估收益率 = 当前收益率 + 估值涨跌幅
            estimated_profit_rate = current_profit_rate + estimated_change
            
            logger.info(
                f"基金 {fund_name}({fund_code}) 止盈指标 -> 类型: {fund_type}, 波动率: {volatility:.2f}%, "
                f"当前收益率: {current_profit_rate}%, 估值变动: {estimated_change}%, "
                f"预估收益率: {estimated_profit_rate:.2f}%, 止盈点: {resolved_stop_rate:.2f}% ({stop_rate_source}), {label_est}"
            )

            prev_trade_record = has_buy_submission_on_dates(user, sub_account_no, fund_code, prev_trade_day)
            if prev_trade_record:
                state = getattr(prev_trade_record, "app_state_text", None) or getattr(prev_trade_record, "status", None)
                logger.info(f"[在途检查] 基金 {fund_code} 上一个交易日({nav_date_str})已有有效交易（状态={state}），跳过止盈")
                continue

            today = datetime.date.today()
            today_trade_record = has_buy_submission_on_dates(user, sub_account_no, fund_code, today)
            if today_trade_record:
                state = getattr(today_trade_record, "app_state_text", None) or getattr(today_trade_record, "status", None)
                logger.info(f"[在途检查] 基金 {fund_code} 今日({today})已有有效交易（状态={state}），跳过止盈")
                continue

            logger.info(f"[在途检查] 基金 {fund_code} nav_date={nav_date_str}, prev_trade_day={prev_trade_day}, 查询结果: 无交易")

            if estimated_profit_rate > resolved_stop_rate or estimated_profit_rate > 10.0:
                # 获取可用份额
                shares = get_bank_shares(user, sub_account_no, fund_code)
                if not shares:
                    logger.info(f"基金 {fund_name}({fund_code}) 满足收益率条件，但查无可用银行卡份额，无法执行止盈")
                    continue

                redeemed = False

                if estimated_profit_rate > resolved_stop_rate:
                    logger.info(f"基金 {fund_name}({fund_code}) 预估收益率 {estimated_profit_rate:.2f}% > 止盈点 {resolved_stop_rate:.2f}%，尝试赎回0费率份额")

                    # 执行0费率赎回
                    # 注意：sell_0_fee_shares 内部会判断是否有0费率份额，如果有则赎回，没有则跳过
                    result = sell_0_fee_shares(user, sub_account_no, fund_code, shares)
                    if result:
                        redeem_count += 1
                        redeemed = True
                    else:
                        logger.info(f"基金 {fund_name}({fund_code}) 赎回0费率份额未成功 (可能查无0费率份额或接口拦截)")

                # 兜底逻辑：当预估收益率 > 10.0% 时，若0费率未卖成，则尝试卖出低费率份额
                if estimated_profit_rate > 10.0 and not redeemed:
                    logger.info(f"基金 {fund_name}({fund_code}) 预估收益率 {estimated_profit_rate:.2f}% > 兜底线 10.0%，尝试兜底赎回低费率份额")
                    result = sell_low_fee_shares(user, sub_account_no, fund_code, shares)
                    if result:
                        redeem_count += 1
                    else:
                        logger.info(f"基金 {fund_name}({fund_code}) 兜底赎回低费率份额未成功")
                elif not redeemed:
                    logger.info(f"基金 {fund_name}({fund_code}) 未能完成止盈 (预估收益 {estimated_profit_rate:.2f}% <= 兜底线 10.0%，不执行低费率兜底)")
            else:
                 logger.info(
                     f"基金 {fund_name}({fund_code}) 不满足止盈条件: "
                     f"预估收益率 {estimated_profit_rate:.2f}% <= 止盈点 {resolved_stop_rate:.2f}%，"
                     f"且未达 10.0% 兜底线"
                 )

        except Exception as e:
            logger.error(f"处理基金 {asset.fund_code} 止盈时发生错误: {e}")
            continue

    logger.info(f"止盈检查完成，共触发 {redeem_count} 只基金的赎回尝试")
    return True

if __name__ == "__main__":
    from src.common.constant import DEFAULT_USER
    try:
        # 1. 构造测试用户
        test_user = DEFAULT_USER
        
        # 2. 设置测试参数
        test_sub_account = "智投平台"

        print(f"--- 开始测试黄金多利止盈 ---")
        print(f"用户: {test_user.customer_name}")
        print(f"组合: {test_sub_account}")
        
        # 3. 调用止盈函数
        redeem_gold_funds(test_user, test_sub_account)
        
        print(f"--- 测试结束 ---")

    except Exception as e:
        logger.error(f"测试执行失败: {e}")
