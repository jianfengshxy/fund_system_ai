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

def process_fund_name(name):
    """
    去除基金名称中的字母'A'和'C'
    """
    if not name:
        return name
    # 去除字母A和C（大小写）
    processed_name = re.sub(r'[AaCc]', '', name)
    return processed_name

def get_reduction_fund_names(user):
    """
    直接调用减仓风向标函数获取减仓基金名称列表
    """
    try:
        # 导入减仓风向标模块
        import sys
        import os
        sys.path.append(os.path.dirname(__file__))
        
        # 直接导入并调用函数
        from API.大数据.减仓风向标 import getFundReductionInvestmentIndicators
        
        # 获取减仓基金列表
        reduction_indicators = getFundReductionInvestmentIndicators(user)
        
        if reduction_indicators and hasattr(reduction_indicators, '__iter__'):
            fund_names = set()
            for indicator in reduction_indicators:
                if hasattr(indicator, 'fund_name'):
                    fund_names.add(indicator.fund_name)
            return fund_names
        else:
            logging.warning("减仓基金列表为空或格式不正确")
            return set()
            
    except ImportError as e:
        logging.warning(f"无法导入减仓风向标模块: {str(e)}")
        return set()
    except Exception as e:
        logging.warning(f"获取减仓基金名称失败: {str(e)}")
        return set()

def process_fund_investment_indicators(user, page_size=20) -> List[FundInvestmentIndicator]:
    """
    处理加仓风向标基金信息，包含所有业务逻辑
    
    参数:
    user: 用户对象
    page_size: 每页数量，默认为20
    
    返回:
    List[FundInvestmentIndicator]: 处理后的基金信息列表
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
        
        # 添加初始基金数量统计日志
        logger.info(f"=== 开始过滤处理，初始基金数量: {len(indicators)} ===")
        for i, ind in enumerate(indicators):
            logger.info(f"  初始基金{i+1}: {ind.fund_name}({ind.fund_code}) - 类型:{ind.fund_type} - 子类型:{ind.fund_sub_type}")
        
        # 先过滤掉名称中不包含字母"C"的基金
        original_count = len(indicators)
        indicators = [ind for ind in indicators if "C" in ind.fund_name or "c" in ind.fund_name]
        filtered_out_no_c = original_count - len(indicators)
        logger.info(f"=== 步骤1: 过滤名称中不包含字母'C'的基金 ===")
        logger.info(f"过滤前数量: {original_count}, 过滤后数量: {len(indicators)}, 被过滤: {filtered_out_no_c}")
        if filtered_out_no_c > 0:
            logger.info("保留的基金（包含字母C）:")
            for i, ind in enumerate(indicators):
                logger.info(f"  保留基金{i+1}: {ind.fund_name}({ind.fund_code})")
        
        # 然后处理基金名称，去除字母A和C
        logger.info(f"=== 步骤2: 处理基金名称，去除字母A和C ===")
        for indicator in indicators:
            original_name = indicator.fund_name
            indicator.fund_name = process_fund_name(indicator.fund_name)
            if original_name != indicator.fund_name:
                logger.info(f"  名称处理: {original_name} -> {indicator.fund_name}")
        
        # 过滤掉包含"债"的基金，以及基金子类型等于002003的基金
        original_count = len(indicators)
        debt_funds = [ind for ind in indicators if "债" in ind.fund_name]
        type_002003_funds = [ind for ind in indicators if ind.fund_sub_type == "002003"]
        wrong_type_funds = [ind for ind in indicators if ind.fund_type not in ["000","001","002"]]
        
        logger.info(f"=== 步骤3: 过滤债券基金和特定类型基金 ===")
        logger.info(f"包含'债'的基金数量: {len(debt_funds)}")
        for fund in debt_funds:
            logger.info(f"  债券基金: {fund.fund_name}({fund.fund_code})")
        
        logger.info(f"子类型为002003的基金数量: {len(type_002003_funds)}")
        for fund in type_002003_funds:
            logger.info(f"  002003类型基金: {fund.fund_name}({fund.fund_code})")
        
        logger.info(f"基金类型不在[000,001,002]的基金数量: {len(wrong_type_funds)}")
        for fund in wrong_type_funds:
            logger.info(f"  错误类型基金: {fund.fund_name}({fund.fund_code}) - 类型:{fund.fund_type}")
        
        filtered_indicators = [ind for ind in indicators if "债" not in ind.fund_name and ind.fund_sub_type != "002003" and ind.fund_type in ["000","001","002"]]
        filtered_out_debt_type = original_count - len(filtered_indicators)
        logger.info(f"过滤前数量: {original_count}, 过滤后数量: {len(filtered_indicators)}, 被过滤: {filtered_out_debt_type}")
        
        if len(filtered_indicators) > 0:
            logger.info("通过债券和类型过滤的基金:")
            for i, ind in enumerate(filtered_indicators):
                logger.info(f"  通过基金{i+1}: {ind.fund_name}({ind.fund_code}) - 类型:{ind.fund_type} - 子类型:{ind.fund_sub_type}")
        else:
            logger.warning("所有基金都被债券和类型过滤规则过滤掉了！")
        
        # 获取减仓基金列表，用于过滤重名基金
        logger.info(f"=== 步骤4: 减仓基金重名过滤 ===")
        try:
            reduction_fund_names = get_reduction_fund_names(user)
            if reduction_fund_names:
                original_count = len(filtered_indicators)
                logger.info(f"获取到减仓基金名称列表，共{len(reduction_fund_names)}个: {list(reduction_fund_names)}")
                # 记录被过滤的基金名称
                filtered_fund_names = [ind.fund_name for ind in filtered_indicators if ind.fund_name in reduction_fund_names]
                filtered_indicators = [ind for ind in filtered_indicators if ind.fund_name not in reduction_fund_names]
                filtered_count = original_count - len(filtered_indicators)
                logger.info(f"过滤掉了 {filtered_count} 个与减仓基金重名的基金")
                if filtered_fund_names:
                    logger.info(f"被过滤的基金名称: {', '.join(filtered_fund_names)}")
                
                if len(filtered_indicators) > 0:
                    logger.info("通过减仓基金过滤的基金:")
                    for i, ind in enumerate(filtered_indicators):
                        logger.info(f"  通过基金{i+1}: {ind.fund_name}({ind.fund_code})")
                else:
                    logger.warning("所有基金都被减仓基金重名过滤规则过滤掉了！")
            else:
                logger.info("未获取到减仓基金列表，跳过重名过滤")
        except Exception as e:
            logger.warning(f"获取减仓基金列表失败，跳过重名过滤: {str(e)}")
        
        # 对基金类型为"000"的基金按index_code去重，只保留第一个
        logger.info(f"=== 步骤5: 基金类型000去重处理 ===")
        try:
            seen_index_codes = set()
            final_indicators = []
            type_000_count = len([ind for ind in filtered_indicators if ind.fund_type == "000"])
            type_001_count = len([ind for ind in filtered_indicators if ind.fund_type == "001"])
            type_002_count = len([ind for ind in filtered_indicators if ind.fund_type == "002"])
            
            logger.info(f"开始处理基金类型000去重，共有 {type_000_count} 个基金类型为000的基金")
            logger.info(f"基金类型统计: 000类型={type_000_count}, 001类型={type_001_count}, 002类型={type_002_count}")
            
            for indicator in filtered_indicators:
                if indicator.fund_type == "000":
                    try:
                        # 获取基金详细信息以获得index_code
                        logger.info(f"正在获取基金 {indicator.fund_name}({indicator.fund_code}) 的详细信息...")
                        fund_info = get_all_fund_info(user, indicator.fund_code)
                        if fund_info and hasattr(fund_info, 'index_code') and fund_info.index_code:
                            if fund_info.index_code not in seen_index_codes:
                                seen_index_codes.add(fund_info.index_code)
                                final_indicators.append(indicator)
                                logger.info(f"保留基金 {indicator.fund_name}({indicator.fund_code})，跟踪指数: {fund_info.index_code}")
                            else:
                                logger.info(f"过滤基金 {indicator.fund_name}({indicator.fund_code})，跟踪指数 {fund_info.index_code} 已存在")
                        else:
                            # 如果获取不到index_code，仍然保留该基金
                            final_indicators.append(indicator)
                            logger.info(f"保留基金 {indicator.fund_name}({indicator.fund_code})，未获取到跟踪指数信息")
                    except Exception as fund_error:
                        # 如果获取基金信息失败，仍然保留该基金
                        final_indicators.append(indicator)
                        logger.warning(f"获取基金 {indicator.fund_name}({indicator.fund_code}) 信息失败，仍然保留: {str(fund_error)}")
                else:
                    # 非"000"类型的基金直接保留
                    final_indicators.append(indicator)
                    logger.info(f"直接保留非000类型基金: {indicator.fund_name}({indicator.fund_code}) - 类型:{indicator.fund_type}")
            
            filtered_indicators = final_indicators
            logger.info(f"基金类型000去重后剩余 {len(filtered_indicators)} 个基金")
        except Exception as e:
            logger.warning(f"基金类型000去重处理失败，跳过此步骤: {str(e)}")
            import traceback
            logger.warning(f"异常堆栈: {traceback.format_exc()}")
        
        # 根据product_rank从小到大排序
        filtered_indicators.sort(key=lambda x: x.product_rank)
        
        # 最终结果统计
        logger.info(f"=== 最终结果统计 ===")
        logger.info(f"最终返回基金数量: {len(filtered_indicators)}")
        if len(filtered_indicators) > 0:
            logger.info("最终基金列表:")
            for i, ind in enumerate(filtered_indicators):
                logger.info(f"  最终基金{i+1}: {ind.fund_name}({ind.fund_code}) - 类型:{ind.fund_type} - 排名:{ind.product_rank}")
        else:
            logger.error("警告: 所有基金都被过滤掉了，返回空列表！")
        
        return filtered_indicators
        
    except Exception as e:
        logger.error(f'处理加仓风向标基金信息失败: {str(e)}')
        return []

if __name__ == "__main__":
    # 配置日志
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    from common.constant import DEFAULT_USER

    try:
        # 获取并处理加仓风向标基金信息
        result = process_fund_investment_indicators(DEFAULT_USER, page_size=20)

        if result:
            print("\n加仓风向标基金信息处理成功:")
            print(f"总共获取到 {len(result)} 条基金信息（已过滤）")
            print("===================================")

            for i, indicator in enumerate(result, 1):
                # 获取基金的详细信息，包括估算涨幅
                fund_info = get_all_fund_info(DEFAULT_USER, indicator.fund_code)
                estimated_change = fund_info.estimated_change if fund_info else 'N/A'
                index_code = fund_info.index_code if fund_info and fund_info.index_code else '无'

                print(f"{i}. {indicator.fund_name} ({indicator.fund_code})")
                print(f"   排名: {indicator.product_rank}")
                print(f"   今日估算涨幅: {estimated_change}%")
                if indicator.fund_type == '000':
                    print(f"   跟踪指数: {index_code}")
                print(f"   一年收益率: {indicator.one_year_return if indicator.one_year_return != 0 else '暂无'}%")
                print(f"   成立以来收益率: {indicator.since_launch_return}%")
                print(f"   基金类型: {indicator.fund_type}")
                print(f"   基金子类型: {indicator.fund_sub_type}")
                print(f"   更新时间: {indicator.update_time}")
                print("-----------------------------------")
        else:
            print("处理加仓风向标基金信息失败或无数据返回")
    except Exception as e:
        print(f"执行过程中发生异常: {str(e)}")

