import os
import sys
import logging
import urllib.parse
import urllib3
import warnings
import requests
from typing import List, Dict, Any, Optional
import re
import subprocess

# 添加项目根目录到路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from common.constant import DEFAULT_USER, FUND_CODE
from domain.fund_plan import ApiResponse
from domain.fund.fund_investment_indicator import FundInvestmentIndicator
from service.基金信息.基金信息 import get_all_fund_info

# 删除这行导入：
# from API.大数据.减仓风向标 import getFundReductionInvestmentIndicators

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
        from 减仓风向标 import getFundReductionInvestmentIndicators
        
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

def getFundInvestmentIndicators(user, page_size=20) -> ApiResponse[List[FundInvestmentIndicator]]:
    """
    获取加仓风向标基金信息
    
    参数:
    user: 用户对象
    page_size: 每页数量，默认为20
    
    返回:
    ApiResponse: 包含加仓风向标基金信息列表的响应对象
    """
    url = 'https://fundcomapi.tiantianfunds.com/mm/FundCustom/multiFundTypeSpeConfigListPage'
    
    headers = {
        'Connection': 'keep-alive',
        'Content-Type': 'application/x-www-form-urlencoded',
        'validmark': 'Li4RtWc+9LvmhgcBNN3qg3dzZjFUt4WiApOOGmkaVZL5BWm0DcGX9NZYIxjsAsZdVcHJ8J2NdZhXTNMQR9BMpxG3EMlqXyJoFeiMLZWZZtJ1DXqiIOSu/kLYsAt37vKDllijg7ffsKY6LcVX2IpgamPZG7YN4mKd7mTYGSc0Sjg=',
        'mp_instance_id': '68',
        'Referer': 'https://mpservice.com/fund9bb5726fafc14e/release/pages/home/index',
        'gtoken': 'ceaf-4a997831b1b3b90849f585f98ca6f30e',
        'clientInfo': 'ttjj-ZTE 7534N-Android-11',
        'traceparent': '00-0000000046aa4cae0000019426368b65-0000000000000000-01',
        'tracestate': 'pid=0x9cf938d,taskid=0x25b8739',
        'Host': 'fundcomapi.tiantianfunds.com',
        'User-Agent': 'okhttp/3.12.13'
    }
    
    data = {
        'FIELDS': 'SHORTNAME,RSFUNDTYPE,RSBTYPE,SYL_1N,SYL_LN,FCODE,EUTIME',
        'product': 'EFund',
        'pageSize': page_size,
        'passportctoken': user.passport_ctoken,
        'configType': '9',
        'passportutoken': user.passport_utoken,
        'deviceid': '15a16f86a738f59811cbd40da4da1d97||iemi_tluafed_me',
        'userid': user.customer_no,
        'version': '6.7.0',
        'configSort': 'asc',
        'configSortColumn': 'PRODUCT_RANK',
        'ctoken': user.c_token,
        'uid': user.customer_no,
        'utoken': user.u_token,
        'plat': 'Android',
        'passportid': user.passport_id
    }
    
    logger = logging.getLogger("FundInvestmentIndicator")
    try:
        response = requests.post(url, data=data, headers=headers, verify=False)
        response.raise_for_status()
        json_data = response.json()
        logger.info(f"响应数据: {json_data}")
        
        try:
            if not json_data.get('success', False):
                return ApiResponse(
                    Success=json_data.get('success', False),
                    ErrorCode=json_data.get('errorCode'),
                    Data=None,
                    FirstError=json_data.get('firstError'),
                    DebugError=json_data.get('hasWrongToken')
                )
            
            data = json_data.get('data')
            if data is None:
                raise Exception('解析响应数据失败: data字段为空')
            
            # 获取类型为9的基金列表
            fund_list = data.get('9', [])
            if not fund_list:
                logger.warning("未找到加仓风向标基金数据")
                return ApiResponse(
                    Success=True,
                    ErrorCode=None,
                    Data=[],
                    FirstError=None,
                    DebugError=None
                )
            
            indicators = []
            
            for fund_data in fund_list:
                indicator = FundInvestmentIndicator.from_dict(fund_data)
                indicators.append(indicator)
            
            # 先过滤掉名称中不包含字母"C"的基金
            indicators = [ind for ind in indicators if "C" in ind.fund_name or "c" in ind.fund_name]
            
            # 然后处理基金名称，去除字母A和C
            for indicator in indicators:
                indicator.fund_name = process_fund_name(indicator.fund_name)
            
            # 过滤掉包含"债"的基金，以及基金子类型等于002003的基金
            filtered_indicators = [ind for ind in indicators if "债" not in ind.fund_name and ind.fund_sub_type != "002003" and ind.fund_type in ["000","001","002"]]
            
            # 获取减仓基金列表，用于过滤重名基金
            try:
                reduction_fund_names = get_reduction_fund_names(user)
                if reduction_fund_names:
                    original_count = len(filtered_indicators)
                    # 记录被过滤的基金名称
                    filtered_fund_names = [ind.fund_name for ind in filtered_indicators if ind.fund_name in reduction_fund_names]
                    filtered_indicators = [ind for ind in filtered_indicators if ind.fund_name not in reduction_fund_names]
                    filtered_count = original_count - len(filtered_indicators)
                    logger.info(f"过滤掉了 {filtered_count} 个与减仓基金重名的基金")
                    if filtered_fund_names:
                        logger.info(f"被过滤的基金名称: {', '.join(filtered_fund_names)}")
                else:
                    logger.info("未获取到减仓基金列表，跳过重名过滤")
            except Exception as e:
                logger.warning(f"获取减仓基金列表失败，跳过重名过滤: {str(e)}")
            
            # 对基金类型为"000"的基金按index_code去重，只保留第一个
            try:
                seen_index_codes = set()
                final_indicators = []
                
                for indicator in filtered_indicators:
                    if indicator.fund_type == "000":
                        # 获取基金详细信息以获得index_code
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
                    else:
                        # 非"000"类型的基金直接保留
                        final_indicators.append(indicator)
                
                filtered_indicators = final_indicators
                logger.info(f"基金类型000去重后剩余 {len(filtered_indicators)} 个基金")
            except Exception as e:
                logger.warning(f"基金类型000去重处理失败，跳过此步骤: {str(e)}")
            
            # 根据product_rank从小到大排序
            filtered_indicators.sort(key=lambda x: x.product_rank)
            
            # 直接返回过滤后的基金指标数组
            return filtered_indicators
            
            # api_response = ApiResponse(
            #     Success=True,
            #     ErrorCode=None,
            #     Data=filtered_indicators,
            #     FirstError=None,
            #     DebugError=None
            # )
            # return api_response
            
        except Exception as e:
            logger.error(f'解析响应数据失败: {str(e)}')
            raise Exception(f'解析响应数据失败: {str(e)}')
    except requests.exceptions.RequestException as e:
        logger.error(f'请求失败: {str(e)}')
        raise Exception(f'请求失败: {str(e)}')

if __name__ == "__main__":

    
    # 配置日志
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    try:
        # 获取加仓风向标基金信息
        result = getFundInvestmentIndicators(DEFAULT_USER,page_size=20)
        
        if result:
            print("\n加仓风向标基金信息获取成功:")
            print(f"总共获取到 {len(result)} 条基金信息（已过滤保留名称不包含'债'的基金，并排除基金子类型等于002003的基金，按产品排名从小到大排序）")
            print("===================================")
            
            for i, indicator in enumerate(result, 1):
                print(f"{i}. {indicator.fund_name} ({indicator.fund_code})")
                print(f"   排名: {indicator.product_rank}")
                print(f"   一年收益率: {indicator.one_year_return if indicator.one_year_return != 0 else '暂无'}%")
                print(f"   成立以来收益率: {indicator.since_launch_return}%")
                print(f"   基金类型: {indicator.fund_type}")
                print(f"   基金子类型: {indicator.fund_sub_type}")
                print(f"   更新时间: {indicator.update_time}")
                
                # 输出所有属性和值
                print("   所有属性:")
                for attr, value in vars(indicator).items():
                    print(f"      {attr}: {value}")
                
                print("-----------------------------------")
        else:
            print("获取加仓风向标基金信息失败: 返回结果为空")
    except Exception as e:
        print(f"执行过程中发生异常: {str(e)}")


