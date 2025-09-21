# 模块顶层
import os
import sys

# 将项目根目录加入到 sys.path，确保可以 import src.**
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import logging
import re
from typing import List, Dict, Any, Optional

# 添加项目根目录到路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.domain.fund_plan import ApiResponse
from src.domain.fund.fund_investment_indicator import FundInvestmentIndicator
from src.service.基金信息.基金信息 import get_all_fund_info
from src.API.大数据.加仓风向标 import getFundInvestmentIndicators as getBasicFundInvestmentIndicators
from src.db.fund_repository_impl import FundRepositoryImpl
from src.db.fund_investment_indicator_repository_impl import FundInvestmentIndicatorRepositoryImpl
from datetime import datetime
from src.API.资产管理.getAssetListOfSub import get_asset_list_of_sub
from src.API.组合管理.SubAccountMrg import getSubAccountNoByName


def process_fund_investment_indicators(user, page_size=50) -> List[FundInvestmentIndicator]:
    """
    处理基金投资指标数据，按规则过滤并返回结果
    """
    logger = logging.getLogger("FundInvestmentIndicatorService")
    
    try:
        # 调用API层获取基础数据
        api_response = getBasicFundInvestmentIndicators(user, page_size)
        
        if not api_response.Success:
            logger.error(f"API调用失败: {api_response.FirstError}")
            return []
        
        data = api_response.Data
        if data is None:
            logger.warning("API返回数据为空")
            return []
        
        # 获取类型为9的基金列表
        fund_list = data.get('9', [])
        if not fund_list:
            logger.warning("未找到加仓风向标基金数据")
            return []
        # print(f"{fund_list}")
        indicators = []
        for fund_data in fund_list:
            indicator = FundInvestmentIndicator.from_dict(fund_data)
            indicators.append(indicator)
        
        logger.info(f"=== 开始过滤处理，初始基金数量: {len(indicators)} ===")
        # 添加打印初始基金名称
        for ind in indicators:
            logger.info(f"初始基金: {ind.fund_name} ({ind.fund_code})")
        
        # === 步骤1: 仅保留基金名称中包含"C"的基金 ===
        indicators = [ind for ind in indicators if "C" in ind.fund_name]
        logger.info(f"=== 步骤1: 保留基金名包含'C'的基金，过滤后数量: {len(indicators)} ===")
        
        # === 步骤2: 多条件过滤规则 ===
        filtered_indicators = []
        
        for ind in indicators:
            # 规则1: 过滤掉包含"债"的基金
            if "债" in ind.fund_name:
                continue
            
            # 规则2: 过滤掉子类型 002003
            if ind.fund_sub_type == "002003":
                continue
            
            # 规则3: 仅保留基金类型在 [000,001,002]
            if ind.fund_type not in ["000", "001", "002"]:
                continue

            # 规则4: 当 fund_type == "000" 时，只保留 fund_sub_type == "000001"
            if ind.fund_type == "000" and ind.fund_sub_type != "000001":
                continue

            # 符合条件的保留
            filtered_indicators.append(ind)
        
        logger.info(f"=== 步骤2: 多条件过滤完成，过滤后数量: {len(filtered_indicators)} ===")
        
        # === 步骤3: 获取基金详细信息并进行index_code去重 ===
        logger.info("=== 步骤3: 获取基金详细信息并进行index_code去重 ===")
        
        # 为每个基金添加index_code信息
        # 新增：在此处先根据 six_month_return 是否有值进行“历史数据齐全/成立>=6个月”过滤
        age_ok_indicators = []
        for indicator in filtered_indicators:
            fund_info = get_all_fund_info(user, indicator.fund_code)
            if not fund_info:
                logger.info(f"剔除基金 {indicator.fund_name}({indicator.fund_code}): 无法获取基金详情，视为历史数据不全")
                continue

            six_month_return = getattr(fund_info, 'six_month_return', None)
            if six_month_return is None:
                logger.info(f"剔除基金 {indicator.fund_name}({indicator.fund_code}): six_month_return 无值，历史数据不全或成立不足6个月")
                continue

            # 历史数据齐全，保留并补充 index_code/tracking_index
            indicator.index_code = getattr(fund_info, 'index_code', None)
            indicator.tracking_index = indicator.index_code
            logger.info(f"基金 {indicator.fund_name}({indicator.fund_code}) 通过历史数据检查，index_code: {indicator.index_code}, tracking_index: {indicator.tracking_index}")
            age_ok_indicators.append(indicator)
        
        logger.info(f"=== 历史数据齐全过滤后基金数量: {len(age_ok_indicators)} ===")
        
        # 根据index_code进行去重（新增：优先保留“指数基金组合”中的已持有基金）
        try:
            sub_name = "指数基金组合"
            sub_no = getSubAccountNoByName(user, sub_name)
            if not sub_no:
                logger.warning(f"未找到组合 {sub_name} 的账号，持仓优先去重失效")
                holdings = []
            else:
                holdings = get_asset_list_of_sub(user, sub_no)
            held_codes = {a.fund_code for a in holdings} if holdings else set()
            logger.info(f"已获取组合[{sub_name}]持仓基金数量: {len(held_codes)}（sub_account_no={sub_no}）")
        except Exception as e:
            logger.warning(f"获取组合持仓失败，退化为不考虑持仓优先: {e}")
            held_codes = set()

        # 先将无 index_code 的直接保留
        final_indicators: List[FundInvestmentIndicator] = []
        for ind in age_ok_indicators:
            if not getattr(ind, "index_code", None):
                final_indicators.append(ind)
                logger.info(f"保留无index_code基金: {ind.fund_name}({ind.fund_code})")
        
        # 对有 index_code 的按 index_code 分组
        grouped: Dict[str, List[FundInvestmentIndicator]] = {}
        for ind in age_ok_indicators:
            idx = getattr(ind, "index_code", None)
            if idx:
                grouped.setdefault(idx, []).append(ind)

        # 每个 index_code 只保留一个：优先保留已持有，其次 product_rank 最优
        for idx, group in grouped.items():
            group = [g for g in group if not any((g.fund_code == x.fund_code) for x in final_indicators)]
            if not group:
                continue

            held_group = [g for g in group if g.fund_code in held_codes]
            if held_group:
                chosen = min(held_group, key=lambda x: x.product_rank)
                reason = "按持仓优先保留"
            else:
                chosen = min(group, key=lambda x: x.product_rank)
                reason = "未持有该指数，按排名保留"

            final_indicators.append(chosen)
            logger.info(f"{reason}: {chosen.fund_name}({chosen.fund_code}) - index_code: {idx}")
            for g in group:
                if g.fund_code != chosen.fund_code:
                    logger.info(f"过滤重复index_code基金（优先保留已持有）: 被剔除 {g.fund_name}({g.fund_code}) - index_code: {idx}，保留: {chosen.fund_name}({chosen.fund_code})")
        
        logger.info(f"=== 步骤3: index_code去重后基金数量: {len(final_indicators)} ===")
        
        # 根据product_rank从小到大排序
        final_indicators.sort(key=lambda x: x.product_rank)
        
        return final_indicators
        
    except Exception as e:
        logger.error(f'处理加仓风向标基金信息失败: {str(e)}')
        import traceback
        logger.error(f"异常堆栈: {traceback.format_exc()}")
        return []


def save_fund_investment_indicators(user):
    indicators = process_fund_investment_indicators(user)  
    if not indicators:
        return
    # 从第一个指标的 update_time 提取 update_date
    update_time = indicators[0].update_time
    update_date = datetime.strptime(update_time, '%Y-%m-%d %H:%M:%S').strftime('%Y-%m-%d')
    repo = FundInvestmentIndicatorRepositoryImpl()
    repo.save_investment_indicators(indicators, update_date)


# 添加缓存字典
_fund_indicators_cache = {}

def get_fund_investment_indicators(days=10, threshold=3) -> List[FundInvestmentIndicator]:
    cache_key = f"{days}_{threshold}"
    if cache_key in _fund_indicators_cache:
        logging.info(f"从缓存中获取基金投资指标: days={days}, threshold={threshold}")
        return _fund_indicators_cache[cache_key]
    
    repo = FundInvestmentIndicatorRepositoryImpl()
    indicators = repo.get_frequent_indicators(days, threshold)
    
    # 根据tracking_index去重（如果有）
    if indicators:
        seen_indexes = set()
        unique_indicators = []
        for ind in indicators:
            if ind.tracking_index and ind.tracking_index not in seen_indexes:
                seen_indexes.add(ind.tracking_index)
                unique_indicators.append(ind)
            elif not ind.tracking_index:
                unique_indicators.append(ind)  # 保留无tracking_index的
        indicators = unique_indicators
        logging.info(f"去重后基金数量: {len(indicators)}")
    
    _fund_indicators_cache[cache_key] = indicators
    logging.info(f"已缓存基金投资指标: days={days}, threshold={threshold}")
    return indicators


if __name__ == "__main__":
    from common.constant import DEFAULT_USER
    
    try:
        indicators = process_fund_investment_indicators(DEFAULT_USER)
        
        if indicators:
            print(f"加仓风向标基金信息处理成功:")
            print(f"总共获取到 {len(indicators)} 条基金信息（已过滤）")
            print("-----------------------------------")
            
            for i, indicator in enumerate(indicators, 1):
                index_code = getattr(indicator, 'index_code', None)
                index_code_display = index_code if index_code else ""
                
                print(f"{i}. {indicator.fund_name} ({indicator.fund_code})")
                print(f"   排名: {indicator.product_rank}")
                print(f"   基金类型: {indicator.fund_type}")
                print(f"   基金子类型: {indicator.fund_sub_type}")
                print(f"   指数代码: {index_code_display}")
                print(f"   更新时间: {indicator.update_time}")
                print("-----------------------------------")
        else:
            print("处理加仓风向标基金信息失败或无数据返回")
    except Exception as e:
        print(f"执行过程中发生异常: {str(e)}")
