import os
import sys
import logging
import requests
from typing import List, Dict, Any, Optional

# 添加项目根目录到路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from common.constant import DEFAULT_USER, FUND_CODE
from domain.fund_plan import ApiResponse
from domain.fund.fund_investment_indicator import FundInvestmentIndicator

def getFundInvestmentIndicators(user, page_size=20) -> ApiResponse[Dict[str, Any]]:
    """
    获取加仓风向标基金信息 - 基础API接口
    
    参数:
    user: 用户对象
    page_size: 每页数量，默认为20
    
    返回:
    ApiResponse: 包含原始API响应数据的响应对象
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
    
    logger = logging.getLogger("FundInvestmentIndicatorAPI")
    
    try:
        response = requests.post(url, data=data, headers=headers, verify=False)
        response.raise_for_status()
        json_data = response.json()
        
        logger.info(f"API调用成功，返回数据: {json_data.get('success', False)}")
        
        return ApiResponse(
            Success=json_data.get('success', False),
            ErrorCode=json_data.get('errorCode'),
            Data=json_data.get('data'),
            FirstError=json_data.get('firstError'),
            DebugError=json_data.get('hasWrongToken')
        )
        
    except requests.exceptions.RequestException as e:
        logger.error(f'API请求失败: {str(e)}')
        return ApiResponse(
            Success=False,
            ErrorCode='REQUEST_ERROR',
            Data=None,
            FirstError=f'请求失败: {str(e)}',
            DebugError=None
        )
    except Exception as e:
        logger.error(f'API调用异常: {str(e)}')
        return ApiResponse(
            Success=False,
            ErrorCode='UNKNOWN_ERROR',
            Data=None,
            FirstError=f'未知错误: {str(e)}',
            DebugError=None
        )

if __name__ == "__main__":
    # 配置日志
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    try:
        # 测试API接口
        result = getFundInvestmentIndicators(DEFAULT_USER, page_size=20)
        
        if result.Success:
            print("\n=== API调用成功 ===")
            print(f"成功状态: {result.Success}")
            print(f"错误代码: {result.ErrorCode if result.ErrorCode else '无'}")
            print("返回数据:")
            import json
            print(json.dumps(result.Data, indent=4, ensure_ascii=False))
        else:
            print("\n=== API调用失败 ===")
            print(f"错误代码: {result.ErrorCode}")
            print(f"错误信息: {result.FirstError}")
            if result.DebugError:
                print(f"调试错误: {result.DebugError}")
    except Exception as e:
        print("\n=== 执行过程中发生异常 ===")
        print(f"异常信息: {str(e)}")


