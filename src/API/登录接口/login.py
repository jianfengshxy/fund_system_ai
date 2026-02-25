import hashlib
from typing import Dict

if __name__ == "__main__":
    import os
    import sys

    root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    if root_dir not in sys.path:
        sys.path.insert(0, root_dir)

from src.API._core.client import default_client
from src.common.constant import PHONE_TYPE, SERVER_VERSION, MOBILE_KEY
from src.common.logger import get_logger
from src.domain.user.User import User

def login(account: str, password: str) -> User:
    """
    用户登录
    Args:
        account: 账号
        password: 密码
    Returns:
        User: 登录成功返回用户对象，失败返回None
    """
    url = 'https://tradeapilvs5.1234567.com.cn/User/Account/LoginForMobileReturnContextId'
    
    # 对密码进行MD5加密（32位小写）
    md5_password = hashlib.md5(password.encode('utf-8')).hexdigest()
    
    headers = {
        'Accept': '*/*',
        'Accept-Encoding': 'gzip, deflate, br',
        'Connection': 'keep-alive',
        'Content-Type': 'application/json; charset=utf-8',
        'Host': 'tradeapilvs5.1234567.com.cn',
        'Referer': 'https://mpservice.com/fundffc6fe53910b4e/release/pages/index?needFillAccount=true&defaultAccount=',
        'User-Agent': 'okhttp/3.12.13',
        'clientInfo': 'ttjj-ZTE 7534N-Android-11',
        'gtoken': 'ceaf-5ec1aeaf313a267434fbe314a1575707',
        'mp_instance_id': '20',
        'traceparent': '00-0000000046aa4cae000001968a71d18e-0000000000000000-01',
        'tracestate': 'pid=0xacad202,taskid=0x8000ff6'
    }
    
    data = {
        'Account': account,
        'ServerVersion': SERVER_VERSION,
        'DeviceOS': 'Android 11',
        'CertificateType': 0,
        'DeviceType': 'Android11',
        'PhoneType': PHONE_TYPE,
        'Version': SERVER_VERSION,
        'MobileKey': '15a16f86a738f59811cbd40da4da1d97||iemi_tluafed_me',
        'AppType': 'ttjj',
        'Password': md5_password,
        'DeviceName': 'ZTE'
    }
    
    logger = get_logger("Login")
    extra = {"account": account, "action": "login"}
    try:
        json_data = default_client.post_json(url, headers=headers, json=data, timeout=10)
        # logger.info(f"登录响应数据: {json_data}")
        
        if not json_data.get('Success', False):
            logger.error("登录失败，接口返回Success=False", extra=extra)
            return None
            
        data = json_data.get('Data')
        if not data:
            logger.error("登录失败，接口返回Data为空", extra=extra)
            return None
            
        try:
            # 首先创建基本的User对象
            user = User(account=account, password=password)
            
            # 然后使用属性赋值的方式设置其他字段
            user.customer_no = data.get('CustomerNo', '')
            user.customer_name = data.get('CustomerName', '')
            user.c_token = data.get('CToken', '')
            user.u_token = data.get('UToken', '')
            user.mobile_phone = data.get('MobilePhone', '')
            user.risk = data.get('Risk', '')
            user.risk_name = data.get('RiskName', '')
            user.vip_level = int(data.get('VipLevel', 0))
            user.index = int(data.get('Zone', 0))
            
            return user
            
        except TypeError as e:
            logger.error(f"创建User对象失败: {str(e)}", extra=extra)
            return None
            
    except Exception as e:
        logger.error(f'登录失败: {str(e)}', extra=extra)
        return None

def login_passport(user: User) -> User:
    """
    获取用户的 passport 信息
    Args:
        user: 用户对象
    Returns:
        User: 更新后的用户对象，失败返回None
    """
    url = f"https://tradeapilvs{user.index}.1234567.com.cn/User/Passport/PLogin"
    
    headers = {
        'Connection': 'keep-alive',
        'Content-Type': 'application/x-www-form-urlencoded',
        'Host': f'tradeapilvs{user.index}.1234567.com.cn',
        'Accept': '*/*',
        'GTOKEN': 'ceaf-5ec1aeaf313a267434fbe314a1575707',
        'clientInfo': 'ttjj-ZTE 7534N-Android-11',
        'MP-VERSION': '2.2.5',
        'Accept-Language': 'zh-Hans-CN;q=1',
        'User-Agent': 'okhttp/3.12.13',
        'Referer': 'https://mpservice.com/8543c2ac1ae2a93335b443a3f9f1028f/release/pages/index/index'
    }
    
    data = {
        'AppType': 'ttjj',
        'CToken': user.c_token,
        'CustomerNo': user.customer_no,
        'MobileKey': MOBILE_KEY,
        'PhoneType': PHONE_TYPE,
        'ServerVersion': SERVER_VERSION,
        'UToken': user.u_token,
        'UserId': user.customer_no,
        'Version': SERVER_VERSION,
        'ctoken': user.c_token,
        'userId': user.customer_no,
        'utoken': user.u_token
    }

    logger = get_logger("Login")
    extra = {"account": getattr(user, 'mobile_phone', None) or getattr(user, 'account', None), "action": "login_passport"}
    try:
        json_data = default_client.post_form(url, data=data, headers=headers, timeout=10)
        logger.info(f"Passport登录响应数据: {json_data}", extra=extra)
        
        if not json_data.get('Success', False):
            logger.warning("Passport登录失败，接口返回Success=False", extra=extra)
            return None
            
        data = json_data.get('Data')
        if not data:
            logger.error("Passport登录失败，接口返回Data为空", extra=extra)
            return None
            
        try:
            # 更新用户的passport相关信息
            user.passport_uid = data.get('PassportUid', '')
            user.passport_ctoken = data.get('PassportCToken', '')
            user.passport_utoken = data.get('PassportUToken', '')
            
            return user
            
        except TypeError as e:
            logger.error(f"更新User对象的Passport信息失败: {str(e)}", extra=extra)
            return None
            
    except Exception as e:
        logger.error(f'Passport登录失败: {str(e)}', extra=extra)
        return None

def inference_passport_for_bind(user: User) -> User:
    """
    获取用户的passport绑定信息
    Args:
        user: 用户对象
    Returns:
        User: 更新后的用户对象，失败返回None
    """
    url = f'https://tradeapilvs{user.index}.1234567.com.cn/User/Passport/InferencePassportForBind'
    
    headers = {
        'Accept': '*/*',
        'Accept-Encoding': 'gzip, deflate, br',
        'Connection': 'keep-alive',
        'Content-Type': 'application/json; charset=utf-8',
        'Host': 'tradeapilvs5.1234567.com.cn',
        'Referer': 'https://mpservice.com/fundffc6fe53910b4e/release/pages/index?needFillAccount=true&defaultAccount=',
        'User-Agent': 'okhttp/3.12.13',
        'clientInfo': 'ttjj-ZTE 7534N-Android-11',
        'gtoken': 'ceaf-5ec1aeaf313a267434fbe314a1575707',
        'mp_instance_id': '20',
        'traceparent': '00-0000000046aa4cae000001968a71d211-0000000000000000-01',
        'tracestate': 'pid=0xacad202,taskid=0xced6330'
    }
    
    data = {
        'SceneType': 2,
        'LocalPassportId': '',
        'ServerVersion': '6.7.1',
        'PhoneType': 'Android',
        'Version': '7.6.0',
        'MobileKey': '15a16f86a738f59811cbd40da4da1d97||iemi_tluafed_me',
        'UserId': user.customer_no,
        'UToken': user.u_token,
        'AppType': 'ttjj',
        'CToken': user.c_token,
        'GTOKEN': 'ceaf-5ec1aeaf313a267434fbe314a1575707'
    }

    logger = get_logger("Login")
    extra = {"account": getattr(user, 'mobile_phone', None) or getattr(user, 'account', None), "action": "inference_passport"}
    try:
        json_data = default_client.post_json(url, headers=headers, json=data, timeout=10)
        # logger.info(f"Passport绑定信息响应数据: {json_data}")
        
        if not json_data.get('Success', False):
            logger.error("获取Passport绑定信息失败，接口返回Success=False", extra=extra)
            return None
            
        data = json_data.get('Data', {}).get('Passport')
        if not data:
            logger.error("获取Passport绑定信息失败，接口返回Data为空", extra=extra)
            return None
            
        try:
            # 更新用户的passport相关信息
            user.passport_id = data.get('UID', '')
            user.passport_uid = data.get('UID', '')
            user.passport_ctoken = data.get('CToken', '')
            user.passport_utoken = data.get('UToken', '')
            
            return user
            
        except TypeError as e:
            logger.error(f"更新User对象的Passport绑定信息失败: {str(e)}", extra=extra)
            return None
            
    except Exception as e:
        logger.error(f'Passport绑定信息失败: {str(e)}', extra=extra)
        return None




_LOGIN_CACHE: Dict[str, User] = {}

def _copy_tokens(dst: User, src: User) -> None:
    dst.c_token = src.c_token
    dst.u_token = src.u_token
    dst.customer_no = src.customer_no or dst.customer_no
    dst.index = src.index or dst.index
    dst.passport_id = getattr(src, 'passport_id', getattr(src, 'passport_uid', '')) or getattr(dst, 'passport_id', '')
    dst.passport_uid = getattr(src, 'passport_uid', '') or getattr(dst, 'passport_uid', '')
    dst.passport_ctoken = getattr(src, 'passport_ctoken', '') or getattr(dst, 'passport_ctoken', '')
    dst.passport_utoken = getattr(src, 'passport_utoken', '') or getattr(dst, 'passport_utoken', '')

def cache_user(user: User) -> None:
    account = getattr(user, 'account', '')
    if account:
        _LOGIN_CACHE[account] = user

def get_cached_user(account: str) -> User:
    return _LOGIN_CACHE.get(account)

def ensure_user_fresh(user: User, max_age_sec: int = 600, force_refresh: bool = False) -> User:
    account = getattr(user, 'account', '')
    if not account:
        return user
    cached = get_cached_user(account)
    if cached and not force_refresh:
        _copy_tokens(user, cached)
        return cached
    try:
        from src.service.用户管理.用户信息 import get_user_from_store_or_cache, refresh_user_tokens, get_user_all_info
    except Exception:
        get_user_from_store_or_cache = None
        refresh_user_tokens = None
        get_user_all_info = None
    pwd = getattr(user, 'password', '')
    if not force_refresh and get_user_from_store_or_cache:
        u2 = get_user_from_store_or_cache(account, pwd)
        if u2:
            cache_user(u2)
            _copy_tokens(user, u2)
            return u2
    u3 = None
    if not force_refresh and get_user_all_info:
        u3 = get_user_all_info(account, pwd)
    if not u3 and refresh_user_tokens:
        try:
            u3 = refresh_user_tokens(account, pwd)
        except Exception:
            u3 = None
    if not u3:
        u3 = login(account, pwd)
        if u3:
            u3 = inference_passport_for_bind(u3) or login_passport(u3)
    if u3:
        cache_user(u3)
        _copy_tokens(user, u3)
        return u3
    return user
