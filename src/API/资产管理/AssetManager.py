import sys
import os
import logging
from src.common.logger import get_logger
from src.common.errors import RetriableError, ValidationError
import urllib.parse
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))) ))

import requests
from typing import Optional
from src.domain.user.api_response import ApiResponse  # 修改为 src.domain.fund_plan

from src.common.constant import (
    SERVER_VERSION, PHONE_TYPE, MOBILE_KEY,
    USER_ID, U_TOKEN, C_TOKEN, PASSPORT_ID, DEFAULT_USER
)

def GetMyAssetMainPartAsync(user) -> ApiResponse:
    """
    获取用户资产信息
    """
    url = f'https://tradeapilvs{user.index}.1234567.com.cn/User/Asset/GetMyAssetMainPartAsync'
    data = {
        'ServerVersion': SERVER_VERSION,
        'PhoneType': PHONE_TYPE,
        'MobileKey': MOBILE_KEY,
        'Version': SERVER_VERSION,
        'UserId': user.customer_no,
        'ContainsPension': True,
        'UToken': user.u_token,
        'AppType': 'ttjj',
        'CustomerNo': user.customer_no,
        'CToken': user.c_token
    }
    headers = {
        'Accept': '*/*',
        'Accept-Encoding': 'gzip, deflate, br',
        'Connection': 'keep-alive',
        'Content-Type': 'application/json; charset=utf-8',
        'Host': f'tradeapilvs{user.index}.1234567.com.cn',
        'Referer': 'https://mpservice.com/882b8205738149eeb1b0f4f516953fe9/release/pages/home/index',
        'User-Agent': 'okhttp/3.12.13',
        'clientInfo': 'ttjj-ZTE 7534N-Android-11',
        'gtoken': 'ceaf-4a997831b1b3b90849f585f98ca6f30e',
        'mp_instance_id': '8',
        'traceparent': '00-0000000046aa4cae00000196718a6d24-0000000000000000-01',
        'tracestate': 'pid=0x186caf0,taskid=0x11a8e41'
    }
    logger = get_logger("AssetManager")
    extra = {"account": getattr(user, 'mobile_phone', None) or getattr(user, 'account', None), "action": "GetMyAssetMainPartAsync"}
    try:
        response = requests.post(url, json=data, headers=headers, verify=False)
        response.raise_for_status()
        json_data = response.json()
        try:
            data = json_data.get('Data')
            if data is None:
                if not json_data.get('Success', False):
                    return ApiResponse(
                        Success=json_data.get('Success', False),
                        ErrorCode=json_data.get('ErrorCode'),
                        Data=None,
                        FirstError=json_data.get('FirstError'),
                        DebugError=json_data.get('DebugError')
                    )
                raise Exception('解析响应数据失败: Data字段为空')

            api_response = ApiResponse(
                Success=json_data.get('Success', False),
                ErrorCode=json_data.get('ErrorCode'),
                Data=data,
                FirstError=json_data.get('FirstError'),
                DebugError=json_data.get('DebugError')
            )
            return api_response
        except Exception as e:
            logger.error(f'解析响应数据失败: {str(e)}', extra=extra)
            raise ValidationError(str(e))
    except requests.exceptions.RequestException as e:
        logger.error(f'请求失败: {str(e)}', extra=extra)
        raise RetriableError(str(e))


if __name__ == "__main__":
    from src.common.constant import DEFAULT_USER
    response = GetMyAssetMainPartAsync(DEFAULT_USER)
    print(response)
