import logging
import requests
from typing import Dict, Any, List, Optional, Union
import os
import sys

# Add root dir to path if running as script to allow src imports
if __name__ == "__main__":
    root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    if root_dir not in sys.path:
        sys.path.insert(0, root_dir)

from src.common.logger import get_logger
from src.common.requests_session import session
from src.domain.user.User import User
from src.common.constant import SERVER_VERSION, MOBILE_KEY, PHONE_TYPE, DEVICE_ID

logger = get_logger("FundIndexStagePerf")

def get_fund_index_stage_performance(user: User, index_code: str) -> Dict[str, Any]:
    """
    获取基金指数阶段涨幅及相关指标（上涨天数、下跌天数、胜率等）
    Args:
        user: User对象
        index_code: 市场指数代码 (e.g. "399959")
    Returns:
        Dict[str, Any]: 阶段涨幅及统计指标字典
    """
    url = "https://fundcomapi.tiantianfunds.com/mm/FundIndex/FundIndexDiy"
    
    headers = {
        'Accept': '*/*',
        'Accept-Encoding': 'gzip, deflate, br',
        'Accept-Language': 'zh-Hans-CN;q=1',
        'Connection': 'keep-alive',
        'Content-Type': 'application/x-www-form-urlencoded',
        'GTOKEN': '03FC9273690F4DC4B71CB2247A0E4338',
        'Host': 'fundcomapi.tiantianfunds.com',
        'MP-VERSION': '1.3.6',
        'Referer': 'https://mpservice.com/7d7b3460cd40444ba58cdabdfae34442/release/pages/index-detail/index',
        'User-Agent': f'EMProjJijin/{SERVER_VERSION} (iPhone; iOS 16.0; Scale/3.00)',
        'clientInfo': 'ttjj-iPhone18,1-iOS-iOS16.0',
        'traceparent': '00-0160dd2825e2446ba4ff1c6c6cd91ec8-0000000000000000-01',
        'tracestate': 'pid=0x105032130,taskid=0x1462b6be0',
        'validmark': 'Li4RtWc+9LvmhgcBNN3qg3dzZjFUt4WiApOOGmkaVZL5BWm0DcGX9NZYIxjsAsZdSIrQ1Lx4ygfw5br2rQnUfMES8ernsO5lB/RKZKLdR3wGTOXNmNZFC2UPo8zBqCl4rhSrgPLj6p18fmTjJyofJQ=='
    }
    
    fields = "UPDAYS_W,UPDAYS_M,UPDAYS_Q,UPDAYS_HY,UPDAYS_Y,UPDAYS_TWY,UPDAYS_TRY,UPDAYS_FY,UPDAYS_SY,DOWNDAYS_W,DOWNDAYS_M,DOWNDAYS_Q,DOWNDAYS_HY,DOWNDAYS_Y,DOWNDAYS_TWY,DOWNDAYS_TRY,DOWNDAYS_FY,DOWNDAYS_SY,INDEXOTYPE,ISUSEPBP,MAKERNAME,BASICDATE,BASICDATE,XLFLOW_SCORE,PROFIT_RATE_TRY,PROFIT_RATE_Y,PROFIT_RATE_HY,PROFIT_RATE_Q,AVGSYL_TRY,AVGSYL_Y,AVGSYL_HY,AVGSYL_Q,PEP100_Y,PBP100_Y,PEP100_TRY,PBP100_TRY,PEP100_FY,PBP100_FY,PEP100_TY,PBP100_TY,PEP100_SE,PBP100_SE"
    
    # Using GET method as per curl, but passing parameters via params
    params = {
        'FCODES': index_code,
        'FIELDS': fields,
        'ctoken': user.c_token,
        'deviceid': DEVICE_ID,
        'indexTypeFields': 'TYPE_NAME,TYPE_CODE',
        'passportctoken': user.passport_ctoken or user.c_token,
        'passportid': user.passport_id,
        'passportutoken': user.passport_utoken or user.u_token,
        'plat': 'Iphone',
        'product': 'EFund',
        'uid': user.customer_no,
        'userid': user.customer_no,
        'utoken': user.u_token,
        'version': SERVER_VERSION
    }
    
    try:
        response = session.get(url, headers=headers, params=params, verify=False, timeout=10)
        response.raise_for_status()
        result = response.json()
        
        if result.get("success"):
            data_list = result.get("data", [])
            if data_list:
                return data_list[0]
            return {}
        else:
            logger.error(f"获取基金阶段涨幅失败: {result.get('message', 'Unknown error')}")
            return {}
            
    except Exception as e:
        logger.error(f"获取基金阶段涨幅异常: {e}")
        return {}

if __name__ == "__main__":
    from src.common.constant import DEFAULT_USER
    from src.API.登录接口.login import ensure_user_fresh
    
    print("Refreshing user token...")
    user = ensure_user_fresh(DEFAULT_USER)
    
    # Test with index code from example (399959 - 中证军工)
    test_index_code = "399959" 
    print(f"\n--- Testing Fund Index Stage Performance for {test_index_code} ---")
    data = get_fund_index_stage_performance(user, index_code=test_index_code)
    
    if data:
        print(f"Index Code: {data.get('INDEXCODE')}, Name: {data.get('TYPE_NAME')}")
        print(f"Up Days (Year): {data.get('UPDAYS_Y')}, Down Days (Year): {data.get('DOWNDAYS_Y')}")
        print(f"Profit Rate (Year): {data.get('PROFIT_RATE_Y')}%")
        print(f"PE Percentile (Year): {data.get('PEP100_Y')}%")
    else:
        print("Failed to get fund index stage performance.")
