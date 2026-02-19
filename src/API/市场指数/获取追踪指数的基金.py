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

logger = get_logger("TrackingFund")

def get_tracking_funds(user: User, index_code: str, page_index: int = 1, page_size: int = 50) -> List[Dict[str, Any]]:
    """
    获取追踪指定市场指数的基金列表
    Args:
        user: User对象
        index_code: 市场指数代码 (e.g. "931865")
        page_index: 页码
        page_size: 每页数量
    Returns:
        List[Dict[str, Any]]: 基金列表
    """
    url = "https://fundcomapi.tiantianfunds.com/mm/FundIndex/getTrackingFundV3"
    
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
        'traceparent': '00-1c19e64ecb9948e3a1f06019d57354f5-0000000000000000-01',
        'tracestate': 'pid=0x105032130,taskid=0x16e567780',
        'validmark': 'Li4RtWc+9LvmhgcBNN3qg3dzZjFUt4WiApOOGmkaVZL5BWm0DcGX9NZYIxjsAsZdSIrQ1Lx4ygfw5br2rQnUfMES8ernsO5lB/RKZKLdR3wAAGmVQLWANU3i0tjy67WgLvbnSZ/KH6k+z2XEdZ8BgQ=='
    }
    
    fields = 'RZDF,SYL_LN,SYL_D,SYL_Z,SYL_Y,SYL_3Y,SYL_6Y,SYL_1N,SYL_2N,SYL_3N,SYL_5N,SYL_JN,ENDNAV,TRKERROR,SHORTNAME,DISCOUNT,SHRATE7,ISCLASSC,DTZT,ISBUY,FEATURE,ESTABDATE,INDEXCODE,MAXSG,ZERODISCOUNTFLAG'
    rfields = 'RATECOST_Q,SUBRERATE_Q,CSSFEERATE_Q,RATECOST_HY,SUBRERATE_HY,CSSFEERATE_HY,RATECOST_Y,SUBRERATE_Y,CSSFEERATE_Y,RATECOST_TRY,SUBRERATE_TRY,CSSFEERATE_TRY,RATECOST_FY,SUBRERATE_FY,CSSFEERATE_FY,RAW_RATECOST_Q,RAW_RATECOST_HY,RAW_RATECOST_Y,RAW_RATECOST_TRY,RAW_RATECOST_FY'
    
    data = {
        'BUY': '',
        'ENDNAV': '',
        'FIELDS': fields,
        'FUNDTYPE': '',
        'INDEXCODES': index_code,
        'MAXSG': '',
        'RFIELDS': rfields,
        'YEAR': '',
        'ctoken': user.c_token,
        'deviceid': DEVICE_ID,
        'pageIndex': str(page_index),
        'pageSize': str(page_size),
        'passportctoken': user.passport_ctoken or user.c_token,
        'passportid': user.passport_id,
        'passportutoken': user.passport_utoken or user.u_token,
        'plat': 'Iphone',
        'product': 'EFund',
        'sort': 'desc',
        'sortColumn': 'ENDNAV',
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
            data_map = result.get("data", {})
            # Return the list for the requested index_code
            return data_map.get(index_code, [])
        else:
            logger.error(f"获取追踪指数基金失败: {result.get('message', 'Unknown error')}")
            return []
            
    except Exception as e:
        logger.error(f"获取追踪指数基金异常: {e}")
        return []

if __name__ == "__main__":
    from src.common.constant import DEFAULT_USER
    from src.API.登录接口.login import ensure_user_fresh
    
    print("Refreshing user token...")
    user = ensure_user_fresh(DEFAULT_USER)
    
    # Test with index code from example (931865 - 中证半导体)
    test_index_code = "931865" 
    print(f"\n--- Testing Tracking Funds for Index {test_index_code} ---")
    funds = get_tracking_funds(user, index_code=test_index_code, page_size=50)
    
    for item in funds:
        print(f"Fund: {item.get('SHORTNAME')} ({item.get('FCODE')}), NAV: {item.get('ENDNAV')}, 1Y Return: {item.get('SYL_1N')}%")
