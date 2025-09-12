import logging
import os
import sys
from typing import Optional, List, Tuple

# 获取项目根目录路径
root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# 如果项目根目录不在Python路径中，则添加
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

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

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def redeem_funds(user: User, sub_account_name: str, total_budget: Optional[float] = None) -> bool:
    """
    加仓风向标止盈算法实现（不依赖定投）：
    1. 获取组合所有基金资产
    2. 对于每个基金，如果在加仓风向标中，且组合持有基金数量<=20或已有止盈，则跳过
    3. 如果组合持有基金数量>20且当天没有止盈，从加仓风向标中选择预估涨幅>3%且持有基金预估收益率>5%的最高收益基金进行止盈
    4. 对于非加仓风向标基金，计算预估收益率，检查止盈条件
    5. 根据条件执行赎回操作
    
    Args:
        user: 用户对象
        sub_account_name: 组合名称
        total_budget: 总预算（用于计算止盈点等）
        amount: 可选的赎回金额
        fund_type: 基金类型 ('all', 'index', 'non_index')
    
    Returns:
        bool: 操作是否成功
    """
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
    
    wind_vane_codes = {f.fund_code for f in wind_vane_funds}
    wind_vane_indices = {get_all_fund_info(user, f.fund_code).index_code for f in wind_vane_funds if f.fund_type == '000'}
    
    success_count = 0
    wind_vane_candidates = []
    
    # 第一轮遍历：处理非加仓风向标基金，并收集加仓风向标基金作为候选
    for asset in user_assets:
        fund_code = asset.fund_code
        fund_info = get_all_fund_info(user, fund_code)
        if not fund_info:
            continue
        
        fund_name = fund_info.fund_name
        
        # 检查是否在风向标中
        in_wind_vane = False
        if fund_info.fund_type == '000':
            if fund_info.index_code in wind_vane_indices:
                in_wind_vane = True
        elif fund_code in wind_vane_codes:
            in_wind_vane = True
        
        # 计算预估收益率
        current_profit_rate = asset.constant_profit_rate or 0.0
        estimated_change = fund_info.estimated_change or 0.0
        estimated_profit_rate = current_profit_rate + estimated_change
        
        # 添加可用份额检查
        available_vol = asset.available_vol
        if available_vol == 0.0:
            logger.info(f"{user.customer_name}的基金{fund_name}({fund_code})可用份额为0, 跳过赎回.")
            continue
        
        if in_wind_vane:
            # 收集加仓风向标基金作为候选
            if estimated_change > 3.0 and estimated_profit_rate > 5.0:
                wind_vane_candidates.append((asset, fund_info, estimated_profit_rate))
                logger.info(f"加入候选: {fund_code} {fund_name}: 在加仓风向标中，预估涨幅{estimated_change}%，预估收益率{estimated_profit_rate}%")
            else:
                logger.info(f"跳过 {fund_code} {fund_name}: 在加仓风向标中，但不满足候选条件")
            continue
        
        # 处理非加仓风向标基金
        volatility = fund_info.volatility
        stop_rate = min(volatility * 100, 5.0) if estimated_change != 0.0 else 5.0
        
        # 记录计算细节
        logger.info(f"{user.customer_name}的基金{fund_name}({fund_code})的收益{current_profit_rate}加上估值增长率{estimated_change}结果{estimated_profit_rate},计算止盈点:{volatility},实际止盈点:{stop_rate}")
        
        if estimated_profit_rate > stop_rate and estimated_profit_rate > 1.0:
            try:
                bank_shares = get_bank_shares(user, sub_account_no, fund_code)
                logger.info(f"{user.customer_name}的止盈操作开始：基金{fund_name}({fund_code})预估收益{estimated_profit_rate},计算止盈点:{volatility},实际止盈点:{stop_rate}. 满足止盈条件")
                sell_result = sell_low_fee_shares(user, sub_account_no, fund_code, bank_shares)
                if sell_result and sell_result.busin_serial_no:
                    logger.info(f"{user.customer_name}的基金{fund_name}({fund_code})卖出止盈成功")
                    success_count += 1
                else:
                    logger.warning(f"{user.customer_name}的基金{fund_name}({fund_code})止盈失败")
            except Exception as e:
                logger.error(f"止盈 {fund_code} {fund_name} 失败: {e}")
    
    # 如果组合持有基金数量>20且当天没有止盈且组合资产总和大于预算的80%，从加仓风向标候选中选择基金今日估值涨幅大于3%的持有基金中止盈预估收益率最高的
    # 计算组合资产总和
    total_asset_value = sum(asset.asset_value for asset in user_assets if asset.asset_value is not None)
    asset_budget_ratio = 0
    if total_budget:
        asset_budget_ratio = total_asset_value / total_budget * 100
        logger.info(f"组合资产总和: {total_asset_value}，占总预算比例: {asset_budget_ratio:.2f}%")
    
    # 三个条件同时满足才触发特殊止盈：
    # 1) 组合基金数量 > 20
    # 2) 当天尚未发生止盈（success_count == 0）
    # 3) 组合资产总和 > 预算的 80%（且 total_budget 有效）
    eligible_for_special_take_profit = (
        fund_count > 20
        and success_count == 0
        and (total_budget is not None and total_budget > 0)
        and total_asset_value > total_budget * 0.8
        and len(wind_vane_candidates) > 0
    )

    if eligible_for_special_take_profit:
        # 仅从候选中选择“今日估值涨幅 > 3%”的持有基金，并按“预估收益率”从高到低排序
        eligible_candidates = []
        for asset, fund_info, estimated_profit_rate in wind_vane_candidates:
            try:
                est_change = getattr(fund_info, "estimated_change", 0.0) or 0.0
            except Exception:
                est_change = 0.0
            if est_change > 3.0 and estimated_profit_rate > 5.0:
                eligible_candidates.append((asset, fund_info, estimated_profit_rate, est_change))

        if not eligible_candidates:
            logger.info("满足触发条件，但加仓风向标候选中无'今日估值涨幅>3%'的持有基金，跳过特殊止盈")
        else:
            # 选择预估收益率最高的
            eligible_candidates.sort(key=lambda x: x[2], reverse=True)
            asset, fund_info, estimated_profit_rate, est_change = eligible_candidates[0]
            fund_code = asset.fund_code
            fund_name = fund_info.fund_name

            try:
                bank_shares = get_bank_shares(user, sub_account_no, fund_code)
                logger.info(
                    f"{user.customer_name}的特殊止盈开始："
                    f"{fund_name}({fund_code}) 预估收益率={estimated_profit_rate:.2f}%，今日估值涨幅={est_change:.2f}%，"
                    f"触发原因：基金数>{20} 且 今日未止盈 且 资产/预算>{80}%（当前{asset_budget_ratio:.2f}%）"
                )
                sell_result = sell_low_fee_shares(user, sub_account_no, fund_code, bank_shares)
                if sell_result and sell_result.busin_serial_no:
                    logger.info(f"{user.customer_name}的加仓风向标基金{fund_name}({fund_code})卖出止盈成功")
                    success_count += 1
                else:
                    logger.warning(f"{user.customer_name}的加仓风向标基金{fund_name}({fund_code})止盈失败")
            except Exception as e:
                logger.error(f"止盈加仓风向标基金 {fund_code} {fund_name} 失败: {e}")
    else:
        logger.info(
            "未触发特殊止盈条件："
            f"fund_count={fund_count}（需>20）, success_count={success_count}（需==0）, "
            f"total_budget={total_budget}, total_asset_value={total_asset_value}（需>80%预算）, "
            f"候选数={len(wind_vane_candidates)}"
        )
    
    logger.info(f"止盈操作完成，成功处理 {success_count} 个基金")
    return success_count > 0

if __name__ == "__main__":
    try:
        redeem_funds(DEFAULT_USER, "低风险组合", 1000000.0)
        logging.info(f"用户 {DEFAULT_USER.customer_name} 止盈操作完成")
    except Exception as e:
        logging.error(f"测试用户处理失败：{str(e)}")