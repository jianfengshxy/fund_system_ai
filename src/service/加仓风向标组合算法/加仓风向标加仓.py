import logging
import os
import sys
import math
from typing import Optional

# 获取项目根目录路径
root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# 如果项目根目录不在Python路径中，则添加
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from src.domain.user.User import User
from src.service.资产管理.get_fund_asset_detail import get_sub_account_asset_by_name
from src.API.组合管理.SubAccountMrg import getSubAccountNoByName
from src.service.基金信息.基金信息 import get_all_fund_info
from src.API.交易管理.trade import get_trades_list, get_bank_shares
from src.API.交易管理.buyMrg import commit_order
from src.service.大数据.加仓风向标服务 import get_fund_investment_indicators
from src.common.constant import DEFAULT_USER
from src.API.基金信息.FundRank import get_fund_growth_rate
from src.API.资产管理.AssetManager import GetMyAssetMainPartAsync

import datetime

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def increase_funds(user: User, sub_account_name: str, total_budget: float, amount: Optional[float] = None, fund_type: str = 'all') -> bool:
    """
    加仓风向标加仓算法实现（不依赖定投）：
    1. 获取组合所有基金资产
    2. 对于每个基金，如果预估收益率 >= -1.0%，跳过
    3. 如果有在途交易，跳过
    4. 检查是否在加仓风向标中（指数基金检查指数，非指数检查代码）
    5. 如果在风向标中且资产 < 预算，买入
    6. 如果不在风向标中，应用原increase.py的加仓逻辑（排名、收益率判断）
    
    Args:
        user: 用户对象
        sub_account_name: 组合名称
        total_budget: 总预算
        fund_amount: 定投金额
        fund_type: 基金类型 ('all', 'index', 'non_index')
    
    Returns:
        bool: 操作是否成功
    """
    customer_name = user.customer_name
    logger.info(f"开始为用户 {customer_name} 执行加仓操作，组合: {sub_account_name}")
    
    # 同步新增.py的预算计算逻辑
    fund_num = 5  # 每天加仓的基金个数
    budget_per_fund = round(total_budget / fund_num / 20, 2)
    logger.info(f"计算得出单个基金加仓金额：{budget_per_fund}元")
    
    # 同步检查用户可用资金
    try:
        asset_response = GetMyAssetMainPartAsync(user)
        if asset_response.Success and asset_response.Data:
            available_balance = asset_response.Data.get('HqbValue', 0.0)
            logger.info(f"从资产API获取HqbValue: {available_balance}元")
        else:
            raise Exception("资产API调用失败")
    except Exception as e:
        logger.error(f"获取用户资产失败: {e}")
        return False
    
    if available_balance < budget_per_fund:
        logger.warning(f"用户可用余额 {available_balance}元 小于单个基金预算 {budget_per_fund}元")
        budget_per_fund = min(available_balance * 0.8, budget_per_fund)  # 使用80%的可用余额
        logger.info(f"调整单个基金预算为: {budget_per_fund}元")
    
    # 使用amount或计算的budget_per_fund
    fund_amount = amount if amount is not None else budget_per_fund
    
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
    
    logger.info(f"组合中共有 {len(user_assets)} 个基金资产")
    
    # 获取加仓风向标数据
    wind_vane_funds = get_fund_investment_indicators()
    if not wind_vane_funds:
        logger.error("获取加仓风向标数据失败")
        return False
    
    # 根据fund_type过滤风向标
    if fund_type == 'index':
        wind_vane_funds = [f for f in wind_vane_funds if f.fund_type == '000']
    elif fund_type == 'non_index':
        wind_vane_funds = [f for f in wind_vane_funds if f.fund_type != '000']
    
    wind_vane_codes = {f.fund_code for f in wind_vane_funds}
    wind_vane_indices = {get_all_fund_info(user, f.fund_code).index_code for f in wind_vane_funds if f.fund_type == '000'}
    
    success_count = 0
    for asset in user_assets:
        fund_code = asset.fund_code
        fund_info = get_all_fund_info(user, fund_code)
        if not fund_info:
            continue
        
        fund_name = fund_info.fund_name  # 立即赋值 fund_name
        
        current_profit_rate = asset.constant_profit_rate or 0.0
        estimated_change = fund_info.estimated_change or 0.0
        estimated_profit_rate = current_profit_rate + estimated_change
        
        if estimated_profit_rate >= -1.0:
            logger.info(f"跳过 {fund_code} {fund_name}: 预估收益率 {estimated_profit_rate} >= -1.0")
            continue
        
        # 检查在途交易
        on_way_count = asset.on_way_transaction_count
        if on_way_count > 0:
            logger.info(f"跳过 {fund_code}{fund_name}: 有在途交易{on_way_count}")
            continue
        
        # 检查是否在风向标中
        in_wind_vane = False
        if fund_info.fund_type == '000':
            if fund_info.index_code in wind_vane_indices:
                in_wind_vane = True
        elif fund_code in wind_vane_codes:
            in_wind_vane = True
        
        if in_wind_vane:
            if asset.asset_value < total_budget:
                try:
                    commit_order(user, sub_account_no, fund_code, fund_amount)
                    logger.info(f"买入 {fund_code}{fund_name} 成功，金额: {fund_amount}")
                    success_count += 1
                except Exception as e:
                    logger.error(f"买入 {fund_code} {fund_name}失败: {e}")
            continue
        
        # 如果不在风向标中，应用原increase.py逻辑
        fund_name = fund_info.fund_name  # 假设有fund_name
        # 100日排名检查
        if fund_info.rank_100day < 20:
            logger.info(f"{fund_name} rank_100 {fund_info.rank_100day} < 20. Skip......")
            continue    
        
        if fund_info.rank_100day > 90:
            logger.info(f"{fund_name} rank_100 {fund_info.rank_100day} > 90. Skip......")
            continue                 
        
        if fund_info.rank_30day < 5:
            logger.info(f"{fund_name} rank_30 {fund_info.rank_30day} < 5. Skip......")
            continue
        
        season_growth_rate = fund_info.three_month_return
        month_growth_rate = fund_info.month_return
        week_growth_rate = fund_info.week_return
        logger.info(f"收益率数据 - {fund_name}周收益率预估:{week_growth_rate},{fund_name}月收益率预估:{month_growth_rate},季度收益率预估:{season_growth_rate}")
        
        if week_growth_rate < 0.0 and month_growth_rate < 0.0 and season_growth_rate < 0.0:
            logger.info(f"{fund_name}周收益率预估:{week_growth_rate},{fund_name}月收益率预估:{month_growth_rate},季度收益率预估:{season_growth_rate}.Skip......")
            continue    
        
        if season_growth_rate < 0.0 and (month_growth_rate < 0.0 or week_growth_rate < 0.0):
            logger.info(f"季度收益率为负且月/周收益率至少一个为负 - 执行跳过")
            logger.info(f"{fund_name}周收益率预估:{week_growth_rate},{fund_name}月收益率预估:{month_growth_rate},季度收益率预估:{season_growth_rate}.Skip......")
            continue
        
        if season_growth_rate > 0.0 and (month_growth_rate < 0.0 and week_growth_rate < 0.0):
            logger.info(f"季度收益率为正但月、周收益率均为负 - 执行跳过")
            logger.info(f"{fund_name}周收益率预估:{week_growth_rate},{fund_name}月收益率预估:{month_growth_rate},季度收益率预估:{season_growth_rate}.Skip......")
            continue

        try:
            season_growth_rate, season_item_rank, season_item_sc = get_fund_growth_rate(fund_info, '3Y')
            month_growth_rate, month_item_rank, month_item_sc = get_fund_growth_rate(fund_info, 'Y')
            logger.info(f"排名数据获取 - 季度排名: {season_item_rank}/{season_item_sc}, 月排名: {month_item_rank}/{month_item_sc}")
            
            month_rank_rate = month_item_rank / month_item_sc      
            season_rank_rate = season_item_rank / season_item_sc
            logger.info(f"排名占比计算 - 季度排名占比: {season_rank_rate:.4f}, 月排名占比: {month_rank_rate:.4f}")
            
            if month_rank_rate > 0.75 or season_rank_rate > 0.75:
                logger.info(f"排名占比过高 - {fund_name}季度排名占比:{season_rank_rate},月排名占比:{month_rank_rate}, 执行跳过")
                continue
        except Exception as e:
            logger.error(f"获取基金排名数据失败: {e}")
            continue

        logger.info(f"所有条件检查通过 - 组合{sub_account_name}中{fund_name}{fund_code}候选成功.") 
        
        # 基础加仓
        try:
            logger.info(f"执行基础加仓 - 金额: {fund_amount}")
            commit_order(user, sub_account_no, fund_code, fund_amount)
            logger.info(f"基础加仓订单提交成功")
            success_count += 1
        except Exception as e:
            logger.error(f"基础加仓订单提交失败: {e}")
        
        # -3.0%额外加仓
        if estimated_profit_rate < -3.0:
            try:
                logger.info(f"执行-3.0%额外加仓 - 金额: {fund_amount}")
                commit_order(user, sub_account_no, fund_code, fund_amount)
                logger.info(f"-3.0%额外加仓订单提交成功")
                success_count += 1
            except Exception as e:
                logger.error(f"-3.0%额外加仓订单提交失败: {e}")
                
        # -5.0%额外加仓
        # if estimated_profit_rate < -5.0:
        #     try:
        #         logger.info(f"执行-5.0%额外加仓 - 金额: {fund_amount}")
        #         commit_order(user, sub_account_no, fund_code, fund_amount)
        #         logger.info(f"-5.0%额外加仓订单提交成功")
        #         success_count += 1
        #     except Exception as e:
        #         logger.error(f"-5.0%额外加仓订单提交失败: {e}")
    
    logger.info(f"加仓操作完成，成功处理 {success_count} 个基金")
    return success_count > 0


if __name__ == "__main__":
    # 测试单个用户的加仓流程
    try:
        # 执行加仓操作
        increase_funds(DEFAULT_USER, "低风险组合", 1000000.0, None, 'non_index')  # 使用 DEFAULT_USER，并假设参数合适
        logging.info(f"用户 {DEFAULT_USER.customer_name} 加仓操作完成")
    except Exception as e:
        logging.error(f"测试用户处理失败：{str(e)}")