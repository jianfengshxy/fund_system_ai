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

logger = get_logger("IndexDetail")

def get_index_detail(user: User, index_code: str) -> Dict[str, Any]:
    """
    获取指数详情
    Args:
        user: User对象
        index_code: 市场指数代码 (e.g. "399959")
    Returns:
        Dict[str, Any]: 指数详情字典
    """
    url = "https://fundcomapi.tiantianfunds.com/mm/FundIndex/FundZSBZSIndex"
    
    headers = {
        'Accept': '*/*',
        'Accept-Encoding': 'gzip, deflate, br',
        'Accept-Language': 'zh-Hans-CN;q=1',
        'Connection': 'keep-alive',
        'GTOKEN': '03FC9273690F4DC4B71CB2247A0E4338',
        'Host': 'fundcomapi.tiantianfunds.com',
        'MP-VERSION': '1.3.6',
        'Referer': 'https://mpservice.com/7d7b3460cd40444ba58cdabdfae34442/release/pages/index-detail/index',
        'User-Agent': f'EMProjJijin/{SERVER_VERSION} (iPhone; iOS 16.0; Scale/3.00)',
        'clientInfo': 'ttjj-iPhone18,1-iOS-iOS16.0',
        'traceparent': '00-d2247c611e03462d880c99c37920d8f3-0000000000000000-01',
        'tracestate': 'pid=0x105032130,taskid=0x1462b61c0',
        'validmark': 'Li4RtWc+9LvmhgcBNN3qg3dzZjFUt4WiApOOGmkaVZL5BWm0DcGX9NZYIxjsAsZdSIrQ1Lx4ygfw5br2rQnUfMES8ernsO5lB/RKZKLdR3xaO8ABbqI5hQKVcn0/1qOLyecTlyx+itvuAISjWzUcfg=='
    }
    
    data = {
        'indexCode': index_code,
        'ctoken': user.c_token,
        'deviceid': DEVICE_ID,
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
        response = session.post(url, headers=headers, data=data, verify=False, timeout=10)
        response.raise_for_status()
        result = response.json()
        
        if result.get("success"):
            return result.get("data", {})
        else:
            logger.error(f"获取指数详情失败: {result.get('message', 'Unknown error')}")
            return {}
            
    except Exception as e:
        logger.error(f"获取指数详情异常: {e}")
        return {}

if __name__ == "__main__":
    from src.common.constant import DEFAULT_USER
    from src.API.登录接口.login import ensure_user_fresh
    
    print("Refreshing user token...")
    user = ensure_user_fresh(DEFAULT_USER)
    
    # Test with index code from example (399959 - 中证军工)
    test_index_code = "399959" 
    print(f"\n--- Testing Index Detail for {test_index_code} ---")
    detail = get_index_detail(user, index_code=test_index_code)
    
    if detail:
        print(f"Name: {detail.get('INDEXNAME')} ({detail.get('INDEXCODE')})")
        print(f"Price: {detail.get('NEWPRICE')}, Change: {detail.get('NEWCHG')}%")
        print(f"PE (TTM): {detail.get('PETTM')}")
        print(f"Description: {detail.get('REAPROFILE')}")
    else:
        print("Failed to get index details.")
