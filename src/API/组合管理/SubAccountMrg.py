import logging

if __name__ == "__main__":
    import os
    import sys

    root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    if root_dir not in sys.path:
        sys.path.insert(0, root_dir)

from src.common.logger import get_logger
import urllib.parse
import hashlib

import requests
from src.domain.user import ApiResponse
from src.domain.sub_account.sub_account_response import SubAccountResponse
from src.domain.sub_account.sub_asset_mult_list_response import SubAssetMultListResponse, SubAccountGroup, GroupType

from src.common.constant import (
    SERVER_VERSION, PHONE_TYPE, MOBILE_KEY,
    USER_ID, U_TOKEN, C_TOKEN
)

from src.domain.sub_account.sub_account import SubAccount
from typing import List
from typing import Optional, List
from src.API.登录接口.login import ensure_user_fresh
from src.common.requests_session import session

def createSubAccount(user, name: str, style: str = 'S1') -> ApiResponse[SubAccountResponse]:
    """
    创建子账户
    """
    url = f'https://tradeapilvs{user.index}.1234567.com.cn/User/SubA/CreateSubA'
    
    headers = {
        'Accept': '*/*',
        'Accept-Encoding': 'gzip, deflate, br',
        'Connection': 'keep-alive',
        'Host': f'tradeapilvs{user.index}.1234567.com.cn',
        'Referer': 'https://mpservice.com/cd85628df2c04bd8a525f2ff4bbaf7d7/release/pages/index',
        'User-Agent': 'okhttp/3.12.13',
        'clientInfo': 'ttjj-ZTE 7534N-Android-11',
        'gtoken': 'ceaf-5ec1aeaf313a267434fbe314a1575707',
        'mp_instance_id': '26',
        'traceparent': '00-0000000046aa4cae000001968c26da88-0000000000000000-01',
        'tracestate': 'pid=0x2415841,taskid=0xc2035a6'
    }
    
    data = {
        'ServerVersion': SERVER_VERSION,
        'PhoneType': PHONE_TYPE,
        'MobileKey': MOBILE_KEY,
        'Version': SERVER_VERSION,
        'UserId': user.customer_no,
        'Style': style,
        'UToken': user.u_token,
        'AppType': 'ttjj',
        'CustomerNo': user.customer_no,
        'CToken': user.c_token,
        'Name': name
    }
    
    logger = get_logger("SubAccountMrg")
    extra = {"account": getattr(user, 'mobile_phone', None) or getattr(user, 'account', None), "action": "create_sub_account", "name": name}
    try:
        response = session.post(url, data=data, headers=headers, verify=False, timeout=10)
        response.raise_for_status()
        json_data = response.json()
        # logger.info(f"响应数据: {json_data}")
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

            sub_account = SubAccountResponse(
                sub_account_app_no=data.get('SubAccountAppNo', ''),
                user_id=data.get('UserId', ''),
                last_close_time=data.get('LastCloseTime'),
                open_state=data.get('OpenState', 0),
                sub_account_no_idea=data.get('SubAccountNoIdea'),
                customize_property=data.get('CustomizeProperty'),
                followed_customer_no=data.get('FollowedCustomerNo'),
                followed_sub_account_no=data.get('FollowedSubAccountNo'),
                property=data.get('Property', ''),
                manual_review_state=data.get('ManualReviewState', 0),
                style=data.get('Style', ''),
                create_time=data.get('CreateTime', ''),
                is_enabled=data.get('IsEnabled', False),
                state=data.get('State', 0),
                name=data.get('Name', ''),
                alias=data.get('Alias'),
                sub_account_no=data.get('SubAccountNo', ''),
                update_time=data.get('UpdateTime', ''),
                manual_review_field=data.get('ManualReviewField', '')
            )

            api_response = ApiResponse(
                Success=json_data.get('Success', False),
                ErrorCode=json_data.get('ErrorCode'),
                Data=sub_account,
                FirstError=json_data.get('FirstError'),
                DebugError=json_data.get('DebugError')
            )
            return api_response
        except Exception as e:
            logger.error(f'解析响应数据失败: {str(e)}', extra=extra)
            raise Exception(f'解析响应数据失败: {str(e)}')
    except requests.exceptions.RequestException as e:
        logger.error(f'请求失败: {str(e)}', extra=extra)
        raise Exception(f'请求失败: {str(e)}')


def disbandSubAccount(user, sub_account_no: str) -> ApiResponse[SubAccountResponse]:
    """
    解散子账户
    """
    url = f'https://tradeapilvs{user.index}.1234567.com.cn/User/SubA/DisbandSubA'
    
    headers = {
        'Accept': '*/*',
        'Accept-Encoding': 'gzip, deflate, br',
        'Connection': 'keep-alive',
        'Host': f'tradeapilvs{user.index}.1234567.com.cn',
        'Referer': 'https://mpservice.com/33cb2e2622954432b6073633f27149ba/release/pages/subAccountDetail/index',
        'User-Agent': 'okhttp/3.12.13',
        'clientInfo': 'ttjj-ZTE 7534N-Android-11',
        'gtoken': 'ceaf-5ec1aeaf313a267434fbe314a1575707',
        'mp_instance_id': '22',
        'traceparent': '00-0000000046aa4cae000001968c23f5f2-0000000000000000-01',
        'tracestate': 'pid=0x1ed8479,taskid=0x7760c9e'
    }
    
    # 对密码进行MD5加密（32位小写）
    md5_password = hashlib.md5(user.password.encode('utf-8')).hexdigest()
    
    data = {
        'product': 'EFund',
        'ServerVersion': SERVER_VERSION,
        'SubType': -1,
        'PhoneType': PHONE_TYPE,
        'Password': md5_password,
        'MobileKey': '15a16f86a738f59811cbd40da4da1d97||iemi_tluafed_me',
        'Version': '6.7.1',
        'UserId': user.customer_no,
        'SubAccountNo': sub_account_no,
        'UToken': user.u_token,
        'AppType': 'ttjj',
        'CustomerNo': user.customer_no,
        'CToken': user.c_token,
        'deviceid': '15a16f86a738f59811cbd40da4da1d97||iemi_tluafed_me',
        'uid': user.customer_no,
        'plat': 'Android'
    }
    
    logger = get_logger("SubAccountMrg")
    extra = {"account": getattr(user, 'mobile_phone', None) or getattr(user, 'account', None), "action": "disband_sub_account", "sub_account_no": sub_account_no}
    try:
        response = session.post(url, json=data, headers=headers, verify=False, timeout=10)
        response.raise_for_status()
        json_data = response.json()
        # logger.info(f"响应数据: {json_data}")
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

            sub_account = SubAccountResponse(
                sub_account_app_no=data.get('SubAccountAppNo'),
                user_id=data.get('UserId', ''),
                last_close_time=data.get('LastCloseTime'),
                open_state=data.get('OpenState', 0),
                sub_account_no_idea=data.get('SubAccountNoIdea'),
                customize_property=data.get('CustomizeProperty'),
                followed_customer_no=data.get('FollowedCustomerNo'),
                followed_sub_account_no=data.get('FollowedSubAccountNo'),
                property=data.get('Property', ''),
                manual_review_state=data.get('ManualReviewState', 0),
                style=data.get('Style', ''),
                create_time=data.get('CreateTime', ''),
                is_enabled=data.get('IsEnabled', False),
                state=data.get('State', 0),
                name=data.get('Name', ''),
                alias=data.get('Alias'),
                sub_account_no=data.get('SubAccountNo', ''),
                update_time=data.get('UpdateTime', ''),
                manual_review_field=data.get('ManualReviewField', '')
            )

            api_response = ApiResponse(
                Success=json_data.get('Success', False),
                ErrorCode=json_data.get('ErrorCode'),
                Data=sub_account,
                FirstError=json_data.get('FirstError'),
                DebugError=json_data.get('DebugError')
            )
            return api_response
        except Exception as e:
            logger.error(f'解析响应数据失败: {str(e)}', extra=extra)
            raise Exception(f'解析响应数据失败: {str(e)}')
    except requests.exceptions.RequestException as e:
        logger.error(f'请求失败: {str(e)}', extra=extra)
        raise Exception(f'请求失败: {str(e)}')


def updateSubAccount(user, sub_account_no: str, open_state: int) -> ApiResponse[SubAccountResponse]:
    """
    更新子账户状态
    Args:
        user: 用户信息s
        sub_account_no: 子账户编号
        open_state: 开放状态  3：关闭 2：开放
    Returns:
        ApiResponse[SubAccountResponse]: 接口响应
    """
    url = f'https://tradeapilvs{user.index}.1234567.com.cn/User/SubA/UpdateSubA'
    
    headers = {
        'Accept': '*/*',
        'Accept-Encoding': 'gzip, deflate, br',
        'Connection': 'keep-alive',
        'Host': f'tradeapilvs{user.index}.1234567.com.cn',
        'Referer': 'https://mpservice.com/a461099f332046f0b32783c5d3d980a8/release/pages/index/index',
        'User-Agent': 'okhttp/3.12.13',
        'clientInfo': 'ttjj-ZTE 7534N-Android-11',
        'gtoken': 'ceaf-5ec1aeaf313a267434fbe314a1575707',
        'mp_instance_id': '188',
        'traceparent': '00-0000000046aa4cae000001968af92885-0000000000000000-01',
        'tracestate': 'pid=0x71e334,taskid=0x52a82c9'
    }
    
    # 对密码进行MD5加密（32位小写）
    md5_password = hashlib.md5(user.password.encode('utf-8')).hexdigest()
    
    data = {
        'ServerVersion': SERVER_VERSION,
        'Password': md5_password,
        'SubAccountNo': sub_account_no,
        'PrivacyMode': 0,
        'CustomerNo': user.customer_no,
        'L2Password': '',
        'ShutDownSubAccount': 'false',
        'PhoneType': PHONE_TYPE,
        'MobileKey': MOBILE_KEY,
        'Version': SERVER_VERSION,
        'UserId': user.customer_no,
        'UToken': user.u_token,
        'UpdateValue': open_state,
        'AppType': 'ttjj',
        'CToken': user.c_token,
        'UpdateName': 'OpenState'
    }
    
    logger = get_logger("SubAccountMrg")
    extra = {"account": getattr(user, 'mobile_phone', None) or getattr(user, 'account', None), "action": "update_sub_account", "sub_account_no": sub_account_no}
    try:
        response = session.post(url, json=data, headers=headers, verify=False, timeout=10)
        response.raise_for_status()
        json_data = response.json()
        # logger.info(f"响应数据: {json_data}")
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

            sub_account = SubAccountResponse(
                sub_account_app_no=data.get('SubAccountAppNo'),
                user_id=data.get('UserId', ''),
                last_close_time=data.get('LastCloseTime'),
                open_state=data.get('OpenState', 0),
                sub_account_no_idea=data.get('SubAccountNoIdea'),
                customize_property=data.get('CustomizeProperty'),
                followed_customer_no=data.get('FollowedCustomerNo'),
                followed_sub_account_no=data.get('FollowedSubAccountNo'),
                property=data.get('Property', ''),
                manual_review_state=data.get('ManualReviewState', 0),
                style=data.get('Style', ''),
                create_time=data.get('CreateTime', ''),
                is_enabled=data.get('IsEnabled', False),
                state=data.get('State', 0),
                name=data.get('Name', ''),
                alias=data.get('Alias'),
                sub_account_no=data.get('SubAccountNo', ''),
                update_time=data.get('UpdateTime', ''),
                manual_review_field=data.get('ManualReviewField', '')
            )

            api_response = ApiResponse(
                Success=json_data.get('Success', False),
                ErrorCode=json_data.get('ErrorCode'),
                Data=sub_account,
                FirstError=json_data.get('FirstError'),
                DebugError=json_data.get('DebugError')
            )
            return api_response
        except Exception as e:
            logger.error(f'解析响应数据失败: {str(e)}', extra=extra)
            raise Exception(f'解析响应数据失败: {str(e)}')
    except requests.exceptions.RequestException as e:
        logger.error(f'请求失败: {str(e)}', extra=extra)
        raise Exception(f'请求失败: {str(e)}')


class SubAccountListItem:
    """
    子账户列表项
    """
    def __init__(self, 
                 customer_no: str = '',
                 sub_account_no: str = '',
                 sub_account_name: str = '',
                 sub_account_alias: str = None,
                 sub_account_style: str = '',
                 sub_account_property: str = None,
                 sub_account_objective: str = '',
                 create_time: str = '',
                 follow_customer_no: str = None,
                 follow_sub_account_no: str = None,
                 state: int = 0,
                 open_flag: int = 0,
                 last_open_time: str = '',
                 passport_id: str = '',
                 asset_value: str = '',
                 asset_decimal: float = 0.0,
                 bank_account_no: str = None,
                 bank_card_no: str = None,
                 bank_code: str = None,
                 show_bank_code: str = None,
                 bank_name: str = ''):
        self.customer_no = customer_no
        self.sub_account_no = sub_account_no
        self.sub_account_name = sub_account_name
        self.sub_account_alias = sub_account_alias
        self.sub_account_style = sub_account_style
        self.sub_account_property = sub_account_property
        self.sub_account_objective = sub_account_objective
        self.create_time = create_time
        self.follow_customer_no = follow_customer_no
        self.follow_sub_account_no = follow_sub_account_no
        self.state = state
        self.open_flag = open_flag
        self.last_open_time = last_open_time
        self.passport_id = passport_id
        self.asset_value = asset_value
        self.asset_decimal = asset_decimal
        self.bank_account_no = bank_account_no
        self.bank_card_no = bank_card_no
        self.bank_code = bank_code
        self.show_bank_code = show_bank_code
        self.bank_name = bank_name


class SubAccountListResponse:
    """
    子账户列表响应
    """
    def __init__(self, sub_accounts: List[SubAccountListItem] = None, is_fund_support: bool = False):
        self.sub_accounts = sub_accounts if sub_accounts else []
        self.is_fund_support = is_fund_support


def getSubAccountList(user) -> ApiResponse[List[SubAccount]]:
    """
    获取子账户列表
    Args:
        user: 用户信息
    Returns:
        ApiResponse[List[SubAccount]]: 接口响应，包含子账户列表
    """
    u = ensure_user_fresh(user)
    url = f'https://tradeapilvs{u.index}.1234567.com.cn/User/SubA/SubAList'
    
    headers = {
        'Accept': '*/*',
        'Accept-Encoding': 'gzip, deflate, br',
        'Connection': 'keep-alive',
        'Content-Type': 'application/json; charset=utf-8',
        'Host': f'tradeapilvs{u.index}.1234567.com.cn',
        'Referer': 'https://mpservice.com/fund46516ffab83642/release/pages/home/index',
        'User-Agent': 'okhttp/3.12.13',
        'clientInfo': 'ttjj-ZTE 7534N-Android-11',
        'gtoken': 'ceaf-5ec1aeaf313a267434fbe314a1575707',
        'mp_instance_id': '28',
        'traceparent': '00-0000000046aa4cae00000196baba22e2-0000000000000000-01',
        'tracestate': 'pid=0x71d3ee2,taskid=0x9e51735'
    }
    
    request_payload = {
        'product': 'EFund',
        'ServerVersion': SERVER_VERSION,
        'SubType': -1,
        'PhoneType': PHONE_TYPE,
        'MobileKey': MOBILE_KEY,
        'Version': SERVER_VERSION,
        'UserId': u.customer_no,
        'UToken': u.u_token,
        'AppType': 'ttjj',
        'CustomerNo': u.customer_no,
        'CToken': u.c_token,
        'deviceid': MOBILE_KEY,
        'uid': u.customer_no,
        'plat': 'Android'
    }
        
    logger = get_logger("SubAccountMrg")
    extra = {"account": getattr(user, 'mobile_phone', None) or getattr(user, 'account', None), "action": "sub_account_list"}
    try:
        response = session.post(url, json=request_payload, headers=headers, verify=False, timeout=10)
        response.raise_for_status()
        json_data = response.json()
        # logger.info(f"响应数据: {json_data}")
        try:
            data = json_data.get('Data')
            if data is None:
                # 检查是否为正常空数据（ErrorCode=0 或 Success=True）
                error_code = json_data.get('ErrorCode')
                is_success = json_data.get('Success', False)
                if is_success or error_code == 0 or str(error_code) == "0":
                    logger.info(f"获取子账户列表为空 (ErrorCode=0)", extra=extra)
                    return ApiResponse(
                        Success=True,
                        ErrorCode=0,
                        Data=[],
                        FirstError=json_data.get('FirstError'),
                        DebugError=json_data.get('DebugError')
                    )

                if not is_success:
                    err = str(json_data.get('FirstError', '') or '')
                    need_refresh = any(k in err for k in ['Token', 'token', '凭证', 'passport', '未登录', '请登录', 'UToken', 'CToken', 'passportid', '权限'])
                    if need_refresh:
                        u2 = ensure_user_fresh(u, force_refresh=True)
                        url2 = f'https://tradeapilvs{u2.index}.1234567.com.cn/User/SubA/SubAList'
                        data2 = dict(request_payload)
                        data2['UserId'] = u2.customer_no
                        data2['UToken'] = u2.u_token
                        data2['CustomerNo'] = u2.customer_no
                        data2['CToken'] = u2.c_token
                        data2['uid'] = u2.customer_no
                        r2 = session.post(url2, json=data2, headers=headers, verify=False, timeout=10)
                        r2.raise_for_status()
                        jd2 = r2.json()
                        if jd2.get('Success', False) and jd2.get('Data'):
                            json_data = jd2
                            data = json_data.get('Data') # Update data reference after retry success
                        else:
                            return ApiResponse(
                                Success=json_data.get('Success', False),
                                ErrorCode=json_data.get('ErrorCode'),
                                Data=None,
                                FirstError=json_data.get('FirstError'),
                                DebugError=json_data.get('DebugError')
                            )
                    else:
                        return ApiResponse(
                            Success=json_data.get('Success', False),
                            ErrorCode=json_data.get('ErrorCode'),
                            Data=None,
                            FirstError=json_data.get('FirstError'),
                            DebugError=json_data.get('DebugError')
                        )
                
                # If data is None but logic falls through (should not happen if Success=True handled above)
                if data is None:
                     raise Exception('解析响应数据失败: Data字段为空')

            sub_accounts = []
            for account in data.get('SubAccounts', []):
                # 使用 SubAccount 类创建子账户对象
                sub_account = SubAccount(
                    customer_no=account.get('CustomerNo', ''),
                    sub_account_no=account.get('SubAccountNo', ''),
                    sub_account_name=account.get('SubAccountName', '')
                )
                
                # 设置额外属性
                sub_account.open_flag = account.get('OpenFlag', 0)
                sub_account.state = account.get('State', 0)
                
                # 如果有资产信息，设置资产相关属性
                if 'AssetValue' in account:
                    # 移除逗号后再转换为浮点数
                    asset_value_str = account.get('AssetValue', '0.0') or '0.0'
                    asset_value_str = asset_value_str.replace(',', '')
                    sub_account.asset_value = float(asset_value_str)
                
                # 设置其他可能的属性
                if account.get('SubAccountAlias'):
                    sub_account.alias = account.get('SubAccountAlias')
                
                if account.get('SubAccountStyle'):
                    sub_account.style = account.get('SubAccountStyle')
                
                if account.get('CreateTime'):
                    sub_account.create_time = account.get('CreateTime')
                
                if account.get('FollowedCustomerNo'):
                    sub_account.followed_customer_no = account.get('FollowedCustomerNo')
                
                if account.get('FollowedSubAccountNo'):
                    sub_account.followed_sub_account_no = account.get('FollowedSubAccountNo')
                
                # 设置组合类型相关属性
                if account.get('GroupType'):
                    sub_account.group_type = account.get('GroupType')
                
                # 设置评分
                if account.get('Score'):
                    sub_account.score = account.get('Score')
                
                # 设置组合类型列表
                if account.get('GroupTypes'):
                    sub_account.group_types = account.get('GroupTypes', [])
                
                # 设置区间收益率
                if account.get('IntervalProfitRate'):
                    sub_account.interval_profit_rate = account.get('IntervalProfitRate')
                
                if account.get('IntervalProfitRateName'):
                    sub_account.interval_profit_rate_name = account.get('IntervalProfitRateName')
                
                # 设置子账户说明
                if account.get('SubAccountExplain'):
                    sub_account.sub_account_explain = account.get('SubAccountExplain')
                
                # 设置在途交易信息
                if account.get('OnWayTradeCount'):
                    sub_account.on_way_trade_count = int(account.get('OnWayTradeCount', 0))
                
                if account.get('OnWayTradeDesc'):
                    sub_account.on_way_trade_desc = account.get('OnWayTradeDesc')
                
                # 设置是否正在解散
                if account.get('IsDissolving') is not None:
                    sub_account.is_dissolving = bool(account.get('IsDissolving'))
                
                # 设置总资产金额
                if account.get('TotalAmount'):
                    total_amount_str = account.get('TotalAmount', '0.0') or '0.0'
                    total_amount_str = total_amount_str.replace(',', '')
                    sub_account.total_amount = float(total_amount_str)
                
                # 设置总收益和收益率
                if account.get('TotalProfit'):
                    total_profit_str = account.get('TotalProfit', '0.0') or '0.0'
                    total_profit_str = total_profit_str.replace(',', '')
                    sub_account.total_profit = float(total_profit_str)
                
                if account.get('TotalProfitRate'):
                    total_profit_rate_str = account.get('TotalProfitRate', '0.0') or '0.0'
                    total_profit_rate_str = total_profit_rate_str.replace(',', '')
                    sub_account.total_profit_rate = float(total_profit_rate_str)
                
                sub_accounts.append(sub_account)

            # 返回包含子账户列表的 ApiResponse
            api_response = ApiResponse(
                Success=json_data.get('Success', False),
                ErrorCode=json_data.get('ErrorCode'),
                Data=sub_accounts,
                FirstError=json_data.get('FirstError'),
                DebugError=json_data.get('DebugError')
            )
            return api_response
        except Exception as e:
            logger.error(f'解析响应数据失败: {str(e)}', extra=extra)
            raise Exception(f'解析响应数据失败: {str(e)}')
    except requests.exceptions.RequestException as e:
        logger.error(f'请求失败: {str(e)}', extra=extra)
        raise Exception(f'请求失败: {str(e)}')


def getSubAccountNoByName(user, name: str) -> Optional[str]:
    """
    根据组合名称获取组合编号
    """
    response = getSubAssetMultList(user)
    if response.Success and response.Data:
        for group in response.Data.list_group:
            if group.group_name == name:
                return group.sub_account_no
    return None


def getSubAssetMultList(user) -> ApiResponse[SubAssetMultListResponse]:
    """
    获取组合资产列表
    """
    u = ensure_user_fresh(user)
    url = f'https://tradeapilvs{u.index}.1234567.com.cn/User/SubA/SubAAssetMultList'
    
    headers = {
        'Accept': '*/*',
        'Accept-Encoding': 'gzip, deflate, br',
        'Connection': 'keep-alive',
        'Host': f'tradeapilvs{u.index}.1234567.com.cn',
        'Referer': 'https://mpservice.com/33cb2e2622954432b6073633f27149ba/release/pages/subAccountHome/index',
        'User-Agent': 'okhttp/3.12.13',
        'clientInfo': 'ttjj-ZTE 7534N-Android-11',
        'gtoken': 'ceaf-5ec1aeaf313a267434fbe314a1575707',
        'mp_instance_id': '162',
        'traceparent': '00-0000000046aa4cae000001968ae7a434-0000000000000000-01',
        'tracestate': 'pid=0xc3c6c4a,taskid=0x7f81dfc'
    }
    
    data = {
        'ServerVersion': SERVER_VERSION,
        'PhoneType': PHONE_TYPE,
        'MobileKey': MOBILE_KEY,
        'Version': SERVER_VERSION,
        'UserId': u.customer_no,
        'FetchDissolve': 'true',
        'UToken': u.u_token,
        'AppType': 'ttjj',
        'CustomerNo': u.customer_no,
        'CToken': u.c_token
    }
    
    logger = get_logger("SubAccountMrg")
    extra = {"account": getattr(user, 'mobile_phone', None) or getattr(user, 'account', None), "action": "sub_asset_mult_list"}
    try:
        response = session.post(url, json=data, headers=headers, verify=False, timeout=10)
        response.raise_for_status()
        json_data = response.json()
        # logger.info(f"响应数据: {json_data}")
        try:
            data = json_data.get('Data')
            if data is None:
                if not json_data.get('Success', False):
                    u2 = ensure_user_fresh(u, force_refresh=True)
                    url2 = f'https://tradeapilvs{u2.index}.1234567.com.cn/User/SubA/SubAAssetMultList'
                    data2 = dict(data)
                    data2['UserId'] = u2.customer_no
                    data2['UToken'] = u2.u_token
                    data2['CustomerNo'] = u2.customer_no
                    data2['CToken'] = u2.c_token
                    r2 = session.post(url2, json=data2, headers=headers, verify=False, timeout=10)
                    r2.raise_for_status()
                    jd2 = r2.json()
                    if jd2.get('Success', False) and jd2.get('Data'):
                        json_data = jd2
                    else:
                        return ApiResponse(
                            Success=json_data.get('Success', False),
                            ErrorCode=json_data.get('ErrorCode'),
                            Data=None,
                            FirstError=json_data.get('FirstError'),
                            DebugError=json_data.get('DebugError')
                        )
                raise Exception('解析响应数据失败: Data字段为空')

            list_group = []
            for group in data.get('ListGroup', []):
                group_types = []
                for gt in group.get('GroupTypes', []):
                    group_types.append(GroupType(
                        group_type_name=gt.get('GroupTypeName', ''),
                        color=gt.get('Color', '')
                    ))
                
                list_group.append(SubAccountGroup(
                    open_flag=group.get('OpenFlag', ''),
                    is_dissolving=group.get('IsDissolving', False),
                    race_id=group.get('RaceId'),
                    on_way_trade_count=group.get('OnWayTradeCount', 0),
                    on_way_trade_desc=group.get('OnWayTradeDesc'),
                    sub_account_no=group.get('SubAccountNo', ''),
                    group_name=group.get('GroupName', ''),
                    group_type=group.get('GroupType'),
                    total_profit=group.get('TotalProfit', ''),
                    total_profit_rate=group.get('TotalProfitRate'),
                    total_amount=group.get('TotalAmount', ''),
                    total_amount_decimal=float(group.get('TotalAmountDecimal', 0)),
                    day_profit=group.get('DayProfit', ''),
                    comment=group.get('Comment'),
                    score=group.get('Score', ''),
                    fund_updating=group.get('FundUpdating', False),
                    to_or_yes_day_profit=group.get('ToOrYesDayProfit', False),
                    list_profit=group.get('ListProfit'),
                    group_types=group_types,
                    interval_profit_rate=group.get('IntervalProfitRate', ''),
                    interval_profit_rate_name=group.get('IntervalProfitRateName', ''),
                    sub_account_explain=group.get('SubAccountExplain'),
                    followed_sub_account_no=group.get('FollowedSubAccountNo')
                ))

            sub_asset_mult_list = SubAssetMultListResponse(
                sub_bank_state=data.get('SubBankState', ''),
                group_card_tip=data.get('GroupCardTip', ''),
                sub_account_remark=data.get('SubAccountRemark', ''),
                update=data.get('Update', False),
                sub_account_asset=data.get('SubAccountAsset'),
                has_condition_trade=data.get('HasConditionTrade', False),
                condition_trade_amount=data.get('ConditionTradeAmount', ''),
                condition_trade_profit=data.get('ConditionTradeProfit', ''),
                condition_trade_to_or_yes_day_profit=data.get('ConditionTradeToOrYesDayProfit', False),
                base_account_amount=data.get('BaseAccountAmount', ''),
                yesterday_profit=data.get('YesterDayProfit', ''),
                list_group=list_group,
                to_or_yes_day_profit=data.get('ToOrYesDayProfit', False),
                sub_total_amount=data.get('SubTotalAmount', '')
            )

            api_response = ApiResponse(
                Success=json_data.get('Success', False),
                ErrorCode=json_data.get('ErrorCode'),
                Data=sub_asset_mult_list,
                FirstError=json_data.get('FirstError'),
                DebugError=json_data.get('DebugError')
            )
            return api_response
        except Exception as e:
            logger.error(f'解析响应数据失败: {str(e)}', extra=extra)
            raise Exception(f'解析响应数据失败: {str(e)}')
    except requests.exceptions.RequestException as e:
        logger.error(f'请求失败: {str(e)}', extra=extra)
        raise Exception(f'请求失败: {str(e)}')

 
