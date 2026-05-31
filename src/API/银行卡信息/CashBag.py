import logging

if __name__ == "__main__":
    import os
    import sys

    root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    if root_dir not in sys.path:
        sys.path.insert(0, root_dir)

from src.common.logger import get_logger
import urllib.parse
import requests
from src.common.requests_session import session

from typing import Optional, List
from src.domain.fund_plan import ApiResponse
from src.common.constant import (
    CLIENT_INFO_ANDROID_ZTE_7534N_11,
    GTOKEN_CEAF_5EC1AEAF313A267434FBE314A1575707,
    MOBILE_KEY,
    MP_INSTANCE_ID_CASHBAG,
    PHONE_TYPE,
    SERVER_VERSION,
    TRACEPARENT_CASHBAG,
    TRACESTATE_CASHBAG,
    USER_AGENT_OKHTTP_3_12_13,
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
        'User-Agent': USER_AGENT_OKHTTP_3_12_13,
        'clientInfo': CLIENT_INFO_ANDROID_ZTE_7534N_11,
        'gtoken': GTOKEN_CEAF_5EC1AEAF313A267434FBE314A1575707,
        'mp_instance_id': MP_INSTANCE_ID_CASHBAG,
        'traceparent': TRACEPARENT_CASHBAG,
        'tracestate': TRACESTATE_CASHBAG,
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
    
    logger = get_logger("CashBag")
    extra = {"account": getattr(user,'mobile_phone',None) or getattr(user,'account',None), "action": "getCashBagAvailableShareV2"}
    try:
        response = session.post(url, data=data, headers=headers, verify=False, timeout=30)
        response.raise_for_status()
        json_data = response.json()
        # logger.info(f"响应数据: {json_data}")
        
        if not json_data.get('Success', False):
            logger.error(f"请求失败 for user {user.customer_no}: {json_data.get('FirstError')} Full response: {json_data}", extra=extra)
            return []

        data = json_data.get('Data')
        if data is None:
            logger.error(f'解析响应数据失败: Data字段为空 for user {user.customer_no} Full response: {json_data}', extra=extra)
            return []

        hqb_banks = []
        for bank_data in data.get('HqbBanks', []):
            try:
                hqb_bank = HqbBank.from_dict(bank_data)
                hqb_banks.append(hqb_bank)
            except Exception as e:
                logger.error(f"解析银行卡数据失败 for user {user.customer_no}: {str(e)}, 数据: {bank_data}", extra=extra)
                continue
        
        # 按照余额从高到低排序
        hqb_banks.sort(key=lambda x: float(x.BankAvaVol) if x.BankAvaVol else 0, reverse=True)
        # logger.info(f"排序后的银行卡数量: {len(hqb_banks)}")
                
        return hqb_banks
            
    except requests.exceptions.RequestException as e:
        logger.error(f"请求失败 for user {user.customer_no}: {str(e)}", extra=extra)
        return []
    except Exception as e:
        logger.error(f"处理响应数据失败 for user {user.customer_no}: {str(e)}", extra=extra)
        return []
