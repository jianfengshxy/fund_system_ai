import logging
import requests
from typing import Dict, Any, List, Optional
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

logger = get_logger("MarketIndex")

def get_market_index(user: User, type_code: str = "001003", page_index: int = 1, page_size: int = 20, sort_type: str = "DESC", sort_name: str = "NEWCHG") -> List[Dict[str, Any]]:
    """
    获取市场指数排行
    Args:
        user: User对象，包含用户认证信息
        type_code: 指数类型代码，001003为主题，001002为行业
        page_index: 页码
        page_size: 每页数量
        sort_type: 排序类型，DESC/ASC
        sort_name: 排序字段，NEWCHG(涨跌幅)
    Returns:
        List[Dict[str, Any]]: 指数列表
    """
    url = "https://fundcomapi.tiantianfunds.com/mm/FundIndex/FundZSBIndexRankV2"
    
    headers = {
        'Accept': '*/*',
        'Accept-Encoding': 'gzip, deflate, br',
        'Accept-Language': 'zh-Hans-CN;q=1',
        'Connection': 'keep-alive',
        'GTOKEN': '03FC9273690F4DC4B71CB2247A0E4338',
        'Host': 'fundcomapi.tiantianfunds.com',
        'MP-VERSION': '1.3.6',
        'Referer': 'https://mpservice.com/7d7b3460cd40444ba58cdabdfae34442/release/pages/rank',
        'User-Agent': f'EMProjJijin/{SERVER_VERSION} (iPhone; iOS 16.0; Scale/3.00)',
        'clientInfo': 'ttjj-iPhone18,1-iOS-iOS16.0',
        'traceparent': '00-b368e007d4eb4a6b9b833e67470de310-0000000000000000-01',
        'tracestate': 'pid=0x105032130,taskid=0x16e672340',
        'validmark': 'Li4RtWc+9LvmhgcBNN3qg3dzZjFUt4WiApOOGmkaVZL5BWm0DcGX9NZYIxjsAsZdSIrQ1Lx4ygfw5br2rQnUfMES8ernsO5lB/RKZKLdR3zMThZx2ZX8G1uEXj73HzHkj4RnL0fUh8xQ7MADEom6wQ=='
    }
    
    data = {
        'ctoken': user.c_token,
        'deviceid': DEVICE_ID,
        'indexValue': '',
        'pageIndex': str(page_index),
        'pageSize': str(page_size),
        'passportctoken': user.passport_ctoken or user.c_token,
        'passportid': user.passport_id,
        'passportutoken': user.passport_utoken or user.u_token,
        'plat': 'Iphone',
        'product': 'EFund',
        'secCode': '0',
        'sortName': sort_name,
        'sortType': sort_type,
        'type': type_code,
        'uid': user.customer_no,
        'userid': user.customer_no,
        'utoken': user.u_token,
        'valuationType': '',
        'version': SERVER_VERSION
    }
    
    try:
        response = session.post(url, headers=headers, data=data, verify=False, timeout=10)
        response.raise_for_status()
        result = response.json()
        
        if result.get("success"):
            return result.get("data", [])
        else:
            logger.error(f"获取市场指数失败: {result.get('message', 'Unknown error')}")
            return []
            
    except Exception as e:
        logger.error(f"获取市场指数异常: {e}")
        return []

if __name__ == "__main__":
    from src.common.constant import DEFAULT_USER
    from src.API.登录接口.login import ensure_user_fresh
    
    print("Refreshing user token...")
    user = ensure_user_fresh(DEFAULT_USER)
    
    print("\n--- Testing Market Index (Theme 001003) ---")
    themes = get_market_index(user, type_code="001003", page_size=50)
    for item in themes:
        print(f"Name: {item.get('SEC_NAME')}, Code: {item.get('SEC_CODE')}, INDEXCODE: {item.get('INDEXCODE')},Change: {item.get('NEWCHG')}%")
        
    print("\n--- Testing Market Index (Industry 001002) ---")
    industries = get_market_index(user, type_code="001002", page_size=50)
    for item in industries:
        print(f"Name: {item.get('SEC_NAME')}, Code: {item.get('SEC_CODE')},INDEXCODE: {item.get('INDEXCODE')}, Change: {item.get('NEWCHG')}%")
