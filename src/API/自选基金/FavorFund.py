import logging
import time
import urllib.parse
from typing import Any, Dict, Optional

import requests
import os
import sys
SRC_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if SRC_DIR not in sys.path:
    sys.path.append(SRC_DIR)

from common.constant import (
    SERVER_VERSION,
    PHONE_TYPE,
    MOBILE_KEY,
    DEFAULT_USER,
)
from domain.fund_plan import ApiResponse
from domain.user.User import User

FUND_FAVOR_HOST = "fundfavorapi.eastmoney.com"


# 补充：导入最新用户信息函数，并设置指定账号密码
from service.用户管理.用户信息 import get_user_all_info
PREFERRED_ACCOUNT = "13918199137"
PREFERRED_PASSWORD = "sWX15706"


def _get_user(user: Optional[User]) -> User:
    if user:
        return user
    latest = get_user_all_info(PREFERRED_ACCOUNT, PREFERRED_PASSWORD)
    return latest or DEFAULT_USER


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

    # actionparam 形如: "-1,001743"
    actionparam = f"{group_id},{fund_code}"

    params = [
        ("MobileKey", MOBILE_KEY),
        ("actionparam", actionparam),
        ("appType", "ttjj"),
        ("appVersion", SERVER_VERSION),
        ("ctoken", u.c_token),
        ("deviceid", MOBILE_KEY),
        ("favorversion", str(int(time.time() * 1000))),
        ("passportctoken", u.passport_ctoken),
        ("passportid", u.passport_id),
        ("passportutoken", u.passport_utoken),
        ("plat", "Web"),
        ("product", "EFund"),
        ("uid", u.customer_no),
        ("utoken", u.u_token),
        ("version", SERVER_VERSION),
    ]
    query = urllib.parse.urlencode(params)
    full_url = f"{url}?{query}"

    headers = _build_headers()
    logger = logging.getLogger("FavorFund.add")

    try:
        resp = requests.get(full_url, headers=headers, verify=False, timeout=10)
        resp.raise_for_status()
        json_data = resp.json()

        # 兼容大小写
        success = json_data.get("Success", json_data.get("success", False))
        error_code = json_data.get("ErrorCode", json_data.get("errorCode"))
        first_error = (
            json_data.get("FirstError")
            or json_data.get("ErrMsg")
            or json_data.get("ErrorMessage")
            or json_data.get("Message")
        )
        data = json_data.get("Data", json_data.get("data"))

        return ApiResponse(
            Success=bool(success),
            ErrorCode=error_code,
            Data=data,
            FirstError=first_error,
            DebugError=json_data.get("hasWrongToken"),
        )
    except requests.exceptions.RequestException as e:
        logger.error(f"请求失败: {str(e)}")
        return ApiResponse(False, "REQUEST_ERROR", None, f"请求失败: {str(e)}", None)
    except Exception as e:
        logger.error(f"解析失败: {str(e)}")
        return ApiResponse(False, "UNKNOWN_ERROR", None, f"未知错误: {str(e)}", None)


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
    from API.登录接口.login import login, login_passport, inference_passport_for_bind
    u0 = login(user.account, user.password)
    if not u0:
        return None
    u1 = login_passport(u0)
    if not u1:
        return None
    u2 = inference_passport_for_bind(u1)
    return u2 or u1

def _ensure_auth_ready(user: Optional[User]) -> User:
    # 先获取最新用户信息；若失败再退回到默认/刷新逻辑
    u = _get_user(user)
    has_all = all([
        getattr(u, "c_token", None),
        getattr(u, "u_token", None),
        getattr(u, "passport_ctoken", None),
        getattr(u, "passport_utoken", None),
        getattr(u, "passport_id", None),
    ])
    if not has_all:
        # 尝试直接用最新账号密码获取完整用户信息（带缓存）
        latest = get_user_all_info("13918199137", "sWX15706")
        if latest:
            return latest
        # 若仍不完整，回退到旧的刷新逻辑
        refreshed = _refresh_user_tokens(u)
        if refreshed:
            return refreshed
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

    form = {
        "ctoken": u.c_token,
        "deviceid": MOBILE_KEY,
        "favorversion": favor_version,
        "fundtype": str(fund_type),
        "groupids": group_ids,
        "passportctoken": u.passport_ctoken,
        "passportid": u.passport_id,
        "passportutoken": u.passport_utoken,
        "plat": plat,
        "product": "EFund",
        "uid": u.customer_no,
        "utoken": u.u_token,
        "version": SERVER_VERSION,
    }

    logger = logging.getLogger("FavorFund.getgroup")
    try:
        resp = requests.post(url, headers=headers, data=form, verify=False, timeout=10)
        resp.raise_for_status()
        json_data = resp.json()

        success = json_data.get("Success", json_data.get("success", False))
        error_code = json_data.get("ErrorCode", json_data.get("errorCode"))
        first_error = json_data.get("FirstError") or json_data.get("ErrMsg") or json_data.get("ErrorMessage") or json_data.get("Message")
        data = json_data.get("Data", json_data.get("data"))

        if not success and (error_code == 63120 or json_data.get("hasWrongToken")):
            u2 = _refresh_user_tokens(u)
            if u2:
                form.update({
                    "ctoken": u2.c_token,
                    "passportctoken": u2.passport_ctoken,
                    "passportid": u2.passport_id,
                    "passportutoken": u2.passport_utoken,
                    "uid": u2.customer_no,
                    "utoken": u2.u_token,
                })
                resp = requests.post(url, headers=headers, data=form, verify=False, timeout=10)
                resp.raise_for_status()
                json_data = resp.json()
                success = json_data.get("Success", json_data.get("success", False))
                error_code = json_data.get("ErrorCode", json_data.get("errorCode"))
                first_error = json_data.get("FirstError") or json_data.get("ErrMsg") or json_data.get("ErrorMessage") or json_data.get("Message")
                data = json_data.get("Data", json_data.get("data"))

        return ApiResponse(bool(success), error_code, data, first_error, json_data.get("hasWrongToken"))
    except requests.exceptions.RequestException as e:
        logger.error(f"请求失败: {str(e)}")
        return ApiResponse(False, "REQUEST_ERROR", None, f"请求失败: {str(e)}", None)
    except Exception as e:
        logger.error(f"解析失败: {str(e)}")
        return ApiResponse(False, "UNKNOWN_ERROR", None, f"未知错误: {str(e)}", None)


__all__ = ["add_to_favorites", "get_favor_group"]

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

if __name__ == "__main__":
    # 演示：打印指定分组内的全部基金（结构化格式）
    r2 = get_favor_group(group_ids="1618328428396", fund_type=0)
    print("get_favor_group:", r2.Success, r2.ErrorCode, r2.FirstError)
    if r2.Success and r2.Data is not None:
        _print_group_funds(r2.Data)
    else:
        print("分组信息获取失败或无数据")