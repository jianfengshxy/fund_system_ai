if __name__ == "__main__":
    import os
    import sys

    root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    if root_dir not in sys.path:
        sys.path.insert(0, root_dir)

from src.common.logger import get_logger
import requests
from src.common.requests_session import session
from src.API.登录接口.login import ensure_user_fresh

from typing import List
from src.common.constant import (
    IOS_CLIENT_INFO,
    DEFAULT_GTOKEN,
    MOBILE_KEY,
    MP_INSTANCE_ID_CASHBAG,
    PHONE_TYPE,
    SERVER_VERSION,
    TRACEPARENT_CASHBAG,
    TRACESTATE_CASHBAG,
    IOS_USER_AGENT,
)

from  src.domain.bank.bank import HqbBank

def _is_auth_error(payload: dict) -> bool:
    """
    判断接口响应是否属于登录态/Token 失效。

    CashBag 接口在登录态过期时，经常返回：
    - `ErrorCode = 1111`
    - `HasWrongToken = True`
    - `FirstError = 您的登录状态已失效，请重新登录。`

    这里统一收敛判断逻辑，便于触发自动刷新并重试。
    """
    error_code = payload.get("ErrorCode")
    first_error = str(payload.get("FirstError") or "")
    return (
        str(error_code) == "1111"
        or bool(payload.get("HasWrongToken"))
        or any(k in first_error for k in ["登录状态已失效", "请重新登录", "Token", "token", "凭证"])
    )

def getCashBagAvailableShareV2(user) -> List[HqbBank]:
    """
    获取活期宝可用份额信息 V2。

    该接口会返回用户名下可用于活期宝/交易场景的银行卡列表，
    上层通常会据此选择余额最大的银行卡作为默认扣款卡。

    为了减少“缓存 token 过期导致误判为没有银行卡”的情况，
    这里会先确保用户登录态尽量新鲜；如果接口明确返回登录失效，
    会强制刷新一次 token 后自动重试。

    Args:
        user: User对象，包含用户认证信息
    Returns:
        List[HqbBank]: 活期宝银行卡列表，按余额从高到低排序
    """
    logger = get_logger("CashBag")
    extra = {"account": getattr(user,'mobile_phone',None) or getattr(user,'account',None), "action": "getCashBagAvailableShareV2"}

    def _build_request_parts(curr_user):
        url = f'https://tradeapilvs{curr_user.index}.1234567.com.cn/Business/CashBag/CashBagAvailableShareV2'
        headers = {
            'Accept': '*/*',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Host': f'tradeapilvs{curr_user.index}.1234567.com.cn',
            'Referer': 'https://mpservice.com/fund4046e6539c4c47/release/pages/buy-fund/index',
            'User-Agent': IOS_USER_AGENT,
            'clientInfo': IOS_CLIENT_INFO,
            'gtoken': DEFAULT_GTOKEN,
            'mp_instance_id': MP_INSTANCE_ID_CASHBAG,
            'traceparent': TRACEPARENT_CASHBAG,
            'tracestate': TRACESTATE_CASHBAG,
        }
        data = {
            'ServerVersion': SERVER_VERSION,
            'PhoneType': PHONE_TYPE,
            'isNeedAllCashBagCard': 'true',
            'MobileKey': MOBILE_KEY,
            'Version': SERVER_VERSION,
            'UserId': curr_user.customer_no,
            'UToken': curr_user.u_token,
            'AppType': 'ttjj',
            'CustomerNo': curr_user.customer_no,
            'CToken': curr_user.c_token
        }
        return url, headers, data

    try:
        current_user = ensure_user_fresh(user)
        url, headers, data = _build_request_parts(current_user)
        response = session.post(url, data=data, headers=headers, verify=False, timeout=30)
        response.raise_for_status()
        json_data = response.json()
        # logger.info(f"响应数据: {json_data}")
        
        if not json_data.get('Success', False):
            if _is_auth_error(json_data):
                logger.warning(
                    f"检测到 CashBag 登录态失效，准备刷新 token 后重试。FirstError={json_data.get('FirstError')}",
                    extra=extra,
                )
                refreshed_user = ensure_user_fresh(current_user, force_refresh=True)
                url, headers, data = _build_request_parts(refreshed_user)
                retry_response = session.post(url, data=data, headers=headers, verify=False, timeout=30)
                retry_response.raise_for_status()
                json_data = retry_response.json()

            if not json_data.get('Success', False):
                logger.error(f"请求失败 for user {current_user.customer_no}: {json_data.get('FirstError')} Full response: {json_data}", extra=extra)
                return []

        data = json_data.get('Data')
        if data is None:
            logger.error(f'解析响应数据失败: Data字段为空 for user {current_user.customer_no} Full response: {json_data}', extra=extra)
            return []

        hqb_banks = []
        for bank_data in data.get('HqbBanks', []):
            try:
                hqb_bank = HqbBank.from_dict(bank_data)
                hqb_banks.append(hqb_bank)
            except Exception as e:
                logger.error(f"解析银行卡数据失败 for user {current_user.customer_no}: {str(e)}, 数据: {bank_data}", extra=extra)
                continue
        
        # 按照余额从高到低排序
        hqb_banks.sort(key=lambda x: float(x.BankAvaVol) if x.BankAvaVol else 0, reverse=True)
        # logger.info(f"排序后的银行卡数量: {len(hqb_banks)}")
                
        return hqb_banks
            
    except requests.exceptions.RequestException as e:
        logger.error(f"请求失败 for user {getattr(user, 'customer_no', None)}: {str(e)}", extra=extra)
        return []
    except Exception as e:
        logger.error(f"处理响应数据失败 for user {getattr(user, 'customer_no', None)}: {str(e)}", extra=extra)
        return []
