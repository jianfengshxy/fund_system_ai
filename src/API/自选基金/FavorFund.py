import logging
import time
import urllib.parse
from typing import Any, Dict, Optional

import requests

if __name__ == "__main__":
    import os
    import sys

    root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    if root_dir not in sys.path:
        sys.path.insert(0, root_dir)

from src.common.logger import get_logger
from src.common.requests_session import session

from src.common.constant import (
    SERVER_VERSION,
    PHONE_TYPE,
    MOBILE_KEY,
    DEFAULT_USER,
)
from src.domain.fund_plan import ApiResponse
from src.domain.user.User import User

FUND_FAVOR_HOST = "fundfavorapi.eastmoney.com"


def _get_user(user: Optional[User]) -> User:
    if user:
        return user
    return DEFAULT_USER


def _build_headers() -> Dict[str, str]:
    """
    参考项目内其它 API 的风格，组织统一 headers。
    注意：GTOKEN/validmark/clientInfo/mp-version 等取自抓包样例，必要时可按需更新。
    """
    return {
        "Accept": "*/*",
        "Accept-Encoding": "gzip, deflate, br",
        "Accept-Language": "zh-Hans-CN;q=1",
        "Connection": "keep-alive",
        "Content-Type": "application/x-www-form-urlencoded",
        "Host": FUND_FAVOR_HOST,
        "Referer": "https://mpservice.com/fund4b3f5b59595d45/release/pages/mainpage/mainindex",
        "User-Agent": "EMProjJijin/6.6.9 (iPhone; iOS 16.2; Scale/3.00)",
        "clientInfo": "ttjj-iPhone 11 Pro-iOS-iOS16.2",
        "GTOKEN": "4474AFD3E15F441E937647556C01C174",
        "MP-VERSION": "1.5.6",
        "validmark": "Li4RtWc+9LvmhgcBNN3qg3dzZjFUt4WiApOOGmkaVZL5BWm0DcGX9NZYIxjsAsZd9JYBOfWXLz4ujEjOUCkzX5OOMubE0Xuw+PGl6/XhtW58ZqXh/Xc3OOE5LZ58h/eoII25voWA/jdiRh3oRljk0Q==",
    }


def add_to_favorites(
    fund_code: str,
    group_id: int = -1,
    user: Optional[User] = None,
) -> ApiResponse[Dict[str, Any]]:
    """
    基金添加到自选（GET /favor/fcode/add）
    Args:
        fund_code: 基金代码，如 '001743'
        group_id: 分组ID，默认 -1（系统默认分组）
        user: 用户对象（默认 DEFAULT_USER/施小雨）
    Returns:
        ApiResponse，Data 返回接口原始数据
    """
    # 使用确保鉴权完整的用户信息（而非直接 DEFAULT_USER）
    u = _ensure_auth_ready(user)

    url = f"https://{FUND_FAVOR_HOST}/favor/fcode/add"

    actionparam = f"{group_id},{fund_code}"

    current_version = None
    try:
        rv = get_favor_group(group_ids=str(group_id), user=u)
        if rv and rv.Data and isinstance(rv.Data, dict):
            current_version = rv.Data.get("version") or rv.Data.get("Version")
    except Exception:
        current_version = None

    favor_version = current_version or "-2000"

    params = [
        ("MobileKey", MOBILE_KEY),
        ("actionparam", actionparam),
        ("appType", "ttjj"),
        ("appVersion", SERVER_VERSION),
        ("ctoken", u.c_token),
        ("deviceid", MOBILE_KEY),
        ("favorversion", favor_version),
        ("passportctoken", u.passport_ctoken),
        ("passportid", u.passport_id),
        ("passportutoken", u.passport_utoken),
        ("plat", "Iphone"),
        ("product", "EFund"),
        ("uid", u.customer_no),
        ("utoken", u.u_token),
        ("version", SERVER_VERSION),
    ]
    query = urllib.parse.urlencode(params)
    full_url = f"{url}?{query}"

    # 使用专门的 headers（包含特定的 validmark）
    headers = _build_headers_for_add()
    logger = get_logger("FavorFund.add")
    extra = {"account": getattr(u, 'mobile_phone', None) or getattr(u, 'account', None), "action": "favor_add", "fund_code": fund_code}
    
    max_retries = 1
    for attempt in range(max_retries + 1):
        params = [
            ("MobileKey", MOBILE_KEY),
            ("actionparam", actionparam),
            ("appType", "ttjj"),
            ("appVersion", SERVER_VERSION),
            ("ctoken", u.c_token),
            ("deviceid", MOBILE_KEY),
            ("favorversion", favor_version),
            ("passportctoken", getattr(u, "passport_ctoken", None)),
            ("passportid", getattr(u, "passport_id", None)),
            ("passportutoken", getattr(u, "passport_utoken", None)),
            ("plat", "Iphone"),
            ("product", "EFund"),
            ("uid", u.customer_no),
            ("utoken", u.u_token),
            ("version", SERVER_VERSION),
        ]
        query = urllib.parse.urlencode(params)
        full_url = f"{url}?{query}"

        try:
            form_data = dict(params)
            resp = session.post(url, headers=headers, data=form_data, verify=False, timeout=10)
            if resp.status_code == 405:
                resp = session.get(full_url, headers=headers, verify=False, timeout=10)
            resp.raise_for_status()
            json_data = resp.json()

            success = json_data.get("Success", json_data.get("success", False))
            error_code = json_data.get("ErrorCode", json_data.get("errorCode"))

            # Handle token expiration (ErrorCode 63120)
            if not success and str(error_code) == "63120" and attempt < max_retries:
                logger.warning(f"Token expired (63120), refreshing tokens and retrying... Attempt {attempt+1}/{max_retries}", extra=extra)
                u_refreshed = _refresh_user_tokens(u)
                if u_refreshed:
                    u = u_refreshed
                    # Also update favor_version if possible? No, version comes from get_favor_group
                    continue 
                else:
                    logger.error("Failed to refresh tokens", extra=extra)

            first_error = (
                json_data.get("FirstError")
                or json_data.get("ErrMsg")
                or json_data.get("ErrorMessage")
                or json_data.get("Message")
            )
            data = json_data.get("Data", json_data.get("data"))

            if not success and str(error_code) == "63117" and isinstance(data, dict):
                new_version = data.get("version") or data.get("Version")
                if new_version and new_version != favor_version:
                    favor_version = new_version # Update for next loop if needed, but we retry immediately here
                    params_retry = list(params)
                    for i, (k, v) in enumerate(params_retry):
                        if k == "favorversion":
                            params_retry[i] = (k, new_version)
                            break
                    form_retry = dict(params_retry)
                    resp2 = session.post(url, headers=headers, data=form_retry, verify=False, timeout=10)
                    if resp2.status_code == 405:
                        query_retry = urllib.parse.urlencode(params_retry)
                        resp2 = session.get(f"{url}?{query_retry}", headers=headers, verify=False, timeout=10)
                    resp2.raise_for_status()
                    json_data2 = resp2.json()
                    success = json_data2.get("Success", json_data2.get("success", False))
                    error_code = json_data2.get("ErrorCode", json_data2.get("errorCode"))
                    first_error = (
                        json_data2.get("FirstError")
                        or json_data2.get("ErrMsg")
                        or json_data2.get("ErrorMessage")
                        or json_data2.get("Message")
                    )
                    data = json_data2.get("Data", json_data2.get("data"))

            return ApiResponse(
                Success=bool(success),
                ErrorCode=error_code,
                Data=data,
                FirstError=first_error,
                DebugError=json_data.get("hasWrongToken"),
            )
        except requests.exceptions.RequestException as e:
            if attempt < max_retries:
                 logger.warning(f"Request failed, retrying... Attempt {attempt+1}/{max_retries}: {str(e)}", extra=extra)
                 continue
            logger.error(f"请求失败: {str(e)}", extra=extra)
            return ApiResponse(False, "REQUEST_ERROR", None, f"请求失败: {str(e)}", None)
        except Exception as e:
            logger.error(f"解析失败: {str(e)}", extra=extra)
            return ApiResponse(False, "UNKNOWN_ERROR", None, f"未知错误: {str(e)}", None)
    
    return ApiResponse(False, "UNKNOWN_ERROR", None, "Max retries exceeded", None)


def _build_headers_for_add() -> Dict[str, str]:
    return {
        "Host": "fundfavorapi.eastmoney.com",
        "Accept": "*/*",
        "GTOKEN": "4474AFD3E15F441E937647556C01C174",
        "clientInfo": "ttjj-iPhone12,3-iOS-iOS15.6.1",
        "MP-VERSION": "1.0.46",
        "Accept-Encoding": "gzip, deflate, br",
        "Accept-Language": "zh-Hans-CN;q=1",
        "validmark": "Li4RtWc+9LvmhgcBNN3qgwo4uTinnFWrHABZNIBbbP+TjjLmxNF7sPjxpev14bVuGjrNMBb239zO/yTBM+QQsAAWwxJ0M/IqAe8/I5bNBFM=",
        "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8",
        "User-Agent": "EMProjJijin/6.5.9 (iPhone; iOS 15.6.1; Scale/3.00)",
        "Connection": "keep-alive",
        "Referer": "https://mpservice.com/fund4b3f5b59595d45/release/pages/mainpage/mainindex",
    }

def _build_headers_for_getgroup() -> Dict[str, str]:
    return {
        "Host": "fundfavorapi.eastmoney.com",
        "Accept": "*/*",
        "GTOKEN": "4474AFD3E15F441E937647556C01C174",
        "clientInfo": "ttjj-iPhone12,3-iOS-iOS15.6",
        "MP-VERSION": "1.4.6-0906",
        "Accept-Language": "zh-Hans-CN;q=1",
        "validmark": "Li4RtWc+9LvmhgcBNN3q3dzZjFUt4WiApOOGmkaVZL5BWm0DcGX9NZYIxjsAsZd9JYBOfWXLz4ujEjOUCkzX5OOMubE0Xuw+PGl6/XhtW5tgVesvdjlwb5iJcnlwg3l9mreBxReX0zBMSyV8XVjqg==",
        "User-Agent": "EMProjJijin/6.5.8 (iPhone; iOS 15.6; Scale/3.00)",
        "Referer": "https://mpservice.com/770ddc37537896dae8ecd8160cb25336/release/pages/fundList/customListPage",
        "Content-Type": "application/x-www-form-urlencoded",
    }

def _refresh_user_tokens(user: User) -> Optional[User]:
    from src.API.登录接口.login import login, login_passport, inference_passport_for_bind
    from src.service.用户管理.用户信息 import update_user_cache

    u0 = login(user.account, user.password)
    if not u0:
        return None
    u1 = login_passport(u0)
    if not u1:
        return None
    u2 = inference_passport_for_bind(u1)
    
    final_user = u2 or u1
    if final_user:
        update_user_cache(final_user)
        
    return final_user

def _ensure_auth_ready(user: Optional[User]) -> User:
    u = _get_user(user)
    has_all = all([
        getattr(u, "c_token", None),
        getattr(u, "u_token", None),
        getattr(u, "passport_ctoken", None),
        getattr(u, "passport_utoken", None),
        getattr(u, "passport_id", None),
    ])
    if not has_all:
        try:
            from src.API.登录接口.login import ensure_user_fresh

            u2 = ensure_user_fresh(u, 600, True)
            if u2:
                u = u2
        except Exception:
            refreshed = _refresh_user_tokens(u)
            if refreshed:
                u = refreshed
    return u


def get_favor_group(
    group_ids: str,
    fund_type: int = 0,
    user: Optional[User] = None,
    favor_version: str = "-2000",
    plat: str = "Iphone",
) -> ApiResponse[Dict[str, Any]]:
    u = _ensure_auth_ready(user)
    url = f"https://{FUND_FAVOR_HOST}/favor/fcode/getgroup"
    headers = _build_headers_for_getgroup()

    max_retries = 1
    
    for attempt in range(max_retries + 1):
        form = {
            "ctoken": u.c_token,
            "deviceid": MOBILE_KEY,
            "favorversion": favor_version,
            "fundtype": str(fund_type),
            "groupids": group_ids,
            "passportctoken": getattr(u, "passport_ctoken", None),
            "passportid": getattr(u, "passport_id", None),
            "passportutoken": getattr(u, "passport_utoken", None),
            "plat": plat,
            "product": "EFund",
            "uid": u.customer_no,
            "utoken": u.u_token,
            "version": SERVER_VERSION,
        }

        logger = get_logger("FavorFund.getgroup")
        extra = {"account": getattr(u, 'mobile_phone', None) or getattr(u, 'account', None), "action": "favor_getgroup"}
        try:
            resp = session.post(url, headers=headers, data=form, verify=False, timeout=10)
            resp.raise_for_status()
            json_data = resp.json()

            success = json_data.get("Success", json_data.get("success", False))
            error_code = json_data.get("ErrorCode", json_data.get("errorCode"))
            
            # Handle token expiration (ErrorCode 63120)
            if not success and str(error_code) == "63120" and attempt < max_retries:
                logger.warning(f"Token expired (63120), refreshing tokens and retrying... Attempt {attempt+1}/{max_retries}", extra=extra)
                u_refreshed = _refresh_user_tokens(u)
                if u_refreshed:
                    u = u_refreshed
                    continue # Retry with new user tokens
                else:
                    logger.error("Failed to refresh tokens", extra=extra)

            if not success:
                logger.warning(f"get_favor_group (singular) failed: {json_data}", extra=extra)

            first_error = json_data.get("FirstError") or json_data.get("ErrMsg") or json_data.get("ErrorMessage") or json_data.get("Message")
            data = json_data.get("Data", json_data.get("data"))

            return ApiResponse(bool(success), error_code, data, first_error, json_data.get("hasWrongToken"))
        except requests.exceptions.RequestException as e:
            if attempt < max_retries:
                 logger.warning(f"Request failed, retrying... Attempt {attempt+1}/{max_retries}: {str(e)}", extra=extra)
                 continue
            logger.error(f"请求失败: {str(e)}", extra=extra)
            return ApiResponse(False, "REQUEST_ERROR", None, f"请求失败: {str(e)}", None)
        except Exception as e:
            logger.error(f"解析失败: {str(e)}", extra=extra)
    return ApiResponse(False, "UNKNOWN_ERROR", None, f"未知错误: {str(e)}", None)


def remove_from_favorites(
    fund_code: str,
    group_id: int = -1,
    user: Optional[User] = None,
) -> ApiResponse[Dict[str, Any]]:
    u = _ensure_auth_ready(user)
    actionparam = f"{group_id},{fund_code}"
    current_version = None
    try:
        rv = get_favor_group(group_ids=str(group_id), user=u)
        if rv and rv.Data and isinstance(rv.Data, dict):
            current_version = rv.Data.get("version") or rv.Data.get("Version")
    except Exception:
        current_version = None
    favor_version = current_version or "-2000"
    headers = _build_headers_for_add()
    endpoints = [
        f"https://{FUND_FAVOR_HOST}/favor/fcode/del",
    ]
    last_resp = None
    
    max_retries = 1
    for url in endpoints:
        for attempt in range(max_retries + 1):
            params = [
                ("MobileKey", MOBILE_KEY),
                ("actionparam", actionparam),
                ("appType", "ttjj"),
                ("appVersion", SERVER_VERSION),
                ("ctoken", u.c_token),
                ("deviceid", MOBILE_KEY),
                ("favorversion", favor_version),
                ("passportctoken", getattr(u, "passport_ctoken", None)),
                ("passportid", getattr(u, "passport_id", None)),
                ("passportutoken", getattr(u, "passport_utoken", None)),
                ("plat", "Iphone"),
                ("product", "EFund"),
                ("uid", u.customer_no),
                ("utoken", u.u_token),
                ("version", SERVER_VERSION),
            ]
            
            try:
                form_data = dict(params)
                resp = session.post(url, headers=headers, data=form_data, verify=False, timeout=10)
                if resp.status_code == 405:
                    query = urllib.parse.urlencode(params)
                    resp = session.get(f"{url}?{query}", headers=headers, verify=False, timeout=10)
                resp.raise_for_status()
                json_data = resp.json()
                success = json_data.get("Success", json_data.get("success", False))
                error_code = json_data.get("ErrorCode", json_data.get("errorCode"))
                
                # Handle token expiration (ErrorCode 63120)
                if not success and str(error_code) == "63120" and attempt < max_retries:
                    u_refreshed = _refresh_user_tokens(u)
                    if u_refreshed:
                        u = u_refreshed
                        continue
                
                first_error = (
                    json_data.get("FirstError")
                    or json_data.get("ErrMsg")
                    or json_data.get("ErrorMessage")
                    or json_data.get("Message")
                )
                data = json_data.get("Data", json_data.get("data"))
                last_resp = ApiResponse(bool(success), error_code, data, first_error, json_data.get("hasWrongToken"))
                if success:
                    return last_resp
                if not success and str(error_code) == "63117" and isinstance(data, dict):
                    new_version = data.get("version") or data.get("Version")
                    if new_version and new_version != favor_version:
                        favor_version = new_version # Update for next retry if needed
                        params_retry = list(params)
                        for i, (k, v) in enumerate(params_retry):
                            if k == "favorversion":
                                params_retry[i] = (k, new_version)
                                break
                        form_retry = dict(params_retry)
                        resp2 = session.post(url, headers=headers, data=form_retry, verify=False, timeout=10)
                        if resp2.status_code == 405:
                            query_retry = urllib.parse.urlencode(params_retry)
                            resp2 = session.get(f"{url}?{query_retry}", headers=headers, verify=False, timeout=10)
                        resp2.raise_for_status()
                        json_data2 = resp2.json()
                        success2 = json_data2.get("Success", json_data2.get("success", False))
                        error_code2 = json_data2.get("ErrorCode", json_data2.get("errorCode"))
                        first_error2 = (
                            json_data2.get("FirstError")
                            or json_data2.get("ErrMsg")
                            or json_data2.get("ErrorMessage")
                            or json_data2.get("Message")
                        )
                        data2 = json_data2.get("Data", json_data2.get("data"))
                        last_resp = ApiResponse(bool(success2), error_code2, data2, first_error2, json_data2.get("hasWrongToken"))
                        if success2:
                            return last_resp
            except requests.exceptions.RequestException as e:
                if attempt < max_retries:
                    continue
                last_resp = ApiResponse(False, "REQUEST_ERROR", None, str(e), None)
            except Exception as e:
                last_resp = ApiResponse(False, "UNKNOWN_ERROR", None, str(e), None)
                
    return last_resp or ApiResponse(False, "UNKNOWN_ERROR", None, "未知错误", None)


__all__ = ["add_to_favorites", "remove_from_favorites", "get_favor_group", "get_favor_groups"]

# 新增：抽取基金项并打印详情的辅助方法
def _is_fund_item(d: Dict[str, Any]) -> bool:
    return any(k in d for k in ["fcode", "FundCode", "fund_code", "FCODE", "code"])

def _get(d: Dict[str, Any], keys: list, default=None):
    for k in keys:
        if k in d:
            return d[k]
    return default

def _collect_fund_items(obj: Any) -> list:
    items = []
    def walk(x):
        if isinstance(x, dict):
            if _is_fund_item(x):
                items.append(x)
            else:
                for v in x.values():
                    walk(v)
        elif isinstance(x, list):
            for i in x:
                walk(i)
    walk(obj)
    return items

# 新增：按列友好打印分组基金
def _print_group_funds(data: Any):
    funds = _collect_fund_items(data)
    print(f"分组基金数量: {len(funds)}")
    def _truncate(s: str, n: int) -> str:
        if not isinstance(s, str):
            s = str(s) if s is not None else ""
        return s if len(s) <= n else s[:n-1] + "…"
    for idx, item in enumerate(funds, 1):
        code = _get(item, ["fcode", "FundCode", "fund_code", "FCODE", "code"], "")
        name = _truncate(_get(item, ["shortname", "fname", "FundName", "fund_name", "name"], ""), 32)
        eitime = _get(item, ["eitime", "addTime", "AddTime"], "")
        tflag = _get(item, ["t"], "")
        pflag = _get(item, ["p"], "")
        set_top = bool(_get(item, ["setTop"], False))
        topics = _get(item, ["relatedTopic"], [])
        topic_str = ",".join(topics) if isinstance(topics, list) else (str(topics) if topics else "")
        print(f"{idx:>2}. {code:<8} {name}")
        extras = []
        if eitime: extras.append(f"添加时间: {eitime}")
        if tflag:  extras.append(f"类型: {tflag}")
        if pflag:  extras.append(f"标志: {pflag}")
        extras.append(f"置顶: {'是' if set_top else '否'}")
        if topic_str: extras.append(f"主题: {topic_str}")
        print(f"    {' | '.join(extras)}")

def get_favor_groups(
    user: Optional[User] = None,
    favor_version: str = "-2000",
    plat: str = "Iphone",
) -> ApiResponse[Dict[str, Any]]:
    u = _ensure_auth_ready(user)
    url = f"https://{FUND_FAVOR_HOST}/favor/group/get"
    headers = _build_headers_for_getgroup()

    max_retries = 1
    
    for attempt in range(max_retries + 1):
        form = {
            "ctoken": u.c_token,
            "deviceid": MOBILE_KEY,
            "favorversion": favor_version,
            "passportctoken": getattr(u, "passport_ctoken", None),
            "passportid": getattr(u, "passport_id", None),
            "passportutoken": getattr(u, "passport_utoken", None),
            "plat": plat,
            "product": "EFund",
            "uid": u.customer_no,
            "utoken": u.u_token,
            "version": SERVER_VERSION,
        }
        
        logger = get_logger("FavorFund.group_get")
        extra = {"account": getattr(u, 'mobile_phone', None) or getattr(u, 'account', None), "action": "favor_group_get"}
        
        try:
            resp = session.post(url, headers=headers, data=form, verify=False, timeout=10)
            resp.raise_for_status()
            json_data = resp.json()
            
            success = json_data.get("Success", json_data.get("success", False))
            error_code = json_data.get("ErrorCode", json_data.get("errorCode"))
            
            # Handle token expiration (ErrorCode 63120)
            if not success and str(error_code) == "63120" and attempt < max_retries:
                logger.warning(f"Token expired (63120), refreshing tokens and retrying... Attempt {attempt+1}/{max_retries}", extra=extra)
                u_refreshed = _refresh_user_tokens(u)
                if u_refreshed:
                    u = u_refreshed
                    continue # Retry with new user tokens
                else:
                    logger.error("Failed to refresh tokens", extra=extra)

            if not success:
                logger.warning(f"get_favor_groups (plural) failed: {json_data}", extra=extra)

            first_error = json_data.get("FirstError") or json_data.get("ErrMsg") or json_data.get("ErrorMessage") or json_data.get("Message")
            data = json_data.get("Data", json_data.get("data"))
            
            return ApiResponse(bool(success), error_code, data, first_error, json_data.get("hasWrongToken"))
            
        except requests.exceptions.RequestException as e:
            if attempt < max_retries:
                 logger.warning(f"Request failed, retrying... Attempt {attempt+1}/{max_retries}: {str(e)}", extra=extra)
                 continue
            logger.error(f"请求失败: {str(e)}", extra=extra)
            return ApiResponse(False, "REQUEST_ERROR", None, f"请求失败: {str(e)}", None)
        except Exception as e:
            logger.error(f"解析失败: {str(e)}", extra=extra)
            return ApiResponse(False, "UNKNOWN_ERROR", None, f"未知错误: {str(e)}", None)
            
    return ApiResponse(False, "UNKNOWN_ERROR", None, "Max retries exceeded", None)

if __name__ == "__main__":
    # 演示：打印指定分组内的全部基金（结构化格式）
    r2 = get_favor_group(group_ids="1618328428396", fund_type=0)
    print("get_favor_group:", r2.Success, r2.ErrorCode, r2.FirstError)
    if r2.Success and r2.Data is not None:
        _print_group_funds(r2.Data)
    else:
        print("分组信息获取失败或无数据")
