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

logger = get_logger("IndexStagePerf")

def get_index_stage_performance(user: User, index_code: str, range_type: str = "3y") -> List[Dict[str, Any]]:
    """
    获取指数阶段走势（如季度涨幅、月度涨幅等）
    Args:
        user: User对象
        index_code: 市场指数代码 (e.g. "399959")
        range_type: 统计周期类型
            - y: 月
            - 3y: 季度 (3个月)
            - 6y: 半年 (6个月)
            - n: 年
    Returns:
        List[Dict[str, Any]]: 阶段涨幅列表
    """
    url = "https://fundcomapi.tiantianfunds.com/mm/FundIndex/IndexYearQuarterIncrease"
    
    headers = {
        'Accept': '*/*',
        'Accept-Encoding': 'gzip, deflate, br',
        'Accept-Language': 'zh-Hans-CN;q=1',
        'Connection': 'keep-alive',
        'GTOKEN': '03FC9273690F4DC4B71CB2247A0E4338',
        'Host': 'fundcomapi.tiantianfunds.com',
        'MP-VERSION': '1.3.6',
        'Referer': 'https://mpservice.com/7d7b3460cd40444ba58cdabdfae34442/release/pages/index-detail/sub-pages/common/index',
        'User-Agent': f'EMProjJijin/{SERVER_VERSION} (iPhone; iOS 16.0; Scale/3.00)',
        'clientInfo': 'ttjj-iPhone18,1-iOS-iOS16.0',
        'traceparent': '00-7e4eac313ad34daaa59573ee4ef38cde-0000000000000000-01',
        'tracestate': 'pid=0x105032130,taskid=0x12e49ff60',
        'validmark': 'Li4RtWc+9LvmhgcBNN3qg3dzZjFUt4WiApOOGmkaVZL5BWm0DcGX9NZYIxjsAsZdSIrQ1Lx4ygfw5br2rQnUfMES8ernsO5lB/RKZKLdR3yj54DzeINgWEBBLeGjQZaII+DeT0GPg7/PfGdusqta+Q=='
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
            logger.error(f"获取指数阶段走势失败: {result.get('message', 'Unknown error')}")
            return []
            
    except Exception as e:
        logger.error(f"获取指数阶段走势异常: {e}")
        return []

if __name__ == "__main__":
    from src.common.constant import DEFAULT_USER
    from src.API.登录接口.login import ensure_user_fresh
    
    print("Refreshing user token...")
    user = ensure_user_fresh(DEFAULT_USER)
    
    # Test with index code from example (399959 - 中证军工?)
    test_index_code = "399959" 
    print(f"\n--- Testing Index Stage Performance (Quarterly - 3y) for {test_index_code} ---")
    data = get_index_stage_performance(user, index_code=test_index_code, range_type="3y")
    
    # Show last 5 quarters
    for item in data[-5:]:
        print(f"Period: {item.get('title')}, Change: {item.get('syl')}%, UpDays: {item.get('upDays')}, DownDays: {item.get('downDays')}")
        
    print(f"\n--- Testing Index Stage Performance (Yearly - y) for {test_index_code} ---")
    data_y = get_index_stage_performance(user, index_code=test_index_code, range_type="y")
    for item in data_y[-5:]:
        print(f"Period: {item.get('title')}, Change: {item.get('syl')}%, UpDays: {item.get('upDays')}, DownDays: {item.get('downDays')}")
