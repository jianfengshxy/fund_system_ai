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

logger = get_logger("IndexMoneyFlow")

def get_index_money_flow(user: User, index_code: str, range_type: str = "n") -> List[Dict[str, Any]]:
    """
    获取指数资金流向数据
    Args:
        user: User对象
        index_code: 市场指数代码 (e.g. "399959")
        range_type: 时间范围 (default "n")
    Returns:
        List[Dict[str, Any]]: 资金流向数据列表，包含日期、点位、涨跌幅、资金流向得分
    """
    url = "https://fundcomapi.tiantianfunds.com/mm/FundIndex/FundIndexPrice"
    
    headers = {
        'Accept': '*/*',
        'Accept-Encoding': 'gzip, deflate, br',
        'Accept-Language': 'zh-Hans-CN;q=1',
        'Connection': 'keep-alive',
        'Content-Type': 'application/x-www-form-urlencoded',
        'GTOKEN': '03FC9273690F4DC4B71CB2247A0E4338',
        'Host': 'fundcomapi.tiantianfunds.com',
        'MP-VERSION': '1.3.6',
        'Referer': 'https://mpservice.com/7d7b3460cd40444ba58cdabdfae34442/release/pages/index-detail/sub-pages/capital/index',
        'User-Agent': f'EMProjJijin/{SERVER_VERSION} (iPhone; iOS 26.0.1; Scale/3.00)',
        'clientInfo': 'ttjj-iPhone18,1-iOS-iOS26.0.1',
        'traceparent': '00-daba033e0a1f4986b39426b61e0b3619-0000000000000000-01',
        'tracestate': 'pid=0x105032130,taskid=0x157a9ef40',
        'validmark': 'Li4RtWc+9LvmhgcBNN3qg3dzZjFUt4WiApOOGmkaVZL5BWm0DcGX9NZYIxjsAsZdSIrQ1Lx4ygfw5br2rQnUfMES8ernsO5lB/RKZKLdR3zD2KNQjemM+lwlJAhAHjbPa1Sl+8lg3dobsr1ny7eoGw=='
    }
    
    data = {
        'INDEXCODE': index_code,
        'RANGE': range_type,
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
            return result.get("data", [])
        else:
            logger.error(f"获取指数资金流向失败: {result.get('message', 'Unknown error')}")
            return []
            
    except Exception as e:
        logger.error(f"获取指数资金流向异常: {e}")
        return []

if __name__ == "__main__":
    from src.common.constant import DEFAULT_USER
    from src.API.登录接口.login import ensure_user_fresh
    
    print("Refreshing user token...")
    user = ensure_user_fresh(DEFAULT_USER)
    
    # Test with index code from example (399959 - 中证军工)
    test_index_code = "399959" 
    print(f"\n--- Testing Index Money Flow for {test_index_code} ---")
    data = get_index_money_flow(user, index_code=test_index_code)
    
    if data:
        print(f"Retrieved {len(data)} records.")
        # Print first 3 and last 3 records
        print("First 3 records:")
        for item in data[:3]:
            print(f"Date: {item.get('PDATE')}, Price: {item.get('PERCENTPRICE')}, Change: {item.get('CHGRT')}%, Flow Score: {item.get('XLFLOW_SCORE')}")
        
        if len(data) > 3:
            print("...")
            print("Last 3 records:")
            for item in data[-3:]:
                print(f"Date: {item.get('PDATE')}, Price: {item.get('PERCENTPRICE')}, Change: {item.get('CHGRT')}%, Flow Score: {item.get('XLFLOW_SCORE')}")
    else:
        print("Failed to get index money flow data.")
