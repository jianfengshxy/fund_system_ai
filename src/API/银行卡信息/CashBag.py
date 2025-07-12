import sys
import os
import logging
import urllib.parse
import urllib3
import warnings
import requests
# 添加项目根目录到路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# 禁用 urllib3 的警告信息
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


from typing import Optional, List
from src.domain.fund_plan import ApiResponse
from src.common.constant import (
    SERVER_VERSION, PHONE_TYPE, MOBILE_KEY
)

from  src.domain.bank.bank import BankCard, HqbBank, BankApiResponse

def getCashBagAvailableShareV2(user) -> List[HqbBank]:
    """
    获取活期宝可用份额信息V2版本
    Args:
        user: User对象，包含用户认证信息
    Returns:
        List[HqbBank]: 活期宝银行卡列表，按余额从高到低排序
    """
    url = f'https://tradeapilvs{user.index}.1234567.com.cn/Business/CashBag/CashBagAvailableShareV2'
    
    headers = {
        'Accept': '*/*',
        'Accept-Encoding': 'gzip, deflate, br',
        'Connection': 'keep-alive',
        'Host': f'tradeapilvs{user.index}.1234567.com.cn',
        'Referer': 'https://mpservice.com/fund4046e6539c4c47/release/pages/buy-fund/index',
        'User-Agent': 'okhttp/3.12.13',
        'clientInfo': 'ttjj-ZTE 7534N-Android-11',
        'gtoken': 'ceaf-5ec1aeaf313a267434fbe314a1575707',
        'mp_instance_id': '34',
        'traceparent': '00-0000000046aa4cae000001968a7a72d3-0000000000000000-01',
        'tracestate': 'pid=0xcdf0f1b,taskid=0x3e3f74b'
    }
    
    data = {
        'ServerVersion': SERVER_VERSION,
        'PhoneType': PHONE_TYPE,
        # 'businType': '22',
        'isNeedAllCashBagCard': 'true',
        'MobileKey': MOBILE_KEY,
        'Version': SERVER_VERSION,
        'UserId': user.customer_no,
        'UToken': user.u_token,
        'AppType': 'ttjj',
        'CustomerNo': user.customer_no,
        'CToken': user.c_token
    }
    
    logger = logging.getLogger("CashBag")
    try:
        response = requests.post(url, data=data, headers=headers, verify=False)
        response.raise_for_status()
        json_data = response.json()
        # logger.info(f"响应数据: {json_data}")
        
        if not json_data.get('Success', False):
            logger.error(f"请求失败: {json_data.get('FirstError')}")
            return []

        data = json_data.get('Data')
        if data is None:
            logger.error('解析响应数据失败: Data字段为空')
            return []

        hqb_banks = []
        for bank_data in data.get('HqbBanks', []):
            try:
                hqb_bank = HqbBank.from_dict(bank_data)
                hqb_banks.append(hqb_bank)
            except Exception as e:
                logger.error(f"解析银行卡数据失败: {str(e)}, 数据: {bank_data}")
                continue
        
        # 按照余额从高到低排序
        hqb_banks.sort(key=lambda x: float(x.BankAvaVol) if x.BankAvaVol else 0, reverse=True)
        logger.info(f"排序后的银行卡数量: {len(hqb_banks)}")
                
        return hqb_banks
            
    except requests.exceptions.RequestException as e:
        logger.error(f"请求失败: {str(e)}")
        return []
    except Exception as e:
        logger.error(f"处理响应数据失败: {str(e)}")
        return []