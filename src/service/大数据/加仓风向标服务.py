import os
import sys
import logging
import re
from typing import List, Dict, Any, Optional

# 添加项目根目录到路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from domain.fund_plan import ApiResponse
from domain.fund.fund_investment_indicator import FundInvestmentIndicator
from service.基金信息.基金信息 import get_all_fund_info
from API.大数据.加仓风向标 import getFundInvestmentIndicators as getBasicFundInvestmentIndicators
from src.db.fund_repository_impl import FundRepositoryImpl
from src.db.fund_investment_indicator_repository_impl import FundInvestmentIndicatorRepositoryImpl
from datetime import datetime


def process_fund_investment_indicators(user, page_size=20) -> List[FundInvestmentIndicator]:
    """
    处理基金投资指标数据，按规则过滤并返回结果
    
    调整后规则：
    1. 保留基金名中包含"C"的基金
    2. 过滤规则：
        - 过滤掉基金名包含"债"的
        - 过滤掉 fund_sub_type == "002003" 的
        - 仅保留 fund_type in ["000","001","002"]
        - 当 fund_type == "000" 时，只保留 fund_sub_type == "000001"
    3. 获取基金详细信息以获得index_code并进行去重
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
        
        indicators = []
        for fund_data in fund_list:
            indicator = FundInvestmentIndicator.from_dict(fund_data)
            indicators.append(indicator)
        
        logger.info(f"=== 开始过滤处理，初始基金数量: {len(indicators)} ===")
        
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
        
        # === 步骤3: 获取基金详细信息以获得index_code ===
        logger.info("=== 步骤3: 获取基金详细信息并进行index_code去重 ===")
        
        # 为每个基金添加index_code信息
        for indicator in filtered_indicators:
            fund_info = get_all_fund_info(user, indicator.fund_code)
            if fund_info:
                indicator.index_code = getattr(fund_info, 'index_code', None)
                indicator.tracking_index = indicator.index_code  # 根据index_code赋值tracking_index
                logger.info(f"基金 {indicator.fund_name}({indicator.fund_code}) 获得index_code: {indicator.index_code}, tracking_index: {indicator.tracking_index}")
            else:
                indicator.index_code = ''
                indicator.tracking_index = None  # 或 ''
                logger.warning(f"基金 {indicator.fund_name}({indicator.fund_code}) 未找到详细信息")
        
        # 根据index_code进行去重
        seen_index_codes = set()
        final_indicators = []
        
        for indicator in filtered_indicators:
            if indicator.index_code:
                if indicator.index_code not in seen_index_codes:
                    seen_index_codes.add(indicator.index_code)
                    final_indicators.append(indicator)
                    logger.info(f"保留基金: {indicator.fund_name}({indicator.fund_code}) - index_code: {indicator.index_code}")
                else:
                    logger.info(f"过滤重复index_code基金: {indicator.fund_name}({indicator.fund_code}) - index_code: {indicator.index_code}")
            else:
                # 没有index_code的基金也保留
                final_indicators.append(indicator)
                logger.info(f"保留无index_code基金: {indicator.fund_name}({indicator.fund_code})")
        
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
