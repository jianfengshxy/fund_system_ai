import sys
import os
import logging
import urllib.parse
import urllib3
import warnings
import requests
from typing import List, Dict, Any, Optional
import logging
from common.constant import DEFAULT_USER, FUND_CODE

# 添加项目根目录到路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from domain.fund_plan import ApiResponse
from domain.fund.fund_investment_indicator import FundInvestmentIndicator
import re

def process_fund_name(name):
    """
    去除基金名称中的字母'A'和'C'
    """
    if not name:
        return name
    # 去除字母A和C（大小写）
    processed_name = re.sub(r'[AaCc]', '', name)
    return processed_name

def getFundReductionInvestmentIndicators(user, page_size=20) -> ApiResponse[List[FundInvestmentIndicator]]:
    """
    获取加仓风向标基金信息
    
    参数:
    user: 用户对象
    page_size: 每页数量，默认为40
    
    返回:
    ApiResponse: 包含减仓风向标基金信息列表的响应对象
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
        'configType': '10',
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
    
    logger = logging.getLogger("FundReductionInvestmentIndicator")
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
            fund_list = data.get('10', [])
            if not fund_list:
                logger.warning("未找到减仓风向标基金数据")
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
                # 处理基金名称，去除字母A和C
                indicator.fund_name = process_fund_name(indicator.fund_name)
                indicators.append(indicator)
            
            # 根据product_rank从小到大排序
            indicators.sort(key=lambda x: x.product_rank)
            
            # 直接返回过滤后的基金指标数组
            return indicators
            
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
        result = getFundReductionInvestmentIndicators(DEFAULT_USER,page_size=20)
        
        if result:
            print("\n加仓风向标基金信息获取成功:")
            print(f"总共获取到 {len(result)} 条基金信息（已过滤保留名称中包含字母'C'且不包含'债'的基金，并排除基金子类型等于002003的基金，按产品排名从小到大排序）")
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


