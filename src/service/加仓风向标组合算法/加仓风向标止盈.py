# 顶部导入片段
import logging
import os
import sys
from typing import Optional, List, Tuple

# 获取项目根目录路径
root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# 如果项目根目录不在Python路径中，则添加
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from src.common.logger import get_logger

from src.domain.user.User import User
from src.service.资产管理.get_fund_asset_detail import get_sub_account_asset_by_name
from src.API.组合管理.SubAccountMrg import getSubAccountNoByName
from src.service.基金信息.基金信息 import get_all_fund_info
from src.API.交易管理.trade import get_bank_shares
from src.service.大数据.加仓风向标服务 import get_fund_investment_indicators
from src.common.constant import DEFAULT_USER
from src.API.资产管理.AssetManager import GetMyAssetMainPartAsync
from src.API.基金信息.FundRank import get_fund_growth_rate
from src.service.交易管理.赎回基金 import sell_low_fee_shares, sell_0_fee_shares, sell_usable_non_zero_fee_shares
from src.service.公共服务.nav_gate_service import nav5_gate, nav5_fall_gate

logger = get_logger(__name__)

from src.service.公共服务.risk_control_service import check_hqb_risk_allowed

def redeem_funds(user: User, sub_account_name: str, total_budget: Optional[float] = None) -> bool:
    customer_name = user.customer_name
    logger.info(f"开始为用户 {customer_name} 执行止盈操作，组合: {sub_account_name}")
    
    # 获取组合账号
    sub_account_no = getSubAccountNoByName(user, sub_account_name)
    if not sub_account_no:
        logger.error(f"未找到组合 {sub_account_name} 的账号")
        return False
    
    # 获取组合所有基金资产
    user_assets = get_sub_account_asset_by_name(user, sub_account_name)
    if not user_assets:
        logger.info(f"组合 {sub_account_name} 中没有基金资产")
        return True
    
    # 检查组合持有基金数量
    fund_count = len(user_assets)
    logger.info(f"组合中共有 {fund_count} 个基金资产")
    
    # 获取加仓风向标数据
    wind_vane_funds = get_fund_investment_indicators()
    if not wind_vane_funds:
        logger.error("获取加仓风向标数据失败")
        return False
    
    # 构建风向标集合：非指数用 fund_code，指数用 index_code
    wind_vane_codes = {f.fund_code for f in wind_vane_funds}
    wind_vane_indices = set()
    for f in wind_vane_funds:
        if getattr(f, "fund_type", None) == "000":
            try:
                fi = get_all_fund_info(user, f.fund_code)
                if fi and getattr(fi, "index_code", None):
                    wind_vane_indices.add(fi.index_code)
            except Exception as e:
                logger.warning(f"获取指数风向标 index_code 异常: {f.fund_code}, {e}")
    
    # 引入费率份额查询（函数内导入，避免顶部改动）
    from src.service.交易管理.费率查询 import get_0_fee_shares, get_low_fee_shares
    
    success_count = 0

    def _safe_float(v, default=0.0):
        try:
            if v is None:
                return default
            return float(v)
        except Exception:
            return default

    logger.info("采用新止盈策略：两轮按风向标内外，止盈点=max(波动率, 3.0)，最多成功3个")

    # 第一轮：处理不在加仓风向标内的基金
    for asset in user_assets:
        if success_count >= 3:
            break

        fund_code = asset.fund_code
        fund_info = get_all_fund_info(user, fund_code)
        if not fund_info:
            logger.info(f"第一轮跳过：无法获取基金信息 {fund_code}")
            continue

        fund_name = getattr(fund_info, "fund_name", fund_code)
        fund_type = getattr(fund_info, "fund_type", None)

        # 判断是否在风向标中（指数用 index_code，非指数用 fund_code）
        in_wind_vane = False
        if fund_type == "000":
            idx_code = getattr(fund_info, "index_code", None)
            in_wind_vane = idx_code in wind_vane_indices if idx_code else False
        else:
            in_wind_vane = fund_code in wind_vane_codes

        if in_wind_vane:
            logger.info(f"第一轮跳过：在风向标内 {fund_name}({fund_code})")
            continue

        # 预估收益率与止盈点
        current_profit_rate = _safe_float(getattr(asset, "constant_profit_rate", 0.0), 0.0)
        estimated_change = _safe_float(getattr(fund_info, "estimated_change", 0.0), 0.0)
        estimated_profit_rate = current_profit_rate + estimated_change
        volatility = _safe_float(getattr(fund_info, "volatility", None), 0.0) 
        stop_rate = max(volatility, 3.0)

        # C类与非C类分流处理
        is_c = "C" in str(fund_name)
        if estimated_profit_rate > stop_rate:
            try:
                shares = get_bank_shares(user, sub_account_no, fund_code)
                if is_c:
                    zero_fee_shares = _safe_float(get_0_fee_shares(user, fund_code), 0.0)
                    if zero_fee_shares > 10.0:
                        logger.info(
                            f"{user.customer_name} 第一轮止盈：不在风向标且预估收益>{stop_rate:.2f}%，C类赎回0费率份额 "
                            f"{fund_name}({fund_code}) 预估={estimated_profit_rate:.2f}% 波动率={volatility:.2f} 0费率份额={zero_fee_shares:.2f}"
                        )
                        redeem_ok = bool(sell_0_fee_shares(user, sub_account_no, fund_code, shares))
                        if redeem_ok:
                            success_count += 1
                        else:
                            logger.info(f"{user.customer_name} 第一轮止盈未成功或被跳过：{fund_name}({fund_code})")
                    else:
                        logger.info(f"第一轮跳过：{fund_name}({fund_code}) 0费率份额≤10 预估={estimated_profit_rate:.2f}% 止盈点={stop_rate:.2f}%")
                else:
                    low_fee_shares = _safe_float(get_low_fee_shares(user, fund_code), 0.0)
                    if low_fee_shares > 10.0:
                        logger.info(
                            f"{user.customer_name} 第一轮止盈：不在风向标且预估收益>{stop_rate:.2f}%，非C赎回低费率份额 "
                            f"{fund_name}({fund_code}) 预估={estimated_profit_rate:.2f}% 波动率={volatility:.2f} 低费率份额={low_fee_shares:.2f}"
                        )
                        redeem_ok = bool(sell_low_fee_shares(user, sub_account_no, fund_code, shares))
                        if redeem_ok:
                            success_count += 1
                        else:
                            logger.info(f"{user.customer_name} 第一轮止盈未成功或被跳过：{fund_name}({fund_code})")
                    else:
                        logger.info(f"第一轮跳过：{fund_name}({fund_code}) 低费率份额≤10 预估={estimated_profit_rate:.2f}% 止盈点={stop_rate:.2f}%")
            except Exception as e:
                logger.error(f"第一轮止盈失败：{fund_name}({fund_code}) 异常={e}")
        else:
            logger.info(f"第一轮跳过：{fund_name}({fund_code}) 预估收益率≤止盈点({stop_rate:.2f}%) 预估={estimated_profit_rate:.2f}%")

    # 第二轮：若第一轮成功数不足3，处理在加仓风向标内的基金
    if success_count < 3:
        logger.info(f"第一轮止盈成功 {success_count} 个，开始第二轮在风向标内的止盈（最多补足到3个）")
        for asset in user_assets:
            if success_count >= 3:
                break

            fund_code = asset.fund_code
            fund_info = get_all_fund_info(user, fund_code)
            if not fund_info:
                logger.info(f"第二轮跳过：无法获取基金信息 {fund_code}")
                continue

            fund_name = getattr(fund_info, "fund_name", fund_code)
            fund_type = getattr(fund_info, "fund_type", None)

            # 是否在风向标内
            in_wind_vane = False
            if fund_type == "000":
                idx_code = getattr(fund_info, "index_code", None)
                in_wind_vane = idx_code in wind_vane_indices if idx_code else False
            else:
                in_wind_vane = fund_code in wind_vane_codes
            if not in_wind_vane:
                logger.info(f"第二轮跳过：不在风向标内 {fund_name}({fund_code})")
                continue

            # 预估收益率与止盈点
            current_profit_rate = _safe_float(getattr(asset, "constant_profit_rate", 0.0), 0.0)
            estimated_change = _safe_float(getattr(fund_info, "estimated_change", 0.0), 0.0)
            estimated_profit_rate = current_profit_rate + estimated_change
            volatility = _safe_float(getattr(fund_info, "volatility", None), 0.0)
            stop_rate = max(volatility, 3.0)

            # C类与非C类分流处理
            is_c = "C" in str(fund_name)
            if estimated_profit_rate > stop_rate:
                try:
                    shares = get_bank_shares(user, sub_account_no, fund_code)
                    if is_c:
                        zero_fee_shares = _safe_float(get_0_fee_shares(user, fund_code), 0.0)
                        if zero_fee_shares > 10.0:
                            logger.info(
                                f"{user.customer_name} 第二轮止盈：在风向标且预估收益>{stop_rate:.2f}%，C类赎回0费率份额 "
                                f"{fund_name}({fund_code}) 预估={estimated_profit_rate:.2f}% 波动率={volatility:.2f} 0费率份额={zero_fee_shares:.2f}"
                            )
                            redeem_ok = bool(sell_0_fee_shares(user, sub_account_no, fund_code, shares))
                            if redeem_ok:
                                success_count += 1
                            else:
                                logger.info(f"{user.customer_name} 第二轮止盈未成功或被跳过：{fund_name}({fund_code})")
                        else:
                            logger.info(f"第二轮跳过：{fund_name}({fund_code}) 0费率份额≤10 预估={estimated_profit_rate:.2f}% 止盈点={stop_rate:.2f}%")
                    else:
                        low_fee_shares = _safe_float(get_low_fee_shares(user, fund_code), 0.0)
                        if low_fee_shares > 10.0:
                            logger.info(
                                f"{user.customer_name} 第二轮止盈：在风向标且预估收益>{stop_rate:.2f}%，非C赎回低费率份额 "
                                f"{fund_name}({fund_code}) 预估={estimated_profit_rate:.2f}% 波动率={volatility:.2f} 低费率份额={low_fee_shares:.2f}"
                            )
                            redeem_ok = bool(sell_low_fee_shares(user, sub_account_no, fund_code, shares))
                            if redeem_ok:
                                success_count += 1
                            else:
                                logger.info(f"{user.customer_name} 第二轮止盈未成功或被跳过：{fund_name}({fund_code})")
                        else:
                            logger.info(f"第二轮跳过：{fund_name}({fund_code}) 低费率份额≤10 预估={estimated_profit_rate:.2f}% 止盈点={stop_rate:.2f}%")
                except Exception as e:
                    logger.error(f"第二轮止盈失败：{fund_name}({fund_code}) 异常={e}")
            else:
                logger.info(f"第二轮跳过：{fund_name}({fund_code}) 预估收益率≤止盈点({stop_rate:.2f}%) 预估={estimated_profit_rate:.2f}%")

    # 第三轮：持仓比率>80%，不在风向标且预估收益率<-10%的基金执行止损（第三轮无外层 success_count 进入判断）
    # 计算组合持仓占比
    try:
        total_asset_value = sum(_safe_float(getattr(a, "asset_value", 0.0), 0.0) for a in user_assets)
        if total_budget and total_budget > 0.0:
            asset_budget_ratio = (total_asset_value / total_budget) * 100.0
            logger.info(f"组合资产总和: {total_asset_value:.2f} 占总预算比例: {asset_budget_ratio:.2f}%")
        else:
            asset_budget_ratio = None
            logger.info("未提供有效 total_budget，第三轮止盈触发条件将跳过")
    except Exception as e:
        asset_budget_ratio = None
        logger.warning(f"计算持仓占比失败，第三轮止盈触发条件跳过：异常={e}")

    # 第三轮触发条件：持仓比率 > 80.0 OR 活期宝余额 < 预算 * 20%
    hqb_risk_triggered = not check_hqb_risk_allowed(user, threshold=20.0)
    
    if (asset_budget_ratio is not None and asset_budget_ratio > 80.0) or hqb_risk_triggered:
        trigger_reason = []
        if asset_budget_ratio is not None and asset_budget_ratio > 80.0:
            trigger_reason.append(f"持仓比率({asset_budget_ratio:.2f}%)>80%")
        if hqb_risk_triggered:
            trigger_reason.append("活期宝占比不足20%")
            
        logger.info(f"满足第三轮触发条件（{' | '.join(trigger_reason)}）：指数止盈点3%，非指数5%（分别赎回C类0费率与非C低费率份额）")
        for asset in user_assets:
            fund_code = asset.fund_code
            fund_info = get_all_fund_info(user, fund_code)
            if not fund_info:
                logger.info(f"第三轮跳过：无法获取基金信息 {fund_code}")
                continue

            fund_name = getattr(fund_info, "fund_name", fund_code)
            fund_type = getattr(fund_info, "fund_type", None)

            current_profit_rate = _safe_float(getattr(asset, "constant_profit_rate", 0.0), 0.0)
            estimated_change = _safe_float(getattr(fund_info, "estimated_change", 0.0), 0.0)
            estimated_profit_rate = current_profit_rate + estimated_change

            # 指数基金3%，非指数5%
            threshold = 3.0 if fund_type == "000" else 5.0

            is_c = "C" in str(fund_name)
            if estimated_profit_rate > threshold:
                try:
                    shares = get_bank_shares(user, sub_account_no, fund_code)
                    if is_c:
                        logger.info(
                            f"{user.customer_name} 第三轮止盈：重仓且预估收益>{threshold:.2f}%，C类赎回0费率份额 "
                            f"{fund_name}({fund_code}) 当前={current_profit_rate:.2f}% 估值={estimated_change:.2f}% 预估={estimated_profit_rate:.2f}%"
                        )
                        redeem_ok = bool(sell_0_fee_shares(user, sub_account_no, fund_code, shares))
                    else:
                        logger.info(
                            f"{user.customer_name} 第三轮止盈：重仓且预估收益>{threshold:.2f}%，非C赎回低费率份额 "
                            f"{fund_name}({fund_code}) 当前={current_profit_rate:.2f}% 估值={estimated_change:.2f}% 预估={estimated_profit_rate:.2f}%"
                        )
                        redeem_ok = bool(sell_low_fee_shares(user, sub_account_no, fund_code, shares))

                    if redeem_ok:
                        success_count += 1
                    else:
                        logger.info(f"{user.customer_name} 第三轮止盈未成功或被跳过：{fund_name}({fund_code})")
                except Exception as e:
                    logger.error(f"第三轮止盈失败：{fund_name}({fund_code}) 异常={e}")
            else:
                logger.info(
                    f"第三轮跳过：{fund_name}({fund_code}) 预估收益率≤止盈点({threshold:.2f}%) 预估={estimated_profit_rate:.2f}%"
                )
    else:
        logger.info("第三轮未触发：持仓比率≤80% 且 活期宝占比≥20% (或预算未设置)")

    logger.info(f"止盈完成：{user.customer_name} 成功执行 {success_count} 次赎回操作（最多3个）")
    return True

if __name__ == "__main__":
    try:
        redeem_funds(DEFAULT_USER, "飞龙在天", 1000000.0)
        logging.info(f"用户 {DEFAULT_USER.customer_name} 止盈操作完成")
    except Exception as e:
        logging.error(f"测试用户处理失败：{str(e)}")
